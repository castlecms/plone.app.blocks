# -*- coding: utf-8 -*-
from hashlib import md5
import logging

from collective.dexteritytextindexer import searchable
from lxml import html
from plone.app.blocks.interfaces import DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY
from plone.app.blocks.interfaces import IBlocksTransformEnabled
from plone.app.blocks.interfaces import ILayoutField
from plone.app.blocks.interfaces import IOmittedField
from plone.app.blocks.interfaces import _
from plone.app.blocks.vocabularies import AvailableSiteLayouts
from plone.app.theming import utils as theming_utils
from plone.autoform.directives import write_permission
from plone.autoform.interfaces import IFormFieldProvider
from plone.dexterity.browser.view import DefaultView
from plone.memoize.ram import cache
from plone.outputfilters import apply_filters
from plone.outputfilters.interfaces import IFilter
from plone.registry.interfaces import IRegistry
from plone.supermodel import model
from plone.supermodel.directives import fieldset
from zExceptions import NotFound
from zope import schema
from zope.component import getAdapters
from zope.component import getUtility
from zope.interface import alsoProvides
from zope.interface import implements


logger = logging.getLogger('plone.app.blocks')


ERROR_LAYOUT = u"""
<!DOCTYPE html>
<html lang="en" data-layout="./@@page-site-layout">
<body>
<div data-panel="content">
Could not find layout for content
</div>
</body>
</html>"""


class LayoutField(schema.Text):
    """A field used to store layout information
    """

    implements(ILayoutField)


class ILayoutAware(model.Schema):
    """Behavior interface to make a type support layout.
    """
    searchable('content')
    content = LayoutField(
        title=_(u"Custom layout"),
        description=_(u"Custom content and content layout of this page"),
        default=None,
        required=False
    )

    contentLayout = schema.ASCIILine(
        title=_(u'Content Layout'),
        description=_(u'Selected content layout. If selected, custom layout is ignored.'),
        required=False)

    pageSiteLayout = schema.Choice(
        title=_(u"Site layout"),
        description=_(u"Site layout to apply to this page "
                      u"instead of the default site layout"),
        source=AvailableSiteLayouts,
        required=False
    )
    write_permission(pageSiteLayout="plone.ManageSiteLayouts")

    sectionSiteLayout = schema.Choice(
        title=_(u"Section site layout"),
        description=_(u"Site layout to apply to sub-pages of this page "
                      u"instead of the default site layout"),
        source=AvailableSiteLayouts,
        required=False
    )
    write_permission(sectionSiteLayout="plone.ManageSiteLayouts")

    fieldset('layout', label=_('Layout'),
             fields=('content', 'pageSiteLayout', 'sectionSiteLayout', 'contentLayout'))


alsoProvides(ILayoutAware, IFormFieldProvider)
alsoProvides(ILayoutAware['content'], IOmittedField)
alsoProvides(ILayoutAware['pageSiteLayout'], IOmittedField)
alsoProvides(ILayoutAware['sectionSiteLayout'], IOmittedField)


@cache(lambda fun, path, resolved: md5(resolved).hexdigest())
def applyTilePersistent(path, resolved):
    """Append X-Tile-Persistent into resolved layout's tile URLs to allow
    context specific tile configuration overrides.

    (Path is required for proper error message when lxml parser fails.)
    """
    from plone.app.blocks.utils import tileAttrib
    from plone.app.blocks.utils import bodyTileXPath
    from plone.app.blocks.utils import resolve
    tree = resolve(path, resolved=resolved)
    for node in bodyTileXPath(tree):
        url = node.attrib[tileAttrib]
        if 'X-Tile-Persistent' not in url:
            if '?' in url:
                url += '&X-Tile-Persistent=yes'
            else:
                url += '?X-Tile-Persistent=yes'
        node.attrib[tileAttrib] = url
    return html.tostring(tree)


class ContentLayoutView(DefaultView):
    """Default view for a layout aware page
    """

    implements(IBlocksTransformEnabled)

    def __call__(self):
        """Render the contents of the "content" field coming from
        the ILayoutAware behavior.

        This result is supposed to be transformed by plone.app.blocks.
        """
        behavior_data = ILayoutAware(self.context)
        if behavior_data.contentLayout:
            from plone.app.blocks.utils import resolveResource
            try:
                path = behavior_data.contentLayout
                resolved = resolveResource(path)
                layout = applyTilePersistent(path, resolved)
            except (NotFound, RuntimeError):
                layout = ''
        else:
            layout = behavior_data.content

        if not layout:
            from plone.app.blocks.utils import resolveResource
            registry = getUtility(IRegistry)
            try:
                path = registry['%s.%s' % (
                    DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY,
                    self.context.portal_type.replace(' ', '-'))]
            except (KeyError, AttributeError):
                path = None
            try:
                path = path or registry[DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY]
                resolved = resolveResource(path)
                layout = applyTilePersistent(path, resolved)
            except (KeyError, NotFound, RuntimeError):
                pass

        if not layout:
            layout = ERROR_LAYOUT

        # Here we skip legacy portal_transforms and call plone.outputfilters
        # directly by purpose
        filters = [f for _, f
                   in getAdapters((self.context, self.request), IFilter)]
        layout = apply_filters(filters, layout)
        # render with theming engine
        return theming_utils.renderWithTheme(self.context, self.request, layout)
