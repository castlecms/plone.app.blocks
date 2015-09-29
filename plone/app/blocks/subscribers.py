from lxml.html import fromstring
from plone.app.blocks import utils
from plone.tiles.data import ANNOTATIONS_KEY_PREFIX
from zope.annotation.interfaces import IAnnotations
from plone.app.blocks.utils import getLayout


def onLayoutEdited(obj, event):
    """
    need to get the layout because you need to know what are
    acceptible storage values
    """
    layout = getLayout(obj)

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
    previous = annotations.get(ANNOTATIONS_KEY_PREFIX + '.__previous')
    if previous:
        for key in previous:
            if key not in tile_keys and key in annotations:
                del annotations[key]
    annotations[ANNOTATIONS_KEY_PREFIX + '.__previous'] = tile_keys