import bpy
from . import uv
# Per object
class GFlowHighPolyItem(bpy.types.PropertyGroup):
    obj : bpy.props.PointerProperty(type=bpy.types.Object)

def udimItemGenerator(self,context):
    items = []
    for index, u in enumerate(context.scene.gflow.udims):
        items.append( (u.name, u.name, u.name, index) )
    return items
def onVisualUdimChange(self, context):
    value = self.textureSetEnum
    for i, u in enumerate(context.scene.gflow.udims):
        if u.name == value:
            self.textureSet = i
            return
def onCollectionChanged(self, context):
    # Make sure we have at least one UDIM
    if len(context.scene.gflow.udims) == 0:
        context.scene.gflow.udims.add()
        context.scene.gflow.udims[0].name = "UDIM_0"
    
gUV_UNWRAP_METHODS = [
        ("ANGLE_BASED", "Angle Based", "", 1),
        ("CONFORMAL", "Conformal", "", 2),
    ]
class GFlowObject(bpy.types.PropertyGroup):
    # UV mapping
    unwrap: bpy.props.BoolProperty(name="Auto Unwrap", default=True)
    unwrap_method: bpy.props.EnumProperty(default='ANGLE_BASED', items=gUV_UNWRAP_METHODS)
    unwrap_smooth_iterations : bpy.props.IntProperty(name="Smooth iterations", default=16, min=0, soft_max=100, description="How many smoothing iterations to perform")
    unwrap_smooth_strength : bpy.props.FloatProperty(name="Smooth strength", default=0.8, min=0.0, max=1.0, description="How much of the smoothing is applied") # Must be inverted when calling the minimize stretch operator
    textureSet : bpy.props.IntProperty(name="Texture set", default=0, min=0, soft_max=8, description="What texture set to use")
    textureSetEnum : bpy.props.EnumProperty(items = udimItemGenerator, name = 'Texture set', update=onVisualUdimChange)

    # Baking
    objType: bpy.props.EnumProperty(name="Type", default='STANDARD', items=[
        ("STANDARD", "Standard", "", 0),
        ("PROJECTED", "Projected", "An object used exclusively for baking, for example a sculpt", 1),
        ("DECAL", "Decal", "An object used exclusively for baking but without backfaces", 2),
        ("OCCLUDER", "Occluder", "An object used exclusively for baking, but only as a shadow caster", 3),
        ("IGNORED", "Ignored", "This object will be completely ignored", 4),
    ])
    bakeAnchor : bpy.props.PointerProperty(type=bpy.types.Object, name="Anchor")
    bakeGhost: bpy.props.BoolProperty(name="Leave ghost", default=False, description="If enabled, an occluder will be left behind in the high-poly")
    removeHardEdges: bpy.props.BoolProperty(name="Remove hard edges", default=True, description="Remove hard edges in the high-poly")
    includeSelf: bpy.props.BoolProperty(name="Include self", default=True, description="If the object should bake onto itself")
    highpolys: bpy.props.CollectionProperty(type=GFlowHighPolyItem)
    ui_selectedHighPoly : bpy.props.IntProperty(name="[UI] HP Index", default=0, description="Internal")


    # Export
    mergeWithParent: bpy.props.BoolProperty(name="Merge with parents", default=True)
    exportAnchor : bpy.props.PointerProperty(type=bpy.types.Object, name="Anchor", description="Transform used for the final object in the export set")

# Per scene
gUV_PACK_METHODS = [("FAST", "Fast", "", 0), ("REASONABLE", "Reasonable", "", 1), ("ACCURATE", "Accurate", "", 2)]
class GFlowUdim(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty(name="UDIM", default="Main")
    
class GFlowDisplay(bpy.types.PropertyGroup):
    uvGridification: bpy.props.BoolProperty(name="Gridification", default=True)
    uvScale: bpy.props.BoolProperty(name="Scale", default=True)
    detailEdges: bpy.props.BoolProperty(name="Details", default=True)    
    
class GFlowScene(bpy.types.PropertyGroup):
    # Sets
    workingCollection : bpy.props.PointerProperty(type=bpy.types.Collection, name="Working set", update=onCollectionChanged)
    painterLowCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    painterHighCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    exportCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    # UVs
    uvMargin : bpy.props.FloatProperty(name="Margin", subtype='FACTOR', default=16/2048,  precision=4, step=0.1, min=0.0, soft_max=0.1, description="Margin between UV islands")
    uvPackSettings :  bpy.props.EnumProperty(name="Packer", default='FAST', items=gUV_PACK_METHODS)
    uvScaleFactor: bpy.props.FloatProperty(name="Scale", subtype='FACTOR', default=1.0,  precision=2, step=0.1, min=0.0, soft_max=2.0, description="Island scale factor")
    # Udims
    udims: bpy.props.CollectionProperty(type=GFlowUdim)
    ui_selectedUdim : bpy.props.IntProperty(name="[UI] UDIM Index", default=0, description="Internal")
    
    # export
    exportTarget: bpy.props.EnumProperty(name="Target", default='UNITY', items=[
        ("UNITY", "FBX - Unity", "", 0),
        ("BLENDER", "FBX - Blender", "", 1),
        ("BLENDER_LIB", "Blender library", "Blender's asset library", 2),
    ])    
    exportAnimations: bpy.props.BoolProperty(name="Animation", default=True) 
    lightmapUvs: bpy.props.BoolProperty(name="Lightmap", default=False) 
    exportMethod: bpy.props.EnumProperty(name="Method", default='SINGLE', items=[
        ("SINGLE", "Single file", "One file is exported", 0),
        ("KIT", "Kit", "One file is exported for each root in the export set", 1),
    ])     
    
    # Overlays
    overlays : bpy.props.PointerProperty(type=GFlowDisplay, name="Overlays")
    


def register():
    bpy.utils.register_class(GFlowHighPolyItem)
    bpy.utils.register_class(GFlowObject)
    bpy.types.Object.gflow = bpy.props.PointerProperty(type=GFlowObject)
    
    bpy.utils.register_class(GFlowUdim)
    bpy.utils.register_class(GFlowDisplay)
    bpy.utils.register_class(GFlowScene)
    bpy.types.Scene.gflow = bpy.props.PointerProperty(type=GFlowScene)
        
    

def unregister():
    #del bpy.types.View3DOverlay.gflow
    #bpy.utils.unregister_class(GFlowDisplay)

    del bpy.types.Object.gflow
    bpy.utils.unregister_class(GFlowObject)
    bpy.utils.unregister_class(GFlowHighPolyItem)
    
    del bpy.types.Scene.gflow
    bpy.utils.unregister_class(GFlowScene)    
    bpy.utils.unregister_class(GFlowDisplay)
    bpy.utils.unregister_class(GFlowUdim)
    
    pass