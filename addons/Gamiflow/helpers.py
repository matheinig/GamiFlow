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
    if obj.type != 'MESH':
        print("GamiFlow error: "+obj.name+" is not a mesh")
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

def copyObject(sourceObj, collection, link=False):
    new_obj = sourceObj.copy()
    if sourceObj.data: 
        if not link: new_obj.data = sourceObj.data.copy()
    # Make sure we allow selection to avoid bugs in other parts
    if sourceObj.hide_select: new_obj.hide_select = False
    collection.objects.link(new_obj)
    return new_obj
def deleteObject(obj):
    mustDeleteObject = True
    # Make sure we absolutely nuke the meshes too
    # This avoids 'leaking' an increasingly large amout of orphaned meshes into the file
    if obj.type == 'MESH': 
        if obj.data.users == 1: 
            bpy.data.meshes.remove(obj.data)
            mustDeleteObject = False
    if mustDeleteObject:
        bpy.data.objects.remove(obj, do_unlink=True)

def applyModifiersByName(context, obj, modifierNames):
    modifiers = []
    for mn in modifierNames:
        modifiers.append(obj.modifiers[mn])
    applyModifiers(context, obj, modifiers)
    return
def applyModifiers(context, obj, modifiers):
    if modifiers is None or len(modifiers) == 0: return
    if obj.data.shape_keys is None:
        # No Shape keys, easy method
        applyModifiers_simple(context, obj, modifiers)
    elif len(obj.data.shape_keys.key_blocks) == 1:
        # Only one shape key, we delete it and canapply the modifiers
        obj.shape_key_remove(obj.data.shape_keys.key_blocks[0])
        applyModifiers_simple(context, obj, modifiers)
    else:
        # Multiple shape keys, needs the hacky method
        applyModifiers_shapeKeys(context, obj, modifiers)
    return
def backupOtherModifiers(obj, modifiersToDiscard):
    backedUp = []
    for m in obj.modifiers:
        if m not in modifiersToDiscard: backedUp.append([m, m.show_viewport])
    return backedUp
def applyModifiers_shapeKeys(context, obj, modifiers):
    # Make a backup copy that will retain all the shape key data until we're done
    duplicate = copyObject(obj, context.collection)
    modifierNames = [mn.name for mn in modifiers]
    
    # Remove all the shape keys on the main object
    obj.shape_key_clear()

    # Apply the modifiers to the main object as normally
    applyModifiers_simple(context, obj, modifiers)
    
    baseObjBasisShapeKey = obj.shape_key_add(name=duplicate.data.shape_keys.key_blocks[0].name, from_mix=False)
    
    if len(obj.data.vertices) == len(duplicate.data.vertices):
        # This should probably be redone completely and just apply one modifier at a time which is awful.
        # How do we deal with harmless modifiers like triangulate or weighted normals? just skip them?
        # We still have to try and respect the order of modifiers to avoid weird problems
        # We also have the issue of one modifier being easy on its own, but decimate+mirror+array is getting difficult
        # decimate: pretty cheap as we don't have to actually do anything crazy
        #   we remove the shapekeys from obj, we apply the decimation to obj.
        #   for each vertex in Obj, we find its counterpart in Duplicate with a kdtree
        #   we lookup the shapekey for that particular vertex
        # mirror: 
        #   we remove the shapekeys from obj and apply the mirror to obj
        #   ????
        
        # Re-apply the shape keys
        for index, sk in enumerate(duplicate.data.shape_keys.key_blocks):
            if index==0: continue
        
            # Duplicate the backup again, but this time keep only one shape key
            morphedObject = copyObject(duplicate, context.collection)
            morphedObject.show_only_shape_key = True
            morphedObject.active_shape_key_index = index
            
            # Apply the modifiers to the morph duplicate
            modifiersList = []
            for m in modifierNames:
                modifiersList.append(morphedObject.modifiers[m])
            applyModifiers_simple(context, morphedObject, modifiersList)
            # Remove all the other modifiers
            morphedObject.modifiers.clear()
            
            # Copy the vertices to a new shape key on the original object
            baseObjShapeKey = obj.shape_key_add(name=sk.name, from_mix=False)
            for (index, vertex) in enumerate(morphedObject.data.vertices):
                baseObjShapeKey.data[index].co = vertex.co
            
            deleteObject(morphedObject)
            
            # Shapekey settings
            baseObjShapeKey.relative_key = baseObjBasisShapeKey
            baseObjShapeKey.value = sk.value
            baseObjShapeKey.slider_min = sk.slider_min
            baseObjShapeKey.slider_max = sk.slider_max
            baseObjShapeKey.vertex_group = sk.vertex_group
            baseObjShapeKey.mute = sk.mute
            baseObjShapeKey.lock_shape = sk.lock_shape

        # Shapekey animations
        if duplicate.data.shape_keys.animation_data and duplicate.data.shape_keys.animation_data.action:
            if obj.data.shape_keys.animation_data is None: 
                obj.data.shape_keys.animation_data_create()
            obj.data.shape_keys.animation_data.action = duplicate.data.shape_keys.animation_data.action    
            if bpy.app.version >= (4,4,0):
                obj.data.shape_keys.animation_data.action_slot = duplicate.data.shape_keys.animation_data.action_slot

        ## TODO: Figure out drivers
    else:
        # make a dummy shape keywith an error message in it
        obj.shape_key_add(name="Modifiers not compatible", from_mix=False)

    # Cleanup
    deleteObject(duplicate)

    return

def applyModifiers_simple(context, obj, modifiers):
    # Disable the other modifiers for now
    modifiersToKeep = backupOtherModifiers(obj, modifiers)
    for m, v, in modifiersToKeep:
        m.show_viewport = False

    # Evaluate the mesh with only the selected modifiers
    for m in modifiers:
        m.show_viewport = True
    depsgraph = context.evaluated_depsgraph_get()
    evaluatedMesh = bpy.data.meshes.new_from_object(
        obj.evaluated_get(depsgraph), 
        preserve_all_data_layers=True, 
        depsgraph=depsgraph)    
    
    # Delete the applied modifiers from the original object
    for m in modifiers:
        obj.modifiers.remove(m)
    
    # Replace the original object mesh with the newly evaluated one
    originalMesh = obj.data
    originalMeshName = originalMesh.name
    obj.data = evaluatedMesh
    bpy.data.meshes.remove(originalMesh)
    obj.data.name = originalMeshName
        
    # Re-enable the saved modifiers and hope for the best
    for m, v in modifiersToKeep:
        m.show_viewport = v
        
    return

# Mesh islands code from https://blender.stackexchange.com/a/250139
class BMRegion:
    """Warning: this does not validate the BMesh, nor that the passed geometry belongs to same BMesh"""

    def __init__(self, verts, edges, faces):
        self.verts = verts
        self.edges = edges
        self.faces = faces
def _bm_grow_tagged(vert):
    """Flood fill untagged linked geometry starting from a vertex, tags and returns them"""
    verts = [vert]
    edges = []
    faces = []

    for vert in verts:
        for link_face in vert.link_faces:
            if link_face.tag:
                continue
            faces.append(link_face)
            link_face.tag = True
        for link_edge in vert.link_edges:
            if link_edge.tag:
                continue
            link_edge.tag = True
            edges.append(link_edge)
            other_vert = link_edge.other_vert(vert)
            if other_vert.tag:
                continue
            verts.append(other_vert)
            other_vert.tag = True

        vert.tag = True
    return BMRegion(verts, edges, faces)
def bm_loose_parts(bm):
    # Clear tags
    for v in bm.verts:
        v.tag = False
    for e in bm.edges:
        e.tag = False
    for f in bm.faces:
        f.tag = False

    loose_parts = []
    for seed_vert in bm.verts:
        if seed_vert.tag:
            continue
        # We could yield instead
        # but tag could be modifed after yield
        # so better to store results in a list
        loose_parts.append(_bm_grow_tagged(seed_vert))

    return loose_parts

classes = []


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass