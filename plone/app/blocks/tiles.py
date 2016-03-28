# -*- coding: utf-8 -*-
from zope.security import checkPermission
import logging
import traceback
from urlparse import urljoin

from AccessControl import Unauthorized
from lxml import etree
from lxml import html
from plone import api
from plone.tiles import data as tiles_data
from plone.app.blocks import formparser
from plone.app.blocks import utils
from plone.tiles.interfaces import ITile
from plone.tiles.interfaces import ITileDataManager
from zExceptions import NotFound
from zope.component import ComponentLookupError
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.schema import getFields
from AccessControl.SecurityManagement import getSecurityManager

logger = logging.getLogger('plone.app.blocks')


@adapter(ITile)
@implementer(ITileDataManager)
def transientTileDataManagerFactory(tile):
    if (tile.request.get('X-Tile-Persistent') or
            getattr(tile.request, 'tile_persistent', False)):
        return PersistentTileDataManager(tile)
    else:
        return TransientTileDataManager(tile)


class TransientTileDataManager(tiles_data.TransientTileDataManager):
    def get(self):
        # use explicitly set data (saved as annotation on the request)
        if self.key in self.annotations:
            data = dict(self.annotations[self.key])

            if self.tileType is not None and self.tileType.schema is not None:
                for name, field in getFields(self.tileType.schema).items():
                    if name not in data:
                        data[name] = field.missing_value

        # try to use a '_tiledata' parameter in the request
        elif hasattr(self.tile.request, 'tile_data'):
            data = self.tile.request.tile_data

        # fall back to the copy of request.form object itself
        else:
            # If we don't have a schema, just take the request
            if self.tileType is None or self.tileType.schema is None:
                data = self.tile.request.form.copy()
            else:
                # Try to decode the form data properly if we can
                try:
                    data = tiles_data.decode(self.tile.request.form,
                                             self.tileType.schema, missing=True)
                except (ValueError, UnicodeDecodeError,):
                    logger.exception(u"Could not convert form data to schema")
                    return {}
        return data


class PersistentTileDataManager(tiles_data.PersistentTileDataManager):

    def _get_default_request_data(self):
        if hasattr(self.tile.request, 'tile_data'):
            data = self.tile.request.tile_data
        else:
            # If we don't have a schema, just take the request
            if self.tileType is None or self.tileType.schema is None:
                data = self.tile.request.form.copy()
            else:
                # Try to decode the form data properly if we can
                try:
                    data = tiles_data.decode(self.tile.request.form,
                                             self.tileType.schema, missing=True)
                except (ValueError, UnicodeDecodeError):
                    logger.exception(u"Could not convert form data to schema")
                    return {}
        return data


def _modRequest(request, query_string):
    env = request.environ.copy()
    env['QUERY_STRING'] = query_string
    data = formparser.parse(env)
    request.tile_data = data
    if data.get('X-Tile-Persistent'):
        request.tile_persistent = True


def _restoreRequest(request):
    if hasattr(request, 'tile_data'):
        del request.tile_data
    if hasattr(request, 'tile_persistent'):
        del request.tile_persistent


ERROR_TILE_RESULT = """<html><body>
<p class="tileerror">
We apologize, there was an error rendering this snippet
</p></body></html>"""


UNAUTHORIZED_TILE_RESULT = """<html><body>
<p class="tileerror unauthorized">
We apologize, there was an error rendering this snippet
</p></body></html>"""


def _renderTile(request, node, contexts, baseURL, siteUrl, site, sm):
    theme_disabled = request.response.getHeader('X-Theme-Disabled')
    tileHref = node.attrib[utils.tileAttrib]
    tileTree = None
    tileData = ''
    if not tileHref.startswith('/'):
        tileHref = urljoin(baseURL, tileHref)
    try:
        # first try to resolve manually, this will be much faster than
        # doing the subrequest
        relHref = tileHref[len(siteUrl) + 1:]

        contextPath, tilePart = relHref.split('@@', 1)
        contextPath = contextPath.strip('/')
        if contextPath not in contexts:
            ob = site.unrestrictedTraverse(contextPath)
            if not checkPermission('zope2.View', ob):
                # manually check perms. We do not want restriction
                # on traversing through an object
                raise Unauthorized()
            contexts[contextPath] = ob
        context = contexts[contextPath]
        if '?' in tilePart:
            tileName, tileData = tilePart.split('?', 1)
            _modRequest(request, tileData)
        else:
            tileName = tilePart
        tileName, _, tileId = tileName.partition('/')

        tile = getMultiAdapter((context, request), name=tileName)
        try:
            if (contextPath and len(tile.__ac_permissions__) > 0 and
                    not sm.checkPermission(tile.__ac_permissions__[0][0], tile)):
                logger.info('Do not have permission for tile %s on context %s' % (
                    tileName, contextPath))
                return
            else:
                pass
        except:
            logger.warn('Could not check permissions of tile %s on context %s' % (
                tileName, contextPath))
            return
        if tileId:
            tile.id = tileId
        try:
            res = tile()
        except:
            # error rendering, let's just cut out...
            logger.error(
                'nasty uncaught tile error, data: %s,\n%s\n%s' % (
                    tileHref,
                    repr(tileData),
                    traceback.format_exc()))
            res = ERROR_TILE_RESULT

        if not res:
            return

        tileTree = html.fromstring(res).getroottree()
    except (ComponentLookupError, ValueError):
        # fallback to subrequest route, slower but safer?
        try:
            tileTree = utils.resolve(tileHref)
        except NotFound:
            return
        except (RuntimeError, etree.XMLSyntaxError):
            logger.info('error parsing tile url %s' % tileHref)
            return
    except (NotFound, RuntimeError):
        logger.info('error parsing tile url %s' % tileHref)
        return
    except Unauthorized:
        logger.error(
            'unauthorized tile error, data: %s,\n%s\n%s' % (
                tileHref,
                repr(tileData),
                traceback.format_exc()))
        tileTree = html.fromstring(UNAUTHORIZED_TILE_RESULT).getroottree()
    finally:
        _restoreRequest(request)
        if theme_disabled:
            request.response.setHeader('X-Theme-Disabled', '1')
        else:
            request.response.setHeader('X-Theme-Disabled', '')

    return tileTree


def renderTiles(request, tree):
    """Find all tiles in the given response, contained in the lxml element
    tree `tree`, and insert them into the output.

    Assumes panel merging has already happened.
    """
    root = tree.getroot()
    headNode = root.find('head')
    baseURL = request.getURL()
    if request.getVirtualRoot():
        # plone.subrequest deals with VHM requests
        baseURL = ''

    contexts = {}
    site = api.portal.get()
    siteUrl = site.absolute_url()
    sm = getSecurityManager()

    for tileNode in utils.headTileXPath(tree):
        tileTree = _renderTile(request, tileNode, contexts, baseURL, siteUrl, site, sm)
        if tileTree is not None:
            tileRoot = tileTree.getroot()
            utils.replace_with_children(tileNode, tileRoot.find('head'))
        else:
            parent = tileNode.getparent()
            parent.remove(tileNode)

    for tileNode in utils.bodyTileXPath(tree):
        tileTree = _renderTile(request, tileNode, contexts, baseURL, siteUrl, site, sm)
        if tileTree is not None:
            tileRoot = tileTree.getroot()

            tileHead = tileRoot.find('head')
            tileBody = tileRoot.find('body')

            if tileHead is None and tileBody is None:
                tileBody = tileRoot

            if tileHead is not None:
                for tileHeadChild in tileHead:
                    headNode.append(tileHeadChild)
            utils.replace_with_children(tileNode, tileBody)
        else:
            parent = tileNode.getparent()
            parent.remove(tileNode)

    return tree
