"""
"""
from maya import cmds
from maya.OpenMaya import MEventMessage
import maya.api.OpenMaya as api

import mampy
from mampy.core import mvp
from mampy.core.datatypes import BoundingBox
from mampy.core.selectionlist import ComponentList
from mampy.core.dagnodes import DependencyNode, Camera
from mampy.utils import undoable, AbstractDraggerCtx, Singleton


def get_distance_from_camera(sel):
    view = mvp.Viewport.active()
    camera = Camera(view.camera)

    bbox = BoundingBox()
    for i in sel or []:
        bbox.expand(i.bbox)

    return bbox.center.distanceTo(camera.transform.bbox.center)


class BaseContext(AbstractDraggerCtx):

    def __init__(self):
        super(BaseContext, self).__init__()
        self.nodes = []
        self.undo_callback_event = None

    def undo_callback(self, *args):
        if not cmds.currentCtx() == self.NAME:
            self.MEventMessage.removeCallback(self.undo_callback_event)
            return

    def tear_down(self):
        try:
            MEventMessage.removeCallback(self.undo_callback_event)
        except RuntimeError:
            pass
        self.nodes = []
        self.undo_callback_event = None

    def set_context(self):
        self.previous_ctx = cmds.currentCtx()
        if not self.undo_callback_event:
            self.undo_callback_event = MEventMessage.addEventCallback('Undo',
                                                                      self.undo_callback)
        super(BaseContext, self).set_context()


class Bevel(BaseContext):
    """
    """
    __metaclass__ = Singleton

    NAME = 'mamtools_bevel_context'

    _default_segments = 0
    _default_fraction = 0.2

    def toggle_chamfer(self):
        if not self.nodes:
            return
        else:
            for node in self.nodes:
                node.attr['chamfer'] = not(node.attr['chamfer'])

    def execute(self):
        """
        Create new bevel node and reset attribute values.
        """
        super(Bevel, self).execute()
        self.anchor_mitering = self.mitering = 0.0
        self.anchor_mitering_along = self.mitering_along = 0.0
        self.anchor_segments = self.segments = self._default_segments
        self.fraction = self.anchor_fraction = self._default_fraction
        self.control_object = None
        # self.anchor_segments = self.segments - 1

        version = cmds.about(version=True)
        if version == '2016 Extension 2 SP1':
            bevel_func = cmds.polyBevel3
        else:
            bevel_func = cmds.polyBevel

        components = mampy.complist()
        with undoable():
            for comp in components:
                node = bevel_func(
                    comp.cmdslist(),
                    offsetAsFraction=True,
                    fraction=0.2,
                    segments=1,
                    # worldSpace=True,
                    fillNgons=True,
                    mergeVertices=True,
                    mergeVertexTolerance=0.0001,
                    smoothingAngle=40,
                    miteringAngle=180,
                    # angleTolerance=180,
                )[0]
                self.nodes.append(DependencyNode(node))
            cmds.select(cl=True)
            self.control_object = self.nodes[-1]

    def press_ctrl_shift_left(self):
        self.toggle_chamfer()

    def drag_left(self):
        change_fraction = (self.dragPoint[0] - self.anchorPoint[0]) * 0.004
        self.fraction = change_fraction + self.anchor_fraction

        if self.fraction > 5: self.fraction = 1.0
        elif self.fraction < 0: self.fraction = 0.0

        for node in self.nodes:
            node.attr['fraction'] = self.fraction

    def drag_middle(self):
        change_segment = int((self.dragPoint[0] - self.anchorPoint[0]) * 0.2)
        self.segments = change_segment + self.anchor_segments

        if self.segments < 1: self.segments = 1
        for node in self.nodes:
            node.attr['segments'] = self.segments

    def drag_ctrl_left(self):
        change_mitering = int((self.dragPoint[0] - self.anchorPoint[0]) * 0.01)
        self.mitering = change_mitering + self.anchor_mitering

        if self.mitering > 4: self.mitering = 4.0
        if self.mitering < 0: self.mitering = 0.0
        for node in self.nodes:
            node.attr['mitering'] = self.mitering

    def drag_ctrl_middle(self):
        change_mitering_along = int((self.dragPoint[0] - self.anchorPoint[0]) * 0.01)
        self.mitering_along = change_mitering_along + self.anchor_mitering_along

        if self.mitering_along > 3: self.mitering_along = 3.0
        if self.mitering_along < 0: self.mitering_along = 0.0
        for node in self.nodes:
            node.attr['miterAlong'] = self.mitering_along

    def undo_callback(self, *args):
        super(Bevel, self).undo_callback()
        if not self.control_object.exists():
            cmds.setToolTo(self.previous_ctx)

    def release(self):
        """
        """
        super(Bevel, self).release()

        self.anchor_fraction = self.fraction
        self.anchor_segments = self.segments
        self.anchor_mitering = self.mitering


class Extrude(BaseContext):
    """
    """
    __metaclass__ = Singleton

    NAME = 'mamtools_extrude_context'

    _axis_lock_threshold = 3

    def execute(self):
        """
        Create new extrude node and reset attribute values.
        """
        super(Extrude, self).execute()
        self.thickness = self.offset = 0.0
        self.anchor_thickness = self.anchor_offset = 0.0
        self.is_vert = False
        self.control_object = None

        components = mampy.complist()
        with undoable():
            nodes = []
            self.sel = ComponentList()
            for comp in components:
                cmds.select(comp.cmdslist(), r=True)
                if comp.type == api.MFn.kMeshEdgeComponent:
                    node = cmds.polyExtrudeEdge(
                        keepFacesTogether=True,
                        offset=0,
                        thickness=0,
                    )[0]
                elif comp.type == api.MFn.kMeshPolygonComponent:
                    node = cmds.polyExtrudeFacet(
                        keepFacesTogether=True,
                        offset=0,
                        thickness=0,
                    )[0]
                elif comp.type == api.MFn.kMeshVertComponent:
                    self.is_vert = True
                    node = cmds.polyExtrudeVertex(
                        length=0,
                        width=0,
                    )[0]
                self.sel.extend(mampy.complist())
                nodes.append(DependencyNode(node))
            self.nodes.append(nodes)

            # Select new created geo and reset values
            cmds.select(self.sel.cmdslist(), r=True)

        self.control_object = self.nodes[-1][0]

    def press_ctrl_middle(self):
        if self.nodes:
            for node in self.nodes[-1]:
                node.attr['keepFacesTogether'] = not(node.attr['keepFacesTogether'])

    def press_shift_left(self):
        """
        Create new extrude node with shift modifier held.
        """
        self.execute()

    def press_ctrl_shift_left(self):
        """
        Create new extrude node with shift+ctrl modifier held.
        """
        self.execute()

    def drag_left(self):
        """
        Offset and thickness slider.

        Vertical movement changes thickness horizontal changes offset.
        """
        self.update_attribute_values()
        for node in self.nodes[-1]:
            if self.is_vert:
                node.attr['length'] = self.thickness
                node.attr['width'] = self.offset if self.offset > 0 else 0
            else:
                node.attr['thickness'] = self.thickness
                node.attr['offset'] = self.offset

    def drag_ctrl_shift_left(self):
        """
        Enabling ctrl modifer functionality when creating new extrude node.
        """
        self.drag_ctrl_left()

    def drag_shift_left(self):
        """
        Enabling normal behaviour when creating new extrude node.
        """
        self.drag_left()

    def drag_ctrl_left(self):
        """
        Lock axis in either x or y movement depening on which direction reaches
        threshold first.
        """
        if self.active_axis and self.anchorPoint == self.stored_anchor:
            self.update_attribute_values()
            if self.active_axis == 'offset':
                for node in self.nodes[-1]:
                    if self.is_vert:
                        node.attr['width'] = self.offset if self.offset > 0 else 0
                    node.attr['offset'] = self.offset
            elif self.active_axis == 'thickness':
                for node in self.nodes[-1]:
                    if self.is_vert:
                        node.attr['length'] = self.thickness
                    node.attr['thickness'] = self.thickness
            return
        else:
            self.stored_anchor = self.anchorPoint
            self.active_axis = None

        # Lock axis to threshold
        offset = self.dragPoint[0] - self.anchorPoint[0]
        thickness = self.dragPoint[1] - self.anchorPoint[1]
        if ((offset > self._axis_lock_threshold) or
                (-self._axis_lock_threshold > offset)):
            self.active_axis = 'offset'
        elif ((thickness > self._axis_lock_threshold) or
                (-self._axis_lock_threshold > thickness)):
            self.active_axis = 'thickness'

    def undo_callback(self, *args):
        super(Extrude, self).undo_callback()
        if self.control_object.exists():
            self.unify_attributes()
        else:
            self.nodes.pop()
            if not self.nodes:
                cmds.setToolTo(self.previous_ctx)
                return
            else:
                self.control_object = self.nodes[-1][0]
                self.unify_attributes()

    def unify_attributes(self):
        self.anchor_offset = self.offset = self.control_object.attr['offset']
        self.anchor_thickness = self.thickness = self.control_object.attr['thickness']

    def release(self):
        """
        Update anchors.

        call super to undochunk
        """
        super(Extrude, self).release()
        self.unify_attributes()

    def update_attribute_values(self):
        """
        Uses a multiplier that depends on camera distance to get a
        somewhat smooth experience in the viewport.
        """
        mp = 0.001 if not self.is_vert else 0.0001
        multiplier = get_distance_from_camera(self.sel) * mp
        change_offset = (self.dragPoint[0] - self.anchorPoint[0])
        change_thickness = (self.dragPoint[1] - self.anchorPoint[1])
        self.offset = (change_offset * multiplier) + self.anchor_offset
        self.thickness = (change_thickness * multiplier) + self.anchor_thickness


if __name__ == '__main__':
    Extrude().set_context()
