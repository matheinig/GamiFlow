import bpy
from . import sets
from . import settings
from . import helpers
from . import uv

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterLowCollection
    name = sets.getSetName(context) + "_low"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_03"
        context.scene.gflow.painterLowCollection = c    
    if c: c.name = name
    
    return c

def processModifiers(context, obj):
    for m in obj.modifiers:
        # These modifiers need to offset their UV outside of the [0,1] range to avoid bade bakes in Substance Painter
        if m.type == "MIRROR" or m.type == "ARRAY":
            m.offset_u = 1.0
            m.offset_v = 1.0
    # TODO: apply all modifiers here
            

def generatePainterLow(context):
    lowCollection = getCollection(context, createIfNeeded=False)
    if lowCollection: sets.clearCollection(lowCollection)
    
    lowCollection = getCollection(context, createIfNeeded=True)
    
    # Visibility
    sets.setCollectionVisibility(context, lowCollection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterHighCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.exportCollection, False)

    bpy.ops.object.select_all(action='DESELECT')  

    lpsuffix = settings.getSettings().lpsuffix

    # Go through all the objects of the working set
    generated = []
    newObjectToOriginalParent = {}
    knownMeshes = []
    for o in context.scene.gflow.workingCollection.all_objects:
        if o.type != 'MESH': continue
        if o.gflow.objType != 'STANDARD': continue
        
        # Make a copy the object
        newobj = sets.duplicateObject(o, lpsuffix, lowCollection)
        generated.append(newobj)
        
        # Special handling of instanced meshes
        # Painter doesn't like overlapping UVs when baking so we offset the UVs by 1
        if o.data in knownMeshes:
            # NOTE: Don't need to de-instantiate, the lowpoly copy has its own data
            uv.offsetCoordinates(newobj)
        else:
            knownMeshes.append(o.data)
        
        if o.parent != None: 
            helpers.setParent(newobj, o.parent)
            newObjectToOriginalParent[newobj] = o.parent
        
        bpy.ops.object.select_all(action='DESELECT')  
        sets.removeEdgesForLevel(context, newobj, 0, keepPainter=True)
        
        # Set the material
        material = sets.getTextureSetMaterial(o.gflow.textureSet)
        sets.setMaterial(newobj, material)
        
        # Remove flagged modifiers
        sets.removeLowModifiers(context, newobj)
        # handle special modifiers like subdiv, mirrors, etc
        processModifiers(context, newobj)
        
        # Add simple modifiers if need be
        #TODO: check if modifiers already present
        #sets.addWeightedNormals(context, newobj)
        sets.triangulate(context, newobj)
    
    # Now that we have all the objects we can try rebuilding the intended hierarchy
    for newobj, origParent in newObjectToOriginalParent.items():
        # Find new parent
        newParentName = sets.getNewName(origParent, lpsuffix)
        newParent = helpers.findObjectByName(generated, newParentName)
        # Set new parent
        if newParent: 
            matrix = newobj.matrix_world.copy()
            newobj.parent = newParent
            newobj.matrix_world = matrix    
    
    # Deal with anchors
    for o in generated:
        if o.gflow.bakeAnchor:
            o.matrix_world = o.gflow.bakeAnchor.matrix_world.copy()

    return


class GFLOW_OT_MakeLow(bpy.types.Operator):
    bl_idname      = "gflow.make_low"
    bl_label       = "Make Low"
    bl_description = "Generate low-poly meshes for Painter"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):
        generatePainterLow(context)
        
        return {"FINISHED"} 

classes = [GFLOW_OT_MakeLow,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass