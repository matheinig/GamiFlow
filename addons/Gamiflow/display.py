import bpy
import mathutils
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.app.handlers import persistent
from . import geotags
from . import helpers
from . import settings

gShader = None
gMirrorShader = None
gVertexColorShader = None
gWireShader = None


gCachedObject = None
gCachedBatch = None
gCachedMirrorObject = None
gCachedMirrorBatch = None
gCachedUvScaleBatch = None
gCachedDetailBatch = None
gCachedPainterDetailBatch = None
gCachedCageDetailBatch = None

@persistent
def mesh_change_listener(scene, depsgraph):
    if bpy.context.mode != "EDIT_MESH": return

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
    global gCachedObject, gCachedMirrorObject
    gCachedObject = gCachedMirrorObject = None

def purgeCache():
    global gCachedObject, gCachedMirrorObject
    gCachedObject = gCachedMirrorObject = None

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

    shader_info = gpu.types.GPUShaderCreateInfo()
    shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
    shader_info.push_constant('VEC4', "uColor")
    shader_info.push_constant('VEC4', "uSecondaryColor")
    shader_info.vertex_in(0, 'VEC3', "pos")
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

def createMirrorShader():
    vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")

    shader_info = gpu.types.GPUShaderCreateInfo()
    shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
    shader_info.push_constant('VEC4', "uColor")
    shader_info.push_constant('VEC4', "uSecondaryColor")
    shader_info.vertex_in(0, 'VEC3', "pos")
    shader_info.vertex_in(1, 'VEC3', "normal")
    
    vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
    vert_out.smooth('FLOAT', "vLighting")
    shader_info.vertex_out(vert_out)
    shader_info.fragment_out(0, 'VEC4', "FragColor")

    shader_info.vertex_source(
        "void main()"
        "{"
        "  vLighting = dot(normal, vec3(1.0,1.0,1.0))*0.5+0.5;"
        "  gl_Position = ModelViewProjectionMatrix * vec4(pos+normal*0.001, 1.0f);"
        "  gl_Position.z -= 0.0001;"
        "}"
    )
    
    shader_info.fragment_source(
        "void main()"
        "{"
        "  int magic = int(gl_FragCoord.x)/2 + int(gl_FragCoord.y)/2;"
        "  vec4 c = magic % 2 == 0? uColor : uSecondaryColor;"
        "  c.rgb *= vLighting*0.75+0.25;"
        "  FragColor = vec4(c);"
        "}"
    )
    shader = gpu.shader.create_from_info(shader_info)    
    return shader

def makeMirrorDrawBuffer(bm, shader):
    mirror = geotags.getMirrorLayer(bm, forceCreation=False)
    if mirror is None: return None
    
    mirrorFunction =  mathutils.Vector((-1.0,1.0,1.0))
    
    # Could probably cache all the vertices if all we do is play with the indices
    coords = [ (v.co+v.normal*0.000002)*mirrorFunction for v in bm.verts]
    norms = [v.normal * mirrorFunction for v in bm.verts]
    indices = [[loop.vert.index for loop in looptris]
                for looptris in bm.calc_loop_triangles() if looptris[0].face[mirror] != geotags.GEO_FACE_MIRROR_NONE]
    batch = batch_for_shader(shader, 
        'TRIS',
        {"pos": coords, "normal": norms},
        indices=indices)   
    return batch
def drawMirrored():
    if not bpy.context.scene.gflow.overlays.mirroring: return
    obj = bpy.context.edit_object
    if bpy.context.mode != 'EDIT_MESH': return
    if obj is None: return
    if bpy.context.tool_settings.mesh_select_mode[2] == False: return 
    
    global gMirrorShader, gCachedMirrorObject, gCachedMirrorBatch
    
    if not gMirrorShader: gMirrorShader = createMirrorShader() 
    
    if obj != gCachedMirrorObject:
        gCachedMirrorObject = obj
        with helpers.editModeObserverBmesh(obj) as bm: 
            gCachedMirrorBatch = makeMirrorDrawBuffer(bm, gMirrorShader)
   
    if gCachedMirrorBatch is None: return

    model = obj.matrix_world
    viewproj = bpy.context.region_data.perspective_matrix
    gMirrorShader.uniform_float("ModelViewProjectionMatrix", viewproj@model)
    gMirrorShader.uniform_float("uColor", (1, 0.5, 0.5, 0.25))
    gMirrorShader.uniform_float("uSecondaryColor", (1, 0, 0, 0.15))
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_mask_set(False)
    gpu.state.face_culling_set('FRONT')
    gCachedMirrorBatch.draw(gMirrorShader)    

    
    
def makeEdgeDetailDrawBuffer(bm, solidShader, offset=0.0001):
    layer = geotags.getDetailEdgesLayer(bm, forceCreation=False)
    if layer is None: return None, None, None
    
    coords = [v.co+v.normal*offset for v in bm.verts]
    
    # Could probably cache all the vertices if all we do is play with the indices
    solidBatch = None
    indicesSolid = [[v.index for v in edge.verts]
                for edge in bm.edges if edge[layer] >= geotags.GEO_EDGE_LEVEL_LOD0]
    if len(indicesSolid) > 0:
        solidBatch = batch_for_shader(solidShader, 
            'LINES',
            {"pos": coords},
            indices=indicesSolid)   
        
    # Maybe dotted line
    painterBatch = None
    indicesPainter = [[v.index for v in edge.verts]
                for edge in bm.edges if edge[layer] == geotags.GEO_EDGE_LEVEL_PAINTER]
    if len(indicesPainter) > 0:
        painterBatch = batch_for_shader(solidShader, 
            'LINES',
            {"pos": coords},
            indices=indicesPainter)
            
    # Definitely should be a dotted line
    cageBatch = None
    indicesCage = [[v.index for v in edge.verts]
                for edge in bm.edges if edge[layer] == geotags.GEO_EDGE_LEVEL_CAGE]
    if len(indicesCage) > 0:
        cageBatch = batch_for_shader(solidShader, 
            'LINES',
            {"pos": coords},
            indices=indicesCage)   
                  
    return solidBatch, painterBatch, cageBatch
    
def drawDetailEdges():
    if not bpy.context.scene.gflow.overlays.detailEdges: return
    obj = bpy.context.edit_object
    if bpy.context.mode != 'EDIT_MESH': return
    if obj is None: return
    if bpy.context.tool_settings.mesh_select_mode[1] == False: return
    
    global gWireShader, gCachedObject, gCachedDetailBatch, gCachedPainterDetailBatch, gCachedCageDetailBatch
    
    if not gWireShader: gWireShader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')    
    if obj != gCachedObject:
        gCachedObject = obj
        with helpers.editModeObserverBmesh(obj) as bm: 
            gCachedDetailBatch, gCachedPainterDetailBatch, gCachedCageDetailBatch = makeEdgeDetailDrawBuffer(bm, 
                    gWireShader, 
                    bpy.context.scene.gflow.overlays.edgeOffset*0.01)
   
    region = bpy.context.region
    model = obj.matrix_world
    viewproj = bpy.context.region_data.perspective_matrix    
    mvp = viewproj@model
   
    if gCachedDetailBatch or gCachedPainterDetailBatch or gCachedCageDetailBatch:
    
        stg = settings.getSettings()
    
        gWireShader.uniform_float("ModelViewProjectionMatrix", mvp)
        gWireShader.uniform_float("lineWidth", stg.edgeWidth)
        gWireShader.uniform_float("viewportSize", (region.width, region.height))    
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set('BACK')
        if gCachedDetailBatch:
            gWireShader.uniform_float("color", stg.detailEdgeColor)
            gCachedDetailBatch.draw(gWireShader)
        if gCachedPainterDetailBatch:
            w = gpu.state.line_width_get()
            gpu.state.line_width_set(stg.edgeWidth)
            gWireShader.uniform_float("color", stg.painterEdgeColor)
            gCachedPainterDetailBatch.draw(gWireShader)
            gpu.state.line_width_set(w)
        if gCachedCageDetailBatch:
            w = gpu.state.line_width_get()
            gpu.state.line_width_set(stg.edgeWidth)
            gWireShader.uniform_float("color", stg.cageEdgeColor)
            gCachedCageDetailBatch.draw(gWireShader)
            gpu.state.line_width_set(w)            
        
       
       
       
classes = []
handlersFunctions = [drawGridified, drawMirrored, drawUvScale, drawDetailEdges]
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