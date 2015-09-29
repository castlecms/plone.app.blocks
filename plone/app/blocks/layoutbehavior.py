# -*- coding: utf-8 -*-
from hashlib import md5
import logging

from lxml import html
from plone.app.blocks.interfaces import ILayoutField
from plone.app.blocks.interfaces import IOmittedField
from plone.app.blocks.interfaces import _
from plone.autoform.directives import write_permission
from plone.autoform.interfaces import IFormFieldProvider
from plone.memoize.ram import cache
from plone.supermodel import model
from zope import schema
from zope.interface import alsoProvides
from zope.interface import implements
from plone.autoform import directives as form


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

    form.mode(pageSiteLayout='hidden')
    pageSiteLayout = schema.Choice(
        title=_(u"Site layout"),
        description=_(u"Site layout to apply to this page "
                      u"instead of the default site layout"),
        vocabulary="plone.availableSiteLayouts",
        required=False
    )
    write_permission(pageSiteLayout="plone.ManageSiteLayouts")

    form.mode(sectionSiteLayout='hidden')
    sectionSiteLayout = schema.Choice(
        title=_(u"Section site layout"),
        description=_(u"Site layout to apply to sub-pages of this page "
                      u"instead of the default site layout"),
        vocabulary="plone.availableSiteLayouts",
        required=False
    )
    write_permission(sectionSiteLayout="plone.ManageSiteLayouts")
    #
    # fieldset('layout', label=_('Layout'),
    #          fields=('content', 'pageSiteLayout', 'sectionSiteLayout', 'contentLayout'))


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
