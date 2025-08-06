import bpy
import bmesh
import mathutils
import math
import addon_utils
import importlib  
import platform, os, subprocess, queue
import time
from bpy_extras.bmesh_utils import bmesh_linked_uv_islands
from . import geotags
from . import helpers
from . import sets
from . import settings
from . import enums

#BEGINTRIM -------------------------------------------------- 
def isUvPackerAvailable():
    (default, current) = addon_utils.check("UV-Packer")
    return current
    
def getMofConsole(stgs):
    return os.path.join(stgs.mofPath, 'UnWrapConsole3.exe')
def isMofAvailable(stgs):
    if not stgs.mofPath: return False
    consolePath = getMofConsole(stgs)
    if not os.path.exists(consolePath): return False
    return True
def isMofAvailableAndEnbaled(stgs):
    return stgs.useMofUnwrapper and isMofAvailable(stgs)
#ENDTRIM -----------------------------------------------------  
def hardenSeams(context, obj):
    return

def flipUVs(obj):
    with helpers.objectModeBmesh(obj) as bm:
        for face in bm.faces:
            for loop in face.loops:
                for layer in bm.loops.layers.uv:
                    loop[layer].uv[1] = 1.0-loop[layer].uv[1]
        

def areUVsProbablyInside(obj):
    with helpers.objectModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        for f in bm.faces:
            for l in f.loops:
                uv = l[uv_layer].uv
                if uv[0] < 1.0 or uv[1]<1.0: return True
    return True
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
    orientLayer = None
    with helpers.editModeObserverBmesh(obj) as bm:
        orientLayer = geotags.getUvOrientationLayer(bm, forceCreation=False)
    if not orientLayer: return

    anythingRotated = False
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
        uv_layer = bm.loops.layers.uv.active  

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
     
# Makes a nice UV grid from tagged faces if any in individual UV islands (supports non-grid bits too)
def straightenUv(context, obj):
    gridifyLayer = None
    with helpers.editModeObserverBmesh(obj) as bm:
        gridifyLayer = geotags.getGridifyLayer(bm, forceCreation=False)
    if not gridifyLayer: return
    
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
        uv_layer = bm.loops.layers.uv.active

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
                safeUnwrap(context, obj)
                # Unpin
                bpy.ops.uv.pin(clear=True)

            bpy.ops.mesh.select_all(action='DESELECT')
        #endfor islands
        
        # Remove unused gridify layer if need be
        if not somethingFound: geotags.removeGridifyLayer(bm)
    return

def _filterUnwrappableOrPackableObjectsRecurs(all_objects, knownMeshes):
    objects = []
    collections = []
    for o in all_objects:
        if helpers.isObjectCollectionInstancer(o):
            [objs, colls] = _filterUnwrappableOrPackableObjectsRecurs(o.instance_collection.all_objects, knownMeshes)
            objects.extend( objs )
            collections.extend( colls )
            if o.instance_collection not in collections: collections.append(o.instance_collection)
            continue
        if helpers.isObjectValidMesh(o) and o.gflow.objType == 'STANDARD':
            if o.data not in knownMeshes:
                objects.append(o)
                knownMeshes.append(o.data)
            continue
    return objects, collections
def filterUnwrappableOrPackableObjects(all_objects):
    knownMeshes = []
    return _filterUnwrappableOrPackableObjectsRecurs(all_objects, knownMeshes)

def autoUnwrap(context, udimIDs, doUnwrap=True, doPack=True):
    unwrappables, collections = filterUnwrappableOrPackableObjects(context.scene.gflow.workingCollection.all_objects)
    collections.append(context.scene.gflow.workingCollection)
    
    # Make sure all the relevant collections are enabled
    originalCollectionVisibility = {}
    for c in collections:
        originalCollectionVisibility[c] = sets.getCollectionVisibility(context, c)
        sets.setCollectionVisibility(context, c, True)
    
    
    if not context.scene.gflow.mergeUdims:
        # Go through all udims and unwrap them
        for texset in udimIDs: 
            # Gather all objects
            obj = [o for o in unwrappables if o.gflow.textureSet == texset]

            # Unwrap individual objects
            if doUnwrap: unwrap(context, obj)
            # Pack everything together
            if doPack: pack(context, obj, context.scene.gflow.uvPackSettings)    
    else:
        # Special case if the user wants to merge all the udims together
        if doUnwrap: unwrap(context, unwrappables)
        if doPack: pack(context, unwrappables, context.scene.gflow.uvPackSettings)    
            
    
        
    # Revert collection visibility
    for c in collections:
        sets.setCollectionVisibility(context, c, originalCollectionVisibility[c])    

def lightmapUnwrap(context, objects):
    # Sanitise the list  
    obj, collections = filterUnwrappableOrPackableObjects(objects)

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
    
    # Make sure we're not in local view
    view = helpers.findActive3dView(context)
    if view and view.local_view: bpy.ops.view3d.localview()

    for o in objects:
        if not o.gflow.unwrap: continue
        
        if len(o.data.uv_layers) == 0: o.data.uv_layers.new(name='UVMap')
        
        o.select_set(True)
        context.view_layer.objects.active = o
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.mesh.reveal(select=False)

        # Unwrap
        safeUnwrap(context, o)
        
        # Smooth if needed
        if o.gflow.unwrap_smooth_iterations>0:
            bpy.ops.uv.minimize_stretch(blend=1.0-o.gflow.unwrap_smooth_strength, iterations=o.gflow.unwrap_smooth_iterations)
        
        # Straighten if needed
        straightenUv(context, o)
                    
        bpy.ops.object.mode_set(mode='OBJECT')
        
        o.select_set(False)
    bpy.ops.object.select_all(action='DESELECT')

def safeUnwrap(context, o):
    # Unwrap
    method = o.gflow.unwrap_method
    
    # Pre 4.3 blender does not support minimum stretch unwrapping
    if bpy.app.version < (4, 3, 0):
        if method == 'MINIMUM_STRETCH': method = 'ANGLE_BASED'
        bpy.ops.uv.unwrap(method=method, margin=0.001)
    else:
        bpy.ops.uv.unwrap(method=method, margin=0.001, iterations=o.gflow.unwrap_extraParameter)
    

def pack(context, objects, packMethod = 'FAST'):
    if len(objects) == 0: return

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
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
        context.view_layer.objects.active = o

    # Select the UVs
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.reveal(select=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    # Deal with the scale
    ## First average everything
    bpy.ops.uv.average_islands_scale()
    ## Then rescale individual islands based on user values
    for o in objects:
        rescaleIslandsIfNeeded(o)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Actual packing
    bpy.ops.object.mode_set(mode='EDIT')
    ## Pack into [0,1]
    generic_pack_island(context, margin=margin, shape_method=shapeMethod, rotate=True, rotate_method=rotateMethod)
    ## Go through individual objects and orient the islands
    anythingRotated = False
    for o in objects:
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
        for o in objects:
            snapUv(o, resolution)
    
    # Exit
    bpy.ops.object.mode_set(mode='OBJECT')
    pass
def generic_pack_island(context, margin, shape_method, rotate, rotate_method):
    #BEGINTRIM --------------------------------------------------
    if settings.getSettings().uvPacker == "UVPACKER":
        uvpacker_pack_island(context=context, margin=margin, rotate=rotate, rotate_method=rotate_method)
        return
    #ENDTRIM -----------------------------------------------------
    bpy.ops.uv.pack_islands(margin=margin, shape_method=shape_method, rotate=rotate, rotate_method=rotate_method)
    return
#BEGINTRIM --------------------------------------------------
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
#ENDTRIM -----------------------------------------------------
def snapUv(obj, resolution):
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
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
    uvScaleLayer = None
    with helpers.editModeObserverBmesh(obj) as bm:
        uvScaleLayer = geotags.getUvScaleLayer(bm, forceCreation=False)
    if not uvScaleLayer: return
    
    with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
        uv_layer = bm.loops.layers.uv.active
        neutralCode = geotags.getUvScaleCode(1.0)
        for face in bm.faces:
            if face[uvScaleLayer] == neutralCode: continue
            scale = geotags.getUvScaleFromCode(face[uvScaleLayer])
            for loop in face.loops:
                loop[uv_layer].uv = loop[uv_layer].uv * scale    

def offsetCoordinates(obj, offset=mathutils.Vector((1.0,1.0))):
    with helpers.objectModeBmesh(obj) as bm:
        uv_layer = bm.loops.layers.uv.active
        for face in bm.faces:
            for loop in face.loops:
                loop[uv_layer].uv = loop[uv_layer].uv + offset    

class GFLOW_OT_AutoUnwrap(bpy.types.Operator):
    bl_idname      = "gflow.auto_unwrap"
    bl_label       = "Unwrap"
    bl_description = "Automatically unwrap everything.\nCtrl-click to only unwrap the selected UDIM.\nShift-click to only repack."
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        if context.mode != "OBJECT": return False
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True    
    
    def invoke(self, context, event): 
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def modal(self, context, event):
    
        onlyCurrent = False
        doUnwrap=True
        udims = None
        if event.ctrl:
            onlyCurrent = True
            udims = [context.scene.gflow.ui_selectedUdim]
        else:
            udims = range(0, len(context.scene.gflow.udims))
        if event.shift: doUnwrap=False
            
        autoUnwrap(context, udims, doUnwrap=doUnwrap)
        
        return {'FINISHED'}
    def execute(self, context):
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
        with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
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
        
        with helpers.editModeBmesh(obj, loop_triangles=False, destructive=False) as bm:
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
    with helpers.editModeBmesh(editMeshObj, loop_triangles=False, destructive=False) as bm:
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
    bl_description = "Set the relative UV scale of an island"
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
        
class GFLOW_OT_SetUnwrapMethod(bpy.types.Operator):
    bl_idname      = "gflow.set_unwrap_method"
    bl_label       = "Set Unwrap Method"
    bl_description = "Set the unwrap method to the selection"
    bl_options = {"REGISTER", "UNDO"}
    
    unwrap_method: bpy.props.EnumProperty(name="Unwrapper", default='ANGLE_BASED', items=enums.gUV_UNWRAP_METHODS)
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects)>0

    def execute(self, context):
        for o in context.selected_objects:
            o.gflow.unwrap_method = self.unwrap_method
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
    
def findUvWorkspace():
    for ws in bpy.data.workspaces:
        for sc in ws.screens:
            for ar in sc.areas:
                if ar.type == 'IMAGE_EDITOR':
                    # image editor isn't necessarily a uv editor so we need to keep checking
                    for sp in ar.spaces: 
                        if sp.mode == 'UV': return ws
    return ws

class GFLOW_OT_ShowUv(bpy.types.Operator):
    bl_idname      = "gflow.show_uv"
    bl_label       = "Show UV"
    bl_description = "Show the UVs for a given texture set"
    bl_options = {"REGISTER", "UNDO"}
    
    textureSetEnum : bpy.props.EnumProperty(items = udimItemGenerator, name = 'Texture set')
    
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
    
        # find the right udim id
        udim = findUdimId(context, self.textureSetEnum)
        
        # Select all the relevant objects and their faces
        objects, collections = filterUnwrappableOrPackableObjects(context.scene.gflow.workingCollection.all_objects)
        collections.append(context.scene.gflow.workingCollection)
        for c in collections: sets.setCollectionVisibility(context, c, True)
        for o in objects:
            if (not context.scene.gflow.mergeUdims) and o.gflow.textureSet != udim: continue
            o.select_set(True)
            context.view_layer.objects.active = o
            
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.mesh.reveal(select=False)
    
        uvEditor = findUvWorkspace()
        if uvEditor: bpy.context.window.workspace = uvEditor
        
        return {"FINISHED"}         

#BEGINTRIM --------------------------------------------------
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
    # So instead we have to manually call the exe. And to be sure that it's done correctly, 
    # the following code is directly lifted from the UV-Packer addon itself

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
    
    # Back to my own original code
    print("UV Packer response:")
    while not msg_queue.empty():
        print( msg_queue.get() )
    return
    
    print("UV-Packer integration not available in this version of GamiFlow")
    return
    
# Ministry of flat backend
def mofUnwrap(context, obj, seamsOnly=False):
    if obj.type != 'MESH': return

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    
    # Clear the old seams
    helpers.setSelected(context, obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    helpers.setDeselected(obj)

    # First we want to prevent MoF from creating seams on edges that will get deleted by gamiflow
    # The easiest way is to just delete all those edges before unwrapping
    tempObj = obj.copy()
    tempObj.data = obj.data.copy()
    tempObj.name = tempObj.name + "_temporary_for_unwrap"
    context.collection.objects.link(tempObj)
    nbRemovedEdges = sets.removeEdgesForLevel(context, tempObj, 0, keepPainter=False)
    helpers.setSelected(context, tempObj)
    # Export the file as obj
    mofFolder = settings.getSettings().mofPath
    sourceObjPath = os.path.join(mofFolder, "mofTempInput.obj")
    resultObjPath = os.path.join(mofFolder, "mofTempOutput.obj")
    bpy.ops.wm.obj_export(filepath=sourceObjPath, check_existing=False, filter_glob="*.obj", 
        forward_axis='NEGATIVE_Z', up_axis='Y', 
        export_selected_objects = True, export_eval_mode = 'DAG_EVAL_RENDER', apply_modifiers = False,
        export_uv = True, export_normals = True, export_colors = False, export_materials = False, export_pbr_extensions = False, export_triangulated_mesh = False)
    helpers.setDeselected(tempObj)
    
    # Wait for the input file to exist just in case
    while not os.path.exists(sourceObjPath):
        time.sleep(0.05)
    # Make sure to delete any previous output
    if os.path.exists(resultObjPath):
        os.remove(resultObjPath)         
        
    # Run MoF
    mofPath = os.path.join(mofFolder, 'UnWrapConsole3.exe')
    center = " -CENTER "+str(obj.location[0])+" "+str(obj.location[1])+" "+str(obj.location[2]) # Maybe not necessary, mostly for safety
    command = mofPath + " " + sourceObjPath + " " + resultObjPath + " -NORMALS FALSE -SEPARATE TRUE" + center
    os.popen(command)

    # Wait for the output file to exist just in case
    while not os.path.exists(resultObjPath):
        time.sleep(0.05)
    
    # Load the unwrapped obj
    bpy.ops.wm.obj_import(filepath=resultObjPath, global_scale=1.0, clamp_size=0.0, forward_axis='NEGATIVE_Z', up_axis='Y', use_split_objects=True, use_split_groups=False, import_vertex_groups=False, validate_meshes=False)
    unwrappedObj = context.object
    unwrappedObj.name = obj.name + "_mof_unwrap"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    offsetMatrix = (obj.matrix_world.inverted() @ unwrappedObj.matrix_world)
    unwrappedObj.data.transform(offsetMatrix)             
    unwrappedObj.matrix_world = obj.matrix_world
    # Compute seams on the unwrapped object
    helpers.setSelected(context, unwrappedObj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.seams_from_islands() 
    bpy.ops.object.mode_set(mode='OBJECT')     
    helpers.setDeselected(unwrappedObj)

    # If we didn't delete any edges we can transfer the UVs as is
    if nbRemovedEdges == 0:
        helpers.setSelected(context, obj)
        helpers.setSelected(context, unwrappedObj)
        bpy.ops.object.join_uvs()
        helpers.setDeselected(unwrappedObj)
        # Update the seams
        helpers.setSelected(context, obj)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.seams_from_islands() 
        bpy.ops.object.mode_set(mode='OBJECT')         
    # Otherwise all we can do is transfer the seams and unwrap
    else:
        helpers.setSelected(context, obj)
        transferSeam(context, unwrappedObj, obj, transferUVs = not seamsOnly)


    # Big hack: UV-Packer doesn't behave nicely when we have lots of 0-area faces (which can be the case if we dissolved lots of edges). Se we smooth the UVs a tiny bit for safety
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.minimize_stretch(blend=0.99, iterations=1)
    
    # Clean up the scene
    bpy.data.meshes.remove(unwrappedObj.data) # Will get rid of the object too
    bpy.data.meshes.remove(tempObj.data)
    bpy.ops.object.mode_set(mode='EDIT') # the rest of the unwrapper expects to be in edit mode
        
    return True
    
def makeBMeshTree(bmesh, transform=mathutils.Matrix()):
    kd = mathutils.kdtree.KDTree(len(bmesh.verts))
    for v in bmesh.verts:
        kd.insert(v.co @ transform, v.index)
    kd.balance()
    return kd
   
def transferSeam(context, fromObj, toObj, transferUVs=False):
    helpers.setSelected(context, toObj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    with helpers.editModeBmesh(toObj, loop_triangles=False, destructive=False) as tbm:
        # Make the bmeshes
        fbm = bmesh.new()
        fbm.from_mesh(fromObj.data)
        fbm.faces.ensure_lookup_table()
        tbm.faces.ensure_lookup_table()
        tbm.verts.ensure_lookup_table()
        fbm.verts.ensure_lookup_table()        
        # Make the acceleration structures
        ttree = makeBMeshTree(tbm)

        fuv = fbm.loops.layers.uv.active
        tuv = tbm.loops.layers.uv.active
        
        for v in tbm.verts: v.select = False
        
        for fe in fbm.edges:
            if fe.seam:
                tco1, index1, dist1 = ttree.find(fe.verts[0].co)
                tco2, index2, dist2 = ttree.find(fe.verts[1].co)
                if dist1>0.001 and dist2>0.001: 
                    print("GamiFlow: UV transfer went wrong for "+fromObj.name+"->"+toObj.name)
                    continue
                    
                # Easy case: both vertices are on the same edge
                edgeFound = False
                for te in tbm.verts[index1].link_edges:
                    if tbm.verts[index2] in te.verts:
                        te.seam = True
                        edgeFound = True
                        continue
                # Annoying case: weare missing vertices between the two verts (most likely an edge loop was dissolved)
                # So we try to just find the nearest vertex path between the two and assume this is where the seam should go
                if (not edgeFound):
                    tbm.verts[index1].select = True
                    tbm.verts[index2].select = True
                    bpy.ops.mesh.shortest_path_select(edge_mode='SEAM', use_fill=False)
                    bpy.ops.mesh.select_mode(type="EDGE")
                    for e in tbm.edges:
                        if e.select: 
                            e.seam = True
                            e.select = False
                    bpy.ops.mesh.select_mode(type="VERT")

        
        
        if transferUVs:
            # unpin all the loops first
            for tface in tbm.faces:
                for tloop in tface.loops:
                    tloop[tuv].pin_uv = False
            
            # For each face loop on the unwrapped mesh, we try to find the equivalent loop in the original mesh
            # It will always exist since the unwrapped mesh is the one with dissolved geometry
            for fface in fbm.faces:
                for floop in fface.loops:
                    # Find the closest vertex (will always succeed in our case)
                    # However, there are cases where the closest vertex isn't even on the same mesh island (vertices at the same position but belonging to two split geo islands). So we need to look for at least a few vertices just to be safe
                    fco = floop.vert.co
                    for (tco, tindex, dist) in ttree.find_n(fco, 4):
                        if dist>0.001:
                            continue
                   
                        # Now we must find which of the target link_loops would best match the current source loop
                        # Using the face tangent direction (points towards the centre of the face) seems like a pretty good method
                        # Also adding normal just for safety, but maybe not needed
                        referenceT = floop.calc_tangent()
                        referenceN = floop.calc_normal()
                        bestLoop = None
                        bestScore = -1
                        tvert = tbm.verts[tindex]
                        for tloop in tvert.link_loops:
                            tangentScore = referenceT.dot(tloop.calc_tangent())
                            normalScore = abs(referenceN.dot(tloop.calc_normal()))
                            similarity = tangentScore*normalScore
                            if similarity > bestScore:
                                bestLoop = tloop
                                bestScore = similarity
                                if similarity>0.99: break # no need to check further if it's already a great match
                       
                        bestLoop[tuv].uv = floop[fuv].uv
                        bestLoop[tuv].pin_uv = True
                   
            # Unwrap anything that hasn't been touched (i.e. the dissolvable edges) because they are currently undefined
            bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
            bpy.ops.uv.pin(clear=True)
            bpy.ops.uv.select_all(action='DESELECT')
                
        fbm.free()
    return
    
class GFLOW_OT_AutoSeam(bpy.types.Operator):
    bl_idname      = "gflow.auto_seam"
    bl_label       = "Auto Seams"
    bl_description = "Automatically compute UV seams on the selected objects."
    bl_options = {"REGISTER", "UNDO"}
   
    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) == 0:
            cls.poll_message_set("Must select objects.")
            return False
        if not isMofAvailableAndEnbaled(settings.getSettings()): 
            cls.poll_message_set("Only available with the Ministry of Flat addon.")
            return False
        return True
    def execute(self, context):
        selection = context.selected_objects.copy()
        for o in selection:
            helpers.setDeselected(o)
        for o in selection:
            mofUnwrap(context, o, seamsOnly=True)
        
        return {"FINISHED"}
class GFLOW_OT_AutoUV(bpy.types.Operator):
    bl_idname      = "gflow.auto_uv"
    bl_label       = "Auto UVs"
    bl_description = "Automatically unwraps the selected objects. This will ignore gridification."
    bl_options = {"REGISTER", "UNDO"}
   
    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) == 0:
            cls.poll_message_set("Must select objects.")
            return False
        if not isMofAvailableAndEnbaled(settings.getSettings()): 
            cls.poll_message_set("Only available with the Ministry of Flat addon.")
            return False
        return True
    def execute(self, context):
        selection = context.selected_objects.copy()
        for o in selection:
            helpers.setDeselected(o)
        for o in selection:
            mofUnwrap(context, o, seamsOnly=False)
            o.gflow.unwrap = False
        
        return {"FINISHED"}           
    
#ENDTRIM --------------------------------------------------

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
    GFLOW_OT_AddUdim, GFLOW_OT_RemoveUdim, GFLOW_OT_SetToCurrentUdim,
    GFLOW_OT_SetUnwrapMethod]
#BEGINTRIM --------------------------------------------------
classes += [GFLOW_OT_AutoSeam, GFLOW_OT_AutoUV]
#ENDTRIM --------------------------------------------------

def register():
    for c in classes: 
        bpy.utils.register_class(c)
    bpy.app.handlers.load_post.append(onLoad) # Make sure we have an udim whenever we load a new scene
    
    pass
def unregister():
    bpy.app.handlers.load_post.remove(onLoad)
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass