# -*- coding: utf-8 -*-
from lxml import etree
from lxml import html
from plone.app.blocks import panel
from plone.app.blocks import tiles
from plone.tiles import esi
from plone.tiles.interfaces import ESI_HEADER
# Plone5.2 TODO - Remove 'gridsystem' references
from plone.app.blocks import gridsystem
from plone.transformchain.interfaces import ITransform
from repoze.xmliter.serializer import XMLSerializer
from repoze.xmliter.utils import getHTMLSerializer
from zope.interface import implementer

import logging
import re

# Legacy imports
from OFS.Image import File


try:
    # Plone 5.2+
    from Products.CMFPlone.utils import safe_bytes
except ImportError:
    # BBB for Plone 5.1
    from Products.CMFPlone.utils import safe_encode as safe_bytes


logger = logging.getLogger(__name__)



@implementer(ITransform)
class ParseXML(object):
    """First stage in the 8000's chain: parse the content to an lxml tree
    encapsulated in an XMLSerializer.

    The subsequent steps in this package will assume their result inputs are
    XMLSerializer iterables, and do nothing if it is not. This also gives us
    the option to parse the content here, and if we decide it's not HTML,
    we can avoid trying to parse it again.
    """

    order = 8000

    # Tests set this to True
    pretty_print = False

    def __init__(self, published, request):
        self.published = published
        self.request = request

    def transformBytes(self, result, encoding):
        return self.transformIterable([result], encoding)

    def transformUnicode(self, result, encoding):
        return self.transformIterable([result], encoding)

    def transformIterable(self, result, encoding):
        try:
            # We do NOT want to transform File responses since these can be layouts
            if isinstance(self.published.im_self, File):
                self.request['plone.app.blocks.disabled'] = True
                return None
        except AttributeError:
            pass

        if self.request.get('plone.app.blocks.disabled', False):
            return None

        content_type = self.request.response.getHeader('Content-Type')
        if content_type is None or not content_type.startswith('text/html'):
            return None

        contentEncoding = self.request.response.getHeader('Content-Encoding')
        if contentEncoding and contentEncoding in ('zip', 'deflate',
                                                   'compress',):
            return None

        try:
            # Fix layouts with CR[+LF] line endings not to lose their heads
            # (this has been seen with downloaded themes with CR[+LF] endings)
            # The html serializer much prefers only bytes, no unicode/text,
            # and it return a serializer that returns bytes.
            # So we start with ensuring all items in the iterable are bytes.
            iterable = [
                re.sub(b"&#13;", b"\n", re.sub(b"&#13;\n", b"\n", safe_bytes(item)))
                for item in result
                if item
            ]
            result = getHTMLSerializer(
                iterable, pretty_print=self.pretty_print, encoding=encoding
            )
            # Fix XHTML layouts with where etree.tostring breaks <![CDATA[
            if any([b"<![CDATA[" in item for item in iterable]):
                result.serializer = html.tostring

            self.request["plone.app.blocks.enabled"] = True
            return result
        except (AttributeError, TypeError, etree.ParseError) as e:
            logger.error(e)


@implementer(ITransform)
class MergePanels(object):
    """Find the site layout and merge panels."""

    order = 8100

    def __init__(self, published, request):
        self.published = published
        self.request = request

    def transformBytes(self, result, encoding):
        return

    def transformUnicode(self, result, encoding):
        return

    def transformIterable(self, result, encoding):
        if not self.request.get("plone.app.blocks.enabled", False) or not isinstance(
            result, XMLSerializer
        ):
            return

        tree = panel.merge(self.request, result.tree)
        if tree is None:
            return

        # Set a marker in the request to let subsequent steps know the merging
        # has happened
        self.request["plone.app.blocks.merged"] = True

        result.tree = tree

        # Fix serializer when layout has changed doctype from XHTML to HTML
        if result.tree.docinfo.doctype and "XHTML" not in result.tree.docinfo.doctype:
            result.serializer = html.tostring

        return result


@implementer(ITransform)
class IncludeTiles(object):
    """Turn a panel-merged page into the final composition by including tiles.
    Assumes the input result is an lxml tree and returns an lxml tree for
    later serialization.
    """

    order = 8500

    def __init__(self, published, request):
        self.published = published
        self.request = request

    def transformBytes(self, result, encoding):
        return

    def transformUnicode(self, result, encoding):
        return

    def transformIterable(self, result, encoding):
        if not self.request.get("plone.app.blocks.enabled", False) or not isinstance(
            result, XMLSerializer
        ):
            return

        result.tree = tiles.renderTiles(self.request, result.tree)
        return result

# Plone5.2 TODO - Remove 'gridsystem' references
@implementer(ITransform)
class ApplyResponsiveClass(object):
    """Turn a panel-merged page into the final composition by including tiles.
    Assumes the input result is an lxml tree and returns an lxml tree for
    later serialization.
    """

    order = 8900

    def __init__(self, published, request):
        self.published = published
        self.request = request

    def transformString(self, result, encoding):
        return None

    def transformUnicode(self, result, encoding):
        return None

    def transformIterable(self, result, encoding):
        if not self.request.get('plone.app.blocks.enabled', False) or \
                not isinstance(result, XMLSerializer):
            return None
        result.tree = gridsystem.merge(self.request, result.tree)
        return result