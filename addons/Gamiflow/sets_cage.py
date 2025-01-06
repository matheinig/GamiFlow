import bpy
from . import sets
from . import settings
from . import helpers
from . import geotags
from . import sets_low

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
   
   # TODO:
   # 1) either use the kdtree to lookup the original mesh vertices and their smooth normals
   #    or make a temporary geo field with the smooth normals before splitting
   # 2) then lerp between smooth normal and face normal based on user-painted weightmap
   
   # First split the edges that we want 'hard'
   # Currently using the standard blender sharpness, but maybe we need a custom one
    bpy.ops.object.mode_set(mode='EDIT')
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
        for e in bm.edges:
            e.select_set(not e.smooth)
    bpy.ops.mesh.edge_split()
    bpy.ops.object.mode_set(mode='OBJECT')

    #Displace the verts
    offset = obj.gflow.cageOffset
    if offset==0.0: offset = context.scene.gflow.cageOffset
    with helpers.objectModeBmesh(obj) as bm:
        for v in bm.verts:
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
    for o in lowCollection.all_objects:
        if not (o.type == 'MESH'): continue
        
        # Duplicate the lowpoly unless it has a user-defined cage already
        newobj = sets.duplicateObject(o, cageCollection, prefix=namePrefix) # TODO: should we also remove the _low suffix?
        newobj.display_type = 'WIRE'

        # Apply modifiers? (unless it's armature?)
        
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

classes = [GFLOW_OT_MakeCage,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass