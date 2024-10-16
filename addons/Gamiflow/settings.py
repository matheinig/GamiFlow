import bpy
from . import data 
from . import uv

class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    hpsuffix : bpy.props.StringProperty(name = "High poly", default = "_high")
    lpsuffix : bpy.props.StringProperty(name = "Low poly", default = "_low")
    decalsuffix : bpy.props.StringProperty(name = "Decal", default = "_ignorebf")
    exportsuffix : bpy.props.StringProperty(name = "Export", default = "_e")
    
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
    
    edgeWidth : bpy.props.FloatProperty(name="Edge width", default=2.5, min=0.1, max=4.0, description="Thickness of the edge overlay")
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
        
        layout.prop(self, "uvPacker")
        layout.prop(self, "idMap")

        if self.uvPacker == "UVPACKER" and not uv.isUvPackerAvailable():
            row = layout.row()
            row.alert = True
            row.label(text="UV-Packer plugin not found")
            row.operator("wm.url_open", text="Get UV-Packer").url = "https://www.uv-packer.com/download/"
        
        layout.label(text="Overlay")
        
        layout.prop(self, "edgeWidth")
        layout.prop(self, "detailEdgeColor")
        layout.prop(self, "painterEdgeColor")
        
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