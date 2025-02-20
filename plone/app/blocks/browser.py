from lxml import etree
from lxml.html import fromstring, tostring
from plone.app.blocks.interfaces import IBlocksTransformEnabled
from plone.app.blocks.layoutbehavior import ERROR_LAYOUT
from plone.app.blocks.utils import getLayout
from plone.app.theming.utils import theming_policy
from plone.dexterity.browser.view import DefaultView
from plone.outputfilters import apply_filters
from plone.outputfilters.interfaces import IFilter
from zope.component import getAdapters
from zope.interface import implementer

from castle.cms.theming import renderWithTheme

panel_xpath = etree.XPath("//*[@data-panel]")

@implementer(IBlocksTransformEnabled)
class ContentLayoutView(DefaultView):
    """Default view for a layout aware page
    """

    def get_layout(self):
        layout = getLayout(self.context)

        if not layout:
            layout = ERROR_LAYOUT

        # if isinstance(layout, unicode):
        #     layout = layout.encode('utf8', 'xmlcharrefreplace')

        # Here we skip legacy portal_transforms and call plone.outputfilters
        # directly by purpose
        filters = [f for _, f
                   in getAdapters((self.context, self.request), IFilter)]
        return apply_filters(filters, layout)

    @property
    def content(self):
        if not self.layout:
            return 'No layout found'
        dom = fromstring(self.layout)
        content = panel_xpath(dom)
        if len(content) > 0:
            return tostring(content[0])
        return 'No layout found'

    def __call__(self):
        """Render the contents of the "content" field coming from
        the ILayoutAware behavior.

        This result is supposed to be transformed by plone.app.blocks.
        """
        self.layout = self.get_layout()
        policy = theming_policy(self.request)
        settings = policy.getSettings()
        # Python3 TODO - Some layouts don't render when run through index(). Not sure if still needed?
        # try:
        #     if not settings or settings.rules:
        #         return self.index()
        # except AttributeError:
        #     pass
        return renderWithTheme(self.context, self.request, self.layout)
