from plone.app.blocks.layoutbehavior import ERROR_LAYOUT
from plone.app.blocks.interfaces import IBlocksTransformEnabled
from plone.app.blocks.utils import getLayout
from plone.app.theming.transform import renderWithTheme
from plone.dexterity.browser.view import DefaultView
from plone.outputfilters import apply_filters
from plone.outputfilters.interfaces import IFilter
from zope.component import getAdapters
from zope.interface import implements


class ContentLayoutView(DefaultView):
    """Default view for a layout aware page
    """

    implements(IBlocksTransformEnabled)

    def __call__(self):
        """Render the contents of the "content" field coming from
        the ILayoutAware behavior.

        This result is supposed to be transformed by plone.app.blocks.
        """
        layout = getLayout(self.context)

        if not layout:
            layout = ERROR_LAYOUT

        # Here we skip legacy portal_transforms and call plone.outputfilters
        # directly by purpose
        filters = [f for _, f
                   in getAdapters((self.context, self.request), IFilter)]
        layout = apply_filters(filters, layout)
        # render with theming engine
        return renderWithTheme(self.context, self.request, layout)