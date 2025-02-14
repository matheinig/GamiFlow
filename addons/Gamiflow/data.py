import bpy
from . import uv
from . import sets
from . import display
from . import sets_cage

# Per object
class GFlowHighPolyItem(bpy.types.PropertyGroup):
    obj : bpy.props.PointerProperty(type=bpy.types.Object, name="High-poly")

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
def onEdgeOffsetChange(self, context):
    display.purgeCache()
def onCollectionChanged(self, context):
    # Make sure we have at least one UDIM
    if len(context.scene.gflow.udims) == 0:
        context.scene.gflow.udims.add()
        context.scene.gflow.udims[0].name = "UDIM_0"
def onCageOffsetChanged(self, context):
    cageModifier = sets_cage.getCageModifier(context.object)
    if cageModifier:
        value = self.cageOffset
        if value == 0.0: value = context.scene.gflow.cageOffset
        id = cageModifier.node_group.interface.items_tree["Offset"].identifier
        cageModifier[id] = value
        cageModifier.node_group.interface_update(context)
    return
def onDefaultCageOffsetChanged(self, context):
    if context.scene.gflow.workingCollection is None: return
    for o in context.scene.gflow.workingCollection.all_objects:
        if o.gflow.cageOffset == 0:
            cageModifier = sets_cage.getCageModifier(o)
            if cageModifier: 
                id = cageModifier.node_group.interface.items_tree["Offset"].identifier
                if cageModifier[id] != self.cageOffset:
                    cageModifier[id] = self.cageOffset
                    cageModifier.node_group.interface_update(context)
                
        
    
gUV_UNWRAP_METHODS = [
        ("ANGLE_BASED", "Angle Based", "", 1),
        ("CONFORMAL", "Conformal", "", 2),
        ("MINIMUM_STRETCH", "Minimum stretch", "", 3),
    ]
gUV_RESOLUTION = [        
        ("512",  "512",  "", 512),
        ("1024", "1024", "", 1024),
        ("2048", "2048", "", 2048),
        ("4096", "4096", "", 4096),
        ("8192", "8192", "", 8192),
    ]
gUV_MARGIN = [        
        ("2",  "2",  "", 2),
        ("4",  "4",  "", 4),
        ("8",  "8",  "", 8),
        ("16", "16", "", 16),
        ("32", "32", "", 32),
        ("64", "64", "", 64)
    ]    
    
class GFlowObject(bpy.types.PropertyGroup):
    registered: bpy.props.BoolProperty(name="Registered (internal)", description="just to track which objects are known", default=False)

    # export
    instanceType: bpy.props.EnumProperty(name="Instance", default='BOTH', items=[
        ("BAKE", "Bake", "This instance will be used only when baking", 0),
        ("EXPORT", "Export", "This instance will be used only when creating the final export set", 1),
        ("BOTH", "Bake/Export", "This instance will be used when baking and exporting", 2),
    ]) 


    # UV mapping
    unwrap: bpy.props.BoolProperty(name="Auto Unwrap", default=True)
    unwrap_method: bpy.props.EnumProperty(default='ANGLE_BASED', items=gUV_UNWRAP_METHODS)
    unwrap_extraParameter: bpy.props.IntProperty(name="Unwrap param", default=10, min=1, soft_max=20, description="Method-specific parameter")
    unwrap_smooth_iterations : bpy.props.IntProperty(name="Smooth iterations", default=0, min=0, soft_max=100, description="How many smoothing iterations to perform")
    unwrap_smooth_strength : bpy.props.FloatProperty(name="Smooth strength", default=0.8, min=0.0, max=1.0, description="How much of the smoothing is applied") # Must be inverted when calling the minimize stretch operator
    textureSet : bpy.props.IntProperty(name="UDIM", default=0, min=0, soft_max=8, description="What texture set to use")
    textureSetEnum : bpy.props.EnumProperty(items = udimItemGenerator, name = 'UDIM', update=onVisualUdimChange)

    # Baking
    objType: bpy.props.EnumProperty(name="Type", default='STANDARD', items=[
        ("STANDARD", "Standard", "", 0),
        ("PROJECTED", "Projected", "An object used exclusively for baking, for example a sculpt", 1),
        ("DECAL", "Decal (Deprecated ⚠️)", "Use Projected with single-sided faces instead.", 2),
        ("TRIM", "Trim", "A pre-made decal or trim sheet. This object is not processed by GamiFlow but will get exported.", 5),
        ("OCCLUDER", "Occluder", "An object used exclusively for baking, but only as a shadow caster", 3),
        ("IGNORED", "Ignored", "This object will be completely ignored", 4),
    ])
    instanceBake: bpy.props.EnumProperty(name="Instance in", default='LOW_HIGH', items=[
        ("NONE", "None", "", 0),
        ("LOW", "Low", "", 3),
        ("LOW_HIGH", "Low/High", "The instance will be added to the low and high-poly baking sets.", 1),
        ("HIGH", "High", "The instance will be added to the high-poly set.", 2),
    ])
    instancePriority: bpy.props.BoolProperty(name="Main instance", default=False, description="If you have multiple instances in the low set, it can be difficult to predict which one will actually be paintable. Set to True to force it to be this one.")
    bakeAnchor : bpy.props.PointerProperty(type=bpy.types.Object, name="Anchor")
    bakeGhost: bpy.props.BoolProperty(name="Leave ghost", default=False, description="If enabled, an occluder will be left behind in the high-poly")
    singleSided: bpy.props.BoolProperty(name="Single-sided", default=False, description="Treats surface as single-sided, which means the back faces will not cast AO")
    removeHardEdges: bpy.props.BoolProperty(name="Remove hard edges", default=True, description="Remove hard edges in the high-poly")
    includeSelf: bpy.props.BoolProperty(name="Include self", default=True, description="If the object should bake onto itself")
    highpolys: bpy.props.CollectionProperty(type=GFlowHighPolyItem)
    ui_selectedHighPoly : bpy.props.IntProperty(name="[UI] HP Index", default=0, description="Internal")
    
    cageOffset : bpy.props.FloatProperty(name="Cage offset", subtype='DISTANCE', default=0.0, min=0.0, soft_max=0.5, description="Per-object cage offset override. Leave at 0 to use the scene value instead.", update=onCageOffsetChanged)

    # Export
    instanceAllowExport: bpy.props.BoolProperty(name="Export Instance", default=True)
    mergeWithParent: bpy.props.BoolProperty(name="Merge with parents", default=True)
    exportAnchor : bpy.props.PointerProperty(type=bpy.types.Object, name="Anchor", description="Transform used for the final object in the export set")

# Per scene
gUV_PACK_METHODS = [("FAST", "Fast", "", 0), ("REASONABLE", "Reasonable", "", 1), ("ACCURATE", "Accurate", "", 2)]
class GFlowUdim(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty(name="UDIM", default="Main")
    # TODO: custom resolution and margin
    
class GFlowDisplay(bpy.types.PropertyGroup):
    mirroring: bpy.props.BoolProperty(name="Mirrors", default=True)
    uvGridification: bpy.props.BoolProperty(name="Gridification", default=True)
    uvScale: bpy.props.BoolProperty(name="Scale", default=True)
    detailEdges: bpy.props.BoolProperty(name="Details", default=True)  
    edgeOffset: bpy.props.FloatProperty(name="Edge offset", default=0.1, min=0.0, max=1.0, description="Pushes the edges outward to avoid clipping", update=onEdgeOffsetChange)
    
class GFlowScene(bpy.types.PropertyGroup):
    version : bpy.props.IntProperty(name="GamiFlow version", default=0, description="Internal version number")

    # Sets
    workingCollection : bpy.props.PointerProperty(type=bpy.types.Collection, name="Working set", update=onCollectionChanged)
    painterLowCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    painterHighCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    painterCageCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    exportCollection : bpy.props.PointerProperty(type=bpy.types.Collection)
    
    # Cage
    useCage : bpy.props.BoolProperty(name="Generate cage", default=False, description="If enabled, cage objects will generated")    
    cageOffset : bpy.props.FloatProperty(name="Default offset", subtype='DISTANCE', default=0.01, min=0.0, soft_max=0.5, update=onDefaultCageOffsetChanged, description="How much the cage mesh will be inflated")
    
    # UVs
    uvResolution : bpy.props.EnumProperty(name="Resolution", default='2048', items=gUV_RESOLUTION, description="Default resolution in pixels")
    uvMargin : bpy.props.EnumProperty(name="Margin", default='8', items=gUV_MARGIN, description="Margin between UV islands (in pixels)")
    uvSnap : bpy.props.BoolProperty(name="Snap", default=True, description="If enabled, UVs will be snapped to pixels")
    uvPackSettings :  bpy.props.EnumProperty(name="Packer", default='FAST', items=gUV_PACK_METHODS)
    uvScaleFactor: bpy.props.FloatProperty(name="Scale", subtype='FACTOR', default=1.0,  precision=2, step=0.1, min=0.0, soft_max=2.0, description="Island scale factor")
    
    # Udims
    udims: bpy.props.CollectionProperty(type=GFlowUdim)
    ui_selectedUdim : bpy.props.IntProperty(name="[UI] UDIM Index", default=0, description="Internal")
    mergeUdims: bpy.props.BoolProperty(name="Merge UDIMs", default=False, description="All objects will be treated as if part of the first UDIM.\nUseful if you want to experiment and check if you could get away with only one UDIM.") 
    
    # export
    exportTarget: bpy.props.EnumProperty(name="Target", default='UNITY', items=[
        ("UNITY", "FBX - Unity", "", 0),
        ("UNREAL", "FBX - Unreal", "", 3),
        ("BLENDER", "FBX - Blender", "", 1),
        ("BLENDER_LIB", "Blender library", "Blender's asset library", 2),
    ])
    exportFlip: bpy.props.BoolProperty(name="Reversed", default=False, description="Reverse the front and back directions") 
    exportAnimations: bpy.props.BoolProperty(name="Animation", default=True) 
    lightmapUvs: bpy.props.BoolProperty(name="Lightmap", default=False, description="Generate lightmap UVs for the export meshes") 
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