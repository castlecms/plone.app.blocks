# -*- coding: utf-8 -*-
import traceback
from urlparse import urljoin

from Products.CMFPlone.log import logger
from lxml import etree
from lxml import html
from plone import api
from plone.app.blocks import formparser
from plone.app.blocks import utils
from zExceptions import NotFound
from zope.component import ComponentLookupError
from zope.component import getMultiAdapter


def _modRequest(request, query_string):
    request.original_data = request.form
    request.original_qs = request.environ['QUERY_STRING']
    request.environ['QUERY_STRING'] = query_string
    request.form = formparser.parse(request.environ)


def _restoreRequest(request):
    if hasattr(request, 'original_data'):
        request.form = request.original_data
    if hasattr(request, 'original_qs'):
        request.environ['QUERY_STRING'] = request.original_qs


def _renderTile(request, node, contexts, baseURL, siteUrl, site):
    theme_disabled = request.response.getHeader('X-Theme-Disabled')
    tileHref = node.attrib[utils.tileAttrib]
    tileTree = None
    if not tileHref.startswith('/'):
        tileHref = urljoin(baseURL, tileHref)
    try:
        # first try to resolve manually, this will be much faster than
        # doing the subrequest
        relHref = tileHref[len(siteUrl) + 1:]

        contextPath, tilePart = relHref.split('@@', 1)
        contextPath = contextPath.strip('/')
        if contextPath not in contexts:
            contexts[contextPath] = site.restrictedTraverse(contextPath)
        context = contexts[contextPath]
        if '?' in tilePart:
            tileName, tileData = tilePart.split('?', 1)
            _modRequest(request, tileData)
        else:
            tileName = tilePart
        tileName, _, tileId = tileName.partition('/')

        tile = getMultiAdapter((context, request), name=tileName)
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
            res = """<html><body>
            <p class="tileerror">
            We apologize, there was an error rendering this snippet
            </p></body></html>"""

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

    for tileNode in utils.headTileXPath(tree):
        tileTree = _renderTile(request, tileNode, contexts, baseURL, siteUrl, site)
        if tileTree is not None:
            tileRoot = tileTree.getroot()
            utils.replace_with_children(tileNode, tileRoot.find('head'))

    for tileNode in utils.bodyTileXPath(tree):
        tileTree = _renderTile(request, tileNode, contexts, baseURL, siteUrl, site)
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

    return tree