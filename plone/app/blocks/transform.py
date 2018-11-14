# -*- coding: utf-8 -*-
from lxml import etree
from lxml import html
from OFS.Image import File
from plone.app.blocks import gridsystem
from plone.transformchain.interfaces import ITransform
from repoze.xmliter.serializer import XMLSerializer
from repoze.xmliter.utils import getHTMLSerializer
from zope.interface import implementer

import re


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

    def transformString(self, result, encoding):
        return self.transformIterable([result], encoding)

    def transformUnicode(self, result, encoding):
        return self.transformIterable([result], encoding)

    def transformIterable(self, result, encoding):
        try:
            # We do NOT want to transform File responses since these can be layouts
            if isinstance(self.published.__self__, File):
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
            iterable = [re.sub(b'&#13;', b'\n', re.sub(b'&#13;\n', b'\n', item))
                        for item in result if item]
            result = getHTMLSerializer(
                iterable, pretty_print=self.pretty_print, encoding=encoding)
            # We are going to force html output here always as XHTML
            # output does odd character encodings
            result.serializer = html.tostring
            self.request['plone.app.blocks.enabled'] = True
            return result
        except (AttributeError, TypeError, etree.ParseError):
            return None


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
