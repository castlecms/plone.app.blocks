# -*- coding: utf-8 -*-
from plone.resource.manifest import ManifestFormat
from zope import schema
from zope.i18nmessageid import MessageFactory
from zope.interface import Interface


CONTENT_LAYOUT_RESOURCE_NAME = 'contentlayout'
CONTENT_LAYOUT_FILE_NAME = "content.html"
DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY = 'plone.app.blocks.default_layout'

CONTENT_LAYOUT_MANIFEST_FORMAT = ManifestFormat(
    CONTENT_LAYOUT_RESOURCE_NAME,
    keys=('title', 'description', 'file', 'preview', 'for', 'sort_key',
          'layer'),
    defaults={'file': CONTENT_LAYOUT_FILE_NAME}
)

# XXX
# unused, b/w compat defs
SITE_LAYOUT_RESOURCE_NAME = 'sitelayout'
# end ununsed
# XXX

_ = MessageFactory('plone')


class IBlocksLayer(Interface):
    """Browser layer used to ensure blocks functionality can be installed on
    a site-by-site basis for published objects (usually views), which
    provider IBlocksTransformEnabled marker interface.
    """


class IBlocksTransformEnabled(Interface):
    """Marker interface for views (or other published objects), which require
    blocks transform
    """


class IBlocksSettings(Interface):
    """Settings registered with the portal_registry tool
    """

    default_grid_system = schema.ASCIILine(
        title=_(u'Default grid system'),
        description=_(u'Grid system to use when one is not specified '
                      u'the result DOM.'),
        default='deco')


class ILayoutField(Interface):
    """Marker interface for the layout field
    """


class IOmittedField(Interface):
    """Marker interface to distinguish the layout behavior schema fields from
    other fields to allow hiding them in the user interfaces
    """
