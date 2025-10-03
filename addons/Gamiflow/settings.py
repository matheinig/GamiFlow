import bpy
from . import data 
from . import uv
import addon_utils

#BEGINTRIM -------------------------------------------------- 
def isDecalMachineAvailable():
    (default, current) = addon_utils.check("DECALmachine")
    return current    
def isDecalMachineEnabled(stgs):
    return stgs.useDecalMachine and isDecalMachineAvailable()
#ENDTRIM -----------------------------------------------------    

class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    workingsuffix : bpy.props.StringProperty(name = "Working", default = "_working", description="[Optional] If you don't want your export meshes to have the export suffix applied to them, you can instead suffix your working mesh and have the suffix removed in the export set.")
    hpsuffix : bpy.props.StringProperty(name = "High poly", default = "_high")
    lpsuffix : bpy.props.StringProperty(name = "Low poly", default = "_low")
    decalsuffix : bpy.props.StringProperty(name = "Decal", default = "_ignorebf")
    exportsuffix : bpy.props.StringProperty(name = "Export", default = "_e", description="Blender does not allow multiple objects to have the same name, so we have to suffix them with something else.")
    cageprefix : bpy.props.StringProperty(name = "Cage", default = "cage_")
    mergeExportMeshes : bpy.props.BoolProperty(name = "Auto merge", default=True, description="Collapses hierarchies when possible and when allowed")
    renameExportMeshes : bpy.props.BoolProperty(name = "Rename meshes", default=True, description="Renames meshes so that they have the same name as their object")
    
    baker : bpy.props.EnumProperty(
        name="Baker",
        description="Chose which UV packer to use",
        items=
        [
        ("BLENDER", "Blender", "The bake will be done internally by Blender which will be quite slow."),
        ("EXTERNAL", "External", "You want to bake everything in an external tool such as Painter or Toolbag."),
        ],
        default="EXTERNAL"
        )
        
    renameUVs: bpy.props.BoolProperty(name = "Rename UVs", default=True, description="Rename the active UV layer")
    uvName : bpy.props.StringProperty(name = "UV name", default = "UVMap")
        
#BEGINTRIM --------------------------------------------------
    uvPacker : bpy.props.EnumProperty(
        name="UV Packer",
        description="Chose which UV packer to use",
        items=
        [
        ("BLENDER", "Blender", "Native packer, can be quite slow"),
        ("UVPACKER", "UV-Packer", "Free plugin (must be installed separately). Very fast, very good quality."),
        ("PACKERIO", "Packer-IO", "Free plugin (must be installed separately). New version of UV-Packer."),
        ],
        default="BLENDER"
        )
    useMofUnwrapper : bpy.props.BoolProperty(name = "Use Ministry of Flat (MoF)", default=False, description="Enable the Ministry of Flat integration for automatic seams.")
    mofPath : bpy.props.StringProperty(name = "MoF path", default = "", subtype="FILE_PATH", description="Path to the folder containing UnWrapConsole3.exe")
    packerioPath: bpy.props.StringProperty(name = "Packer-IO path", default = "C:\Program Files\Packer-IO\Packer-IO.exe", subtype="FILE_PATH", description="Path to PackerIO.exe")
    useDecalMachine: bpy.props.BoolProperty(name = "Use DECALmachine", default=False, description="Enable the DECALmachine integration.")
#ENDTRIM -----------------------------------------------------           
    idMap : bpy.props.EnumProperty(
        name="ID Map",
        description="Where the ID is supposed to come from",
        items=
        [
        ("MATERIAL", "Material color", ""),
        ("VERTEX", "Vertex color", ""),
        ],
        default="VERTEX"
        )        
    
    edgeWidth : bpy.props.FloatProperty(name="Edge overlay width", default=2.5, min=0.1, max=4.0, description="Thickness of the edge overlay")
    detailEdgeColor : bpy.props.FloatVectorProperty(name='Detail edge', description='', default=(1, 1, 0, 0.85), subtype='COLOR', size=4)
    painterEdgeColor : bpy.props.FloatVectorProperty(name='Painter edge', description='', default=(0.5, 1, 0.2, 0.85), subtype='COLOR', size=4)
    cageEdgeColor : bpy.props.FloatVectorProperty(name='Cage edge', description='', default=(0.8, 0.7, 0.2, 0.85), subtype='COLOR', size=4)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.label(text="Naming convention")
        layout.prop(self, "workingsuffix")
        layout.prop(self, "lpsuffix")
        layout.prop(self, "hpsuffix")
        layout.prop(self, "decalsuffix")
        layout.prop(self, "exportsuffix")
        layout.prop(self, "cageprefix")
        
        layout.label(text="Working set")
#BEGINTRIM --------------------------------------------------     
        
        layout.prop(self, "useMofUnwrapper")
        row = layout.row()
        row.active = self.useMofUnwrapper
        row.prop(self, "mofPath")
        row = layout.row()
        row.active = self.useMofUnwrapper
        if self.useMofUnwrapper and not uv.isMofAvailable(self):
            row = layout.row()
            row.alert = True
            row.label(text="Ministry of Flat executable not found")
            row.operator("wm.url_open", text="Get Ministry of Flat").url = "https://www.quelsolaar.com/ministry_of_flat/"
        layout.prop(self, "uvPacker")
        if self.uvPacker == "UVPACKER" and not uv.isUvPackerAvailable():
            row = layout.row()
            row.alert = True
            row.label(text="UV-Packer plugin not found")
            row.operator("wm.url_open", text="Get UV-Packer").url = "https://www.uv-packer.com/download/"
        if self.uvPacker == "PACKERIO" and not uv.isUvPackerAvailable():
            row = layout.row()
            row.alert = True
            row.label(text="UV-Packer plugin not found")
            row.operator("wm.url_open", text="Get UV-Packer").url = "https://www.uv-packer.com/download/"            
                    
#ENDTRIM -----------------------------------------------------        
        layout.prop(self, "edgeWidth")
        layout.prop(self, "detailEdgeColor")
        layout.prop(self, "painterEdgeColor")
        layout.prop(self, "cageEdgeColor")
        
        layout.label(text="Baking sets")
        layout.prop(self, "baker")
        layout.prop(self, "idMap")
        
        layout.label(text="Export set")
        layout.prop(self, "mergeExportMeshes")
        layout.prop(self, "renameExportMeshes")
        row = layout.row(align=True)
        row.prop(self, "renameUVs")
        sub = row.row()
        sub.active = self.renameUVs
        sub.prop(self, "uvName", text="")
#BEGINTRIM --------------------------------------------------  
        row = layout.row()
        row.prop(self, "useDecalMachine")
        if self.useDecalMachine and not isDecalMachineAvailable():
            col = row.column()
            col.alert = True
            col.label(text="DECALmachine not found")        
#ENDTRIM -----------------------------------------------------      


classes = [AddonPreferences]

def getSettings():
    return bpy.context.preferences.addons[__package__].preferences

def register():
    for c in classes: 
        bpy.utils.register_class(c)

    pass
    
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
        
    pass