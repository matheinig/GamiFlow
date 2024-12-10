import bpy
from . import sets
from . import helpers
from . import settings
from . import uv
from . import geotags

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
def processModifiers(context, obj):
    helpers.setSelected(context, obj)
    
    # Deal with special cases for special modifiers
    # NOTE: Currently no special cases for the Export Set :)
    
    # Collapse all other 'standard' modifiers
    for m in list(obj.modifiers):
        if m.type == 'ARMATURE': continue # Armature modifiers should not be collapsed
        bpy.ops.object.modifier_apply(modifier=m.name)


# Hierarchy optimiser
def areMergeCompatible(p, c, mergeUdims=False):
    if not c.gflow.mergeWithParent: return False
    if not mergeUdims and p.gflow.textureSet != c.gflow.textureSet: return False
    # TODO: there are more conditions that should probably be met such as smoothing method
    return True
def mergeHierarchy(obj, mergeList, todoList, mergeUdims):
    for c in obj.children:
        if areMergeCompatible(obj, c, mergeUdims):
            mergeList.append(c)
            mergeList, todoList = mergeHierarchy(c, mergeList, todoList)
        else:
            todoList.append(c) 
    return mergeList, todoList
def findFirstNonCollapsedParent(obj, mergeUdims):
    if obj.parent is None: return obj
    parent = obj.parent
    if areMergeCompatible(parent, obj): return findFirstNonCollapsedParent(parent, mergeUdims)
    return obj



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
    
    stgs = settings.getSettings()
    exportSuffix = stgs.exportsuffix
    
    # Go through all the objects of the working set and generate the export set
    gen = sets.GeneratorData()

    def populateExportList(objectsToDuplicate, namePrefix=""):
        localgen = sets.GeneratorData()
        roots = []
        parented = []
        instanceRootsTransforms = {}
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type=='EMPTY'): continue # We could potentially allow more types (.e.g lights)
            if o.gflow.objType != 'STANDARD': continue
            

            generateCopy = True
            if helpers.isObjectCollectionInstancer(o): generateCopy = False
            
            # Make a copy the object

            newobj = sets.duplicateObject(o, exportSuffix, collection)
            newobj.name = namePrefix+newobj.name
            gen.register(newobj, o)
            localgen.register(newobj, o)
                
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
                bpy.ops.object.select_all(action='DESELECT')  
                sets.removeEdgesForLevel(context, newobj, 0, keepPainter=False)
                sets.deleteDetailFaces(context, newobj)
                
                # Set the material
                material = sets.getTextureSetMaterial(o.gflow.textureSet, context.scene.gflow.mergeUdims)
                sets.setMaterial(newobj, material)
                
                # Process modifiers, clean up metadata, etc
                sets.removeLowModifiers(context, newobj)
                sets.triangulate(context, newobj)  
                geotags.removeObjectLayers(newobj)
            else:
                newobj.instance_type = 'NONE'
                # Realise the instance
                if helpers.isObjectCollectionInstancer(o) and o.instance_collection:
                    if o.gflow.instanceAllowExport:
                        instanced = o.instance_collection.all_objects
                        instanceRoots = populateExportList(instanced, o.name+"_",)
                        # Keep track of where the instances should be located
                        for r in instanceRoots: 
                            helpers.setParent(r, newobj) # we can parent everything to the new empty
                            r.matrix_world = o.matrix_world @ r.matrix_world  # we also need to move the instances into world space
            #endif empty
            

        #endfor (original objects)

        # Now that we have all the objects we can try rebuilding the intended hierarchy
        for newobj in parented:
            localgen.reparent(newobj)
        # Put the realised instances back in their right place
        #for instanceRoot, xform in instanceRootsTransforms.items():
        #    instanceRoot.matrix_world = xform @ instanceRoot.matrix_world
        # Do another pass to check that we are not parenting to something that will end up getting merged
        for newobj in parented: 
            safeParent = findFirstNonCollapsedParent(newobj.parent, context.scene.gflow.mergeUdims)
            if safeParent != newobj.parent: helpers.setParent(newobj, safeParent)        
        
        return roots
    
    populateExportList(context.scene.gflow.workingCollection.all_objects)

    # Deal with the anchors
    for o in gen.generated:
        if o.gflow.exportAnchor:
            o.matrix_world = o.gflow.exportAnchor.matrix_world.copy()

    # Lightmap UVs generation
    if context.scene.gflow.lightmapUvs:
        uv.lightmapUnwrap(context, gen.generated)
        
    # Now we can apply all the modifiers
    for newobj in gen.generated:
        processModifiers(context, newobj)
        
    # Merge all possible objects
    if stgs.mergeExportMeshes:
        todo = sets.findRoots(collection)
        while len(todo)>0:
            bpy.ops.object.select_all(action='DESELECT')
            
            # Pick one object in the todo list and decide what to do with its children
            root = todo[0]
            todo.remove(root)
            merge, todo = mergeHierarchy(root, [], todo, context.scene.gflow.mergeUdims)
            
            if len(merge) == 0: continue
            
            # Do the merge
            merge.append(root) # root object must be last in the list for Blender to merge the others into it
            oldEmpties = []
            for m in merge:
                if m.type == 'MESH': helpers.setSelected(context, m)
                if m.type == 'EMPTY': oldEmpties.append(m)
            bpy.ops.object.join()
            mergedObject = context.object
            
            # If the root was not a proper mesh we have to make changes to the new merged mesh to match some of the root settings
            if root.type != 'MESH':
                originalRootName = root.name
                # Match the root transform and pivot
                rootTransform = mergedObject.parent.matrix_world
                offsetMatrix = (mergedObject.matrix_world.inverted() @ rootTransform).inverted()
                mergedObject.data.transform(offsetMatrix)
                mergedObject.parent = None
                mergedObject.matrix_world = rootTransform
                mergedObject.parent = root.parent
                # Temporary swap the names until the root gets deleted
                root.name = mergedObject.name
                # Match the root name
                mergedObject.name = originalRootName
                # TODO: there could be other objects with constraints pointing to the original root
                
            for oe in oldEmpties: bpy.data.objects.remove(oe)
        #endwhile (merge todolist) 
    
    if stgs.renameExportMeshes:
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