import bpy
import bmesh
import math
from . import helpers
from . import geotags

def _findLayerCollRec(layerCol, targetCol):
    for c in layerCol.children:
        if c.collection == targetCol: return c
        r = _findLayerCollRec(c, targetCol)
        if r is not None: return r
    return None
def findLayerCollection(context, collection):
    if collection is None: return None
    rootLayerCol = context.view_layer.layer_collection
    layer = _findLayerCollRec(rootLayerCol, collection)
    return layer


def getSetName(context):
    name = context.scene.name
    return name

def setLayerCollectionVisibility(lco, visibility, recursive=True):
    lco.exclude = not visibility
    if recursive:
        for c in lco.children: setLayerCollectionVisibility(c, visibility, recursive)
def setCollectionVisibility(context, coll, visibility, recursive=True):
    layer = findLayerCollection(context, coll)
    if layer: setLayerCollectionVisibility(layer, visibility, recursive=True)
def getCollectionVisibility(context, coll):
    layer = findLayerCollection(context, coll)
    if layer: return not layer.exclude
    return False
def toggleCollectionVisibility(context, coll):
    layer = findLayerCollection(context, coll)
    if layer: setLayerCollectionVisibility(layer, layer.exclude  , recursive=True)
    
def _clearCollection(coll):
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
def deleteCollection(coll):
    for c in coll.children:
        deleteCollection(c)
    _clearCollection(coll)
    bpy.data.collections.remove(coll, do_unlink=True)
def clearCollection(coll):
    for c in coll.children:
        clearCollection(c)
    _clearCollection(coll)

def createCollection(context, name):
    parent = context.scene.collection
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c

def findRoots(collection):
    roots = []
    for o in collection.all_objects:
        if o.parent is None: roots.append(o)
    return roots

def getNewName(sourceObj, suffix):
    return sourceObj.name + suffix
def duplicateObject(sourceObj, suffix, collection):
    new_obj = sourceObj.copy()
    new_obj.name = getNewName(sourceObj, suffix)
    if sourceObj.data: new_obj.data = sourceObj.data.copy()
    collection.objects.link(new_obj)
    return new_obj
    
def getFirstModifierOfType(obj, modType):
    for m in obj.modifiers:
        if modType == m.type: return m
    return None
def getFirstModifierIndex(obj, modType):
    for index, m in enumerate(obj.modifiers):
        if modType == m.type: return index
    return None

def setObjectSmoothing(context, obj, keep_sharp_edges=True):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth(keep_sharp_edges)
    if getFirstModifierOfType(obj, 'WEIGHTED_NORMAL') is None: addWeightedNormals(context, obj)


def addWeightedNormals(context, obj):
    w = obj.modifiers.new(type="WEIGHTED_NORMAL", name="GFLOW Normal")
    w.keep_sharp = True
    w.use_face_influence = True
    
def triangulate(context, obj):
    tri = obj.modifiers.new(type="TRIANGULATE", name="GFLOW Triangulation")
    tri.keep_custom_normals = True

def removeLowModifiers(context, obj):
    for m in list(obj.modifiers):
        if not m.show_render:  obj.modifiers.remove(m)

def getTextureSetName(setNumber):
    udim = bpy.context.scene.gflow.udims[setNumber]
    return udim.name
def getTextureSetMaterial(setNumber):
    name = getTextureSetName(setNumber)
    try:
        m = bpy.data.materials[name]
        return m
    except:
        m = bpy.data.materials.new(name)
        return m
def setMaterial(obj, m):
    obj.data.materials.clear()
    obj.data.materials.append(m)

def removeSharpEdges(obj):
    for edge in obj.data.edges:
        edge.use_edge_sharp = False
        
def removeEdgesForLevel(context, obj, level, keepPainter=False):
    with helpers.objectModeBmesh(obj) as bm:
        layer = geotags.getDetailEdgesLayer(bm, forceCreation=False)
        if not layer: return
        relevantEdges = []
        for e in bm.edges:
            if e[layer] == geotags.GEO_EDGE_LEVEL_DEFAULT: continue
            relevant = False
            if (not keepPainter) and e[layer] == geotags.GEO_EDGE_LEVEL_PAINTER: relevant = True
            if e[layer] >= geotags.GEO_EDGE_LEVEL_LOD0+level: relevant = True
            if relevant: relevantEdges.append(e)
        
        if len(relevantEdges)>0: 
            bmesh.ops.dissolve_edges(bm, edges=relevantEdges, use_verts=True, use_face_split=False)

class GFLOW_OT_SetSmoothing(bpy.types.Operator):
    bl_idname      = "gflow.set_smoothing"
    bl_label       = "Set smoothing"
    bl_description = "Enable weighted normals"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        setObjectSmoothing(context, context.active_object)
        return {"FINISHED"} 
class GFLOW_OT_AddBevel(bpy.types.Operator):
    bl_idname      = "gflow.add_bevel"
    bl_label       = "Quick Bevel"
    bl_description = "Add a bevel modifier to be used only on the high-poly set"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.view_layer.objects.active
        bevel = obj.modifiers.new(type="BEVEL", name="GFLOW Bevel")
        bevel.segments = 2
        bevel.width = 0.01
        bevel.angle_limit = math.radians(60)
        bevel.show_render = False
        wnIndex = getFirstModifierIndex(obj, "WEIGHTED_NORMAL")
        if wnIndex is not None:
            bpy.ops.object.modifier_move_to_index(modifier=bevel.name, index=wnIndex)
        
        return {"FINISHED"}        

class GFLOW_OT_MarkHardSeam(bpy.types.Operator):
    bl_idname      = "gflow.add_hard_seam"
    bl_label       = "Mark Hard Seam"
    bl_description = "Mark the selected edges as hard seams"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.mesh.mark_seam(clear=False)
        bpy.ops.mesh.mark_sharp()
        return {"FINISHED"} 
class GFLOW_OT_MarkSoftSeam(bpy.types.Operator):
    bl_idname      = "gflow.add_soft_seam"
    bl_label       = "Mark Soft Seam"
    bl_description = "Mark the selected edges as soft seams"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.mesh.mark_seam(clear=False)
        bpy.ops.mesh.mark_sharp(clear=True)
        return {"FINISHED"}         
class GFLOW_OT_ClearSeam(bpy.types.Operator):
    bl_idname      = "gflow.clear_seam"
    bl_label       = "Clear Seam"
    bl_description = "Clear the seam and hardness"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.mark_sharp(clear=True)
        return {"FINISHED"} 

class GFLOW_OT_AddHighPoly(bpy.types.Operator):
    bl_idname      = "gflow.add_high"
    bl_label       = "Add High"
    bl_description = "Add a new highpoly mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.object
        obj.gflow.highpolys.add()
        obj.gflow.ui_selectedHighPoly = len(obj.gflow.highpolys)-1
        return {"FINISHED"} 
class GFLOW_OT_RemoveHighPoly(bpy.types.Operator):
    bl_idname      = "gflow.remove_high"
    bl_label       = "Remove High"
    bl_description = "Remove the selected highpoly item"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.object
        obj.gflow.highpolys.remove(obj.gflow.ui_selectedHighPoly)
        obj.gflow.ui_selectedHighPoly = min( obj.gflow.ui_selectedHighPoly, len(obj.gflow.highpolys)-1)
        return {"FINISHED"}         

class GFLOW_OT_ClearGeneratedSets(bpy.types.Operator):
    bl_idname      = "gflow.clear_sets"
    bl_label       = "Clear Generated Sets"
    bl_description = "Deletes all aut-generated sets"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        if context.scene.gflow.painterLowCollection: clearCollection(context.scene.gflow.painterLowCollection)
        if context.scene.gflow.painterHighCollection: clearCollection(context.scene.gflow.painterHighCollection)
        if context.scene.gflow.exportTarget != 'BLENDER_LIB': # The export set must not be deleted if we are exporting for the blender library (as this is the actual final output)
            if context.scene.gflow.exportCollection: clearCollection(context.scene.gflow.exportCollection)
        return {"FINISHED"}  
        
        
class GFLOW_OT_ToggleSetVisibility(bpy.types.Operator):
    bl_idname      = "gflow.toggle_set_visibility"
    bl_label       = "Set the desired set to be visible"
    bl_description = "Click to focus on set. Ctrl-click to toggle visibility."
    bl_options = {"REGISTER", "UNDO"}

    collectionId : bpy.props.IntProperty(default=0)

    def invoke(self, context, event): 
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def modal(self, context, event):
    
        isolate = True
        if event.ctrl:
            isolate = False
        
        collections = [
            context.scene.gflow.workingCollection,
            context.scene.gflow.painterLowCollection, 
            context.scene.gflow.painterHighCollection,
            context.scene.gflow.exportCollection]
        if isolate:
            for i in range(0, len(collections)):
                setCollectionVisibility(context, collections[i], i==self.collectionId)
        else:
            toggleCollectionVisibility(context, collections[self.collectionId])        
        
        return {'FINISHED'}
    def execute(self, context):
        return {"FINISHED"}        
        
        
               
        
        
classes = [GFLOW_OT_SetSmoothing, GFLOW_OT_AddBevel,
    GFLOW_OT_AddHighPoly, GFLOW_OT_RemoveHighPoly,
    GFLOW_OT_MarkHardSeam, GFLOW_OT_MarkSoftSeam, GFLOW_OT_ClearSeam,
    GFLOW_OT_ClearGeneratedSets, GFLOW_OT_ToggleSetVisibility]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass