
from maya import cmds, mel
import maya.api.OpenMaya as api

import mampy
from mampy.utils import DraggerCtx, mvp
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
            bevel = cmds.polyBevel2

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


class edge_slice(DraggerCtx):
    """
    Edge Slice context.

    Give control over certain attributes of polySplitRing node from
    the viewport.

    `left+drag`: Slides the edge along edge ring.
    `ctrl+left+drag: Adds or removes divisions.
    `middle+drag: Adjusts edge flow or pushes edges out or in.

    """

    def __init__(self):
        self.name = 'mamtools_edgeslice_context'
        super(edge_slice, self).__init__(self.name)
        self.run()

    @property
    def multiplier(self):
        """
        Creates a multiplier that is depending on the initial edge selection
        lenght.
        """
        if self._multiplier is None:
            edge = mampy.selected().itercomps().next()
            verts = edge.mesh.getEdgeVertices(edge.index)
            a, b = [
                MeshVert.create(edge.dagpath).add(i).points[0]
                for i in verts
            ]
            self._multiplier = ((a - b).length()) * 0.001
        return self._multiplier

    def setup(self):
        """
        Creates the polySplitRing node.

        If one edge is selected split the whole ring, if more edges are
        selected split between selection.
        """
        # create/reset anchors
        self.weight = 0.5
        self.divisions = 1
        self.edge_flow = 0.0
        self._multiplier = None

        self.anchor_weight = self.weight
        self.anchor_divisions = self.divisions
        self.anchor_edge_flow = self.edge_flow

        # Create polySplitRing node.
        self.sel = mampy.selected()
        if len(self.sel) == 1:
            cmds.polySelectSp(ring=True)
        self.split_node = cmds.polySplitRing(
            divisions=self.divisions,
            weight=self.weight,
            insertWithEdgeFlow=1,
            adjustEdgeFlow=self.edge_flow,
        )[0]
        self.split_node = DependencyNode(self.split_node)

    def drag_left(self):
        """
        Slide edge.

        If divisions are one use left mous button to slide edge.
        """
        if self.split_node['divisions'] > 1:
            return

        change = (self.dragPoint[0] - self.anchorPoint[0])
        self.weight = self.anchor_weight + (change / self.multiplier)

        if self.weight > 1: self.weight = 1.0
        elif self.weight < 0: self.weight = 0.0

        self.split_node['weight'] = self.weight

    def drag_middle(self):
        """
        Change poly split ring divisions.

        If divisions is bigger than one change split type aswell.
        """
        change = int((self.dragPoint[0] - self.anchorPoint[0]) * 0.2)

        self.divisions = self.anchor_divisions + change
        if self.divisions < 1:
            self.divisions = 1

        if self.divisions > 1:
            self.split_node['splitType'] = 2
        else:
            self.split_node['splitType'] = 1

            self.weight = 0.5
            self.edge_flow = 0
            self.split_node['weight'] = self.weight
            self.split_node['adjustEdgeFlow'] = self.edge_flow
            self.split_node['profileCurveInputOffset'] = self.edge_flow
        self.split_node['divisions'] = self.divisions

    def drag_ctrl_left(self):
        """
        Change edge flow.
        """
        multiplier = get_distance_from_camera(self.sel) * 0.00001
        change = (self.dragPoint[0] - self.anchorPoint[0]) * multiplier

        self.edge_flow = self.anchor_edge_flow + change
        if self.split_node['divisions'] > 1:
            self.split_node['profileCurveInputOffset'] = self.edge_flow
        else:
            self.split_node['adjustEdgeFlow'] = self.edge_flow

    def release(self):
        """
        Save current anchor position for affected attributes.

        call super to close undoChunk.
        """
        super(edge_slice, self).release()

        # Anchors
        self.anchor_divisions = self.divisions
        self.anchor_weight = self.weight
        self.anchor_edge_flow = self.edge_flow


if __name__ == '__main__':
    from collections import OrderedDict, defaultdict

    class OrderedDefaultDict(OrderedDict, defaultdict):
        def __init__(self, default_factory=None, *args, **kwargs):
            #in python3 you can omit the args to super
            super(OrderedDefaultDict, self).__init__(*args, **kwargs)
            self.default_factory = default_factory

    # edge_slice()
    s = mampy.selected()
    segments = None
    negative = False
    scale = 1.0 / (segments + 1)

    splitdict = OrderedDefaultDict(list)
    for i in s.itercomps():
        scalar = scale
        for segment in xrange(segments):
            for idx in i.indices:
                splitdict[scalar].append(idx)
            scalar += scale
            # scalar = scale
            # for segment in xrange(segments):
            #     splitdict[idx].append((idx, scalar))
            #     scalar += scalar

    reversed_dict = OrderedDict(reversed(list(splitdict.items())))
    # reversed_dict = splitdict
    # print reversed_dict

    print reversed_dict
    for enum, item in enumerate(reversed_dict.iteritems()):
        value, indices = item
        print value
        if enum == 0:
            l = [(i, value) for i in indices]
        else:
            l = [(i, 1.0-(1.0/segments)) for i in indices]
            segments -= 1
        # value, index =
        cmds.polySplit(ip=l)

        print l
