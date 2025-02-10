import bpy
from . import sets
from . import helpers
from . import settings
from . import uv
from . import geotags
from . import sets_cage

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
    if (not mergeUdims) and p.gflow.textureSet != c.gflow.textureSet: return False
    # TODO: there are more conditions that should probably be met such as smoothing method
    return True
def mergeHierarchy(obj, mergeList, todoList, mergeUdims):
    for c in obj.children:
        if areMergeCompatible(obj, c, mergeUdims):
            mergeList.append(c)
            mergeList, todoList = mergeHierarchy(c, mergeList, todoList, mergeUdims)
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
    
    # Go through all the objects of the working set and generate the export set
    gen = sets.GeneratorData()

    bpy.ops.object.select_all(action='DESELECT')

    knownInstancedCollections = {}#TODO remove
    
    instancedCollections = []

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
            gen.register(newobj, o)
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
                #newObjectToOriginalParent[newobj] = o.parent
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
                        generatedInstance = None
                        # If the instanced collection is unknwon, we duplicate and process all the objects inside
                        if o.instance_collection not in knownInstancedCollections:
                            instanced = o.instance_collection.all_objects
                            generatedInstance = populateExportList(instanced, o.name+"_",)
                            knownInstancedCollections[o.instance_collection] = generatedInstance
                            
                            instColl = InstancedCollection()
                            instColl.generated = generatedInstance
                            instColl.spawnPoint = newobj
                            instancedCollections.append( instColl )                            
                            
                            print("GamiFlow:   - Instantiated "+str(len(generatedInstance.generated))+" objects from '"+o.instance_collection.name+ "' for the first time")
                        # if we've already seen it, we can just duplicate the previously-generated version
                        else:
                            existingInstance = knownInstancedCollections[o.instance_collection]
                            # TODO: issue with recursive???
                            instgen = sets.GeneratorData()
                            for io in existingInstance.generated:
                                i = sets.duplicateObject(io, collection, suffix="_TMP_")
                                instgen.register(i, io)
                            for i in instgen.parented:
                                instgen.reparent(i)
                                
                            instColl = InstancedCollection()
                            instColl.generated = instgen
                            instColl.spawnPoint = newobj
                            instancedCollections.append( instColl )

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
    populateExportList(list(context.scene.gflow.workingCollection.all_objects))

    # Put all the instanced collections in the right place and parent them properly
    for ic in (instancedCollections):
        for root in ic.generated.roots: 
            safeParent = findFirstNonCollapsedParent(ic.spawnPoint, context.scene.gflow.mergeUdims)
            helpers.setParent(root, safeParent) 
            root.matrix_world = ic.spawnPoint.matrix_world @ root.matrix_world  # we also need to move the instances into world space

    # Deal with the anchors
    for o in gen.generated:
        if o.gflow.exportAnchor:
            o.matrix_world = o.gflow.exportAnchor.matrix_world.copy()

    # Lightmap UVs generation
    if context.scene.gflow.lightmapUvs:
        uv.lightmapUnwrap(context, gen.generated)
        
    class Chunk:
        def __init__(self):
            self.objects = []
            self.merged = None
        def merge(self):
            root = self.objects[-1]
            gizmoRoot = root.type == 'EMPTY'
            
            # First, watch out for objects that might get orphaned after the merge
            orphans = []
            if gizmoRoot: # Roots of Empty type will be removed so we need to make sure that we won't lose the hierarchy of their children
                for o in root.children:
                    if o not in self.objects: 
                        orphans.append(o)
                        helpers.setParent(o, None)

            # Also keep track of the actual pivot of the root object
            originalRootTransform = root.matrix_world.copy()
            originalRootName = root.name
            originalRootParent = root.parent
        
            # Do the merge
            oldEmpties = []
            for m in self.objects:
                if m.type == 'MESH': helpers.setSelected(context, m)
                if m.type == 'EMPTY': oldEmpties.append(m)
            bpy.ops.object.join()
            self.mergedObject = context.object
            
            if self.mergedObject is None:
                print("GamiFlow Warning: Nothing merged")
            
            # If the root was not a proper mesh we have to make changes to the new merged mesh to match some of the root settings
            if gizmoRoot:
                # Match the pivot point
                offsetMatrix = (originalRootTransform.inverted() @ self.mergedObject.matrix_world)
                self.mergedObject.data.transform(offsetMatrix)                
                self.mergedObject.matrix_world = originalRootTransform
                # Reparent
                if originalRootParent:
                    self.mergedObject.parent = None
                    helpers.setParent(self.mergedObject, originalRootParent)
                # Temporary swap the names until the root gets deleted
                root.name = self.mergedObject.name
                # Match the root name
                self.mergedObject.name = originalRootName
                # TODO: there could be other objects with constraints pointing to the original root
            helpers.setDeselected(self.mergedObject)
            
            # Re parent the orphans to the new parent
            for o in orphans: helpers.setParent(o, self.mergedObject)            
            
            for oe in oldEmpties: bpy.data.objects.remove(oe)    

            self.objects = None            

        
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
            if len(merge)>0:
                chunk = Chunk()
                chunk.objects = merge+[root]
                chunks.append(chunk)
        # Actually do the merge
        print("GamiFlow: Merge into "+str(len(chunks))+" groups")
        for chunk in chunks:
            chunk.merge()
    
    
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