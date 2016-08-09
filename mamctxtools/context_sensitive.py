"""
"""
import functools
import logging

from maya import cmds
import maya.api.OpenMaya as api

import mampy
from mampy.utils import undoable, repeatable
from mampy.exceptions import InvalidSelection
from mampy.computils import (get_border_edges_from_selection,
                             get_border_loop_from_edge_index)

import mamtools
import mamselect
import mamuvs

from mamctxtools import contexts


logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


def bevel():
    """
    Bevel is a collection of functions usually performed when certain states
    are fulfilled, such as: selection, border edge etc.
    """
    s = mampy.selected()
    if not s:
        return logger.warn('Nothing Selected.')

    comp = s.itercomps().next()
    if comp.type == api.MFn.kMeshEdgeComponent:
        if comp.is_border(comp.index):
            contexts.extrude()
        else:
            contexts.bevel()
    elif comp.type == api.MFn.kMeshPolygonComponent:
        contexts.extrude()
    elif comp.type == api.MFn.kMeshVertComponent:
        contexts.extrude()


@undoable
@repeatable
def bridge():
    selected = mampy.selected()
    if not selected:
        raise InvalidSelection('Nothing selected, select border edges.')

    for component in get_border_edges_from_selection(selected).itercomps():
        if component.type == api.MFn.kMeshPolygonComponent:
            bridge_face()
        else:
            component = component.to_edge()
            connected = list(component.get_connected())
            if len(connected) == 1:
                border_edge = get_border_loop_from_edge_index(component.index)
                if border_edge == set(component.indices):
                    cmds.polyCloseBorder(list(component))
                else:
                    cmds.polyAppend(str(component.dagpath),
                                    s=1,
                                    a=(component.index, component.indices[-1]))
            elif len(connected) == 2:
                cmds.polyBridgeEdge(divisions=0)


@undoable
def bridge_face():
    faces = mampy.selected()
    mamselect.mesh.convert('edge')
    cmds.delete(list(faces))
    cmds.polyBridgeEdge(divisions=0)


def detach(extract=False):
    """
    Dispatches function call depening on selection type or type of panel
    under cursor.
    """
    s = mampy.selected()
    if not s:
        return logger.warn('Nothing Selected.')

    focused_panel = cmds.getPanel(wf=True)
    if focused_panel.startswith('polyTexturePlacementPanel'):
        mamuvs.tear_off()
    elif focused_panel.startswith('modelPanel'):
        s = s[0]
        if s.type == api.MFn.kMeshPolygonComponent:
            mamtools.mesh.detach(extract)
        elif s.type in [api.MFn.kTransform]:
            cmds.duplicate(rr=True)  # parentOnly=hierarchy)


def merge():
    """
    Dispatches function call depending on selection type
    """
    s = mampy.selected()
    if not s:
        return logger.warn('Nothing Selected.')

    obj = s[0]
    logger.debug(obj)
    t = obj.type
    if obj.type in [api.MFn.kTransform]:
        t = obj.get_shape().type

    try:
        {
            api.MFn.kMeshVertComponent: functools.partial(mamtools.delete.merge_verts,
                                                          False),
            api.MFn.kMeshPolygonComponent: mamtools.delete.merge_faces,
            api.MFn.kMeshEdgeComponent: mamtools.delete.collapse,
            api.MFn.kMesh: mamtools.mesh.combine_separate,
        }[t]()
    except KeyError:
        logger.warn('{} is not a valid type'.format(t))


def connect():
    comp = mampy.selected()[0]
    if comp.type == api.MFn.kMeshVertComponent:
        mamtools.mel('ConnectComponents')
    else:
        mamtools.mel('connectTool')

if __name__ == '__main__':
    bridge()
