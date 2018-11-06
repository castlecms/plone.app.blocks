# -*- coding: utf-8 -*-
import json
import logging

from plone.app.blocks import utils
from plone.app.blocks.interfaces import IBlocksSettings
from plone.registry.interfaces import IRegistry
from zope.component import queryUtility
from zope.interface import Interface
from zope.interface import implementer


logger = logging.getLogger('plone.app.blocks')


class IGridSystem(Interface):
    """ Utility to get the grid System
    """


@implementer(IGridSystem)
class BS3GridSystem(object):

    def __init__(self):
        self.offset = 1

    def transform(self, key):
        """ its possible:
            {type: row} -> row
            {type: cell, info: {xs:False, sm:False, md:True, lg:true, pos:{x:1 width:10}}} ->
                hidden-xs hidden-sm col-md-10
        """
        element = json.loads(key)
        if 'type' in element and element['type'] == 'row':
            self.offset = 1
            return 'row'
        elif 'type' in element and element['type'] == 'cell':
            result = ''
            if 'info' in element:
                if 'xs' in element['info'] and element['info']['xs'].lower() == "false":
                    result += 'hidden-xs '
                if 'sm' in element['info'] and element['info']['sm'].lower() == "false":
                    result += 'hidden-sm '
                if 'md' in element['info'] and element['info']['md'].lower() == "false":
                    result += 'hidden-md '
                if 'lg' in element['info'] and element['info']['lg'].lower() == "false":
                    result += 'hidden-lg '
                if 'pos' in element['info']:
                    if 'x' in element['info']['pos'] and element['info']['pos']['x'] > self.offset:
                        result += 'col-md-offset-%d ' % (element['info']['pos']['x'] - (self.offset - 1))  # noqa
                    if 'width' in element['info']['pos']:
                        self.offset += element['info']['pos']['width']
                        result += 'col-md-%d' % element['info']['pos']['width']
            return result


@implementer(IGridSystem)
class FoundationGridSystem(object):

    def transform(self, key):
        """ its possible:
            {type: row} -> row
            {type: cell, info: {sm:False, md:True, lg:true, pos:{width:10}}} ->
                hide-for-small-only medium-10 columns
        """
        element = json.loads(key)
        if 'type' in element and element['type'] == 'row':
            self.offset = 1
            return 'row'
        elif 'type' in element and element['type'] == 'cell':
            result = ''
            if 'info' in element:
                if 'xs' in element['info'] and element['info']['xs'].lower() == "false":
                    result += 'hide-for-small-only '
                if 'sm' in element['info'] and element['info']['sm'].lower() == "false":
                    result += 'hide-for-small-only '
                if 'md' in element['info'] and element['info']['md'].lower() == "false":
                    result += 'hide-for-medium-only '
                if 'lg' in element['info'] and element['info']['lg'].lower() == "false":
                    result += 'hide-for-large-only '
                if 'pos' in element['info']:
                    if 'width' in element['info']['pos']:
                        result += 'medium-%d columns ' % element['info']['pos']['width']
                    if 'offset' in element['info']['pos']:
                        result += 'medium-offset-%d ' % element['info']['pos']['offset']
            return result


@implementer(IGridSystem)
class DecoGridSystem(object):

    def transform(self, key):
        """ its possible:
            {type: row} -> row
            {type: cell, info: {xs:False, sm:False, md:True, lg:true, pos:{x:1 width:10}}} ->
            cell position-1 width-10
        """
        element = json.loads(key)
        if 'type' in element and element['type'] == 'row':
            return 'row'
        elif 'type' in element and element['type'] == 'cell':
            result = 'cell '
            if 'info' in element:
                if 'pos' in element['info']:
                    if 'x' in element['info']['pos']:
                        deco_pos = int(element['info']['pos']['x']) - 1
                        result += 'position-%d ' % deco_pos
                    if 'width' in element['info']['pos']:
                        result += 'width-%d' % element['info']['pos']['width']
            return result


def merge(request, layoutTree):
    """Perform grid system merging for the given page.

    Returns None if the page has no layout.
    """
    # Find layout node
    gridSystem = utils.xpath1(utils.gridXPath, layoutTree)
    if gridSystem is None:
        gridSystem = 'bs3'
        registry = queryUtility(IRegistry)
        if registry:
            settings = registry.forInterface(IBlocksSettings, check=False)
            gridSystem = settings.default_grid_system or 'bs3'

    gridUtil = queryUtility(IGridSystem, gridSystem)
    if gridUtil is None:
        logger.warn('Could not apply grid system "%s"' % gridSystem)
        return layoutTree
    gridUtil = gridUtil()
    for layoutGridNode in utils.gridDataXPath(layoutTree):
        gridinfo = layoutGridNode.attrib['data-grid']
        try:
            cssGridClass = gridUtil.transform(gridinfo)
        except (ValueError, KeyError):
            logger.info('error parsing grid config %s' % gridinfo)
            return layoutTree
        if cssGridClass is not None:
            if 'class' in layoutGridNode.attrib:
                layoutGridNode.attrib['class'] = layoutGridNode.attrib['class'] + ' ' + cssGridClass  # noqa
            else:
                layoutGridNode.attrib['class'] = cssGridClass
        del layoutGridNode.attrib['data-grid']
    return layoutTree
