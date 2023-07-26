# -*- coding: utf-8 -*-
from AccessControl import getSecurityManager
from App.config import getConfiguration
from copy import deepcopy
from diazo import compiler
from diazo import cssrules
from diazo import rules
from diazo import utils
from hashlib import md5
from lxml import etree
from lxml import html
from plone.memoize import ram
from plone.memoize.volatile import DontCache
from plone.resource.utils import queryResourceDirectory
from plone.subrequest import subrequest
from six.moves.urllib import parse
from z3c.form.interfaces import IFieldWidget
from zExceptions import NotFound
from zExceptions import Unauthorized
from zope.component import getMultiAdapter
from zope.component import queryUtility
from zope.component.hooks import getSite
from zope.security.interfaces import IPermission

# Legacy imports
from plone.app.blocks.interfaces import DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY
from plone.app.blocks.layoutbehavior import ILayoutAware
from plone.app.blocks.layoutbehavior import applyTilePersistent
from zope.component import getUtility
from plone.registry.interfaces import IRegistry

import logging
import six
import zope.deferredimport


zope.deferredimport.deprecated(
    "Moved in own behavior due to avoid circular imports. "
    "Import from plone.app.blocks.layoutbehavior instead",
    getDefaultAjaxLayout="plone.app.blocks.layoutbehavior:" "getDefaultAjaxLayout",
    getDefaultSiteLayout="plone.app.blocks.layoutbehavior:" "getDefaultSiteLayout",
    getLayout="plone.app.blocks.layoutbehavior:getLayout",
    getLayoutAwareSiteLayout="plone.app.blocks.layoutbehavior:"
    "getLayoutAwareSiteLayout",
)


headXPath = etree.XPath("/html/head")
layoutAttrib = "data-layout"
layoutXPath = etree.XPath("/html/@" + layoutAttrib)
tileAttrib = "data-tile"
tileXPath = etree.XPath("/html//*[@" + tileAttrib + "]")
headTileXPath = etree.XPath("/html/head//*[@" + tileAttrib + "]")
bodyTileXPath = etree.XPath("/html/body//*[@" + tileAttrib + "]")
panelXPath = etree.XPath("//*[@data-panel]")
gridDataAttrib = "data-grid"
gridDataXPath = etree.XPath("//*[@" + gridDataAttrib + "]")
logger = logging.getLogger("plone.app.blocks")


def extractCharset(response, default="utf-8"):
    """Get the charset of the given response"""

    charset = default
    if "content-type" in response.headers:
        for item in response.headers["content-type"].split(";"):
            if item.strip().startswith("charset"):
                charset = item.split("=")[1].strip()
                break
    return charset


def resolve(url, resolved=None):
    """Resolve the given URL to an lxml tree."""
    if resolved is None:
        try:
            resolved = resolveResource(url)
        except Exception:
            logger.exception(
                "There was an error while resolving the tile: {0}".format(
                    url,
                ),
            )
            scheme, netloc, path, params, query, fragment = parse.urlparse(url)
            tile_parts = {
                "scheme": scheme,
                "netloc": netloc,
                "path": path,
            }
            resolved = """<html>
<body>
    <dl class="portalMessage error" role="alert">
        <dt>Error</dt>
        <dd>There was an error while resolving the tile {scheme}://{netloc}{path}</dd>
    </dl>
</body>
</html>
""".format(
                **tile_parts
            )

    if not resolved.strip():
        return

    if isinstance(resolved, str):
        resolved = resolved.encode("utf-8")

    try:
        html_parser = html.HTMLParser(encoding="utf-8")
        return html.fromstring(resolved, parser=html_parser).getroottree()
    except etree.XMLSyntaxError as e:
        logger.error("%s: %s" % (repr(e), url))
        return


def subresponse_exception_handler(response, exception):
    if isinstance(exception, Unauthorized):
        response.setStatus = 401
        return
    return response.exception()


def resolveResource(url):
    """Resolve the given URL to a unicode string. If the URL is an absolute
    path, it will be made relative to the Plone site root.
    """
    url = parse.unquote(url)  # subrequest does not support quoted paths
    scheme, netloc, path, params, query, fragment = parse.urlparse(url)
    if path.count("++") == 2:
        # it is a resource that can be resolved without a subrequest
        _, resource_type, path = path.split("++")
        resource_name, _, path = path.partition("/")
        directory = queryResourceDirectory(resource_type, resource_name)
        if directory:
            try:
                res = directory.readFile(path)
                if isinstance(res, six.binary_type):
                    res = res.decode()
                return res
            except (NotFound, IOError):
                pass

    if url.startswith("/"):
        site = getSite()
        url = "/".join(site.getPhysicalPath()) + url

    response = subrequest(url, exception_handler=subresponse_exception_handler)
    if response.status == 404:
        raise NotFound(url)
    elif response.status == 401:
        raise Unauthorized(url)

    resolved = response.getBody()

    if isinstance(resolved, six.binary_type):
        charset = extractCharset(response)
        resolved = resolved.decode(charset)

    if response.status in (301, 302):
        site = getSite()
        location = response.headers.get("location") or ""
        if location.startswith(site.absolute_url()):
            return resolveResource(location[len(site.absolute_url()) :])

    elif response.status != 200:
        raise RuntimeError(resolved)

    return resolved


def xpath1(xpath, node, strict=True):
    """Return a single node matched by the given etree.XPath object."""

    if isinstance(xpath, six.string_types):
        xpath = etree.XPath(xpath)

    result = xpath(node)
    if len(result) == 1:
        return result[0]
    elif not ((len(result) > 1 and strict) or len(result) == 0):
        return result


def append_text(element, text):
    if text:
        element.text = (element.text or "") + text


def append_tail(element, text):
    if text:
        element.tail = (element.tail or "") + text


def replace_with_children(element, wrapper):
    """element.replace also replaces the tail and forgets the wrapper.text"""
    # XXX needs tests
    parent = element.getparent()
    index = parent.index(element)
    if index == 0:
        previous = None
    else:
        previous = parent[index - 1]
    if wrapper is None:
        children = []
    else:
        if index == 0:
            append_text(parent, wrapper.text)
        else:
            append_tail(previous, wrapper.text)
        children = wrapper.getchildren()
    parent.remove(element)
    if not children:
        if index == 0:
            append_text(parent, element.tail)
        else:
            append_tail(previous, element.tail)
    else:
        append_tail(children[-1], element.tail)
        children.reverse()
        for child in children:
            parent.insert(index, child)


def replace_content(element, wrapper):
    """Similar to above but keeps parent tag"""
    del element[:]
    if wrapper is not None:
        element.text = wrapper.text
        element.extend(wrapper.getchildren())


def remove_element(element):
    parent = element.getparent()
    parent.remove(element)


class PermissionChecker(object):
    def __init__(self, permissions, context):
        self.permissions = permissions
        self.context = context
        self.sm = getSecurityManager()
        self.cache = {}

    def allowed(self, field_name):
        permission_name = self.permissions.get(field_name, None)
        if permission_name is not None:
            if permission_name not in self.cache:
                permission = queryUtility(IPermission, name=permission_name)
                if permission is None:
                    self.cache[permission_name] = True
                else:
                    self.cache[permission_name] = bool(
                        self.sm.checkPermission(permission.title, self.context)
                    )
        return self.cache.get(permission_name, True)


def _getWidgetName(field, widgets, request):
    if field.__name__ in widgets:
        factory = widgets[field.__name__]
    else:
        factory = getMultiAdapter((field, request), IFieldWidget)
    if isinstance(factory, six.string_types):
        return factory
    if not isinstance(factory, type):
        factory = factory.__class__
    return "%s.%s" % (factory.__module__, factory.__name__)


def isVisible(name, omitted):
    value = omitted.get(name, False)
    if isinstance(value, basestring):
        return value == 'false'
    else:
        return not bool(value)


def cacheKey(func, rules_url, theme_node):
    if getConfiguration().debug_mode:
        raise DontCache()
    key = md5()
    key.update(rules_url)
    key.update(html.tostring(theme_node))
    return key.hexdigest()


def getLayout(content):
    behavior_data = ILayoutAware(content)
    if behavior_data.contentLayout:
        try:
            path = behavior_data.contentLayout
            resolved = resolveResource(path)
            layout = applyTilePersistent(path, resolved)
        except (NotFound, RuntimeError):
            layout = ''
    else:
        layout = behavior_data.content

    if not layout:
        registry = getUtility(IRegistry)
        try:
            path = registry['%s.%s' % (
                DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY,
                content.portal_type.replace(' ', '-'))]
        except (KeyError, AttributeError):
            path = None
        try:
            path = path or registry[DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY]
            resolved = resolveResource(path)
            layout = applyTilePersistent(path, resolved)
        except (KeyError, NotFound, RuntimeError):
            pass
    return layout
