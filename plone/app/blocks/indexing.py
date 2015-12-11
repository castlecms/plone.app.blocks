from Products.CMFPlone.utils import safe_unicode
from lxml.html import fromstring
from lxml.html import tostring
from plone.app.blocks.layoutbehavior import ILayoutAware
from plone.app.contenttypes import indexers
from plone.indexer.decorator import indexer
from plone.tiles.data import ANNOTATIONS_KEY_PREFIX
from zope.annotation.interfaces import IAnnotations


concat = indexers._unicode_save_string_concat


@indexer(ILayoutAware)
def LayoutSearchableText(obj):
    text = []
    try:
        text.append(obj.text.output)
    except AttributeError:
        pass

    behavior_data = ILayoutAware(obj)
    # get data from tile data
    annotations = IAnnotations(obj)
    for key in annotations.keys():
        if key.startswith(ANNOTATIONS_KEY_PREFIX):
            data = annotations[key]
            if not hasattr(data, 'get'):
                continue
            for field_name in ('title', 'label', 'content'):
                val = data.get(field_name)
                if isinstance(val, basestring):
                    text.append(val)
    if not behavior_data.contentLayout and behavior_data.content:
        dom = fromstring(behavior_data.content)
        for el in dom.cssselect('.mosaic-text-tile .mosaic-tile-content'):
            text.append(tostring(el))

    return concat(
        safe_unicode(obj.id),
        safe_unicode(obj.title) or u"",
        safe_unicode(obj.description) or u"",
        ' '.join(text)
    )