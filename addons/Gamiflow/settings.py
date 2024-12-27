import bpy
from . import data 
from . import uv

class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    hpsuffix : bpy.props.StringProperty(name = "High poly", default = "_high")
    lpsuffix : bpy.props.StringProperty(name = "Low poly", default = "_low")
    decalsuffix : bpy.props.StringProperty(name = "Decal", default = "_ignorebf")
    exportsuffix : bpy.props.StringProperty(name = "Export", default = "_e")
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
    
    uvPacker : bpy.props.EnumProperty(
        name="UV Packer",
        description="Chose which UV packer to use",
        items=
        [
        ("BLENDER", "Blender", "Native packer, can be quite slow"),
        ("UVPACKER", "UV-Packer", "Free plugin (must be installed separately). Very fast, very good quality."),
        ],
        default="BLENDER"
        )
        
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
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        
        layout.label(text="Naming convention")
        layout.prop(self, "lpsuffix")
        layout.prop(self, "hpsuffix")
        layout.prop(self, "decalsuffix")
        layout.prop(self, "exportsuffix")
        
        layout.label(text="Working set")
#BEGINTRIM --------------------------------------------------     
        layout.prop(self, "uvPacker")
#ENDTRIM -----------------------------------------------------        
        layout.prop(self, "edgeWidth")
        layout.prop(self, "detailEdgeColor")
        layout.prop(self, "painterEdgeColor")
        
        layout.label(text="Baking sets")
        layout.prop(self, "baker")
        layout.prop(self, "idMap")
        
        layout.label(text="Export set")
        layout.prop(self, "mergeExportMeshes")
        layout.prop(self, "renameExportMeshes")
        
        
        
#BEGINTRIM -------------------------------------------------- 
        if self.uvPacker == "UVPACKER" and not uv.isUvPackerAvailable():
            row = layout.row()
            row.alert = True
            row.label(text="UV-Packer plugin not found")
            row.operator("wm.url_open", text="Get UV-Packer").url = "https://www.uv-packer.com/download/"
#ENDTRIM -----------------------------------------------------          
        
        #layout.prop(self, "my_property")
  

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