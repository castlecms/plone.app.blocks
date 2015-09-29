# -*- coding: utf-8 -*-

def step_setup_various(context):
    if context.readDataFile('plone.app.blocks_default.txt') is None:
        return
