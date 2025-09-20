import bpy
from . import sets
from . import helpers
from . import settings
from . import uv
from . import geotags
from . import sets_cage
import mathutils
import random

#BEGINTRIM -------------------------------------------------- 
try:
    import DECALmachine
except ImportError:
    pass
#ENDTRIM ----------------------------------------------------- 

# Find or create the Export Set
def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.exportCollection
    name = sets.getSetName(context) + "_export"
    if not c and createIfNeeded:
        # Create a brand new set
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_04"
        context.scene.gflow.exportCollection = c
    if c: c.name = name
    return c

# Handle modifiers for a clean export
def processModifiers(context, generatorData, obj):
    helpers.setSelected(context, obj)
    
    sets.updateModifierDependencies(generatorData, obj)
    sets_cage.removeCageModifier(context, obj)
    
    # Deal with special cases for special modifiers
    # NOTE: Currently no special cases for the Export Set :)
    
    # Apply all modifiers except armatures which are needed
    modifiers = [m for m in obj.modifiers if m.type != 'ARMATURE']
    helpers.applyModifiers(context, obj, modifiers)

    
    helpers.setDeselected(obj) 


# Hierarchy optimiser
def areMergeCompatible(p, c, mergeUdims=False):
    if not c.gflow.mergeWithParent: return False
    
    needToCheckUdims = (not mergeUdims)
    if (p.type=='EMPTY' or c.type=='EMPTY'): needToCheckUdims = False
    if (p.type == 'ARMATURE'): return False
    if needToCheckUdims and (p.gflow.textureSet != c.gflow.textureSet): return False
    
    #if c.gflow.objType == 'NON_BAKED' and p.gflow.objType != 'NON_BAKED': return False
    # TODO: there are more conditions that should probably be met such as smoothing method
    return True
def mergeHierarchy(obj, mergeList, todoList, mergeUdims, depth=0):
    for c in obj.children:
        if areMergeCompatible(obj, c, mergeUdims):
            mergeList.append(c)
            mergeList, todoList = mergeHierarchy(c, mergeList, todoList, mergeUdims, depth=depth+1)
        else:
            todoList.append(c) 
    return mergeList, todoList
def findFirstNonCollapsedParent(obj, mergeUdims):
    if obj.parent is None: return obj
    parent = obj.parent
    if areMergeCompatible(parent, obj): return findFirstNonCollapsedParent(parent, mergeUdims)
    return obj

class InstancedCollection:
    def __init__(self):
        self.generated = None
        self.spawnPoint = None
    
def printHierarchy(obj, indent):
    print(" "*indent+"."+obj.name)
    for o in obj.children:
        printHierarchy(o, indent+1)

def getColorValue(source, aoValue, originalColor, randomValue):
    v = 0
    if source == 'ONE':
        v=1.0
    elif source == 'OBJECT_RAND':
        v = randomValue
    elif source == 'CURRENT':
        v = originalColor
    elif source == 'AO':
        v = aoValue
    return v
    
def bakeVertexAO(scene, obj):
    sGflow = scene.gflow
    aoAttribute = None
    if sGflow.vertexChannelR == 'AO' or sGflow.vertexChannelG == 'AO' or sGflow.vertexChannelB == 'AO':
        scene.render.engine = 'CYCLES'
        # We must first create a dummy AO color target
        aoAttribute = obj.data.color_attributes.new("GFLOW_AO_TEMP", type='BYTE_COLOR', domain='CORNER')
        obj.data.color_attributes.active_color = aoAttribute
        # Bake AO
        bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
    return aoAttribute
def bakeVertexColor(context, scene, obj):
    sGflow = scene.gflow
    helpers.setSelected(context, obj)
    
    # Keep track of the originally active color channel
    originalColorAttribute = obj.data.color_attributes.active_color
    # GamiFlow will generate a per-corner color, but if the source color is a per vertex we need to find a corner->vertex mapping
    sourceIsPerCorner = originalColorAttribute == 'CORNER'

    
    # Generate the attribute (it could already exist if the user wanted to be clever)
    gflowVertexColorName = "GFLOW_Color"
    if not gflowVertexColorName in obj.data.color_attributes:
        obj.data.color_attributes.new(gflowVertexColorName, type='BYTE_COLOR', domain='CORNER')
    else:
        # if we already have the color attribute, we assume it's already been done
        helpers.setDeselected(obj)
        return
    
    # Compute AO if needed
    aoTarget = bakeVertexAO(scene, obj)
        

    # Compute a random color
    rndColor = (random.random(), random.random(), random.random())

    # Fill in the data
    vertexColorAttribute = obj.data.color_attributes[gflowVertexColorName]
    for index in range(0, len(vertexColorAttribute.data)):
        aoValue = 1.0
        originalColor = [0.0,0.0,0.0,1.0] 

        if aoTarget: aoValue = aoTarget.data[index].color[0]
        if originalColorAttribute: 
            vi = index if sourceIsPerCorner else obj.data.loops[index].vertex_index
            originalColor = originalColorAttribute.data[vi].color
        
        red = getColorValue(sGflow.vertexChannelR, aoValue, originalColor[0], rndColor[0])
        green = getColorValue(sGflow.vertexChannelG, aoValue, originalColor[1], rndColor[1])
        blue = getColorValue(sGflow.vertexChannelB, aoValue, originalColor[2], rndColor[2])
        
        vertexColorAttribute.data[index].color = [red, green, blue, 1.0]
                   
    # Second pass for random color
    if sGflow.vertexChannelR == 'ISLAND_RAND' or sGflow.vertexChannelG == 'ISLAND_RAND' or sGflow.vertexChannelB == 'ISLAND_RAND':
        with helpers.objectModeBmesh(obj) as bm:        
            parts = helpers.bm_loose_parts(bm)
            colorLayer = bm.loops.layers.color[gflowVertexColorName]
            for faceIsland in parts:
                print("ISland")
                rndColor = (random.random(), random.random(), random.random())
                for face in faceIsland.faces:
                    for loop in face.loops:
                        if sGflow.vertexChannelR == 'ISLAND_RAND':
                            loop[colorLayer][0] = rndColor[0]
                        if sGflow.vertexChannelG == 'ISLAND_RAND':
                            loop[colorLayer][1] = rndColor[1]
                        if sGflow.vertexChannelB == 'ISLAND_RAND':
                            loop[colorLayer][2] = rndColor[2]                        

                   
    obj.data.color_attributes.active_color_name = gflowVertexColorName
    
    # Cleanup
    if aoTarget: 
        obj.data.color_attributes.remove(aoTarget)
    if originalColorAttribute and (sGflow.vertexChannelR == 'CURRENT' or sGflow.vertexChannelG == 'CURRENT' or sGflow.vertexChannelB == 'CURRENT'):
        obj.data.color_attributes.remove(originalColorAttribute)
    
    helpers.setDeselected(obj)
    
    
class Chunk:
    def __init__(self):
        self.objects = []
        self.mergedObject = None
        
    # Called when there is only one mesh left but it still has an empty object as root
    @staticmethod
    def removeGizmoRoot(gizmo, obj):
        # Match the pivot point if the object wasn't centred
        localPosition = obj.matrix_local.col[3].xyz
        if abs(localPosition.dot(localPosition))>0.0001:
            if obj.data.users>1: obj.data = obj.data.copy() # Make sure that the mesh is unique to avoid side effects
            offsetMatrix = (gizmo.matrix_world.inverted() @ obj.matrix_world)
            obj.data.transform(offsetMatrix)             
            obj.matrix_world = gizmo.matrix_world
        # Reparent
        if gizmo.parent:
            helpers.setParent(obj, gizmo.parent)
        # Temporary swap the names until the root gets deleted
        originalName = gizmo.name
        gizmo.name = obj.name
        obj.name = originalName
        
    def merge(self, context, allowGizmoRoot):
        root = self.objects[-1]
        gizmoRoot = root.type == 'EMPTY'
        
        # First check what we have
        oldEmpties = []
        meshobjs = []
        for m in self.objects:
            if m.type == 'MESH': meshobjs.append(m)
            if m.type == 'EMPTY': oldEmpties.append(m)   
        
        if len(meshobjs) == 0: return
        
        # First, watch out for objects that might get orphaned after the merge
        orphans = []
        if gizmoRoot and not allowGizmoRoot: # Roots of Empty type will be removed so we need to make sure that we won't lose the hierarchy of their children
            for o in root.children:
                if o not in self.objects: 
                    orphans.append(o)
                    helpers.setParent(o, None)

        # Do the merge
        if len(meshobjs)>1:
            print(" Merge of "+root.name + " from "+str(len(meshobjs))+" objects")
            # Make sure we do not have a shared mesh on the target object
            if meshobjs[-1].data.users>1:
                meshobjs[-1].data = meshobjs[-1].data.copy()
            # Select everything in the right order and join
            for m in meshobjs:
                helpers.setSelected(context, m)
            bpy.ops.object.join()
            self.mergedObject = context.object
        else:
            self.mergedObject = meshobjs[0]
        
        if self.mergedObject is None:
            print("GamiFlow Warning: Nothing merged")
        
        # If the root was not a proper mesh we have to make changes to the new merged mesh to match some of the root settings
        if gizmoRoot and not allowGizmoRoot: 
            Chunk.removeGizmoRoot(root, self.mergedObject)
        
        helpers.setDeselected(self.mergedObject)
        
        # Re parent the orphans to the new parent
        for o in orphans: helpers.setParent(o, self.mergedObject)            
        
        # Cleanup
        for oe in oldEmpties: bpy.data.objects.remove(oe)   # TODO: maybe make sure we don't delete the root if empty roots are allowed 

        self.objects = None
        
def mergeObjects(context, objects):
    chunks = []
    # Nothing to merge, ezpz
    if len(objects) == 1: 
        return objects
        c = Chunk()
        c.mergedObject = objects[0]
        chunks.append(c)
        return chunks    
    
    bpy.ops.object.select_all(action='DESELECT')
    todo = [o for o in objects if o.parent is None]
        
    # Build a list of 'chunks' that can be merged together
    while(len(todo)>0):
        # Pick one object in the todo list and decide what to do with its children
        root = todo[0]
        todo.remove(root)
        merge, todo = mergeHierarchy(root, [], todo, context.scene.gflow.mergeUdims)
        #if len(merge)>0:
        chunk = Chunk()
        chunk.objects = merge+[root]
        chunks.append(chunk)
    # Actually do the merge
    print("GamiFlow: Merge into "+str(len(chunks))+" groups")
    result = []
    for chunk in chunks:
        chunk.merge(context, False)
        result.append(chunk.mergedObject)
    return result

def triangulateObjects(context, objects):
    todo = list(objects)
    objectsUsingMesh = {}
    for o in todo:
        if not helpers.isObjectValidMesh(o): continue
        
        if o.data.users == 1:
            helpers.setSelected(context, o)
            tri = sets.triangulate(context, o)
            if o.data.shape_keys is None:
                bpy.ops.object.modifier_apply(modifier=tri.name)
            helpers.setDeselected(o)
        elif o.data.users > 1:
            if o.data not in objectsUsingMesh:
                objectsUsingMesh[o.data] = [o]
            else:
                objectsUsingMesh[o.data].append(o)
                
    # Handle shared meshes separately
    for (mesh, objs) in objectsUsingMesh.items():
        # make the first object unique, add triangulate modifier, and apply it
        helpers.setSelected(context, objs[0])
        trimesh = mesh.copy()
        objs[0].data = trimesh
        tri = sets.triangulate(context, objs[0])
        bpy.ops.object.modifier_apply(modifier=tri.name)
        helpers.setDeselected(objs[0])
        # remove the modifier on the other objects and swap the mesh
        for o in objs[1:]:
            o.data = trimesh
           

def generateExport(context):
    # Make sure we don't already have a filled export set
    collection = getCollection(context, createIfNeeded=False)
    if collection: sets.clearCollection(collection)
    # But make we sure do have one
    collection = getCollection(context, createIfNeeded=True)
    
    # Collection visibility
    sets.setCollectionVisibility(context, collection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterLowCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterHighCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterCageCollection, False)
    
    stgs = settings.getSettings()
    exportSuffix = stgs.exportsuffix
    workingSuffix = stgs.workingsuffix
    
    # Get a list of all the actions present now
    actions = set(bpy.data.actions)
    
#BEGINTRIM --------------------------------------------------
    # Show the decalmachine layers (necessary)
    if settings.isDecalMachineEnabled(settings.getSettings()):
        for c in context.collection.children_recursive:
            if c.DM.isdecaltypecol: sets.setCollectionVisibility(context, c, True, recursive=True)
#ENDTRIM -----------------------------------------------------       
    bpy.ops.object.select_all(action='DESELECT')

    # A collection instance template has already been completely processed and merged
    # and is ready to be instanciated again
    collectionInstanceTemplate = {}
    

    def prepareCollectionInstance(collection):
        if collection in collectionInstanceTemplate: return
        print("GamiFlow: Preparing collection "+collection.name + " for instancing")
        
        # Generate all the objects as normal
        generatedInstance = populateExportList(collection.all_objects, collection.name+"_",)
        # Finalise and merge everything
        mergedObjects = mergeObjects(context, generatedInstance.generated)
        processedInstance = sets.GeneratorData()
        for o in mergedObjects:
            processedInstance.register(o, None)
        # Put the pivot on 0 to make instantiating it easier later
        for o in mergedObjects:
            offsetMatrix = (o.matrix_world)
            o.data.transform(offsetMatrix)
            o.matrix_world = mathutils.Matrix.Identity(4)

        collectionInstanceTemplate[collection] = processedInstance
                                    

    def populateExportList(objectsToDuplicate, namePrefix=""):
        localgen = sets.GeneratorData()
        roots = []
        parented = []
        stgs = settings.getSettings()
#BEGINTRIM --------------------------------------------------  
        useDecalMachine = settings.isDecalMachineEnabled(stgs)
        decals = None
        if useDecalMachine: decals = [obj for obj in context.scene.objects if obj.DM.isdecal]
#ENDTRIM -----------------------------------------------------          
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type=='EMPTY' or o.type == 'ARMATURE'): continue # We could potentially allow more types (.e.g lights)
            if not (o.gflow.objType == 'STANDARD' or o.gflow.objType == 'NON_BAKED'): continue
            if not  o.gflow.exportable: continue
            
            # Make a copy the object
            newobj = sets.duplicateObject(o, collection, suffix=exportSuffix, workingSuffix=workingSuffix, link=o.type=='ARMATURE')
            newobj.name = namePrefix+newobj.name
            localgen.register(newobj, o)
            
            sets.setObjectAction(newobj, newobj.gflow.exportAction, newobj.gflow.exportActionObjectSlotName)
            sets.setShapekeyAction(newobj, newobj.gflow.exportAction, newobj.gflow.exportActionShapekeySlotName)
            
            # Rename its UVs
            if stgs.renameUVs and newobj.type == 'MESH':
                for uv in newobj.data.uv_layers:
                    if uv.active_render: 
                        uv.name = stgs.uvName
                        break
            
#BEGINTRIM --------------------------------------------------             
            # Get the DECALmachine decals
            if useDecalMachine:
                for d in decals:
                    # DECALmachine properties that seem relevant (and better than just checking for parenting):
                    # DM.projectedon
                    # DM.slicedon
                    if d.parent == o: 
                        decalCopy = sets.duplicateObject(d, collection, suffix=exportSuffix, workingSuffix=workingSuffix, link=False)
                        decalCopy.parent = newobj
                        decalCopy.gflow.objType = 'NON_BAKED'
                        # Apply the modifiers
                        helpers.setSelected(context, decalCopy)
                        bpy.ops.object.convert(target='MESH')
                        helpers.setDeselected(decalCopy)
                        # Find which UV layer we need to use
                        decalLayer = None
                        atlasLayer = None
                        for uv in decalCopy.data.uv_layers:
                            if uv.name == 'Atlas UVs': atlasLayer = uv;
                            if uv.name == 'Decal UVs': decalLayer = uv;
                        toKeep = atlasLayer if atlasLayer else decalLayer
                        if not toKeep: toKeep = decalCopy.data.uv_layers[0]
                        # Delete any layer that we don't care about
                        for uv in decalCopy.data.uv_layers:
                            if uv != toKeep: decalCopy.data.uv_layers.remove(uv)
                        # Name the UV map after the parent's UVs so that they can be merged later
                        if newobj.type == 'MESH': 
                            toKeep.name = newobj.data.uv_layers[0].name
#ENDTRIM -----------------------------------------------------               
            
            # remove cage control data
            if o.type == 'MESH': 
                sets.removeCageEdges(newobj)
                geotags.removeObjectCageLayers(newobj)
                
            # Unparenting for now as the new parent might not yet exist
            if o.parent != None:
                newobj.parent = None
                newobj.matrix_world = o.matrix_world.copy()
                parented.append(newobj)
            else:
                roots.append(newobj)
                
            if o.type=='MESH':
                sets.generatePartialSymmetryIfNeeded(context, newobj)
            
                # Remove all detail edges
                helpers.setSelected(context, newobj)
                sets.collapseEdges(context, newobj)
                sets.removeEdgesForLevel(context, newobj, 0, keepPainter=False)
                sets.deleteDetailFaces(context, newobj)
                
                # Set the material
                if o.gflow.objType != 'NON_BAKED':
                    material = sets.getTextureSetMaterial(o.gflow.textureSet, context.scene.gflow.mergeUdims)
                    sets.setMaterial(newobj, material)
                
                # Process modifiers, clean up metadata, etc
                sets.removeLowModifiers(context, newobj)
                geotags.removeObjectLayers(newobj)
                helpers.setDeselected(newobj) 
            elif o.type == 'EMPTY':
                newobj.instance_type = 'NONE'
                # Realise the instance
                if helpers.isObjectCollectionInstancer(o) and o.instance_collection:
                    if o.gflow.instanceAllowExport:
                        # If the instanced collection is unknwon, wemake a template from it
                        if o.instance_collection not in collectionInstanceTemplate:
                            prepareCollectionInstance(o.instance_collection)
                   
                        # Instanciate from the template
                        template = collectionInstanceTemplate[o.instance_collection]
                        instgen = sets.GeneratorData()
                        for io in template.generated:
                            i = sets.duplicateObject(io, collection, suffix="_TMP_", workingSuffix=workingSuffix, link=True) # Should ideally use linked but causes issues when merging later
                            instgen.register(i, io)
                        for i in instgen.parented:
                            instgen.reparent(i)
                        for root in instgen.roots: 
                            safeParent = findFirstNonCollapsedParent(newobj, context.scene.gflow.mergeUdims)
                            helpers.setParent(root, safeParent) 
                            root.matrix_world = newobj.matrix_world @ root.matrix_world  # we also need to move the instances into world space
                        localgen.add(instgen)
                        print("GamiFlow:   - Instantiated "+str(len(instgen.generated))+" objects from '"+o.instance_collection.name+"'")

                        pass
             #endif empty
            
        print("GamiFlow:   - Added "+str(len(localgen.generated))+" objects")
        #endfor (original objects)

        # Now that we have all the objects we can try rebuilding the intended hierarchy
        for newobj in parented:
            localgen.reparent(newobj)
            
        # Now we can apply all the modifiers
        for newobj in localgen.generated:
            processModifiers(context, localgen, newobj) 

            
        # Do another pass to check that we are not parenting to something that will end up getting merged
        for newobj in parented: 
            safeParent = findFirstNonCollapsedParent(newobj.parent, context.scene.gflow.mergeUdims)
            if safeParent != newobj.parent: helpers.setParent(newobj, safeParent)        
        
        return localgen
    
    print("GamiFlow: Populate Export Set")
    gen = populateExportList(list(context.scene.gflow.workingCollection.all_objects))

    # Clean up all the instance templates
    for it in collectionInstanceTemplate.values():
        for o in it.generated:
            sets.deleteObject(o)

    # Deal with the anchors
    for o in gen.generated:
        if o.gflow.exportAnchor:
            o.matrix_world = o.gflow.exportAnchor.matrix_world.copy()

    # Lightmap UVs generation
    if context.scene.gflow.lightmapUvs:
        uv.lightmapUnwrap(context, gen.generated)
        
    # Vertex color baking and double sided geo
    bpy.ops.object.select_all(action='DESELECT')
    random.seed(0)
    for index, o in enumerate(gen.generated):
        if helpers.isObjectValidMesh(o):

            if o.gflow.doubleSided:
                # Duplicate and flip normals
                backface = sets.duplicateObject(o, collection, prefix="backface_")
                helpers.setSelected(context, backface)
                bpy.ops.object.editmode_toggle()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.transform.push_pull(value=0.001, mirror=False, use_proportional_edit=False)
                bpy.ops.object.editmode_toggle()
                helpers.setDeselected(o)
                # Bake the colours for both sides
                if context.scene.gflow.exportVertexColors:
                    bakeVertexColor(context, context.scene, backface)
                    bakeVertexColor(context, context.scene, o)
                # Join the two objects together
                helpers.setSelected(context, backface)
                helpers.setSelected(context, o)
                bpy.ops.object.join()
                gen.generated[index] = context.object
                helpers.setDeselected(context.object)
            else:
                if context.scene.gflow.exportVertexColors:
                    bakeVertexColor(context, context.scene, o)            
                
 
    # TODO: double sided geometry
    # double sided geo with AO idea:
    # duplicate object and flip normals
    # then bake AO
    # maybe push verts that aren't in the "Non manifold" list (but probably shouldn't have to)
    # then join back with original
    
    # CHECK: joining might invalidate the objects stored in gen.generated 
    
    # Triangulate and apply 
    # Done after the rest because the DataTransfer modifier gets confused if the source object is triangulated but the current object is not
    # But needs special treatment because shared meshes don't like modifiers being applied
    triangulateObjects(context, gen.generated)

                
    
 
    # Merge all possible objects
    if stgs.mergeExportMeshes:
        print("GamiFlow: Find mergeable meshes")
        todo = sets.findRoots(collection)
        bpy.ops.object.select_all(action='DESELECT')
        
        # Build a list of 'chunks' that can be merged together
        chunks = []
        while(len(todo)>0):
            # Pick one object in the todo list and decide what to do with its children
            root = todo[0]
            todo.remove(root)
            merge, todo = mergeHierarchy(root, [], todo, context.scene.gflow.mergeUdims)
            #if len(merge)>0:
            chunk = Chunk()
            chunk.objects = merge+[root]
            chunks.append(chunk)
        # Actually do the merge
        print("GamiFlow: Merge into "+str(len(chunks))+" groups")
                
        for chunk in chunks:
            chunk.merge(context, False)
    
    # Now that we have our final objects, we can pack their lightmap UVs
    if context.scene.gflow.lightmapUvs:
        uv.lightmapPack(context, collection.all_objects)
    
    if context.scene.gflow.exportFormat == "GLTF" and context.scene.gflow.exportTarget == "SKETCHFAB":
        for o in collection.all_objects:
            if o.type == 'MESH': uv.flipUVs(o)
                
    # Cleanup the actions that were potentially accidentally duplicated
    newActions = set(bpy.data.actions)
    toDelete = newActions-actions
    for a in toDelete:
        print("GamiFlow: Cleaning up action"+a.name+" thatshouldn't have created in the first place")
        bpy.actions.remove(a)
    
    if stgs.renameExportMeshes:
        print("GamiFlow: Rename export meshes")
        meshes = []
        for o in collection.all_objects:
            if o.type == 'MESH' and o.data not in meshes:
                o.data.name = o.name
                meshes.append(o.data)
#BEGINTRIM --------------------------------------------------
    # Hide the DECALmachine layers (nice to have)
    if settings.isDecalMachineEnabled(settings.getSettings()):
        for c in context.collection.children_recursive:
            if c.DM.isdecaltypecol: sets.setCollectionVisibility(context, c, False, recursive=True)
#ENDTRIM -----------------------------------------------------                   
    
    

class GFLOW_OT_MakeExport(bpy.types.Operator):
    bl_idname      = "gflow.make_export"
    bl_label       = "Make Export"
    bl_description = "Generate final meshes"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the Working Collection first")
            return False
        return True
    def execute(self, context):
        generateExport(context)
        
        return {"FINISHED"} 


classes = [GFLOW_OT_MakeExport,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass