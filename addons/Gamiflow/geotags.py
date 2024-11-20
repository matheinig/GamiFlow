import bpy
import bmesh
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
GEO_EDGE_LEVEL_PAINTER = 1  # edge removed for lod0 but is kept in painter
GEO_EDGE_LEVEL_LOD0 = 2 # here we start removing the tagged edges for lod0, at GEO_EDGE_LEVEL_LOD0+1 we remove them at lod1
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

def getMirrorLayer(bm, forceCreation=False):
    layer = None
    try:
        layer = bm.faces.layers.int[GEO_FACE_MIRROR_NAME]
    except:
        if forceCreation: layer = bm.faces.layers.int.new(GEO_FACE_MIRROR_NAME)
    return layer


def getGridifyLayer(bm, forceCreation=False):
    layer = None
    try:
        layer = bm.faces.layers.int[GEO_FACE_GRIDIFY_NAME]
    except:
        if forceCreation: layer = bm.faces.layers.int.new(GEO_FACE_GRIDIFY_NAME)
    return layer
def removeGridifyLayer(bm):
    bm.faces.layers.int.remove(bm.faces.layers.int[GEO_FACE_GRIDIFY_NAME])
    
def getUvOrientationLayer(bm, forceCreation=False):
    layer = bm.edges.layers.int.get(GEO_EDGE_UV_ROTATION_NAME)
    if forceCreation and not layer: layer = bm.edges.layers.int.new(GEO_EDGE_UV_ROTATION_NAME)
    return layer
def removeUvOrientationLayer(bm):
    bm.edges.layers.int.remove(bm.edges.layers.int.get(GEO_EDGE_UV_ROTATION_NAME))
    
def getUvScaleLayer(bm, forceCreation=False):
    layer = bm.faces.layers.float.get(GEO_FACE_UV_SCALE_NAME)
    if forceCreation and not layer: layer = bm.faces.layers.float.new(GEO_FACE_UV_SCALE_NAME)
    return layer     
def getUvScaleCode(scaleFactor):
    return scaleFactor-1.0
def getUvScaleFromCode(code):
    return code+1.0
    
def getDetailFacesLayer(bm, forceCreation=False):
    layer = bm.faces.layers.int.get(GEO_FACE_LEVEL_NAME)
    if forceCreation and not layer: layer = bm.faces.layers.int.new(GEO_FACE_LEVEL_NAME)
    return layer  
    
def getDetailEdgesLayer(bm, forceCreation=False):
    layer = bm.edges.layers.int.get(GEO_EDGE_LEVEL_NAME)
    if forceCreation and not layer: layer = bm.edges.layers.int.new(GEO_EDGE_LEVEL_NAME)
    return layer   
    
class GFLOW_OT_SetEdgeLevel(bpy.types.Operator):
    bl_idname      = "gflow.set_edge_level"
    bl_label       = "Set level"
    bl_description = "Set the detail level of the edges"
    bl_options = {"REGISTER", "UNDO"}

    level : bpy.props.IntProperty(name="Level", default=2, min=0, soft_max=4, description="Edge level", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.edit_object is not None

    def execute(self, context):
        obj = context.edit_object
       
        with helpers.editModeBmesh(obj) as bm:
            layer = getDetailEdgesLayer(bm, forceCreation=True)
            for edge in bm.edges:
                if edge.select: 
                    edge[layer] = self.level

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
    
    
class GFLOW_OT_SetFaceMirror(bpy.types.Operator):
    bl_idname      = "gflow.set_face_mirror"
    bl_label       = "Set mirror"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    level : bpy.props.IntProperty(name="Level", default=0, min=0, soft_max=4, description="Edge level")
     
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
    
def markSelectedFacesAsDetail(context, isDetail):
    obj = context.edit_object

    # Select the bounding edges and mark them as seams
    if isDetail:
        bpy.ops.mesh.region_to_loop()
        bpy.ops.mesh.mark_seam(clear=False)

    
    # Set the UV size to 0 and set the poly flag
    with helpers.editModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        uvScaleLayer = getUvScaleLayer(bm, forceCreation=True)
        faceDetailLayer = getDetailFacesLayer(bm, forceCreation=True)
        
        scaleCode = getUvScaleCode(0.0)
        detailCode = GEO_FACE_LEVEL_LOD0
        
        if not isDetail:
            scaleCode = getUvScaleCode(1.0)
            detailCode = GEO_FACE_LEVEL_DEFAULT
        
        for face in bm.faces:
            if face.select: 
                face[uvScaleLayer] = scaleCode
                face[faceDetailLayer] = detailCode
    
class GFLOW_OT_SetFaceLevel(bpy.types.Operator):
    bl_idname      = "gflow.set_face_level"
    bl_label       = "Mark as detail"
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
        markSelectedFacesAsDetail(context, self.detail)
    
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
    
    
classes = [GFLOW_OT_SetEdgeLevel, GFLOW_OT_SelectEdgeLevel, GFLOW_OT_SetFaceLevel, GFLOW_OT_SelectFaceLevel, GFLOW_OT_SetFaceMirror]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass