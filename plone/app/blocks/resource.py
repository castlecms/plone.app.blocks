# -*- coding: utf-8 -*-
from configparser import SafeConfigParser
import logging

from Products.CMFCore.utils import getToolByName
from plone.app.blocks.interfaces import CONTENT_LAYOUT_FILE_NAME
from plone.app.blocks.interfaces import CONTENT_LAYOUT_MANIFEST_FORMAT
from plone.app.blocks.interfaces import CONTENT_LAYOUT_RESOURCE_NAME
from plone.memoize import view
from plone.resource.manifest import MANIFEST_FILENAME
from plone.resource.traversal import ResourceTraverser
from plone.resource.utils import iterDirectoriesOfType
from zope.annotation import IAnnotations
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary
from zope.dottedname.resolve import resolve
from io import StringIO


logger = logging.getLogger('plone.app.blocks')


class ContentLayoutTraverser(ResourceTraverser):
    """The content layout traverser.

    Allows traversal to /++contentlayout++<name> using ``plone.resource`` to
    fetch things stored either on the filesystem or in the ZODB.
    """

    name = CONTENT_LAYOUT_RESOURCE_NAME


@implementer(IAnnotations)
class AnnotationsDict(dict):
    """Volatile annotations dictionary to pass to view.memoize_contextless when
    request thread local is not set"""


class multidict(dict):
    """
    Taken from: http://stackoverflow.com/questions/9876059/parsing-configure-file-with-same-section-name-in-python  # noqa
    """
    _unique = 0

    def __setitem__(self, key, val):
        if isinstance(val, dict):
            self._unique += 1
            key += str(self._unique)
        dict.__setitem__(self, key, val)


def getLayoutsFromManifest(fp, format, directory_name):
    parser = SafeConfigParser(None, multidict, strict=False)
    # need to translate into stringio
    strfi = StringIO(fp.read().decode('utf-8'))
    parser.readfp(strfi)

    if parser.has_section('config1'):
        layer = parser.get('config1', 'layer')
        if layer:
            req = getRequest()
            layer = resolve(layer)
            if not layer.providedBy(req):
                return {}

    layouts = {}
    for section in parser.sections():
        if not section.startswith(format.resourceType) or ':variants' in section:
            continue
        # id is a combination of directory name + filename
        if parser.has_option(section, 'file'):
            filename = parser.get(section, 'file')
        else:
            filename = ''  # this should not happen...
        _id = directory_name + '/' + filename
        if _id in layouts:
            # because TTW resources are created first, we consider layouts
            # with same id in a TTW to be taken before other resources
            continue
        data = {
            'directory': directory_name
        }
        for key in format.keys:
            if parser.has_option(section, key):
                data[key] = parser.get(section, key)
            else:
                data[key] = format.defaults.get(key, None)
        layouts[_id] = data

    return layouts


def getLayoutsFromDirectory(directory, _format):
    layouts = {}
    name = directory.__name__
    if directory.isFile(MANIFEST_FILENAME):
        manifest = directory.openFile(MANIFEST_FILENAME)
        try:
            layouts.update(getLayoutsFromManifest(manifest, _format, name))
        except Exception:
            logger.exception(
                "Unable to read manifest for theme directory %s", name)
        finally:
            manifest.close()
    else:
        # can provide default file for it with no manifest
        filename = format.defaults.get('file', '')
        if filename and directory.isFile(filename):
            _id = name + '/' + filename
            if _id not in layouts:
                # not overridden
                layouts[_id] = {
                    'title': name.capitalize().replace('-', ' ').replace('.', ' '),
                    'description': '',
                    'directory': name,
                    'file': format.defaults.get('file', '')
                }
    return layouts


def getLayoutsFromResources(_format):
    layouts = {}

    for directory in iterDirectoriesOfType(_format.resourceType):
        layouts.update(getLayoutsFromDirectory(directory, _format))

    return layouts


@implementer(IVocabularyFactory)
class _AvailableLayoutsVocabulary(object):
    """Vocabulary to return request cached available layouts of a given type
    """

    def __init__(self):
        self.request = getRequest() or AnnotationsDict()

    @view.memoize_contextless
    def __call__(self, context, format, defaultFilename):
        items = {}  # dictionary is used here to avoid duplicate tokens

        resources = getLayoutsFromResources(format)
        used = []
        for _id, config in resources.items():
            title = config.get('title', _id)
            filename = config.get('file', defaultFilename)

            path = "/++%s++%s/%s" % (format.resourceType, config['directory'], filename)
            if path in used:
                # term values also need to be unique
                # this should not happen but it's possible for users to screw up
                # their layout definitions and it's better to not error here
                continue
            used.append(path)
            items[_id] = SimpleTerm(path, _id, title)

        items = sorted(items.values(), key=lambda term: term.title)
        return SimpleVocabulary(items)


@implementer(IVocabularyFactory)
class AvailableLayoutsVocabulary(object):
    """Vocabulary to return available layouts of a given type
    """

    def __init__(self, format, defaultFilename):
        self.format = format
        self.defaultFilename = defaultFilename

    def __call__(self, context):
        # Instantiate the factory impl per call to support caching by request
        fab = _AvailableLayoutsVocabulary()
        return fab(context, self.format, self.defaultFilename)


AvailableContentLayoutsVocabularyFactory = AvailableLayoutsVocabulary(
    CONTENT_LAYOUT_MANIFEST_FORMAT,
    CONTENT_LAYOUT_FILE_NAME,
)


def cacheKey(method, self):
    """Invalidate if the fti is modified, the global registry is modified,
    or the content is modified
    """

    # XXX
    # if Globals.DevelopmentMode:
    #     raise volatile.DontCache()

    catalog = getToolByName(self.context, 'portal_catalog')

    return (
        getattr(self.context, '_p_mtime', None),
        self.request.form.get('ajax_load'),
        catalog.getCounter(),
    )
