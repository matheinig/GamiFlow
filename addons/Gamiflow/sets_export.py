import bpy
from . import sets
from . import helpers
from . import settings
from . import uv
from . import geotags
from . import sets_cage
import mathutils

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
    
    # Deal with special cases for special modifiers
    # NOTE: Currently no special cases for the Export Set :)
    
    # Collapse all other 'standard' modifiers (incredibly slow but important if we start merging objects)
    for m in list(obj.modifiers):
        if m.type == 'ARMATURE': continue # Armature modifiers should not be collapsed
        bpy.ops.object.modifier_apply(modifier=m.name)
    sets_cage.removeCageModifier(context, obj)
    helpers.setDeselected(obj) 


# Hierarchy optimiser
def areMergeCompatible(p, c, mergeUdims=False):
    if not c.gflow.mergeWithParent: return False
    
    needToCheckUdims = (not mergeUdims)
    if (p.type=='EMPTY' or c.type=='EMPTY'): needToCheckUdims = False
    if needToCheckUdims and (p.gflow.textureSet != c.gflow.textureSet): return False
    
    #if c.gflow.objType == 'TRIM' and p.gflow.objType != 'TRIM': return False
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
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type=='EMPTY'): continue # We could potentially allow more types (.e.g lights)
            if not (o.gflow.objType == 'STANDARD' or o.gflow.objType == 'TRIM'): continue
            
            # Make a copy the object
            newobj = sets.duplicateObject(o, collection, suffix=exportSuffix)
            newobj.name = namePrefix+newobj.name
            localgen.register(newobj, o)
            
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
                
            if not o.type=='EMPTY':
                sets.generatePartialSymmetryIfNeeded(context, newobj)
            
                # Remove all detail edges
                helpers.setSelected(context, newobj)
                sets.collapseEdges(context, newobj)
                sets.removeEdgesForLevel(context, newobj, 0, keepPainter=False)
                sets.deleteDetailFaces(context, newobj)
                
                # Set the material
                if o.gflow.objType != 'TRIM':
                    material = sets.getTextureSetMaterial(o.gflow.textureSet, context.scene.gflow.mergeUdims)
                    sets.setMaterial(newobj, material)
                
                # Process modifiers, clean up metadata, etc
                sets.removeLowModifiers(context, newobj)
                sets.triangulate(context, newobj)  
                geotags.removeObjectLayers(newobj)
                helpers.setDeselected(newobj) 
            else:
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
                            i = sets.duplicateObject(io, collection, suffix="_TMP_", link=True) # Should ideally use linked but causes issues when merging later
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
    
    if context.scene.gflow.exportFormat == "GLTF" and context.scene.gflow.exportTarget == "SKETCHFAB":
        for o in collection.all_objects:
            if o.type == 'MESH': uv.flipUVs(o)
                
    
    if stgs.renameExportMeshes:
        print("GamiFlow: Rename export meshes")
        meshes = []
        for o in collection.all_objects:
            if o.type == 'MESH' and o.data not in meshes:
                o.data.name = o.name
                meshes.append(o.data)

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