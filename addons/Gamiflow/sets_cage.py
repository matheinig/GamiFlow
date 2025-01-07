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
   

    smoothNormalLayerName = "GFLOW_NORMAL"
    defaultSmoothnessFactor = 0.0
    if obj.gflow.cageHardness == 'SMOOTH':
        defaultSmoothnessFactor = 1.0
   
    # First split the edges that we want sharp
    # The standard hard mode will split on all sharp edges, the custom mode will split every single edge
    bpy.ops.object.mode_set(mode='EDIT')
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
        smoothNormalLayer = bm.verts.layers.float_vector.new(smoothNormalLayerName)
        for v in bm.verts:
            v[smoothNormalLayer] = v.normal
        
        if obj.gflow.cageHardness == 'HARD':
            for e in bm.edges:
                e.select_set(not e.smooth)
                print("YEP")
        elif obj.gflow.cageHardness == 'CUSTOM':
            for e in bm.edges:
                e.select_set(True)
    if obj.gflow.cageHardness != 'SMOOTH':
        bpy.ops.mesh.edge_split()
    bpy.ops.object.mode_set(mode='OBJECT')

    #Displace the verts
    offset = obj.gflow.cageOffset
    if offset==0.0: offset = context.scene.gflow.cageOffset
    with helpers.objectModeBmesh(obj) as bm:
        smoothNormalLayer = bm.verts.layers.float_vector.get(smoothNormalLayerName)  
        colorLayer = geotags.getCageHardnessLayer(bm, forceCreation=False)

        # colorLayer = bm.loops.layers.color.get('gflow_cage_hardness')
        for v in bm.verts:
            factor = defaultSmoothnessFactor
            if colorLayer and obj.gflow.cageHardness == 'CUSTOM': 
                loop = v.link_loops[0] # assume that at this point, all relevant edges have been split so loop 0 is fine
                factor = 1.0-loop[colorLayer][0] # only read red, rest currently irrelevant
            hardNormal = v.normal
            smoothNormal = v[smoothNormalLayer]
            interpolatedNormal = hardNormal.lerp(smoothNormal, factor)
            v.co += interpolatedNormal * offset
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

class GFLOW_OT_AddCageSharpnessMap(bpy.types.Operator):
    bl_idname      = "gflow.add_cage_sharpness_map"
    bl_label       = "Add map"
    bl_description = "Add a vertex color map to define cage sharpness"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.object: return False
        return True
    def execute(self, context):
        with helpers.objectModeBmesh(context.object) as bm:
            layer = geotags.getCageHardnessLayer(bm, forceCreation = True)
        context.object.data.attributes.active_color_name = geotags.GEO_LOOP_CAGE_HARDNESS_NAME
        context.object.data.attributes.render_color_index = context.object.data.attributes.active_color_index 
        
        return {"FINISHED"} 

classes = [GFLOW_OT_MakeCage, 
    GFLOW_OT_AddCageSharpnessMap
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass