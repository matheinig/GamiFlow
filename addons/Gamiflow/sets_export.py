import bpy
from . import sets
from . import helpers
from . import settings
from . import uv

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
def areMergeCompatible(p, c):
    if not c.gflow.mergeWithParent: return False
    if p.gflow.textureSet != c.gflow.textureSet: return False
    # TODO: there are more conditions that should probably be met such as smoothing method
    return True
def mergeHierarchy(obj, mergeList, todoList):
    for c in obj.children:
        if areMergeCompatible(obj, c):
            mergeList.append(c)
            mergeList, todoList = mergeHierarchy(c, mergeList, todoList)
        else:
            todoList.append(c) 
    return mergeList, todoList

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
    
    exportSuffix = settings.getSettings().exportsuffix
    
    # Go through all the objects of the working set and generate the export set
    generated = []
    newObjectToOriginalParent = {}
    originalObjectToFinal = {}
    for o in context.scene.gflow.workingCollection.all_objects:
        if not (o.type == 'MESH' or o.type=='EMPTY'): continue # We could potentially allow more types (.e.g lights)
        if o.gflow.objType != 'STANDARD': continue
        
        isEmpty = (o.type=='EMPTY')
        
        # Make a copy the object
        newobj = sets.duplicateObject(o, exportSuffix, collection)
        originalObjectToFinal[o] = newobj
        
        # Unparenting for now as the new parent might not yet exist
        if o.parent != None:
            newobj.parent = None
            newobj.matrix_world = o.matrix_world.copy()
            newObjectToOriginalParent[newobj] = o.parent
            
        if not isEmpty:
            # Remove all detail edges
            bpy.ops.object.select_all(action='DESELECT')  
            sets.removeEdgesForLevel(context, newobj, 0, keepPainter=False)
            
            # Set the material
            material = sets.getTextureSetMaterial(o.gflow.textureSet)
            sets.setMaterial(newobj, material)
            
            # Remove modifiers flagged as being irrelevant for low-poly
            sets.removeLowModifiers(context, newobj)
            
            # Enforce triangulation
            sets.triangulate(context, newobj)            
            
        generated.append(newobj)
    #endfor (original objects)

    # Now that we have all the objects we can try rebuilding the intended hierarchy
    for newobj, origParent in newObjectToOriginalParent.items():
        # Find new parent
        try:
            newParent = originalObjectToFinal[origParent]
            if newParent != None: helpers.setParent(newobj, newParent)
        except:
            print("Could not find parent of "+newobj+" in the export set")
            
    
    # Deal with the anchors
    for o in generated:
        if o.gflow.exportAnchor:
            o.matrix_world = o.gflow.exportAnchor.matrix_world.copy()

    # Lightmap UVs generation
    if context.scene.gflow.lightmapUvs:
        uv.lightmapUnwrap(context, generated)
        
    # Now we can apply all the modifiers
    for newobj in generated:
        processModifiers(context, newobj)
    # Merge all possible objects
    todo = sets.findRoots(collection)
    while len(todo)>0:
        bpy.ops.object.select_all(action='DESELECT')
        
        # Pick one object in the todo list and decide what to do with its children
        root = todo[0]
        todo.remove(root)
        merge, todo = mergeHierarchy(root, [], todo)
        
        if len(merge) == 0: continue
        
        # Do the merge
        merge.append(root) # root object must be last in the list for Blender to merge the others into it
        for m in merge:
            if m.type == 'MESH': helpers.setSelected(context, m)
        bpy.ops.object.join()
        mergedObject = context.object
        
        # If the root was not a proper mesh we have to make changes to the new merged mesh to match some of the root settings
        if root.type != 'MESH':
            mergedObject.name = root.name
            # TODO: match new pivot to the original root
            # TODO: there could be other objects with constraints pointing to the original root
    #endwhile (merge todolist)    

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