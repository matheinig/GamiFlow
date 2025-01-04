import bpy
import bmesh
import contextlib

def findActive3dView(context):
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            return area.spaces.active
    return None

def convertToMesh(context, obj):
    if obj.type == 'MESH': return
    setSelected(context, obj)
    bpy.ops.object.convert(target='MESH')
def isObjectValidMesh(obj):
    return obj.type == 'MESH' and len(obj.data.polygons)>0
def isObjectMeshLike(obj):
    return obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT'

def getMaterialTreeOutput(tree):
    for n in tree.nodes:
        if n.type == 'OUTPUT_MATERIAL': return n
    return None

def getMaterialColour(material):
    if material.use_nodes:
        # Try to figure out what the Base Color might be by tracing back the material tree
        tree = material.node_tree
        outputNode = getMaterialTreeOutput(tree)
        if outputNode is None: return material.diffuse_color
        surfaceNode = outputNode.inputs[0].links[0].from_node
        if surfaceNode is None: return material.diffuse_color 
        diffuseInput = surfaceNode.inputs[0]
        # If the BSDF color input is coming from another node, things can get very complicated
        if diffuseInput.is_linked:
            # Having the colour come from an RGB node is still reasonable
            inputNode = diffuseInput.links[0].from_node
            if inputNode.type == 'RGB':
                return inputNode.outputs[0].default_value
            
        # If nothing reasonable further down the tree (or no tree t all), just return the BSDF node base colour
        return diffuseInput.default_value
        
    else:
        return material.diffuse_color
        
def isObjectCollectionInstancer(obj):
    return obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION'

def findObjectByName(objList, name):
    for o in objList:
        if o.name == name: return o
    return None

def setSelected(context, obj):
    obj.select_set(True)
    context.view_layer.objects.active = obj
def setDeselected(obj):
    obj.select_set(False)
    
def setParent(o, parent):
    matrix = o.matrix_world.copy()
    o.parent = parent
    o.matrix_world = matrix

@contextlib.contextmanager
def objectModeBmesh(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    
    yield bm
    
    bm.to_mesh(obj.data) 
    bm.free()
    
@contextlib.contextmanager
def editModeBmesh(obj, loop_triangles=False, destructive=False):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    
    yield bm
    
    bmesh.update_edit_mesh(obj.data, loop_triangles=loop_triangles, destructive=destructive) 
    bm.free()

@contextlib.contextmanager
def editModeObserverBmesh(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    
    yield bm

    bm.free()

def getScreenArea(context, areaType="VIEW_3D"):
    for a in context.screen.areas:
        if a.type == areaType: return a
    return None

classes = []


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass