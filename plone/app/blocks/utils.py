# -*- coding: utf-8 -*-
import logging

from AccessControl import getSecurityManager
import Globals
from lxml import etree
from lxml import html
from plone.app.blocks.interfaces import DEFAULT_CONTENT_LAYOUT_REGISTRY_KEY
from plone.app.blocks.layoutbehavior import ILayoutAware
from plone.app.blocks.layoutbehavior import applyTilePersistent
from plone.memoize.volatile import DontCache
from plone.registry.interfaces import IRegistry
from plone.resource.utils import queryResourceDirectory
from plone.subrequest import subrequest
from z3c.form.interfaces import IFieldWidget
from zExceptions import NotFound
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.component import queryUtility
from zope.security.interfaces import IPermission
from zope.site.hooks import getSite


headXPath = etree.XPath("/html/head")
layoutAttrib = 'data-layout'
layoutXPath = etree.XPath("/html/@" + layoutAttrib)
gridAttrib = 'data-gridsystem'
gridXPath = etree.XPath("/html/@" + gridAttrib)
tileAttrib = 'data-tile'
headTileXPath = etree.XPath("/html/head//*[@" + tileAttrib + "]")
bodyTileXPath = etree.XPath("/html/body//*[@" + tileAttrib + "]")
gridDataAttrib = 'data-grid'
gridDataXPath = etree.XPath("//*[@" + gridDataAttrib + "]")
panelXPath = etree.XPath("//*[@data-panel]")


logger = logging.getLogger('plone.app.blocks')


def extractCharset(response, default='utf-8'):
    """Get the charset of the given response
    """

    charset = default
    if 'content-type' in response.headers:
        for item in response.headers['content-type'].split(';'):
            if item.strip().startswith('charset'):
                charset = item.split('=')[1].strip()
                break
    return charset


def resolve(url, resolved=None):
    """Resolve the given URL to an lxml tree.
    """

    if resolved is None:
        resolved = resolveResource(url)
    if not resolved.strip():
        return None
    try:
        if isinstance(resolved, unicode):
            html_parser = html.HTMLParser(encoding='utf-8')
            return html.fromstring(resolved.encode('utf-8'),
                                   parser=html_parser).getroottree()
        else:
            return html.fromstring(resolved).getroottree()
    except etree.XMLSyntaxError as e:
        logger.error('%s: %s' % (repr(e), url))
        return None


def resolveResource(url):
    """Resolve the given URL to a unicode string. If the URL is an absolute
    path, it will be made relative to the Plone site root.
    """
    if url.count('++') == 2:
        # it is a resource that can be resolved without a subrequest
        _, resource_type, path = url.split('++')
        resource_name, _, path = path.partition('/')
        directory = queryResourceDirectory(resource_type, resource_name)
        if directory:
            try:
                return directory.readFile(str(path))
            except NotFound:
                pass

    if url.startswith('/'):
        site = getSite()
        url = '/'.join(site.getPhysicalPath()) + url

    response = subrequest(url)
    if response.status == 404:
        raise NotFound(url)

    resolved = response.getBody()

    if isinstance(resolved, str):
        charset = extractCharset(response)
        resolved = resolved.decode(charset)

    if response.status in (301, 302):
        site = getSite()
        location = response.headers.get('location') or ''
        if location.startswith(site.absolute_url()):
            return resolveResource(location[len(site.absolute_url()):])

    elif response.status != 200:
        raise RuntimeError(resolved)

    return resolved


def xpath1(xpath, node, strict=True):
    """Return a single node matched by the given etree.XPath object.
    """

    if isinstance(xpath, basestring):
        xpath = etree.XPath(xpath)

    result = xpath(node)
    if len(result) == 1:
        return result[0]
    else:
        if (len(result) > 1 and strict) or len(result) == 0:
            return None
        else:
            return result


def append_text(element, text):
    if text:
        element.text = (element.text or '') + text


def append_tail(element, text):
    if text:
        element.tail = (element.tail or '') + text


def replace_with_children(element, wrapper):
    """element.replace also replaces the tail and forgets the wrapper.text
    """
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
    """Similar to above but keeps parent tag
    """
    del element[:]
    if wrapper is not None:
        element.text = wrapper.text
        element.extend(wrapper.getchildren())


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
                        self.sm.checkPermission(permission.title,
                                                self.context),
                    )
        return self.cache.get(permission_name, True)


def _getWidgetName(field, widgets, request):
    if field.__name__ in widgets:
        factory = widgets[field.__name__]
    else:
        factory = getMultiAdapter((field, request), IFieldWidget)
    if isinstance(factory, basestring):
        return factory
    if not isinstance(factory, type):
        factory = factory.__class__
    return '%s.%s' % (factory.__module__, factory.__name__)


def isVisible(name, omitted):
    value = omitted.get(name, False)
    if isinstance(value, basestring):
        return value == 'false'
    else:
        return not bool(value)


def cacheKey(func, rules_url, theme_node):
    if Globals.DevelopmentMode:
        raise DontCache()
    return ':'.join([rules_url, html.tostring(theme_node)])


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
