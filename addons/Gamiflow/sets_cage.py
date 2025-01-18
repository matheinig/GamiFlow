import bpy
from . import sets
from . import settings
from . import helpers
from . import geotags
from . import sets_low
import mathutils

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterCageCollection
    name = sets.getSetName(context) + "_cage"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_06"
        context.scene.gflow.painterCageCollection = c    
    if c: c.name = name
    
    return c

def processCageMesh(context, obj):
    helpers.setSelected(context, obj)
   
    # Displace the verts
    baseOffset = obj.gflow.cageOffset
    if baseOffset==0.0: baseOffset = context.scene.gflow.cageOffset
    with helpers.objectModeBmesh(obj) as bm:
        displacementMap = geotags.getCageDisplacementMap(obj, forceCreation=False)
        for v in bm.verts:
            offset = baseOffset
            if displacementMap:
                try:
                    weight = 1.0-displacementMap.weight(v.index)
                    offset = offset * weight
                except: pass 
            v.co += v.normal * offset
     
    helpers.setDeselected(obj)
    return

# unlike the other sets, this one isn't derived from the working set but directly from the low set
def generatePainterCage(context):
    lowCollection = sets_low.getCollection(context, createIfNeeded=False)
    if not lowCollection: return
    # Create a clean collection for the cages
    cageCollection = getCollection(context, createIfNeeded=False)
    if cageCollection: sets.clearCollection(cageCollection)
    cageCollection = getCollection(context, createIfNeeded=True)
 
    sets.setCollectionVisibility(context, cageCollection, True)
 
    namePrefix = settings.getSettings().cageprefix
 
    # Go through all meshes of the low poly set
    for o in list(lowCollection.all_objects):
        if not (o.type == 'MESH'): continue
        
        # Duplicate the lowpoly unless it has a user-defined cage already
        newobj = sets.duplicateObject(o, cageCollection, prefix=namePrefix) # TODO: should we also remove the _low suffix?
        newobj.display_type = 'WIRE'
        helpers.setSelected(context, newobj)

        # Apply modifiers? (unless it's armature?)
        for m in list(newobj.modifiers):
            # remove some unwanted modifiers
            if m.type == 'TRIANGULATE' or m.type == 'ARMATURE':
                newobj.modifiers.remove(m)
                continue
            # Apply the rest (particularly important for mirror seams)
            bpy.ops.object.modifier_apply(modifier=m.name)
        
        
        # Generate the cage
        processCageMesh(context, newobj)

        pass
 
    return


class GFLOW_OT_MakeCage(bpy.types.Operator):
    bl_idname      = "gflow.make_cage"
    bl_label       = "Make High"
    bl_description = "Generate bake cages"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):

        
        return {"FINISHED"} 


class GFLOW_OT_AddCageDisplacementMap(bpy.types.Operator):
    bl_idname      = "gflow.add_cage_displacement_map"
    bl_label       = "Add map"
    bl_description = "Add a weightmap to define the cage tightness: a value of 1 means the cage vertex will not be displaced. a value of 0 means the vertex will be fully displaced."
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.object: return False
        return True
    def execute(self, context):
        vmap = geotags.getCageDisplacementMap(context.object, forceCreation=True)
        context.object.vertex_groups.active = vmap
        return {"FINISHED"} 



classes = [GFLOW_OT_MakeCage, 
    GFLOW_OT_AddCageDisplacementMap,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass