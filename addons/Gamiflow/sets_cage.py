import bpy
from . import sets
from . import settings
from . import helpers
from . import geotags
from . import sets_low
from bpy.app.handlers import persistent
import mathutils
import os


CAGE_NODE_NAME = "Cage (GFlow)"

GFLOW_WasInWeightPaintMode = False
GFLOW_LastObject = None
msgSubscriber = object()

@persistent
def load_handler(dummy):
    # We have to subscribe at load time because the context doesn't exist during the plugin load time
    subscribeWeightPaintWatcher(msgSubscriber)
    
def subscribeWeightPaintWatcher(owner):
    #sub = bpy.types.Context, "mode" # doesn't seem to exist
    sub = bpy.types.Object, 'mode'
    bpy.msgbus.subscribe_rna(
        key = sub,
        owner=owner,
        args=(bpy.context,),
        notify=checkWeightPaintMode,
    )
    
    # TODO: also check for when changing weightmap

    
    # also check when changing object
    # Probably not useful since we probably can't switch active object in paint mode so disabled for now
    if False:
        sub = bpy.types.LayerObjects, "active"
        bpy.msgbus.subscribe_rna(
            key = sub,
            owner=owner,
            args=(bpy.context,),
            notify=checkObjectChange,
        )    

def checkObjectChange(context):
    global GFLOW_LastObject
    setCagePreview(GFLOW_LastObject, False)
    setCagePreview(context.object, context.mode == 'PAINT_WEIGHT')
    GFLOW_LastObject = context.object

def setCagePreview(obj, enabled):
    modifier = getCageModifier(obj)
    if modifier:
        id = modifier.node_group.interface.items_tree["Mode"].identifier            
        if enabled: modifier[id] = 2 # preview mode
        else: modifier[id] = 0  # passthrough

def checkWeightPaintMode(context):
    obj = context.object
    if not obj: return
    changed = False
    global GFLOW_WasInWeightPaintMode
    if GFLOW_WasInWeightPaintMode:
        # Check for when we leave the cage paint mode
        # Either we exit the wpaint mode
        if context.mode != 'PAINT_WEIGHT':
            GFLOW_WasInWeightPaintMode = False
            changed = True
        # Or we removed the weights
        if len(obj.vertex_groups) == 0:
            GFLOW_WasInWeightPaintMode = False
            changed = True        
        elif obj.vertex_groups.active.name != geotags.GEO_LOOP_CAGE_OFFSET_NAME: 
            # or we deselected them
            GFLOW_WasInWeightPaintMode = False
            changed = True                 
    else:
        # Check for when we enter
        if context.mode == 'PAINT_WEIGHT':
            if obj.vertex_groups.active and obj.vertex_groups.active.name == geotags.GEO_LOOP_CAGE_OFFSET_NAME:
                GFLOW_WasInWeightPaintMode = True
                changed = True
                
    if changed:
        modifier = getCageModifier(obj)
        setCagePreview(obj, GFLOW_WasInWeightPaintMode)
        pass
    return

def getObjectCageOffset(context, obj):
    value = obj.gflow.cageOffset
    if value == 0.0: value = context.scene.gflow.cageOffset
    return value
def getCageModifier(obj):
    for m in obj.modifiers:
        if m.type == 'NODES' and m.node_group and m.node_group.name == CAGE_NODE_NAME: return m
    return None
def addCageModifier(context, obj):
    modifier = getCageModifier(obj)
    if modifier is not None: return modifier

    # Load the cage modifier if it's not already found
    if CAGE_NODE_NAME not in bpy.data.node_groups.keys():
        folder = os.path.dirname(os.path.abspath(__file__))
        assetsFolder = os.path.join(folder, "assets")
        modifiersPath = str(os.path.join(assetsFolder, 'modifiers.blend'))
        with bpy.data.libraries.load(modifiersPath, link=True, relative=False) as (data_src, data_dst):
            data_dst.node_groups.append(CAGE_NODE_NAME)
            
    # Add the modifier to the object
    modifier = obj.modifiers.new(CAGE_NODE_NAME, "NODES")
    modifier.use_pin_to_last = True
    modifier.node_group = bpy.data.node_groups[CAGE_NODE_NAME]
    offset = getObjectCageOffset(context, obj)
    id = modifier.node_group.interface.items_tree["Offset"].identifier
    modifier[id] = offset    
    return modifier
def removeCageModifier(context, obj):
    modifier = getCageModifier(obj)
    if modifier:
        obj.modifiers.remove(modifier)

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterCageCollection
    name = sets.getSetName(context) + "_cage"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_06"
        context.scene.gflow.painterCageCollection = c    
    if c: c.name = name
    
    return c

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
        
        # Add the cage modifier if there wasn't one already
        cage = addCageModifier(context, newobj)
        # Make sure the cage is set to final mode
        id = cage.node_group.interface.items_tree["Mode"].identifier
        cage[id] = 1 
        

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
        addCageModifier(context, context.object)
        return {"FINISHED"} 

class GFLOW_OT_RemoveCageDisplacementMap(bpy.types.Operator):
    bl_idname      = "gflow.remove_cage_displacement_map"
    bl_label       = "Remove map"
    bl_description = "Remove the cage tightness weightmap."
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.object: return False
        return True
    def execute(self, context):
        vmap = geotags.getCageDisplacementMap(context.object, forceCreation=False)
        context.object.vertex_groups.remove(vmap)
        removeCageModifier(context, context.object)
        return {"FINISHED"}


classes = [GFLOW_OT_MakeCage, 
    GFLOW_OT_AddCageDisplacementMap, GFLOW_OT_RemoveCageDisplacementMap,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
        
    if load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_handler)
   
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
        
    if msgSubscriber is not None:
        bpy.msgbus.clear_by_owner(msgSubscriber)

    if load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_handler)        
    pass