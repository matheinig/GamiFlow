import bpy
from . import sets

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterHighCollection
    name = sets.getSetName(context) + "_high"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_01"
        context.scene.gflow.painterHighCollection = c
    if c: c.name = name
    return c

def generatePainterHigh(context):
    highCollection = getCollection(context, createIfNeeded=False)
    if highCollection: sets.clearCollection(highCollection)
    highCollection = getCollection(context, createIfNeeded=True)
    
    # Visibility
    sets.setCollectionVisibility(context, highCollection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterLowCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.exportCollection, False)

    # Go through all the objects of the working set
    for o in context.scene.gflow.workingCollection.all_objects:
        if o.type != 'MESH': continue
        if not (o.gflow.objType == 'STANDARD' or o.gflow.objType == 'OCCLUDER'): continue
        
        # Make a copy the object
        suffix = "_high"
        if o.gflow.objType == 'OCCLUDER': suffix = "_occluder"
        
        newobj = None
        if o.gflow.includeSelf:
            newobj = sets.duplicateObject(o, suffix, highCollection)
            # Parenting magic
            if o.parent != None:
                newobj.parent = None
                newobj.matrix_world = o.matrix_world.copy()
        
            # handle special modifiers like subdiv
    
            sets.triangulate(context, newobj)
    
            # remove all hard edges
            if o.gflow.removeHardEdges: sets.removeSharpEdges(newobj)
        
        # Add all manually-linked highpolys
        for hp in o.gflow.highpolys:
            newhp = sets.duplicateObject(hp.obj, "_TEMP_", highCollection)
            hpsuffix = suffix
            if hp.obj.gflow.objType == 'DECAL': 
                hpsuffix = hpsuffix + "_ignorebf"
            newhp.name = sets.getNewName(o, hpsuffix) + "_" + hp.obj.name
            sets.triangulate(context, newhp)


    pass


class GFLOW_OT_MakeHigh(bpy.types.Operator):
    bl_idname      = "gflow.make_high"
    bl_label       = "Make High"
    bl_description = "Generate high-poly meshes for Painter"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):
        generatePainterHigh(context)
        
        return {"FINISHED"} 


classes = [GFLOW_OT_MakeHigh,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass