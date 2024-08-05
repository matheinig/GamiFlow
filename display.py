import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.app.handlers import persistent
from . import geotags
from . import helpers

gShader = None
gVertexColorShader = None
gWireShader = None

gChangedObject = False
gCachedObject = None
gCachedBatch = None
gCachedUvScaleBatch = None
gCachedDetailBatch = None

@persistent
def mesh_change_listener(scene, depsgraph):
    # check if we need to iterate through updates at all
    if not depsgraph.id_type_updated('MESH'):
        return

    edit_obj = bpy.context.edit_object
    if edit_obj is None: return
    
    for update in depsgraph.updates:
        if update.id.original == edit_obj and update.is_updated_geometry:
            onObjectModified(edit_obj)
            return
    return

def onObjectModified(obj):
    global gCachedObject
    gCachedObject = None

def createVertexColorShader():
    vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
    vert_out.smooth('VEC4', "vColor")

    shader_info = gpu.types.GPUShaderCreateInfo()
    shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
    shader_info.vertex_in(0, 'VEC3', "pos")
    shader_info.vertex_in(1, 'VEC4', "col")
    shader_info.vertex_out(vert_out)
    shader_info.fragment_out(0, 'VEC4', "FragColor")

    shader_info.vertex_source(
        "void main()"
        "{"
        "  vColor = col;"
        "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0f);"
        "  gl_Position.z -= 0.00001;"
        "}"
    )
    
    # For vertical strips
    #   "  vec4 c = int(gl_FragCoord.x) % 16 > 8? uColor : vec4(uColor.rgb, uColor.a*0.25);"
    shader_info.fragment_source(
        "void main()"
        "{"
        "  FragColor = vColor;"
        "}"
    )
    shader = gpu.shader.create_from_info(shader_info)    
    return shader

def makeUvScaleDrawBuffer(bm, shader):
    layer = geotags.getUvScaleLayer(bm, forceCreation=False)
    if layer is None: return None
    
    # Could probably cache all the vertices if all we do is play with the indices
    baseScale = geotags.getUvScaleCode(1.0)
    pos = []
    color = []
    for looptris in bm.calc_loop_triangles():
        scaleCode = looptris[0].face[layer]
        if scaleCode != baseScale:
            scale = geotags.getUvScaleFromCode(scaleCode)
            
            # Awful colouring
            minv = 0.25
            maxv = 2.0
            c = (1.0,1.0,1.0)
            a = 1.0
            if scale < 1.0:
                a = 1.0-max(min( (scale-minv) / (1.0-minv), 1.0), 0.0)
                c = (0.8,1.0,0.7)
            if scale > 1.0:
                a = 1.0-max(min((maxv-scale) / (maxv-1), 1.0), 0.0)
                c = (1.0,0.5,0.5)            

            for loop in looptris:
                pos.append( loop.vert.co )
                color.append( (c[0], c[1], c[2], a*0.75) )
    
    batch = batch_for_shader(shader, 
        'TRIS',
        {"pos": pos, "col": color})        
    return batch

def drawUvScale():
    if not bpy.context.scene.gflow.overlays.uvScale: return
    
    obj = bpy.context.edit_object
    if bpy.context.mode != 'EDIT_MESH': return
    if obj is None: return
    if bpy.context.tool_settings.mesh_select_mode[2] == False: return 

    global gVertexColorShader, gCachedObject, gCachedUvScaleBatch
    
    if not gVertexColorShader: gVertexColorShader = createVertexColorShader() 
    
    #if obj != gCachedObject:
    #    print("test")
    #    gCachedObject = obj
    with helpers.editModeObserverBmesh(obj) as bm: 
        gCachedUvScaleBatch = makeUvScaleDrawBuffer(bm, gVertexColorShader)
   
    if gCachedUvScaleBatch is None: return

    model = obj.matrix_world
    viewproj = bpy.context.region_data.perspective_matrix
    gVertexColorShader.uniform_float("ModelViewProjectionMatrix", viewproj@model)
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_mask_set(False)
    gpu.state.face_culling_set('BACK')
    gCachedUvScaleBatch.draw(gVertexColorShader)

def createCheckerboardShader():
    vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
    vert_out.smooth('FLOAT', "v_ArcLength")

    shader_info = gpu.types.GPUShaderCreateInfo()
    shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
    shader_info.push_constant('VEC4', "uColor")
    shader_info.push_constant('VEC4', "uSecondaryColor")
    shader_info.vertex_in(0, 'VEC3', "pos")
    #shader_info.vertex_out(vert_out)
    shader_info.fragment_out(0, 'VEC4', "FragColor")

    shader_info.vertex_source(
        "void main()"
        "{"
        "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0f);"
        "  gl_Position.z -= 0.0001;"
        "}"
    )
    
    # For vertical strips
    #   "  vec4 c = int(gl_FragCoord.x) % 16 > 8? uColor : vec4(uColor.rgb, uColor.a*0.25);"
    shader_info.fragment_source(
        "void main()"
        "{"
        "  int magic = int(gl_FragCoord.x)/8 + int(gl_FragCoord.y)/8;"
        "  vec4 c = magic % 2 == 0? uColor : uSecondaryColor;"
        "  FragColor = vec4(c);"
        "}"
    )
    shader = gpu.shader.create_from_info(shader_info)    
    return shader
    
def makeGridifyDrawBuffer(bm, shader):
    gridify = geotags.getGridifyLayer(bm, forceCreation=False)
    if gridify is None: return None
    
    # Could probably cache all the vertices if all we do is play with the indices
    coords = [v.co+v.normal*0.000002 for v in bm.verts]
    indices = [[loop.vert.index for loop in looptris]
                for looptris in bm.calc_loop_triangles() if looptris[0].face[gridify] == geotags.GEO_FACE_GRIDIFY_INCLUDE]
    batch = batch_for_shader(shader, 
        'TRIS',
        {"pos": coords},
        indices=indices)   
    return batch

def drawGridified():
    if not bpy.context.scene.gflow.overlays.uvGridification: return
    obj = bpy.context.edit_object
    if bpy.context.mode != 'EDIT_MESH': return
    if obj is None: return
    if bpy.context.tool_settings.mesh_select_mode[2] == False: return 
    
    global gShader, gCachedObject, gCachedBatch
    
    if not gShader: gShader = createCheckerboardShader() 
    
    if obj != gCachedObject:
        gCachedObject = obj
        with helpers.editModeObserverBmesh(obj) as bm: 
            gCachedBatch = makeGridifyDrawBuffer(bm, gShader)
   
    if gCachedBatch is None: return
        
    model = obj.matrix_world
    viewproj = bpy.context.region_data.perspective_matrix
    gShader.uniform_float("ModelViewProjectionMatrix", viewproj@model)
    gShader.uniform_float("uColor", (1, 1, 0, 0.25))
    gShader.uniform_float("uSecondaryColor", (1, 1, 0, 0.15))
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_mask_set(False)
    gpu.state.face_culling_set('BACK')
    gCachedBatch.draw(gShader)



def makeEdgeDetailDrawBuffer(bm, shader):
    layer = geotags.getDetailEdgesLayer(bm, forceCreation=False)
    if layer is None: return None
    
    # Could probably cache all the vertices if all we do is play with the indices
    coords = [v.co+v.normal*0.0001 for v in bm.verts]
    indices = [[v.index for v in edge.verts]
                for edge in bm.edges if edge[layer] != geotags.GEO_EDGE_LEVEL_DEFAULT]
    batch = batch_for_shader(shader, 
        'LINES',
        {"pos": coords},
        indices=indices)   
    return batch
    
def drawDetailEdges():
    if not bpy.context.scene.gflow.overlays.detailEdges: return
    obj = bpy.context.edit_object
    if bpy.context.mode != 'EDIT_MESH': return
    if obj is None: return
    if bpy.context.tool_settings.mesh_select_mode[1] == False: return
    
    global gWireShader, gCachedObject, gCachedDetailBatch
    
    if not gWireShader: gWireShader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    
    if obj != gCachedObject:
        gCachedObject = obj
        with helpers.editModeObserverBmesh(obj) as bm: 
            gCachedDetailBatch = makeEdgeDetailDrawBuffer(bm, gWireShader)
   
    if gCachedDetailBatch is None: return
        
    model = obj.matrix_world
    viewproj = bpy.context.region_data.perspective_matrix
    gWireShader.uniform_float("ModelViewProjectionMatrix", viewproj@model)
    gWireShader.uniform_float("color", (1, 1, 0, 0.85))
    region = bpy.context.region
    gWireShader.uniform_float("lineWidth", 3)
    gWireShader.uniform_float("viewportSize", (region.width, region.height))    
    #gWireShader.uniform_float("uSecondaryColor", (1, 1, 0, 0.15))
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_mask_set(False)
    gpu.state.face_culling_set('BACK')
    gCachedDetailBatch.draw(gWireShader)
       
       
       
       
classes = []
handlersFunctions = [drawGridified, drawUvScale, drawDetailEdges]
handlers = []

def register():
    for c in classes: 
        bpy.utils.register_class(c)
        
    for handlerFunc in handlersFunctions:
        handlers.append(bpy.types.SpaceView3D.draw_handler_add(handlerFunc, (), 'WINDOW', 'POST_VIEW'))
    
    bpy.app.handlers.depsgraph_update_post.append(mesh_change_listener)
    
    pass
    
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
        
    for handler in handlers:
        bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
    
    bpy.app.handlers.depsgraph_update_post.remove(mesh_change_listener)
    
    pass