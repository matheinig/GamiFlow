import bpy
import bmesh
import math
import mathutils
from . import helpers
from . import geotags
from . import data
from . import enums
from . import settings
  
def backwardCompatibility(scene):
    # The 'scene' is an evaluated copy of the scene rather than the scene itself so we need to retrieve the original first
    realScene = bpy.data.scenes[scene.name]
    
    # Add at least one LOD
    if len(realScene.gflow.lod.lods) == 0:
        realScene.gflow.lod.lods.add()

    currentVersion = 2
    if scene.gflow.version == currentVersion: return
    
    print("[GamiFlow] Scene "+scene.name + " was saved in different version ("+str(scene.gflow.version)+")")

    if realScene.gflow.version == 0:
        # Add at least one UDIM
        if len(realScene.gflow.udims) == 0:
            realScene.gflow.udims.add()
            realScene.gflow.udims[0].name = "UDIM_0"
        # After version 1, we have a flag that says if the object is already known by gflow
        for o in realScene.objects:
            o.gflow.registered = True
    # In version two, the old DECAL projeciton type has been removed and replaced by PROJECTED + single-faced
    if realScene.gflow.version < 2:
        for o in realScene.objects:
            if o.gflow.objType == "DECAL":
                o.gflow.objType = "PROJECTED"
                o.gflow.singleSided = True
            
    realScene.gflow.version = currentVersion 

registeredScenesCount = 0
@bpy.app.handlers.persistent
def onLoad(dummy):
    # Backward compatibility check
    for s in bpy.data.scenes: backwardCompatibility(s)

@bpy.app.handlers.persistent  
def checkForNewObjectsAndScenes(scene, depsgraph):
    # If the scene version is 0, it's a newly-created scene and we need to fix some things first
    if scene.gflow.version == 0:
        backwardCompatibility(scene)   
    # Check the currently selected object and register it if needed
    currentObj = bpy.context.view_layer.objects.active
    if currentObj:
        if not currentObj.gflow.registered:
            onNewObject(currentObj, scene)      
    return

def onNewObject(o, scene):
    o.gflow.registered = True
    o.gflow.textureSetEnum = scene.gflow.udims[scene.gflow.ui_selectedUdim].name
    return

class GeneratorData:
    def __init__(self):
        self.generated = []
        self.generatedToOriginal = {} 
        self.originalToGenerated = {}
        self.parented = []
        self.roots = []
    def register(self, generatedObj, sourceObj):
        self.generated.append(generatedObj)
        if sourceObj:
            self.generatedToOriginal[generatedObj] = sourceObj
            if sourceObj not in self.originalToGenerated.keys(): self.originalToGenerated[sourceObj] = []
            self.originalToGenerated[sourceObj].append(generatedObj)
            if sourceObj.parent: 
                self.parented.append(generatedObj)
            else: 
                self.roots.append(generatedObj)
    def add(self, other):
        self.generated += other.generated
        self.parented += other.parented
        self.roots += other.roots
        self.generatedToOriginal.update(other.generatedToOriginal)
        self.originalToGenerated.update(other.originalToGenerated)
    

    def findSource(self, generatedObj):
        try:
            return self.generatedToOriginal[generatedObj]
        except:
            pass
        return None
    def findGenerated(self, sourceObj):
        if sourceObj is None: return None
        try:
            return self.originalToGenerated[sourceObj]
        except:
            print("Source object "+sourceObj.name+ " was never used to generated anything")
            pass
        return None
    def reparent(self, generatedObj):
        source = self.findSource(generatedObj)
        possibleNewParents = self.findGenerated(source.parent)
        newParent = findBestMatch(possibleNewParents, source.parent)
        if newParent: helpers.setParent(generatedObj, newParent)    
        
# A source object can have multiple generated objects, 
# so when checking for what a generated object's parent should be based on what the original parent was, we potentially have multiple possibilities. We choose by looking at a transform that matches.
def findBestMatch(generatedObjects, source):
    if generatedObjects is None or len(generatedObjects) == 0: return None
    bestCandidate = generatedObjects[0]
    for c in generatedObjects[1:]:
        if c.matrix_world == source.matrix_world: return c
    return bestCandidate

def updateModifierDependencies(generatorData, obj):
    for m in obj.modifiers:
        if m.type == "ARRAY":
            # Find the local version of the array object if possible
            if m.offset_object:
                generated = generatorData.findGenerated(m.offset_object)
                if generated and len(generated)>0: m.offset_object = generated[0]
        elif m.type == "DATA_TRANSFER":
            if m.object:
                generated = generatorData.findGenerated(m.object)
                if generated and len(generated)>0: m.object = generated[0]
        elif m.type == "MIRROR":
            if m.mirror_object:
                generated = generatorData.findGenerated(m.mirror_object)
                if generated and len(generated)>0: m.mirror_object = generated[0] 
        elif m.type == "ARMATURE":
            if m.object:
                generated = generatorData.findGenerated(m.object)
                if generated and len(generated)>0: m.object = generated[0]             
                
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
    if layer: setLayerCollectionVisibility(layer, layer.exclude, recursive=True)
    
def deleteObject(o):
    helpers.deleteObject(o)
    
def _clearCollection(coll):
    for o in list(coll.objects):
        deleteObject(o)
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

def getNewName(sourceObj, prefix, suffix, workingSuffix):
    baseName = sourceObj.name
    if len(workingSuffix)>0: 
        oldLength = len(baseName)
        baseName = baseName.replace(workingSuffix, "")
        if len(baseName) != oldLength:
            suffix = ""
    return prefix + baseName + suffix
def duplicateObject(sourceObj, collection, prefix="", suffix="", workingSuffix="", link=False):
    new_obj = helpers.copyObject(sourceObj, collection, link=link)
    new_obj.name = getNewName(sourceObj, prefix, suffix, workingSuffix)
    new_obj.gflow.generated = True
    return new_obj
    
def setObjectAction(obj, action, slotName):
    if not action: return
    if not obj.animation_data: return
    try:
        obj.animation_data.action = action
        if bpy.app.version >= (4,4,0) and slotName != '': 
            obj.animation_data.action_slot = obj.animation_data.action.slots[slotName]
    except Exception as e:
        print("GamiFlow: Object action slot error in object "+obj.name+":\n"+repr(e))
    
def setShapekeyAction(obj, action, slotName):
    if not action: return
    if obj.type != 'MESH' or not obj.data.shape_keys: return
    if not obj.data.shape_keys.animation_data: return
    try:
        obj.data.shape_keys.animation_data.action = action
        if bpy.app.version >= (4,4,0) and slotName != '': 
            obj.data.shape_keys.animation_data.action_slot = obj.data.shape_keys.animation_data.action.slots[slotName]
    except Exception as e:
        print("GamiFlow: Shapekey action slot error in object "+obj.name+":\n"+repr(e))
    
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
    bpy.ops.object.shade_smooth(keep_sharp_edges=keep_sharp_edges)
    if getFirstModifierOfType(obj, 'WEIGHTED_NORMAL') is None: addWeightedNormals(context, obj)


def addWeightedNormals(context, obj):
    if obj.type != 'MESH': return
    w = obj.modifiers.new(type="WEIGHTED_NORMAL", name="Weighted Normal (GFlow)")
    w.keep_sharp = True
    w.use_face_influence = True
    return w
    
def triangulate(context, obj):
    if obj.type != 'MESH': return
    tri = obj.modifiers.new(type="TRIANGULATE", name="Triangulate (GFlow)")
    # keep custom normals was removed in 4.2 but added again in 4.3
    if bpy.app.version != (4, 2, 0):
        tri.keep_custom_normals = True
    return tri

def removeLowModifiers(context, obj):
    for m in list(obj.modifiers):
        if not m.show_render:  obj.modifiers.remove(m)
def removePainterModifiers(context, obj):
    for m in list(obj.modifiers):
        pass
def applyPainterModifiers(context, obj):
    modifiers = [m for m in obj.modifiers if m.type == 'ARMATURE']
    helpers.applyModifiers(context, obj, modifiers)


def getTextureSetName(setNumber, mergeUdims=False):
    if mergeUdims: return bpy.context.scene.gflow.udims[0].name
    udim = bpy.context.scene.gflow.udims[setNumber]
    return udim.name
def getTextureSetMaterial(setNumber, mergeUdims=False):
    if mergeUdims: setNumber=0
    name = getTextureSetName(setNumber)
    try:
        m = bpy.data.materials[name]
        return m
    except:
        m = bpy.data.materials.new(name)
        m.diffuse_color = (1.0,1.0,1.0,1.0)
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
        if not layer: return 0
        relevantEdges = []
        for e in bm.edges:
            if e[layer] == geotags.GEO_EDGE_LEVEL_DEFAULT: continue
            relevant = False
            if (not keepPainter) and e[layer] == geotags.GEO_EDGE_LEVEL_PAINTER: relevant = True
            if e[layer] <= geotags.GEO_EDGE_LEVEL_LOD0+level: relevant = True
            if relevant: relevantEdges.append(e)
        if len(relevantEdges)>0: 
            bmesh.ops.dissolve_edges(bm, edges=relevantEdges, use_verts=True, use_face_split=False)
        return len(relevantEdges)

def removeCageEdges(obj):
    with helpers.objectModeBmesh(obj) as bm:
        layer = geotags.getDetailEdgesLayer(bm, forceCreation=False)
        if not layer: return
        relevantEdges = []
        for e in bm.edges:
            if e[layer] == geotags.GEO_EDGE_LEVEL_CAGE: relevantEdges.append(e)        
        if len(relevantEdges)>0: 
            bmesh.ops.dissolve_edges(bm, edges=relevantEdges, use_verts=True, use_face_split=False)

def collapseEdges(context, obj, level=0):
    with helpers.objectModeBmesh(obj) as bm:
        layer = geotags.getCollapseEdgesLayer(bm, forceCreation=False)
        if not layer: return
        relevantEdges = []
        for e in bm.edges:
            if e[layer] == geotags.GEO_EDGE_COLLAPSE_DEFAULT: continue
            relevant = False
            if e[layer] <= geotags.GEO_EDGE_COLLAPSE_LOD0+level: relevant = True
            if relevant: relevantEdges.append(e)
        
        if len(relevantEdges)>0: 
            bmesh.ops.collapse(bm, edges=relevantEdges, uvs=True)

def deleteDetailFaces(context, obj, level=0):
    with helpers.objectModeBmesh(obj) as bm:
        faceDetailLayer = geotags.getDetailFacesLayer(bm, forceCreation=False)
        if not faceDetailLayer: return
        faces = [f for f in bm.faces 
            if f[faceDetailLayer]!=geotags.GEO_FACE_LEVEL_DEFAULT 
            and f[faceDetailLayer]<=geotags.GEO_FACE_LEVEL_LOD0+level] 
        bmesh.ops.delete(bm, geom=faces, context="FACES")  

def generatePartialSymmetryIfNeeded(context, obj, offsetUvs=False):
    mirrorLayer = None
    with helpers.objectModeBmesh(obj) as bm:
        mirrorLayer = geotags.getMirrorLayer(bm)
    if not mirrorLayer: return

    helpers.setSelected(context, obj)
    bpy.ops.object.mode_set(mode='EDIT')
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:   
        mirrorLayer = geotags.getMirrorLayer(bm)
        # Select all the faces we want to mirror
        for face in bm.faces:
            face.select = (face[mirrorLayer] == geotags.GEO_FACE_MIRROR_X)
                   
    # Very important: we must temporarily disable automerging
    mergeBackup = context.scene.tool_settings.use_mesh_automerge
    context.scene.tool_settings.use_mesh_automerge = False
        
    # Duplicate and flip the selected faces
    orientation = obj.matrix_world.to_3x3() # TODO: check if there are cases where it's not true
    bpy.ops.mesh.duplicate_move(MESH_OT_duplicate={"mode":1}, TRANSFORM_OT_translate={"value":(0, 0, 0), "orient_type":'LOCAL', "orient_matrix":orientation, "orient_matrix_type":'LOCAL', "constraint_axis":(False, False, False), "mirror":False, "use_proportional_edit":False})
    bpy.ops.transform.mirror(orient_type='LOCAL', orient_matrix=orientation, orient_matrix_type='LOCAL', constraint_axis=(True, False, False), center_override=obj.location)
    bpy.ops.mesh.flip_normals()
    # Offset the UVs outside of the UV square (used in the lowp set to avoid ruining the Painter bakes)
    if offsetUvs:
        with helpers.editModeBmesh(obj) as bm:
            uvOffset = mathutils.Vector((1.0,1.0))
            uv_layer = bm.loops.layers.uv.active  
            for face in bm.faces:
                if not face.select: continue
                for loop in face.loops:
                    loop[uv_layer].uv = loop[uv_layer].uv + uvOffset 
    # Try hding the seam by selecting all the open edges and vertex welding them
    # ISSUE: This could potentially have undesirable effects if the user had non-welded vertices along not just the seam, but any open edge
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
    bpy.ops.mesh.remove_doubles()
    
    context.scene.tool_settings.use_mesh_automerge = mergeBackup
    
    bpy.ops.object.mode_set(mode='OBJECT')
    helpers.setDeselected(obj)


class GFLOW_OT_SetSmoothing(bpy.types.Operator):
    bl_idname      = "gflow.set_smoothing"
    bl_label       = "Set smoothing"
    bl_description = "Enable weighted normals"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects)>0
    def execute(self, context):
        for obj in context.selected_objects.copy():
            setObjectSmoothing(context, obj)
        return {"FINISHED"} 
class GFLOW_OT_AddBevel(bpy.types.Operator):
    bl_idname      = "gflow.add_bevel"
    bl_label       = "Quick Bevel"
    bl_description = "Add a bevel modifier to be used only on the high-poly set"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects)>0
    def execute(self, context):
        for obj in context.selected_objects:
            bevel = obj.modifiers.new(type="BEVEL", name="GFLOW Bevel")
            bevel.segments = 2
            bevel.width = 0.01
            bevel.angle_limit = math.radians(60)
            bevel.show_render = False
            wnIndex = getFirstModifierIndex(obj, "WEIGHTED_NORMAL")
            if wnIndex is not None:
                bpy.ops.object.modifier_move_to_index(modifier=bevel.name, index=wnIndex)
            
        return {"FINISHED"}        

class GFLOW_OT_SetUDIM(bpy.types.Operator):
    bl_idname      = "gflow.set_udim"
    bl_label       = "Set UDIM"
    bl_description = "Apply the current UDIM to the selection"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects)>0
    def execute(self, context):
        udimName = context.scene.gflow.udims[context.scene.gflow.ui_selectedUdim].name
        for o in context.selected_objects:
            o.gflow.textureSetEnum = udimName
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
class GFLOW_OT_SelectHighPoly(bpy.types.Operator):
    bl_idname      = "gflow.select_by_name"
    bl_label       = "Select"
    bl_description = "Select the high-poly"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="Name", default="")

    def execute(self, context):
        if len(self.name)==0: return
        #try:
        obj = context.scene.objects[self.name]
        helpers.setSelected(context, obj)
        #except:
        #    return {"CANCELLED"}
            
        return {"FINISHED"} 

def isObjectInHighList(active, potentialObj):
    for hp in active.gflow.highpolys:
        if hp.obj == potentialObj: return True
    return False
class GFLOW_OT_ProjectToActive(bpy.types.Operator):
    bl_idname      = "gflow.project_to_active"
    bl_label       = "Project to active"
    bl_description = "Project selected objects to the active object."
    bl_options = {"REGISTER", "UNDO"}

    projType: bpy.props.EnumProperty(name="Projection type", default="PROJECTED", items=enums.gPROJECTION_MODES)

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects)>1
    def execute(self, context):
        for o in context.selected_objects:
            if o == context.active_object: continue
            if isObjectInHighList(context.active_object, o): continue
            o.gflow.objType = self.projType
            context.active_object.gflow.highpolys.add()
            context.active_object.gflow.highpolys[-1].obj = o
            
 
        return {"FINISHED"}              

class GFLOW_OT_ClearGeneratedSets(bpy.types.Operator):
    bl_idname      = "gflow.clear_sets"
    bl_label       = "Clear Generated Sets"
    bl_description = "Deletes all aut-generated sets"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        if context.scene.gflow.painterLowCollection: clearCollection(context.scene.gflow.painterLowCollection)
        if context.scene.gflow.painterHighCollection: clearCollection(context.scene.gflow.painterHighCollection)
        if context.scene.gflow.painterCageCollection: clearCollection(context.scene.gflow.painterCageCollection)
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
            context.scene.gflow.exportCollection,
            context.scene.gflow.painterCageCollection]
        if isolate:
            for i in range(0, len(collections)):
                setCollectionVisibility(context, collections[i], i==self.collectionId)
        else:
            toggleCollectionVisibility(context, collections[self.collectionId])        
        
        return {'FINISHED'}
    def execute(self, context):
        return {"FINISHED"}        
        
        
class GFLOW_OT_AddLod(bpy.types.Operator):
    bl_idname      = "gflow.add_lod"
    bl_label       = "Add LOD"
    bl_description = "Add a new LOD"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if len(context.scene.gflow.lod.lods) >= 4:
            cls.poll_message_set("Can only have up to 4 lods")
            return False
        return True
    def execute(self, context):
        context.scene.gflow.lod.lods.add()
        context.scene.gflow.lod.current = len(context.scene.gflow.lod.lods)-1
        #context.scene.gflow.udims[context.scene.gflow.ui_selectedUdim].name = "UDIM_"+str(context.scene.gflow.ui_selectedUdim)
        return {"FINISHED"} 
class GFLOW_OT_RemoveLod(bpy.types.Operator):
    bl_idname      = "gflow.remove_lod"
    bl_label       = "Remove LOD"
    bl_description = "Remove the selected LOD"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if len(context.scene.gflow.lod.lods) <= 1:
            cls.poll_message_set("Need at least one LOD")
            return False
        return True
    def execute(self, context):
        context.scene.gflow.lod.lods.remove(context.scene.gflow.ui_selectedUdim)
        context.scene.gflow.lod.current = min( context.scene.gflow.lod.current, len(context.scene.gflow.lod.lods)-1)
        return {"FINISHED"}                 
        
        
classes = [GFLOW_OT_SetSmoothing, GFLOW_OT_AddBevel, GFLOW_OT_SetUDIM,
    GFLOW_OT_AddHighPoly, GFLOW_OT_RemoveHighPoly, GFLOW_OT_SelectHighPoly, GFLOW_OT_ProjectToActive,
    GFLOW_OT_MarkHardSeam, GFLOW_OT_MarkSoftSeam, GFLOW_OT_ClearSeam,
    GFLOW_OT_ClearGeneratedSets, GFLOW_OT_ToggleSetVisibility,
    GFLOW_OT_AddLod, GFLOW_OT_RemoveLod]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    bpy.app.handlers.depsgraph_update_post.append(checkForNewObjectsAndScenes)
    bpy.app.handlers.load_post.append(onLoad)

    return
def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(checkForNewObjectsAndScenes)
    bpy.app.handlers.load_post.remove(onLoad)
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    return