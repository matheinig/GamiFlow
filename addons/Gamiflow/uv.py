import bpy
import bmesh
import mathutils
import math
import addon_utils
import importlib  
import platform, os, subprocess, queue
from bpy_extras.bmesh_utils import bmesh_linked_uv_islands
from . import geotags
from . import helpers
from . import sets
from . import settings

def isUvPackerAvailable():
    (default, current) = addon_utils.check("UV-Packer")
    return current

def hardenSeams(context, obj):
    return

def findOrientationEdgeInIsland(faces, layer):
    for face in faces:
        for edge in face.edges:
            if edge[layer] != geotags.GEO_EDGE_UV_ROTATION_NEUTRAL: return edge
    return None
def make_rotation_transformation(angle, origin=(0, 0)):
    cos_theta, sin_theta = math.cos(angle), math.sin(angle)
    x0, y0 = origin    
    def xform(point):
        x, y = point[0] - x0, point[1] - y0
        return (x * cos_theta - y * sin_theta + x0,
                x * sin_theta + y * cos_theta + y0)
    return xform
    
# Potentially orients UV islands based on a tagged edge
def orientUv(context, obj):
    anythingRotated = False
    with helpers.editModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active  
        orientLayer = geotags.getUvOrientationLayer(bm, forceCreation=False)
        if orientLayer:
            # Clean slate
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='DESELECT')  
            
            # Check every island for tagged edge
            islands = bmesh_linked_uv_islands(bm, uv_layer)
            for island in islands:
                rotatorEdge = findOrientationEdgeInIsland(island, orientLayer)
                if not rotatorEdge: continue
                
                # Find by how much we need to rotate the current edge
                pt0 = rotatorEdge.link_loops[0][uv_layer].uv
                pt1 = rotatorEdge.link_loops[0].link_loop_next[uv_layer].uv 
                v = (pt0-pt1).normalized()
                targetAngle = math.radians((rotatorEdge[orientLayer]-1)*90.0)                
                currentAngle = math.atan2(v.x, v.y)
                rotationAngle = currentAngle-targetAngle

                # Perform the UV rotation
                if rotationAngle != 0:
                    anythingRotated = True
                    rotationMatrix = make_rotation_transformation(rotationAngle, pt0)
                    for f in island:
                        for l in f.loops:
                            l[uv_layer].uv = rotationMatrix(l[uv_layer].uv)
            #endfor islands

            # Delete the ortientation layer if it was empty
            if not anythingRotated: geotags.removeUvOrientationLayer(bm)
            
    # Upload the mesh changes
    if anythingRotated: bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False) 
                
    return anythingRotated
     
# Makes a nice UV grid from tagged faces if any (supports non-grid bits too)
def straightenUv(context, obj):
    with helpers.editModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        gridifyLayer = geotags.getGridifyLayer(bm, forceCreation=False)
        if gridifyLayer:
            # Clean slate
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='DESELECT')     
            
            somethingFound = False
            
            islands = bmesh_linked_uv_islands(bm, uv_layer)
            for island in islands:
                # Explore the mesh and select the reference face
                mainFace = None
                gridFaces = []
                forbiddenFaces = []
                for f in island:
                    if f[gridifyLayer] == geotags.GEO_FACE_GRIDIFY_INCLUDE: 
                        gridFaces.append(f)
                        somethingFound = True
                        # Use the first quad as our starting point
                        if mainFace is None and len(f.edges) == 4:
                            mainFace = f
                            mainFace.select = True
                            bm.faces.active = mainFace
                    elif f[gridifyLayer] == geotags.GEO_FACE_GRIDIFY_EXCLUDE: 
                        forbiddenFaces.append(f)
                
                # No relevant quad found, we can ignore the island
                if mainFace is None: continue
                    
                # Find the side lengths
                points = []
                for loop in mainFace.loops:
                    uv = loop[uv_layer].uv
                    points.append(uv)
                lengths = []
                for index, p in enumerate(points):
                    pt0 = points[index]
                    pt1 = points[(index+1) % (len(points)-1)]
                    l =  (pt1-pt0).length
                    lengths.append(l)
                    
                ### Doesn't work great with uneven quad sizes
                # Average the sides a bit (maybe optional?)
                #lengths[0] = (lengths[0] + lengths[2])*0.5
                #lengths[1] = (lengths[1] + lengths[3])*0.5
                
                # Turn the main face into a proper rectangle
                currentPt = mainFace.loops[0][uv_layer].uv
                currentPt = currentPt + mathutils.Vector( (lengths[0], 0.0) )
                mainFace.loops[1][uv_layer].uv = currentPt
                currentPt = currentPt + mathutils.Vector( (0.0, -lengths[1]) )
                mainFace.loops[2][uv_layer].uv = currentPt    
                currentPt = currentPt + mathutils.Vector( (-lengths[0], 0.0) )
                mainFace.loops[3][uv_layer].uv = currentPt

                # Upload the mesh changes
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False) 
                
                # Select all gridifiable faces
                for f in gridFaces: f.select = True
                    
                # Gridify
                backup_uvSync = context.scene.tool_settings.use_uv_select_sync
                context.scene.tool_settings.use_uv_select_sync = False
                bpy.ops.uv.follow_active_quads()
                context.scene.tool_settings.use_uv_select_sync = backup_uvSync
                
                # If we had non-gridifiables we have to unwrap them
                # TODO: Blender is not super reliable and might occasionally unwrap into a brand new island
                #       Maybe we can unpin the edges between the gridified and ungridified regions to make it happier
                if len(forbiddenFaces)>0:
                    # Pin the gridifiable quads
                    bpy.ops.uv.pin(clear=False)
                    # Unwrap everything in the island
                    bpy.ops.mesh.select_linked(delimit={'SEAM'})
                    bpy.ops.uv.unwrap(method=obj.gflow.unwrap_method, margin=0.001)
                    # Unpin
                    bpy.ops.uv.pin(clear=True)

                bpy.ops.mesh.select_all(action='DESELECT')
            #endfor layers
            
            # Remove unused gridify layer if need be
            if not somethingFound: geotags.removeGridifyLayer(bm)
    return

def autoUnwrap(context):
    # Make sure the working set is enabled and hide the rest for clarity
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.painterLowCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterHighCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.exportCollection, False)
    
    # Go through all udims and unwrap them
    for texset in range(0, len(context.scene.gflow.udims)): 
        # Gather all objects
        obj = [o for o in context.scene.gflow.workingCollection.all_objects if o.type == 'MESH' and o.gflow.textureSet == texset]

        # Unwrap individual objects
        unwrap(context, obj)
        # Pack everything together
        pack(context, obj, context.scene.gflow.uvPackSettings)

def lightmapUnwrap(context, objects):
    # Sanitise the list
    meshes = []
    obj = []
    for o in objects:
        if o.type != 'MESH': continue # Only real meshes can be unwrapped
        if o.data in meshes: continue # Make sure we only allow one instance of a mesh
        meshes.append(o.data)
        obj.append(o)
        

    # Make sure all objects have a new UV layer and that it's active
    for o in obj:
        if 'UVLightMap' not in o.data.uv_layers:
            uv = o.data.uv_layers.new(name='UVLightMap')
        o.data.uv_layers['UVLightMap'].active = True

    # Everything gets packed into the same lightmap UV regardless of the UDIM
    ## Not sure if that's for the best
    ## Also do we even care about all the custom scale and orientation?
    unwrap(context, obj)
    pack(context, obj, context.scene.gflow.uvPackSettings)

def unwrap(context, objects):
    bpy.ops.object.select_all(action='DESELECT')

    for o in objects:
        if o.type != 'MESH': continue
        if not o.gflow.unwrap: continue
        if o.gflow.objType  != 'STANDARD': continue
        
        o.select_set(True)
        context.view_layer.objects.active = o
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.mesh.reveal(select=False)

        # Unwrap
        bpy.ops.uv.unwrap(method=o.gflow.unwrap_method, margin=0.001)
        
        # Smooth if needed
        if o.gflow.unwrap_smooth_iterations>0:
            bpy.ops.uv.minimize_stretch(blend=1.0-o.gflow.unwrap_smooth_strength, iterations=o.gflow.unwrap_smooth_iterations)
        
        # Straighten if needed
        straightenUv(context, o)
                    
        bpy.ops.object.mode_set(mode='OBJECT')
        
        o.select_set(False)
    bpy.ops.object.select_all(action='DESELECT')


def pack(context, objects, packMethod = 'FAST'):
    shapeMethod = 'AABB'
    rotateMethod = 'AXIS_ALIGNED' # Fast and pretty good
    if packMethod == 'ACCURATE':
        shapeMethod = 'CONCAVE'
        rotateMethod = 'ANY'
    elif packMethod == 'REASONABLE':
        shapeMethod = 'CONCAVE'
        rotateMethod = 'AXIS_ALIGNED'

    resolution = int(context.scene.gflow.uvResolution)
    margin = int(context.scene.gflow.uvMargin) / resolution

    # Select all the relevant meshes
    relevant = []
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        if o.type != 'MESH': continue
        if o.gflow.objType  != 'STANDARD': continue
        o.select_set(True)
        context.view_layer.objects.active = o
        relevant.append(o)

    # Select the UVs
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    # Deal with the scale
    ## First average everything
    bpy.ops.uv.average_islands_scale()
    ## Then rescale individual islands based on user values
    for o in relevant:
        rescaleIslandsIfNeeded(o)
    bpy.ops.object.mode_set(mode='OBJECT')

    
    # Actual packing
    bpy.ops.object.mode_set(mode='EDIT')
    ## Pack into [0,1]
    generic_pack_island(context, margin=margin, shape_method=shapeMethod, rotate=True, rotate_method=rotateMethod)
    ## Go through individual objects and orient the islands
    anythingRotated = False
    for o in relevant:
        o.select_set(True)
        context.view_layer.objects.active = o
        anythingRotated = orientUv(context, o) or anythingRotated
    ## Repack but without allowing rotation if anything has been manually rotated
    if anythingRotated:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        generic_pack_island(context, margin=margin, shape_method=shapeMethod, rotate=False, rotate_method=rotateMethod)

    # Snap UVs to pixels
    if context.scene.gflow.uvSnap:
        for o in relevant:
            snapUv(o, resolution)
    
    # Exit
    bpy.ops.object.mode_set(mode='OBJECT')
    pass
def generic_pack_island(context, margin, shape_method, rotate, rotate_method):
    if settings.getSettings().uvPacker == "BLENDER":
        bpy.ops.uv.pack_islands(margin=margin, margin_method='FRACTION', shape_method=shape_method, rotate=rotate, rotate_method=rotate_method)
    else:
        uvpacker_pack_island(context=context, margin=margin, rotate=rotate, rotate_method=rotate_method)
    return
def uvpacker_pack_island(context, margin, rotate, rotate_method):
    props = context.scene.UVPackerProps
    props.uvp_selection_only = False
    props.uvp_rescale = False
    props.uvp_width = int(context.scene.gflow.uvResolution)
    props.uvp_height = props.uvp_width
    props.uvp_padding = int(margin * props.uvp_width)
    props.uvp_prerotate = rotate
    if rotate:
        if rotate_method == 'AXIS_ALIGNED': 
            props.uvp_rotate = "1"
            props.uvp_fullRotate = False
        if rotate_method == 'ANY': 
            props.uvp_fullRotate = True
    else:
        props.uvp_rotate = "0"
        props.uvp_fullRotate = False
    
    pack_uvpacker(context)
    return
    
def snapUv(obj, resolution):
    with helpers.editModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        for face in bm.faces:
            for loop in face.loops:
                uv = loop[uv_layer].uv
                pixel = uv * resolution
                pixel[0] = round(pixel[0])
                pixel[1] = round(pixel[1])
                uv = pixel / resolution
                loop[uv_layer].uv = uv
    return     

def rescaleIslandsIfNeeded(obj):
    with helpers.editModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        uvScaleLayer = geotags.getUvScaleLayer(bm, forceCreation=False)
        if not uvScaleLayer: return
        neutralCode = geotags.getUvScaleCode(1.0)
        for face in bm.faces:
            if face[uvScaleLayer] == neutralCode: continue
            scale = geotags.getUvScaleFromCode(face[uvScaleLayer])
            for loop in face.loops:
                loop[uv_layer].uv = loop[uv_layer].uv * scale    


class GFLOW_OT_AutoUnwrap(bpy.types.Operator):
    bl_idname      = "gflow.auto_unwrap"
    bl_label       = "Unwrap"
    bl_description = "Automatically unwrap everything"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if context.mode != "OBJECT": return False
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):
        autoUnwrap(context)
        
        return {"FINISHED"}  

# Set/unset gridification
class GFLOW_OT_SetGridify(bpy.types.Operator):
    bl_idname      = "gflow.uv_gridify"
    bl_label       = "Gridify"
    bl_description = "Mark faces as gridifiable"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[2]: 
            cls.poll_message_set("Must be in face mode")
            return False
        return context.object is not None

    def execute(self, context):
        obj = context.object
        
        nonQuadFound = False
        with helpers.editModeBmesh(obj) as bm:
            gridifyLayer = geotags.getGridifyLayer(bm, forceCreation=True)
            for face in bm.faces:
                if face.select: 
                    if len(face.edges) == 4: face[gridifyLayer] = geotags.GEO_FACE_GRIDIFY_INCLUDE
                    else: nonQuadFound = True
        if nonQuadFound:
            self.report({'WARNING'}, 'Gridification: Non-quad faces were ignored')
        return {"FINISHED"} 
class GFLOW_OT_DeGridify(bpy.types.Operator):
    bl_idname      = "gflow.uv_degridify"
    bl_label       = "Gridify"
    bl_description = "Mark selected faces as non-gridifiable"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[2]: 
            cls.poll_message_set("Must be in face mode")
            return False
        return context.object is not None

    def execute(self, context):
        obj = context.object
        
        with helpers.editModeBmesh(obj) as bm:
            gridifyLayer = geotags.getGridifyLayer(bm, forceCreation=True)
            for face in bm.faces:
                if face.select: face[gridifyLayer] = geotags.GEO_FACE_GRIDIFY_EXCLUDE
            # maybe check if no grid faces left
    
        return {"FINISHED"}  
        
# Temporary until we have overlays
class GFLOW_OT_SelectGridify(bpy.types.Operator):
    bl_idname      = "gflow.uv_select_gridify"
    bl_label       = "Select"
    bl_description = "TEST"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.IntProperty(default=1, min=-1, max=1)

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        return context.object is not None

    def execute(self, context):
        obj = context.object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table() 
    
        gridifyLayer = geotags.getGridifyLayer(bm, forceCreation=False)
        if not gridifyLayer: return {"ABORTED"}
        
        for face in bm.faces:
            face.select = face[gridifyLayer] == self.target
    
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False) 
        bm.free()        

        return {"FINISHED"}  







# Set orientation
def setEdgesOrientation(editMeshObj, orientationCode):
    with helpers.editModeBmesh(editMeshObj) as bm:
        layer = geotags.getUvOrientationLayer(bm, forceCreation=True)
        for edge in bm.edges:
            if edge.select: 
                edge[layer] = orientationCode
                
class GFLOW_OT_SetUvOrientationVertical(bpy.types.Operator):
    bl_idname      = "gflow.uv_orient_vertical"
    bl_label       = "Orient Vertical"
    bl_description = "Set the UV orientation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.object is not None

    def execute(self, context):
        for o in context.selected_objects:
            setEdgesOrientation(o, geotags.GEO_EDGE_UV_ROTATION_VERTICAL)
        return {"FINISHED"} 
class GFLOW_OT_SetUvOrientationHorizontal(bpy.types.Operator):
    bl_idname      = "gflow.uv_orient_horizontal"
    bl_label       = "Orient Horizontal"
    bl_description = "Set the UV orientation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.object is not None

    def execute(self, context):
        for o in context.selected_objects:
            setEdgesOrientation(o, geotags.GEO_EDGE_UV_ROTATION_HORIZONTAL)
        return {"FINISHED"} 
class GFLOW_OT_SetUvOrientationNeutral(bpy.types.Operator):
    bl_idname      = "gflow.uv_orient_neutral"
    bl_label       = "Orient Neutral"
    bl_description = "Set the UV orientation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[1]: 
            cls.poll_message_set("Must be in edge mode")
            return False
        return context.object is not None

    def execute(self, context):
        for o in context.selected_objects:
            setEdgesOrientation(o, geotags.GEO_EDGE_UV_ROTATION_NEUTRAL)
        return {"FINISHED"} 

# Scale
class GFLOW_OT_SetUvIslandScale(bpy.types.Operator):
    bl_idname      = "gflow.set_uv_scale"
    bl_label       = "Set scale"
    bl_description = "Set the relative UV scale"
    bl_options = {"REGISTER", "UNDO"}

    scale : bpy.props.FloatProperty(name="Scale", default=0, min=0, soft_max=2, description="Scale factor")

    @classmethod
    def poll(cls, context):
        if context.mode != "EDIT_MESH": return False
        if not context.tool_settings.mesh_select_mode[2]: 
            cls.poll_message_set("Must be in face mode")
            return False
        return context.object is not None

    def execute(self, context):
        bpy.ops.mesh.select_linked(delimit={'SEAM'})
        with helpers.editModeBmesh(context.edit_object) as bm:
            uvScaleLayer = geotags.getUvScaleLayer(bm, forceCreation=True)
            scaleCode = geotags.getUvScaleCode(self.scale)
            for face in bm.faces:
                if face.select: 
                    face[uvScaleLayer] = scaleCode
        return {"FINISHED"} 

class GFLOW_OT_AddUdim(bpy.types.Operator):
    bl_idname      = "gflow.add_udim"
    bl_label       = "Add UDIM"
    bl_description = "Add a new UDIM"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.gflow.udims.add()
        context.scene.gflow.ui_selectedUdim = len(context.scene.gflow.udims)-1
        context.scene.gflow.udims[context.scene.gflow.ui_selectedUdim].name = "UDIM_"+str(context.scene.gflow.ui_selectedUdim)
        return {"FINISHED"} 
class GFLOW_OT_RemoveUdim(bpy.types.Operator):
    bl_idname      = "gflow.remove_udim"
    bl_label       = "Remove UDIM"
    bl_description = "Remove the selected UDIM"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if len(context.scene.gflow.udims) <= 1:
            cls.poll_message_set("Need at least one UDIM")
            return False
        return True
    def execute(self, context):
        context.scene.gflow.udims.remove(context.scene.gflow.ui_selectedUdim)
        context.scene.gflow.ui_selectedUdim = min( context.scene.gflow.ui_selectedUdim, len(context.scene.gflow.udims)-1)
        return {"FINISHED"}    

class GFLOW_OT_SetToCurrentUdim(bpy.types.Operator):
    bl_idname      = "gflow.set_to_current_udim"
    bl_label       = "Set UDIM"
    bl_description = "Apply selected UDIM to object"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        return True
    def execute(self, context):
        context.object.gflow.textureSet = context.scene.gflow.ui_selectedUdim

        return {"FINISHED"}    

def udimItemGenerator(self,context):
    items = []
    for index, u in enumerate(context.scene.gflow.udims):
        items.append( (u.name, u.name, u.name, index) )
    return items
def findUdimId(context, name):
    for i, u in enumerate(context.scene.gflow.udims):
        if u.name==name: return i
    return None
    
class GFLOW_OT_ShowUv(bpy.types.Operator):
    bl_idname      = "gflow.show_uv"
    bl_label       = "Show UV"
    bl_description = "Show the UVs for a given texture set"
    bl_options = {"REGISTER", "UNDO"}
    
    textureSetEnum : bpy.props.EnumProperty(items = udimItemGenerator, name = 'Texture set')
    
    @classmethod
    def poll(cls, context):
        return True
    def execute(self, context):
        sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, True)
    
        # find the right udim id
        udim = findUdimId(context, self.textureSetEnum)
        bpy.ops.object.select_all(action='DESELECT')

        # Find the relevant objects
        objects = []
        meshes = []
        for o in context.scene.gflow.workingCollection.all_objects:
            if o.type != 'MESH': continue
            if o.gflow.objType != 'STANDARD': continue
            if o.gflow.textureSet != udim: continue
            if o.data in meshes: continue # Make sure we don't allow the same mesh twice
            meshes.append(o.data)
            objects.append(o)

        for o in objects:
            o.select_set(True)
            context.view_layer.objects.active = o
            
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.mesh.reveal(select=False)
    
        bpy.context.window.workspace = bpy.data.workspaces["UV Editing"]
        

        return {"FINISHED"}         

# UV-Packer backend
uvPacker = None
def getUvPacker():
    global uvPacker
    if uvPacker is None:
        # UV-Packer unfortunately has a dash in its name making it awkward to import
        uvPacker = importlib.import_module("UV-Packer")
    return uvPacker

def pack_uvpacker(context):
    # UV-Packer is difficult to call externally because all we have is a modal operator.
    # So instead we have to manually call the exe

    uvPacker = getUvPacker()
    
    unique_objects = uvPacker.misc.get_unique_objects(context.selected_objects)
    meshes = uvPacker.misc.get_meshes(unique_objects)
    if len(meshes) == 0: return

    packer_props = context.scene.UVPackerProps

    if packer_props.uvp_create_channel:
        uvPacker.misc.set_map_name(packer_props.uvp_channel_name)
        uvPacker.misc.add_uv_channel_to_objects(unique_objects)

    options = {
      "PackMode": uvPacker.misc.resolve_engine(packer_props.uvp_engine),
      "Width": packer_props.uvp_width,
      "Height": packer_props.uvp_height,
      "Padding": packer_props.uvp_padding,
      "Rescale": packer_props.uvp_rescale,
      "PreRotate": packer_props.uvp_prerotate,
      "Rotation": int(packer_props.uvp_rotate),
      "FullRotation": packer_props.uvp_fullRotate,
      "Combine": True,
      "TilesX": 1,
      "TilesY": 1,
      "Selection": False
    }

    packerDir = "/Applications/UV-Packer-Blender.app/Contents/MacOS/"
    packerExe = "UV-Packer-Blender"
    if (platform.system() == 'Windows'):
        packerDir = os.path.dirname(os.path.realpath(uvPacker.__file__))
        packerExe = packerExe + ".exe"

    process = None
    try:
        process = subprocess.Popen([packerDir + "/" + packerExe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=False)
    except:
        print('UV-Packer executable not found in "' + packerDir + '". Please check the Documentation for installation information.')
        return

    msg_queue = queue.SimpleQueue()
    uvPacker.misc.data_exchange_thread(process, options, meshes, msg_queue)
    print("UV Packer response:")
    while not msg_queue.empty():
        print( msg_queue.get() )
    return


@bpy.app.handlers.persistent
def onLoad(dummy):
    # Make sure we have at least one UDIM
    if len(bpy.context.scene.gflow.udims) == 0:
        bpy.context.scene.gflow.udims.add()
        bpy.context.scene.gflow.udims[0].name = "UDIM_0"





classes = [
    GFLOW_OT_AutoUnwrap, GFLOW_OT_ShowUv,
    GFLOW_OT_SetGridify, GFLOW_OT_DeGridify, GFLOW_OT_SelectGridify,
    GFLOW_OT_SetUvOrientationVertical, GFLOW_OT_SetUvOrientationHorizontal, GFLOW_OT_SetUvOrientationNeutral,
    GFLOW_OT_SetUvIslandScale,
    GFLOW_OT_AddUdim, GFLOW_OT_RemoveUdim, GFLOW_OT_SetToCurrentUdim]

def register():
    for c in classes: 
        bpy.utils.register_class(c)
    bpy.app.handlers.load_post.append(onLoad) # Make sure we have an udim whenever we load a new scene

    print("UVpacker found: "+str(isUvPackerAvailable()))
    
    pass
def unregister():
    bpy.app.handlers.load_post.remove(onLoad)
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass