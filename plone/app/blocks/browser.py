from plone.app.blocks.interfaces import DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY
from plone.app.blocks.interfaces import IBlocksTransformEnabled
from plone.app.blocks.layoutbehavior import (
    applyTilePersistent,
    ERROR_LAYOUT)
from plone.app.blocks.layoutbehavior import ILayoutAware
from plone.app.theming.transform import renderWithTheme
from plone.dexterity.browser.view import DefaultView
from plone.outputfilters import apply_filters
from plone.outputfilters.interfaces import IFilter
from plone.registry.interfaces import IRegistry
from zExceptions import NotFound
from zope.component import getAdapters
from zope.component import getUtility
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
        return renderWithTheme(self.context, self.request, layout)