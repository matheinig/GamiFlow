import bpy
from bpy_extras.io_utils import ExportHelper
import os
from . import sets_low
from . import sets_high
from . import sets
from . import helpers

def exportCollection(context, collection, filename):
    exportObjects(context, collection.all_objects, filename)
    return
    
def exportObjects(context, objects, filename):
    # select all relevant objects
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        helpers.setSelected(context, o)
       
    # old unity: bake space transform, up=Y, forward=-Z
       
    # Export
    bpy.ops.export_scene.fbx(
        filepath=filename+".fbx",
        use_selection=True,
        global_scale  = 1.0, apply_scale_options = 'FBX_SCALE_ALL',
        bake_space_transform  = False, axis_up = 'Z', axis_forward = 'Y',
        use_mesh_modifiers = True,
        use_tspace = True,
        armature_nodetype  = 'NULL',
        colors_type = 'LINEAR',
        bake_anim = context.scene.gflow.exportAnimations
        )
    return
    
class GFLOW_OT_ExportPainter(bpy.types.Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "gflow.export_painter" 
    bl_label = "Export"

    # ExportHelper mixin class uses this
    filename_ext = ".fbx"

    filter_glob: bpy.props.StringProperty(
        default="*.fbx",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.painterLowCollection: 
            cls.poll_message_set("Need to generate the Low set first")
            return False
        if not context.scene.gflow.painterHighCollection: 
            cls.poll_message_set("Need to generate the High set first")
            return False            
        return True
    def execute(self, context):
        name = sets.getSetName(context)
        folder = os.path.dirname(self.filepath)
        baseName = os.path.join(folder,name)

        sets.setCollectionVisibility(context, context.scene.gflow.painterLowCollection, True)
        exportCollection(context, sets_low.getCollection(context), baseName+"_low")
        sets.setCollectionVisibility(context, context.scene.gflow.painterHighCollection, True)
        exportCollection(context, sets_high.getCollection(context), baseName+"_high")
        return {'FINISHED'}

class GFLOW_OT_ExportFinal(bpy.types.Operator, ExportHelper):
    bl_idname = "gflow.export_final" 
    bl_label = "Export"

    # ExportHelper mixin class uses this
    filename_ext = ".fbx"

    filter_glob: bpy.props.StringProperty(
        default="*.fbx",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.exportCollection: 
            cls.poll_message_set("Need to generate the Export set first")
            return False
         
        return True
    def execute(self, context):
        name = sets.getSetName(context)
        folder = os.path.dirname(self.filepath)
        

        collection = context.scene.gflow.exportCollection
        sets.setCollectionVisibility(context, collection, True)
        
        # Simple export
        if context.scene.gflow.exportMethod == 'SINGLE':
            baseName = os.path.join(folder,name)
            exportCollection(context, context.scene.gflow.exportCollection, baseName)
        # Kit export: each root object gets exported separately
        if context.scene.gflow.exportMethod == 'KIT':
            for o in context.scene.gflow.exportCollection.objects:
                filename = os.path.join(folder, o.name)
                exportObjects(context, o.children_recursive, filename)

        return {'FINISHED'}
  
classes = [GFLOW_OT_ExportPainter, GFLOW_OT_ExportFinal,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass