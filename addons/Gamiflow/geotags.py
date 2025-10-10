import bpy
import bmesh
import mathutils
from . import helpers

# Per-face gridification. 0: no straightening, 1=straighten island, -1=subset of faces that cannot be straighten
GEO_FACE_GRIDIFY_NAME = "gflow_face_grifidy" 
GEO_FACE_GRIDIFY_INCLUDE = 1
GEO_FACE_GRIDIFY_EXCLUDE = 0
#TODO/IDEA: master face from which the gridification will start instead of 'whatever quad we find first' 

# Float encoding the uv scale of the face. 0=100%, -1=0%, (-1 offset because we can't have a default value of 1)
GEO_FACE_UV_SCALE_NAME = "gflow_face_uv_scale" 

# UV island orientation. 0: no rotation, 1=vertical, 2=horizontal
GEO_EDGE_UV_ROTATION_NAME = "gflow_edge_uv_orientation"
GEO_EDGE_UV_ROTATION_NEUTRAL = 0
GEO_EDGE_UV_ROTATION_VERTICAL = 1
GEO_EDGE_UV_ROTATION_HORIZONTAL = 2

# Flag for edges that should be dissolved. 0=keep, 1=removed for baking and lod0, 2=removed in lod1, 3=removed in lod2, etc
GEO_EDGE_LEVEL_NAME = "gflow_edge_lowpoly" 
GEO_EDGE_LEVEL_DEFAULT = 0
GEO_EDGE_LEVEL_CAGE = -1
GEO_EDGE_LEVEL_PAINTER = 1  # edge removed for lod0 but is kept in painter
GEO_EDGE_LEVEL_LOD0 = 2 # here we start removing the tagged edges for lod0, at GEO_EDGE_LEVEL_LOD0+1 we remove them at lod1
# Flag for edges that should be collapsed: 0: keep
GEO_EDGE_COLLAPSE_NAME = "gflow_edge_collapse" 
GEO_EDGE_COLLAPSE_DEFAULT = 0
GEO_EDGE_COLLAPSE_LOD0 = 2

# Flag for faces that should be deleted. These faces will be not show up in the UVs and will instead have their own 0-sized UV island in the working set.
GEO_FACE_LEVEL_NAME = "gflow_face_lowpoly" 
GEO_FACE_LEVEL_DEFAULT = 0
GEO_FACE_LEVEL_LOD0 = 2

# Flag for faces that need to be mirrored on the X axis
GEO_FACE_MIRROR_NAME = "gflow_face_mirror"
GEO_FACE_MIRROR_NONE = 0
GEO_FACE_MIRROR_X = 1
GEO_FACE_MIRROR_Y = 2
GEO_FACE_MIRROR_Z = 4

# Cage hardness and displacement
GEO_LOOP_CAGE_OFFSET_NAME = "gflow_cage_tightness"


def removeObjectLayers(o):
    with helpers.objectModeBmesh(o) as bm:
        removeMirrorLayer(bm)
        removeGridifyLayer(bm)  
        removeUvScaleLayer(bm)
        removeDetailFaceLayer(bm)
        removeDetailEdgeLayer(bm)
def removeObjectCageLayers(o):
    removeCageDisplacementMap(o)

# Cage
def getCageDisplacementMap(obj, forceCreation=False):
    vmap = None
    try:
        vmap = obj.vertex_groups[GEO_LOOP_CAGE_OFFSET_NAME]
    except:
        if forceCreation: 
            vmap = obj.vertex_groups.new( name = GEO_LOOP_CAGE_OFFSET_NAME )
    return vmap
def removeCageDisplacementMap(obj):
    try:
         obj.vertex_groups.remove(obj.vertex_groups[GEO_LOOP_CAGE_OFFSET_NAME])
    except:
        pass 

# Mirrors
def getMirrorLayer(bm, forceCreation=False):
    layer = None
    try:
        layer = bm.faces.layers.int[GEO_FACE_MIRROR_NAME]
    except:
        if forceCreation: layer = bm.faces.layers.int.new(GEO_FACE_MIRROR_NAME)
    return layer
def removeMirrorLayer(bm):
    try:
        bm.faces.layers.int.remove(bm.faces.layers.int[GEO_FACE_MIRROR_NAME])
    except:
        pass

# UV grid
def getGridifyLayer(bm, forceCreation=False):
    layer = None
    try:
        layer = bm.faces.layers.int[GEO_FACE_GRIDIFY_NAME]
    except:
        if forceCreation: layer = bm.faces.layers.int.new(GEO_FACE_GRIDIFY_NAME)
    return layer
def removeGridifyLayer(bm):
    try:
        bm.faces.layers.int.remove(bm.faces.layers.int[GEO_FACE_GRIDIFY_NAME])
    except:
        pass
        
# UV orientation
def getUvOrientationLayer(bm, forceCreation=False):
    layer = bm.edges.layers.int.get(GEO_EDGE_UV_ROTATION_NAME)
    if forceCreation and not layer: layer = bm.edges.layers.int.new(GEO_EDGE_UV_ROTATION_NAME)
    return layer
def removeUvOrientationLayer(bm):
    bm.edges.layers.int.remove(bm.edges.layers.int.get(GEO_EDGE_UV_ROTATION_NAME))

# UV scale
def getUvScaleLayer(bm, forceCreation=False):
    layer = bm.faces.layers.float.get(GEO_FACE_UV_SCALE_NAME)
    if forceCreation and not layer: layer = bm.faces.layers.float.new(GEO_FACE_UV_SCALE_NAME)
    return layer     
def getUvScaleCode(scaleFactor):
    return scaleFactor-1.0
def getUvScaleFromCode(code):
    return code+1.0
def removeUvScaleLayer(bm):
    try:
        bm.faces.layers.int.remove(bm.faces.layers.int[GEO_FACE_UV_SCALE_NAME])
    except:
        pass   
    
# Face detail
def getDetailFacesLayer(bm, forceCreation=False):
    layer = bm.faces.layers.int.get(GEO_FACE_LEVEL_NAME)
    if forceCreation and not layer: layer = bm.faces.layers.int.new(GEO_FACE_LEVEL_NAME)
    return layer  
def removeDetailFaceLayer(bm):
    try:
        bm.faces.layers.int.remove(bm.faces.layers.int[GEO_FACE_LEVEL_NAME])
    except:
        pass   

# Edge detail  
def getDetailEdgesLayer(bm, forceCreation=False):
    layer = bm.edges.layers.int.get(GEO_EDGE_LEVEL_NAME)
    if forceCreation and not layer: layer = bm.edges.layers.int.new(GEO_EDGE_LEVEL_NAME)
    return layer   
def removeDetailEdgeLayer(bm):
    try:
        bm.edges.layers.int.remove(bm.edges.layers.int[GEO_EDGE_LEVEL_NAME])
    except:
        pass   
def setObjectSelectedEdgeLevel(obj, level=GEO_EDGE_LEVEL_LOD0):
    with helpers.editModeBmesh(obj) as bm:
        layer = getDetailEdgesLayer(bm, forceCreation=True)
        for edge in bm.edges:
            if edge.select: 
                edge[layer] = level
        
class GFLOW_OT_SetEdgeLevel(bpy.types.Operator):
    bl_idname      = "gflow.set_edge_level"
    bl_label       = "Set level"
    bl_description = "Set the detail level of the edges"
    bl_options = {"REGISTER", "UNDO"}

    level : bpy.props.IntProperty(name="Level", default=GEO_EDGE_LEVEL_LOD0, min=-1, soft_max=4, description="Edge level", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        setObjectSelectedEdgeLevel(context.edit_object, self.level)
        return {"FINISHED"}
        
class GFLOW_OT_SetCheckeredEdgeLevel(bpy.types.Operator):
    bl_idname      = "gflow.set_checkered_ring_edge_level"
    bl_label       = "Set checkered level"
    bl_description = "Set the edge level for every other edge in the ring"
    bl_options = {"REGISTER", "UNDO"}
    
    level : bpy.props.IntProperty(name="Level", default=GEO_EDGE_LEVEL_LOD0, min=-1, soft_max=4, description="Edge level", options={'HIDDEN'})

    
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None
    def execute(self, context):
        # Select the entire ring
        bpy.ops.mesh.loop_multi_select(ring=True)
        # Remove one in two edges
        bpy.ops.mesh.select_nth(offset=1) # TODO: add support for num selected/unselected (must figure out offset first)
        # Extend the selection to the entire loop
        bpy.ops.mesh.loop_multi_select(ring=False)
        # Mark as high level
        setObjectSelectedEdgeLevel(context.edit_object, self.level)
        return {"FINISHED"}
class GFLOW_OT_SelectEdgeLevel(bpy.types.Operator):
    bl_idname      = "gflow.select_edge_level"
    bl_label       = "Select level"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    level : bpy.props.IntProperty(name="Level", default=0, min=0, soft_max=4, description="Edge level")
        
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        #bpy.ops.mesh.select_all(action='DESELECT')
        for obj in context.selected_objects:
            if obj.type != 'MESH': continue
            with helpers.editModeBmesh(obj) as bm:
                layer = getDetailEdgesLayer(bm, forceCreation=False)
                if not layer: continue
                for e in bm.edges:
                    e.select = False
                    if e[layer] == GEO_EDGE_LEVEL_DEFAULT: continue
                    #relevant = (not keepPainter) and e[layer] == GEO_EDGE_LEVEL_PAINTER
                    relevant = (e[layer] >= GEO_EDGE_LEVEL_LOD0+self.level)
                    if relevant: e.select = True
        return {"FINISHED"}
    
# Edge collapse    
def getCollapseEdgesLayer(bm, forceCreation=False):
    layer = bm.edges.layers.int.get(GEO_EDGE_COLLAPSE_NAME)
    if forceCreation and not layer: layer = bm.edges.layers.int.new(GEO_EDGE_COLLAPSE_NAME)
    return layer   
def removeCollapseEdgesLayer(bm):
    try:
        bm.edges.layers.int.remove(bm.edges.layers.int[GEO_EDGE_COLLAPSE_NAME])
    except:
        pass   
def setObjectSelectedEdgeCollapse(obj, level=GEO_EDGE_COLLAPSE_LOD0):
    with helpers.editModeBmesh(obj) as bm:
        layer = getCollapseEdgesLayer(bm, forceCreation=True)
        for edge in bm.edges:
            if edge.select: 
                edge[layer] = level
class GFLOW_OT_SetEdgeCollapseLevel(bpy.types.Operator):
    bl_idname      = "gflow.set_edge_collapse_level"
    bl_label       = "Collapse"
    bl_description = "Set the collapse level of the edges"
    bl_options = {"REGISTER", "UNDO"}

    level : bpy.props.IntProperty(name="Level", default=GEO_EDGE_COLLAPSE_LOD0, min=-1, soft_max=4, description="Edge level", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        setObjectSelectedEdgeCollapse(context.edit_object, self.level)
        return {"FINISHED"}
        
# Based on the following answer (itself based on the internal blender C code)
# https://blender.stackexchange.com/questions/79988/bmesh-get-edge-loop/79995#79995        
def BM_edge_other_loop(edge, loop):
    if loop.edge == edge:
        l_other = loop
    else:
        l_other = loop.link_loop_prev
    l_other = l_other.link_loop_radial_next
    if l_other.vert == loop.vert:
        l_other = l_other.link_loop_prev
    elif l_other.link_loop_next.vert == loop.vert:
        l_other = l_other.link_loop_next
    else:
        print( "GamiFlow: Edge loop walk failure A")
        return None
    return l_other
    
def BM_vert_step_fan_loop(loop, e_step, quadOnly=True):
    e_prev = e_step

    if quadOnly:
        if len(loop.vert.link_edges) != 4: return None, True

    if loop.edge == e_prev:
        e_next = loop.link_loop_prev.edge
    elif loop.link_loop_prev.edge == e_prev:
        e_next = loop.edge
    else:
        print( "GamiFlow: Edge loop walk failure B")
        return None, False

    if e_next.is_manifold:
        return BM_edge_other_loop(e_next, loop), False
    # if we reached this place, we probably reached the end of the geometry
    return None, True

def walkEdgeLoop(bm, startEdge, reverse=False):
    edges = []

    loop = startEdge.link_loops[0]
    if reverse: loop = loop.link_loop_next
    edge = startEdge
    pcv = loop.vert  # Previous Current Vert (loop's vert)
    pov = loop.edge.other_vert(loop.vert)  # Previous Other Vert 
    startLoop = loop            
       
    iteration = 0
    blocked = False
    while True:
        new_loop, blocked = BM_vert_step_fan_loop(loop, edge)
        if not new_loop: break
        edge = new_loop.edge
        if edge == startEdge: break
        #if iteration > 1000: break

        edges.append(new_loop.edge)
        iteration = iteration+1
        
        cur_vert = new_loop.vert
        oth_vert = new_loop.edge.other_vert(new_loop.vert)
        rad_vert = new_loop.link_loop_radial_next.vert
        if cur_vert == rad_vert and oth_vert != pcv:
            loop = new_loop.link_loop_next
            pcv = oth_vert
            pov = cur_vert
        elif oth_vert == pcv:
            loop = new_loop
            pcv = cur_vert
            pov = oth_vert
        elif cur_vert ==  pcv:
            loop = new_loop.link_loop_radial_next
            pcv = oth_vert
            pov = cur_vert  
    return edges, blocked
def getEdgeLoop(bm, startEdge, reverse=False):
    edges = [startEdge]
    forwardEdges, blocked = walkEdgeLoop(bm, startEdge, reverse=reverse)
    edges += forwardEdges
    if blocked:
        backwardEdges, blocked = walkEdgeLoop(bm, startEdge, reverse=not reverse)
        # need to merge the two lists in the right order
        backInds = [backwardEdges[0].verts[0].index, backwardEdges[0].verts[1].index]
        if edges[0].verts[0].index in backInds or edges[0].verts[1].index in backInds:
            edges = list(reversed(backwardEdges)) + edges
        else:
            edges += reversed(backwardEdges)
    return edges
class GFLOW_OT_SetCheckeredEdgeCollapse(bpy.types.Operator):
    bl_idname      = "gflow.set_checkered_edge_collapse"
    bl_label       = "Mark checkered collapse"
    bl_description = "Collapse every other edge on the loop"
    bl_options = {"REGISTER", "UNDO"}
    
    selected : bpy.props.IntProperty(name="Selected", default=1, min=0, soft_max=4, description="How many edges in a row will be selected")    
    reverse : bpy.props.BoolProperty(name="Reverse", default=False)
    level: bpy.props.IntProperty(name="Level", min=-1)
    
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None
    def execute(self, context):
        with helpers.editModeBmesh(context.edit_object) as bm:
            # Get a full edge loop
            startEdge = bm.select_history.active
            if not startEdge: return {"CANCELLED"}
            
            layer = getCollapseEdgesLayer(bm, forceCreation=True) # Layer must be created first to avoid it invalidating the edges list
            startEdge = bm.select_history.active
            edges = getEdgeLoop(bm, startEdge, reverse=self.reverse)
            # We need to make sure that the original edge is at index "0" even though it's not
            startIndex = 0
            for index, edge in enumerate(edges):
                if edge == startEdge:
                    startIndex=index
                    break
            
            # Mark the edges
            for index, edge in enumerate(edges):
                id = index-startIndex
                wrapped = (id) % (self.selected + 1)
                if wrapped < self.selected:
                    edge[layer] = self.level
                else:
                    edge[layer] = GEO_EDGE_COLLAPSE_DEFAULT
        
        return {"FINISHED"}
class GFLOW_OT_CollapseEdgeRing(bpy.types.Operator):
    bl_idname      = "gflow.collapse_edge_ring"
    bl_label       = "Collapse Edge Ring"
    bl_description = "Collapse an edge ring into a single loop"
    bl_options = {"REGISTER", "UNDO"}
    
    level : bpy.props.IntProperty(name="Level", default=GEO_EDGE_LEVEL_LOD0, min=-1, soft_max=4, description="Edge level", options={'HIDDEN'})
    
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None
    def execute(self, context):
        bpy.ops.mesh.loop_multi_select(ring=True)
        setObjectSelectedEdgeCollapse(context.edit_object, self.level)
        return {"FINISHED"}

class GFLOW_OT_UnmarkEdge(bpy.types.Operator):
    bl_idname      = "gflow.unmark_edge"
    bl_label       = "Unmark edge"
    bl_description = "Edge will no longer be dissolved or collapsed"
    bl_options = {"REGISTER", "UNDO"}
  
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        with helpers.editModeBmesh(context.edit_object) as bm:
            dissolveLayer = getDetailEdgesLayer(bm, forceCreation=False)
            collapseLayer = getCollapseEdgesLayer(bm, forceCreation=False)
            if dissolveLayer or collapseLayer: 
                for edge in bm.edges:
                    if edge.select:
                        if dissolveLayer: edge[dissolveLayer] = GEO_EDGE_LEVEL_DEFAULT
                        if collapseLayer: edge[collapseLayer] = GEO_EDGE_COLLAPSE_DEFAULT

        return {"FINISHED"}
    
class GFLOW_OT_SetFaceMirror(bpy.types.Operator):
    bl_idname      = "gflow.set_face_mirror"
    bl_label       = "Set mirror"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    mirror: bpy.props.EnumProperty(name="Mirror mode", default='X', items=[
        ("NONE", "None", "", GEO_FACE_MIRROR_NONE),
        ("X", "X", "", GEO_FACE_MIRROR_X),
        ])
    
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[2]: 
            cls.poll_message_set("Must be in face mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        obj = context.edit_object
        mirrorCode = {"NONE":GEO_FACE_MIRROR_NONE, "X":GEO_FACE_MIRROR_X}[self.mirror]
        with helpers.editModeBmesh(obj) as bm:
            mirrorLayer = getMirrorLayer(bm, forceCreation=True)
            for face in bm.faces:
                if face.select: face[mirrorLayer] = mirrorCode
        return {"FINISHED"}        
    
def markSelectedFacesAsDetail(context, deleteFromLevel):
    obj = context.edit_object

    # Set the UV size to 0 and set the poly flag
    with helpers.editModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        uvScaleLayer = getUvScaleLayer(bm, forceCreation=True)
        faceDetailLayer = getDetailFacesLayer(bm, forceCreation=True)
        
        rescaleUVs = False
        scaleCode = getUvScaleCode(0.0)
        detailCode = GEO_FACE_LEVEL_LOD0+deleteFromLevel
        if deleteFromLevel == 0: rescaleUVs=True
        
        # Unmark and leave visible at all levels
        if deleteFromLevel==-1:
            rescaleUVs = True
            scaleCode = getUvScaleCode(1.0)
            detailCode = GEO_FACE_LEVEL_DEFAULT
        for face in bm.faces:
            if face.select: 
                if rescaleUVs: face[uvScaleLayer] = scaleCode
                face[faceDetailLayer] = detailCode
                
    # Select the bounding edges and mark them as seams
    if deleteFromLevel!=-1 and rescaleUVs:
        bpy.ops.mesh.region_to_loop()
        bpy.ops.mesh.mark_seam(clear=False)
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
                
    
class GFLOW_OT_SetFaceLevel(bpy.types.Operator):
    bl_idname      = "gflow.set_face_level"
    bl_label       = "Mark as detail"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    deleteFromLevel : bpy.props.IntProperty(name="Detail", default=-10)
        
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[2]: 
            cls.poll_message_set("Must be in face mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        lod = self.deleteFromLevel
        if lod == -10:
            lod = context.scene.gflow.lod.current
        markSelectedFacesAsDetail(context, lod)
    
        return {"FINISHED"}    

class GFLOW_OT_SelectFaceLevel(bpy.types.Operator):
    bl_idname      = "gflow.select_face_level"
    bl_label       = "Select level"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    detail : bpy.props.BoolProperty(name="Detail", default=True)
        
    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[2]: 
            cls.poll_message_set("Must be in face mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        #bpy.ops.mesh.select_all(action='DESELECT')
        for obj in context.selected_objects:
            if obj.type != 'MESH': continue
            with helpers.editModeBmesh(obj) as bm:
                faceDetailLayer = getDetailFacesLayer(bm, forceCreation=False)
                if not faceDetailLayer: continue
                for f in bm.faces:
                    f.select = False
                    if self.detail: 
                        f.select = f[faceDetailLayer] != GEO_FACE_LEVEL_DEFAULT
                    else:
                        f.select = f[faceDetailLayer] == GEO_FACE_LEVEL_DEFAULT

        return {"FINISHED"}    
    
    
classes = [
    GFLOW_OT_SetEdgeLevel, GFLOW_OT_SetCheckeredEdgeLevel, GFLOW_OT_SelectEdgeLevel, 
    GFLOW_OT_SetEdgeCollapseLevel, GFLOW_OT_SetCheckeredEdgeCollapse, GFLOW_OT_CollapseEdgeRing,
    GFLOW_OT_UnmarkEdge,
    GFLOW_OT_SetFaceLevel, GFLOW_OT_SelectFaceLevel, GFLOW_OT_SetFaceMirror]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass