from lxml import etree
from lxml.html import tostring
from lxml.html import fromstring
from plone.app.theming.utils import theming_policy
from plone.app.blocks.layoutbehavior import ERROR_LAYOUT
from plone.app.blocks.interfaces import IBlocksTransformEnabled
from plone.app.blocks.utils import getLayout
from castle.cms.theming import renderWithTheme
from plone.dexterity.browser.view import DefaultView
from plone.outputfilters import apply_filters
from plone.outputfilters.interfaces import IFilter
from zope.component import getAdapters
from zope.interface import implements


panel_xpath = etree.XPath("//*[@data-panel]")


class ContentLayoutView(DefaultView):
    """Default view for a layout aware page
    """

    implements(IBlocksTransformEnabled)

    def get_layout(self):
        layout = getLayout(self.context)

        if not layout:
            layout = ERROR_LAYOUT

        if isinstance(layout, unicode):
            layout = layout.encode('utf8', 'ignore')

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
        if not settings or settings.rules:
            return self.index()
        return renderWithTheme(self.context, self.request, self.layout)
