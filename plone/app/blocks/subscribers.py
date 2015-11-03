from lxml.html import fromstring
from plone.app.blocks import utils
from plone.app.blocks.interfaces import DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY
from plone.app.blocks.layoutbehavior import ILayoutAware
from plone.app.blocks.layoutbehavior import applyTilePersistent
from plone.app.blocks.utils import resolveResource
from plone.registry.interfaces import IRegistry
from plone.tiles.data import ANNOTATIONS_KEY_PREFIX
from zExceptions import NotFound
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility


def onLayoutEdited(obj, event):
    behavior_data = ILayoutAware(obj)
    if behavior_data.contentLayout:
        try:
            path = behavior_data.contentLayout
            resolved = resolveResource(path)
            layout = applyTilePersistent(path, resolved)
        except (NotFound, RuntimeError):
            layout = ''
    else:
        layout = behavior_data.content

    if not layout:
        registry = getUtility(IRegistry)
        try:
            path = registry['%s.%s' % (
                DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY,
                obj.portal_type.replace(' ', '-'))]
        except (KeyError, AttributeError):
            path = None
        try:
            path = path or registry[DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY]
            resolved = resolveResource(path)
            layout = applyTilePersistent(path, resolved)
        except (KeyError, NotFound, RuntimeError):
            pass

    if not layout:
        return

    tree = fromstring(layout)
    tile_keys = []
    for el in utils.bodyTileXPath(tree):
        tile_url = el.attrib.get('data-tile', '')
        if 'plone.app.standardtiles.field' in tile_url:
            continue
        tile_keys.append(
            ANNOTATIONS_KEY_PREFIX + '.' + tile_url.split('?')[0].split('/')[-1])

    annotations = IAnnotations(obj)
    for key in list(annotations.keys()):
        if key.startswith(ANNOTATIONS_KEY_PREFIX) and key not in tile_keys:
            del annotations[key]