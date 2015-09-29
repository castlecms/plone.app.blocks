from plone.app.theming.interfaces import THEME_RESOURCE_NAME
from plone.app.theming.utils import getCurrentTheme
from plone.resource.utils import queryResourceDirectory
from zope.globalrequest import getRequest
from zope.interface import implements
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary


CACHE_REQ_KEY = 'plone.sitelayouts'

class AvailableSiteLayoutsFactory(object):
    """Vocabulary to return available layouts of a given type
    """

    implements(IVocabularyFactory)

    def __call__(self, context):
        req = getRequest()
        if req and CACHE_REQ_KEY in req.environ:
            return req.environ[CACHE_REQ_KEY]

        currentTheme = getCurrentTheme()
        if currentTheme is None:
            return SimpleVocabulary([])

        themeDirectory = queryResourceDirectory(
            THEME_RESOURCE_NAME, currentTheme)
        if themeDirectory is None:
            return SimpleVocabulary([])

        terms = []
        for filename in themeDirectory.listDirectory():
            if filename[0] == '_' or '_.html' in filename:
                continue
            if filename.endswith('.html'):
                if filename == 'index.html':
                    terms.append(
                        SimpleVocabulary.createTerm(filename, filename, 'Default'))
                else:
                    name = filename.replace('.html', '')
                    label = name.replace('_', ' ').replace('-', ' ').capitalize()
                    terms.append(
                        SimpleVocabulary.createTerm(filename, filename, label))
        res = SimpleVocabulary(terms)
        if req:
            req.environ[CACHE_REQ_KEY] = res
        return res
AvailableSiteLayouts = AvailableSiteLayoutsFactory()
