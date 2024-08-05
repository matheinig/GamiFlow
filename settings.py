import bpy
from . import data 


class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="This is a preferences view for our add-on")
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