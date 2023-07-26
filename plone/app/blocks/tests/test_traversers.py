# -*- coding: utf-8 -*-
from plone.app.blocks.testing import BLOCKS_INTEGRATION_TESTING

import unittest


class TestTraversers(unittest.TestCase):

    layer = BLOCKS_INTEGRATION_TESTING

    def test_site_layout_traverser_registered(self):
        from plone.resource.file import FilesystemFile
<<<<<<< HEAD
        portal = self.layer['portal']

        layout = portal.restrictedTraverse(
            '++sitelayout++testlayout1/site.html')
=======

        portal = self.layer["portal"]

        layout = portal.restrictedTraverse("++sitelayout++testlayout1/site.html")
>>>>>>> blocks/main
        self.assertTrue(isinstance(layout, FilesystemFile))

    def test_site_layouts_vocabulary_and_manifest(self):
        from zope.schema.vocabulary import getVocabularyRegistry
<<<<<<< HEAD
        portal = self.layer['portal']

        vocab = getVocabularyRegistry().get(portal,
                                            'plone.availableSiteLayouts')
=======

        portal = self.layer["portal"]

        vocab = getVocabularyRegistry().get(portal, "plone.availableSiteLayouts")
>>>>>>> blocks/main
        vocab = list(vocab)
        vocab.sort(key=lambda t: t.token)

        self.assertEqual(len(vocab), 3)

        def _get_layout_vocab(token):
            for term in vocab:
                if term.token == token:
                    return term

<<<<<<< HEAD
        term = _get_layout_vocab('testlayout1/site.html')
        self.assertEqual(term.title, 'Testlayout1')
        self.assertEqual(term.value,
                         u'/++sitelayout++testlayout1/site.html')

        term = _get_layout_vocab('testlayout2/mylayout.html')
        self.assertEqual(term.title, 'My site layout')
        self.assertEqual(term.value,
                         u'/++sitelayout++testlayout2/mylayout.html')

        term = _get_layout_vocab('testlayout2/mylayout2.html')
        self.assertEqual(term.title, 'My site layout 2')
        self.assertEqual(term.value,
                         u'/++sitelayout++testlayout2/mylayout2.html')
=======
        term = _get_layout_vocab("testlayout1/site.html")
        self.assertEqual(term.title, "Testlayout1")
        self.assertEqual(term.value, u"/++sitelayout++testlayout1/site.html")

        term = _get_layout_vocab("testlayout2/mylayout.html")
        self.assertEqual(term.title, "My site layout")
        self.assertEqual(term.value, u"/++sitelayout++testlayout2/mylayout.html")

        term = _get_layout_vocab("testlayout2/mylayout2.html")
        self.assertEqual(term.title, "My site layout 2")
        self.assertEqual(term.value, u"/++sitelayout++testlayout2/mylayout2.html")
>>>>>>> blocks/main
