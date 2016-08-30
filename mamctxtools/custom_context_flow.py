"""
"""
import functools
import logging

from maya import cmds
from maya.api.OpenMaya import MFn
import maya.api.OpenMaya as api

import mampy
from mampy.utils import undoable, repeatable
from mampy.core.exceptions import (NothingSelected, InvalidComponentSelection,
                                   InvalidSelection)
from mampy.core.selectionlist import get_borders_from_complist
from mampy.core.components import get_border_loop_indices_from_edge_index

from mampy.utils.decorators import restore_context

import mamtools
import mamselect

from mamctxtools import dragger_contexts


logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


def bevel():
    """
    Bevel is a collection of functions usually performed when certain states
    are fulfilled, such as: selection, border edge etc.
    """
    selected = mampy.complist()
    if not selected:
        raise NothingSelected()

    component = selected[0]
    # Eearly return in case of map components
    if component.type == MFn.kMeshMapComponent:
        raise InvalidComponentSelection()

    if component.type == api.MFn.kMeshEdgeComponent:
        # Check if we can extrude edge borders or bevel internal edges.
        if all(component.is_border(i) for i in component.indices):
            # When extruding border edges we don't want the context tool to handle
            # the manipulation. Just restore old tool right away.
            with restore_context():
                dragger_contexts.Extrude()
        elif not any(component.is_border(i) for i in component.indices):
            dragger_contexts.Bevel().run()
        else:
            raise InvalidSelection('Mixed selections, cant mix edge borders with '
                                   'non borders when beveling.')
    else:
        # Else perform an extrude on polygon or vertex.
        if cmds.currentCtx() == dragger_contexts.Extrude.NAME:
            dragger_contexts.Extrude().setup()
        else:
            dragger_contexts.Extrude().run()


@undoable()
@repeatable
def bridge():
    selected = mampy.complist()
    if not selected:
        raise NothingSelected()

    # Quit early if face selections.
    if selected[0].type == api.MFn.kMeshPolygonComponent:
        bridge_face()

    # Only work on border components
    for component in get_borders_from_complist(selected):
        component = component.to_edge(internal=True)
        connected = list(component.get_connected_components())
        # If border is closed or edges are next to each others
        if len(connected) == 1:
            border_edge = get_border_loop_indices_from_edge_index(component.index)
            if border_edge == set(component.indices):
                cmds.polyCloseBorder(component.cmdslist())
            else:
                cmds.polyAppend(
                    str(component.dagpath),
                    s=1,
                    a=(component.index, component.indices[-1])
                )
        else:
            cmds.polyBridgeEdge(divisions=0)


def bridge_face():
    faces = mampy.complist()
    # Get edge border before deleting face.
    mamselect.mesh.convert('edge')
    # Now safe to delete face and perform bridge.
    cmds.delete(faces.cmdslist())
    cmds.polyBridgeEdge(divisions=0)


def detach(extract=False):
    """
    Dispatches function call depening on selection type or type of panel
    under cursor.
    """
    selected = mampy.complist() or mampy.daglist()
    if not selected:
        raise NothingSelected()

    object_type = selected.pop().type
    if object_type == MFn.kMeshPolygonComponent:
        mamtools.mesh.detach(extract)
    elif object_type in [api.MFn.kTransform]:
        cmds.duplicate(rr=True)


def merge():
    """
    Dispatches function call depending on selection type
    """
    selected = mampy.complist() or mampy.daglist()
    if not selected:
        raise NothingSelected()

    control_object = selected.pop()
    if control_object.type in [MFn.kTransform]:
        object_type = control_object.shape.type
    else:
        object_type = control_object.type

    try:
        {
            MFn.kMeshVertComponent: functools.partial(mamtools.delete.merge_verts,
                                                      False),
            MFn.kMeshPolygonComponent: mamtools.delete.merge_faces,
            MFn.kMeshEdgeComponent: mamtools.delete.collapse,
            MFn.kMesh: mamtools.mesh.combine_separate,
        }[object_type]()
    except KeyError:
        logger.warn('{} is not a valid type'.format(object_type))


def connect():
    """
    Control flow for connected component tools.
    """
    selected = mampy.complist()
    if selected:
        object_type = selected.pop().type
        if object_type in [MFn.kMeshMapComponent]:
            raise InvalidComponentSelection()
        elif object_type == MFn.kMeshVertComponent:
            mamtools.mel('ConnectComponents')
        else:
            mamtools.mel('connectTool')

if __name__ == '__main__':
    bevel()
