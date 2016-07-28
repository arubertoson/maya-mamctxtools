
from maya import cmds, mel
import maya.api.OpenMaya as api

import mampy
from mampy.utils import DraggerCtx, mvp, undo
from mampy.dgcomps import MeshVert
from mampy.dgnodes import DependencyNode
from mampy.dgcontainers import SelectionList


def get_distance_from_camera(sel):
    view = mvp.Viewport.active()
    camera = mampy.get_node(view.camera)

    vec = api.MPoint()
    for i in sel.itercomps():
        vec += i.bounding_box.center

    vec = camera.bounding_box.center - (vec / len(sel))
    return vec.length()


class bevel(DraggerCtx):

    def __init__(self):
        self.name = 'mamtools_bevel_context'
        super(bevel, self).__init__(self.name)
        self.run()

    def setup(self):
        """
        Create new bevel node and reset attribute values.
        """
        self.nodes = []
        version = cmds.about(version=True)
        if version == '2016 Extension 2 SP1':
            bevel = cmds.polyBevel3
        else:
            bevel = cmds.polyBevel

        with undo():
            for comp in mampy.selected().itercomps():
                node = bevel(
                    list(comp),
                    offsetAsFraction=True,
                    fraction=0.2,
                    segments=1,
                    # worldSpace=True,
                    fillNgons=True,
                    mergeVertices=True,
                    mergeVertexTolerance=0.0001,
                    smoothingAngle=30,
                    miteringAngle=180,
                    # angleTolerance=180,
                )[0]
                self.nodes.append(DependencyNode(node))
            cmds.select(cl=True)

        # Reset values
        self.segments = 1
        self.anchor_segments = 0
        self.fraction = self.anchor_fraction = 0.2

    def drag_left(self):
        change_fraction = (self.dragPoint[0] - self.anchorPoint[0]) * 0.004
        self.fraction = change_fraction + self.anchor_fraction

        if self.fraction > 5: self.fraction = 1.0
        elif self.fraction < 0: self.fraction = 0.0

        for node in self.nodes:
            node['fraction'] = self.fraction

    def drag_middle(self):
        change_segment = int((self.dragPoint[0] - self.anchorPoint[0]) * 0.2)
        self.segments = change_segment + self.anchor_segments

        if self.segments < 1: self.segments = 1

        for node in self.nodes:
            node['segments'] = self.segments

    def release(self):
        """
        """
        super(bevel, self).release()

        self.anchor_fraction = self.fraction
        self.anchor_segments = self.segments


class extrude(DraggerCtx):
    """
    """
    def __init__(self):
        self.name = 'mamtools_extrude_context'
        self.axis_lock_threshold = 3
        super(extrude, self).__init__(self.name)

        self.run()

    def setup(self):
        """
        Create new extrude node and reset attribute values.
        """
        self.nodes = []
        self.is_vert = False
        self.sel = SelectionList()

        with undo():
            for comp in mampy.selected().itercomps():
                cmds.select(list(comp), r=True)
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
                self.sel.extend(mampy.selected())
                self.nodes.append(DependencyNode(node))

            # Select new created geo and reset values
            cmds.select(list(self.sel), r=True)

        self.thickness = 0.0
        self.offset = 0.0
        self.anchor_offset = 0.0
        self.anchor_thickness = 0.0

    def press_shift_left(self):
        """
        Create new extrude node with shift modifier held.
        """
        self.setup()

    def press_ctrl_shift_left(self):
        """
        Create new extrude node with shift+ctrl modifier held.
        """
        self.setup()

    def drag_left(self):
        """
        Offset and thickness slider.

        Vertical movement changes thickness horizontal changes offset.
        """
        self.update_attribute_values()
        for node in self.nodes:
            if self.is_vert:
                node['length'] = self.thickness
                node['width'] = self.offset if self.offset > 0 else 0
            else:
                node['thickness'] = self.thickness
                node['offset'] = self.offset

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
                for node in self.nodes:
                    if self.is_vert:
                        node['width'] = self.offset if self.offset > 0 else 0
                    node['offset'] = self.offset
            elif self.active_axis == 'thickness':
                for node in self.nodes:
                    if self.is_vert:
                        node['length'] = self.thickness
                    node['thickness'] = self.thickness
            return
        else:
            self.stored_anchor = self.anchorPoint
            self.active_axis = None

        # Lock axis to threshold
        offset = self.dragPoint[0] - self.anchorPoint[0]
        thickness = self.dragPoint[1] - self.anchorPoint[1]
        if ((offset > self.axis_lock_threshold) or
                (-self.axis_lock_threshold > offset)):
            self.active_axis = 'offset'
        elif ((thickness > self.axis_lock_threshold) or
                (-self.axis_lock_threshold > thickness)):
            self.active_axis = 'thickness'

    def release(self):
        """
        Update anchors.

        call super to undochunk
        """
        super(extrude, self).release()
        self.anchor_offset = self.offset
        self.anchor_thickness = self.thickness

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
    pass
