import bpy
from bpy_extras.io_utils import ExportHelper
import os
from . import sets_low
from . import sets_high
from . import sets
from . import helpers
from . import settings

def getAxis(baseAxis, flipped):
    if flipped:
        dic = {  "X": "-X", 
                "-X":  "X",
                 "Y": "-Y",
                "-Y":  "Y",
                 "Z": "-Z",
                "-Z":  "Z"}
        return dic[baseAxis]
    return baseAxis

def exportCollection(context, collection, filename, fFormat, exportTarget = "UNITY", flip=False, isHighPoly=False):
    exportObjects(context, collection.all_objects, filename, fFormat, exportTarget, flip, isHighPoly=isHighPoly)
    return
    
def exportTextureSets(context, collection, baseFilename, fFormat):
    for (i, texset) in enumerate(context.scene.gflow.udims):
        objs = [o for o in collection.all_objects if o.gflow.textureSet == i]
        exportObjects(context, objs, baseFilename+"_"+texset.name, fFormat)
    
def exportObjects(context, objects, filename, fFormat, exportTarget = "UNITY", flip=False, isHighPoly=False):
    # select all relevant objects
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        helpers.setSelected(context, o)
    if fFormat == "FBX":
        exportselectedFbx(context, objects, filename, exportTarget = exportTarget, flip=flip, isHighPoly=isHighPoly)
    else:
        exportSelectedGltf(context, objects, filename, exportTarget = exportTarget, flip=flip, isHighPoly=isHighPoly)
    
def exportSelectedGltf(context, objects, filename, exportTarget = "UNITY", flip=False, isHighPoly=False):
    bpy.ops.export_scene.gltf(
        filepath=filename+".gltf",
        use_selection = True,
        export_format = 'GLTF_SEPARATE',
        # Transforms
        export_yup = True,
        export_apply = True,
        # Mesh data
        export_texcoords=not isHighPoly, export_normals=True, export_tangents=not isHighPoly, export_vertex_color='ACTIVE',
        # Materials
        export_materials = 'EXPORT',
    )
    
def exportselectedFbx(context, objects, filename, exportTarget = "UNITY", flip=False, isHighPoly=False):
    # Defaults for modern Unity
    axisForward = getAxis('Y', flip)
    axisUp = 'Z'
       
    # old unity: bake space transform, up=Y, forward=-Z
    
    
    # Unreal: X is forward
    if exportTarget == "UNREAL":
        axisForward= getAxis('X', flip)

    if exportTarget == "SKETCHFAB":
        axisForward = getAxis('-Z', flip)
        axisUp = 'Y'
    
    # Export
    bpy.ops.export_scene.fbx(
        filepath=filename+".fbx",
        use_selection=True,
        # Transforms
        global_scale = 1.0, apply_scale_options = 'FBX_SCALE_ALL', # Prevents 100x scale in Unity/Unreal
        bake_space_transform = False, axis_up = axisUp, axis_forward = axisForward,
        # Mesh data
        use_mesh_modifiers = True,
        use_tspace = not isHighPoly,
        colors_type = 'LINEAR',
        # Armatures and animation
        armature_nodetype = 'NULL',
        use_armature_deform_only = True,
        bake_anim = context.scene.gflow.exportAnimations,
        bake_anim_use_all_bones = True, # Maybe not necessary, but probably safer. Will make fbx larger
        bake_anim_use_all_actions = False,
        bake_anim_simplify_factor = 0.0,
        
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
        gflow = context.scene.gflow
        if len(gflow.painterLowCollection.all_objects)>0:
            sets.setCollectionVisibility(context, gflow.painterLowCollection, True)
            exportCollection(context, gflow.painterLowCollection, baseName+"_low", "FBX")
        if len(gflow.painterHighCollection.all_objects)>0:
            sets.setCollectionVisibility(context, gflow.painterHighCollection, True)
            exportCollection(context, gflow.painterHighCollection, baseName+"_high", "FBX", isHighPoly=True)
        
        if gflow.painterCageCollection and len(gflow.painterCageCollection.objects)>0:
            sets.setCollectionVisibility(context, gflow.painterCageCollection, True)
            # Because of the way painter matches the geometry, we have to export one cageper texture set
            exportTextureSets(context, gflow.painterCageCollection, baseName+"_cage", "FBX")
        
        return {'FINISHED'}

def findRoots(objectsList):
    roots = [o for o in objectsList if o.parent is None]
    return roots


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
        stgs = settings.getSettings()

        gflow = context.scene.gflow

        collection = gflow.exportCollection
        sets.setCollectionVisibility(context, collection, True)
        
        # Simple export
        if gflow.exportMethod == 'SINGLE':
            baseName = os.path.join(folder,name)
            exportCollection(context, gflow.exportCollection, baseName, gflow.exportFormat, exportTarget=gflow.exportTarget, flip=gflow.exportFlip)
        # Kit export: each root object gets exported separately
        if gflow.exportMethod == 'KIT':
            roots = findRoots(gflow.exportCollection.objects)
            for o in roots:
                cleanname = o.name.strip(stgs.exportsuffix)
                filename = os.path.join(folder, cleanname)
                objects = list(o.children_recursive)
                objects.append(o)
                exportObjects(context, objects, filename, gflow.exportFormat, exportTarget=gflow.exportTarget, flip=gflow.exportFlip)

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