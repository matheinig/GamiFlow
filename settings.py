import bpy
from . import data 


class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    hpsuffix : bpy.props.StringProperty(name = "High poly", default = "_high")
    lpsuffix : bpy.props.StringProperty(name = "Low poly", default = "_low")
    decalsuffix : bpy.props.StringProperty(name = "Decal", default = "_ignorebf")
    exportsuffix : bpy.props.StringProperty(name = "Export", default = "_e")
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="Naming convention")
        layout.prop(self, "lpsuffix")
        layout.prop(self, "hpsuffix")
        layout.prop(self, "decalsuffix")
        layout.prop(self, "exportsuffix")
        
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