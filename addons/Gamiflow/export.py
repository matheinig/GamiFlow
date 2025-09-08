import bpy
from bpy_extras.io_utils import ExportHelper
import os
from . import sets_low
from . import sets_high
from . import sets
from . import helpers
from . import settings
from enum import Enum

class ExportType(Enum):
    BAKE_LOW = 1
    BAKE_HIGH = 2
    BAKE_CAGE = 3
    FINAL = 0


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

def exportCollection(context, collection, filename, fFormat, exportTarget = "UNITY", flip=False, exportType=ExportType.FINAL):
    exportObjects(context, collection.all_objects, filename, fFormat, exportTarget, flip, exportType=exportType)
    return
    
def exportTextureSets(context, collection, baseFilename, fFormat, exportType):
    for (i, texset) in enumerate(context.scene.gflow.udims):
        objs = [o for o in collection.all_objects if o.gflow.textureSet == i]
        exportObjects(context, objs, baseFilename+"_"+texset.name, fFormat, exportType=exportType)
    
def exportObjects(context, objects, filename, fFormat, exportTarget = "UNITY", flip=False, exportType=ExportType.FINAL):
    # select all relevant objects
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        helpers.setSelected(context, o)
    if fFormat == "FBX":
        exportselectedFbx(context, objects, filename, exportTarget = exportTarget, flip=flip, exportType=exportType)
    else:
        exportSelectedGltf(context, objects, filename, exportTarget = exportTarget, flip=flip, exportType=exportType)
    
def exportSelectedGltf(context, objects, filename, exportTarget = "UNITY", flip=False, exportType=ExportType.FINAL):
    bpy.ops.export_scene.gltf(
        filepath=filename+".gltf",
        use_selection = True,
        export_format = 'GLTF_SEPARATE',
        # Transforms
        export_yup = True,
        export_apply = True,
        # Mesh data
        export_texcoords=exportType is not ExportType.BAKE_HIGH, export_normals=True, 
        export_tangents=exportType is not ExportType.BAKE_HIGH, export_vertex_color='ACTIVE',
        # Materials
        export_materials = 'EXPORT',
    )
    
def exportselectedFbx(context, objects, filename, exportTarget = "UNITY", flip=False, exportType=ExportType.FINAL):
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
    
    tangents = True
    if exportType is ExportType.BAKE_HIGH or exportType is ExportType.BAKE_CAGE:
        tangents = False

    # Check if we have any shape keys to be exported
    # In which case we absolutely cannot apply the modifiers for some reason
    applyModifiers = True
    if exportType is ExportType.FINAL:
        for o in objects:
            if o.type == 'MESH' and o.data.shape_keys and len(o.data.shape_keys.key_blocks) > 0:
                applyModifiers = False
                print("GamiFlow: Cannot export with applied modifiers because of shape keys")
                break
    
    # Export
    bpy.ops.export_scene.fbx(
        filepath=filename+".fbx",
        use_selection=True,
        # Transforms
        global_scale = 1.0, apply_scale_options = 'FBX_SCALE_ALL', # Prevents 100x scale in Unity/Unreal
        bake_space_transform = False, axis_up = axisUp, axis_forward = axisForward,
        # Mesh data
        use_mesh_modifiers = applyModifiers, 
        use_tspace = tangents,
        colors_type = 'LINEAR',
        # Armatures and animation
        armature_nodetype = 'NULL',
        use_armature_deform_only = True,
        bake_anim = context.scene.gflow.exportAnimations,
        bake_anim_use_nla_strips = False, bake_anim_use_all_actions = True,
        bake_anim_use_all_bones = True, # Maybe not necessary, but probably safer. Will make fbx larger
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
            exportCollection(context, gflow.painterLowCollection, baseName+"_low", "FBX", ExportType.BAKE_LOW)
        if len(gflow.painterHighCollection.all_objects)>0:
            sets.setCollectionVisibility(context, gflow.painterHighCollection, True)
            exportCollection(context, gflow.painterHighCollection, baseName+"_high", "FBX", ExportType.BAKE_HIGH)
        
        if gflow.painterCageCollection and len(gflow.painterCageCollection.objects)>0:
            sets.setCollectionVisibility(context, gflow.painterCageCollection, True)
            # Because of the way painter matches the geometry, we have to export one cageper texture set
            exportTextureSets(context, gflow.painterCageCollection, baseName+"_cage", "FBX", ExportType.BAKE_CAGE)
        
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
            exportCollection(context, gflow.exportCollection, baseName, gflow.exportFormat, exportTarget=gflow.exportTarget, flip=gflow.exportFlip, exportType=ExportType.FINAL)
        # Kit export: each root object gets exported separately
        if gflow.exportMethod == 'KIT':
            roots = findRoots(gflow.exportCollection.objects)
            for o in roots:
                cleanname = o.name
                if cleanname.endswith(stgs.exportsuffix):
                    cleanname = cleanname[:-len(stgs.exportsuffix)]
                filename = os.path.join(folder, cleanname)
                objects = list(o.children_recursive)
                objects.append(o)
                exportObjects(context, objects, filename, gflow.exportFormat, exportTarget=gflow.exportTarget, flip=gflow.exportFlip, exportType=ExportType.FINAL)

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