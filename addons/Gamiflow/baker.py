import bpy

from . import helpers
from . import settings
from . import sets
from . import sets_low
from . import sets_high
from . import uv
import time

def findNodeByName(name, nodes):
    for n in nodes: 
        if n.name == name: return n
    return None
def findNodeByLabel(label, nodes):
    for n in nodes:
        if n.label == label: return n
    return None
    
def createTextures(context, udimId):
    mergeUdims = context.scene.gflow.mergeUdims
    udimName = sets.getTextureSetName(udimId, mergeUdims=mergeUdims)
    resolution = int(context.scene.gflow.uvResolution)
    material = sets.getTextureSetMaterial(udimId, mergeUdims)
    
    material.use_nodes = True
    imageNodes = [node for node in material.node_tree.nodes if node.type=='TEX_IMAGE']
    rootNode = None
    for n in material.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            rootNode = n
            break
    
    # Prepare the AO map
    ao_name = udimName + "_occlusion"
    ## Delete old image
    if ao_name in bpy.data.images: bpy.data.images.remove(bpy.data.images[ao_name])
    ## Create a new one with the right settings
    bpy.ops.image.new(name=ao_name, width=resolution, height=resolution, color=(1.0, 1.0, 1.0, 1.0), alpha=False, generated_type='BLANK', float=False)
    ao_texture = bpy.data.images[ao_name]
    ao_texture.colorspace_settings.name = 'Non-Color'
    ## Add the AO map to the lowpoly material
    aoNode = findNodeByName(ao_name, imageNodes)
    if aoNode is None:
        aoNode = material.node_tree.nodes.new("ShaderNodeTexImage")
        aoNode.name = ao_name
        aoNode.location = (-500,300)
        material.node_tree.links.new(aoNode.outputs['Color'], rootNode.inputs['Base Color'])
    aoNode.image = ao_texture

    # Prepare the Tangent Normal map
    normal_name = udimName + "_normal"
    ## Delete old image
    if normal_name in bpy.data.images: bpy.data.images.remove(bpy.data.images[normal_name])
    ## Create a new one with the right settings
    bpy.ops.image.new(name=normal_name, width=resolution, height=resolution, color=(0.5, 0.5, 1.0, 1.0), alpha=False, generated_type='BLANK', float=False)
    normal_texture = bpy.data.images[normal_name]
    normal_texture.colorspace_settings.name = 'Non-Color'
    # Add the normal node
    normalNode = findNodeByName(normal_name, imageNodes)
    if normalNode is None:
        normalNode = material.node_tree.nodes.new("ShaderNodeTexImage")
        normalNode.name = normal_name
        normalNode.location = (-500, 0)
        
        # add the normal map node too
        normalMapNode = material.node_tree.nodes.new("ShaderNodeNormalMap")
        normalMapNode.space = 'TANGENT'
        normalMapNode.location = (-250, 0)
        # link everything
        material.node_tree.links.new(normalNode.outputs['Color'], normalMapNode.inputs['Color'])
        material.node_tree.links.new(normalMapNode.outputs['Normal'], rootNode.inputs['Normal'])
    normalNode.image = normal_texture

    return [material, aoNode, normalNode]
    
def bake(context):
    nbUdims = len(context.scene.gflow.udims)
    if context.scene.gflow.mergeUdims: nbUdims = 1
    for udimId in range(0, nbUdims):
        bakeUdim(context, udimId)
        
def findRelevantHighPolys(stg, lowpoly, allHighPolys):
    matches = []
    baseName = lowpoly.name
    suffixPos = lowpoly.name.find(stg.lpsuffix)
    if suffixPos == -1: return matches
    baseName = lowpoly.name[0:suffixPos]
    for hp in allHighPolys:
        if not helpers.isObjectMeshLike(hp): continue
        if not hp.name.startswith(baseName): continue 
        matches.append(hp)
    return matches
        
def bakeUdim(context, udimId):
    stgs = settings.getSettings()
    lowCollection = sets_low.getCollection(context, createIfNeeded=False)
    highCollection = sets_high.getCollection(context, createIfNeeded=False)
    if not (lowCollection and highCollection): return
    
    bpy.ops.object.select_all(action='DESELECT')
    
    setup = createTextures(context, udimId)
    material = setup[0]
    aoNode = setup[1]
    normalNode = setup[2]
    
    sets.setCollectionVisibility(context, lowCollection, True)
    sets.setCollectionVisibility(context, highCollection, True)
    
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    bakeSettings = context.scene.render.bake
    bakeSettings.target = 'IMAGE_TEXTURES'
    if bakeSettings.cage_extrusion == 0.0:
        bakeSettings.cage_extrusion = 0.25 # TODO
    bakeSettings.margin_type = 'EXTEND'
    bakeSettings.use_selected_to_active = True
    
    margin = int(context.scene.gflow.uvMargin)
    
    start = time.time()
    
    useClear = True
    total = len(lowCollection.all_objects)
    count = 0
    for o in lowCollection.all_objects:
        if o.type != 'MESH': continue
        if not context.scene.gflow.mergeUdims:
            if o.gflow.textureSet != udimId: continue
        if not uv.areUVsProbablyInside(o): continue
        print("Processing "+o.name+" "+str(count+1)+"/"+str(total))
        
        # Find its high-poly counterparts and select them
        highpolys = findRelevantHighPolys(stgs, o, highCollection.all_objects)
        for hp in highpolys: hp.select_set(True)
        # Select the low poly and make it active
        helpers.setSelected(context, o)
    
        # Run the bake
        ## AO
        material.node_tree.nodes.active = aoNode
        bpy.ops.object.bake(type="AO", margin = margin, use_clear = useClear)
        ## Tangent-space normal map
        material.node_tree.nodes.active = normalNode
        bpy.ops.object.bake(type="NORMAL", normal_space = 'TANGENT', margin = margin, use_clear = useClear)
        # Deselect everything
        helpers.setDeselected(o)
        for hp in highpolys: hp.select_set(False)
        
        useClear = False
        count = count + 1
    end = time.time()
    print("Baked udim "+str(udimId)+" in "+str(end-start)+"s")
        
    sets.setCollectionVisibility(context, highCollection, False)
      
class GFLOW_OT_Bake(bpy.types.Operator):
    bl_idname      = "gflow.bake"
    bl_label       = "Bake"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}


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
        bake(context)
        return {"FINISHED"} 
        
classes = [GFLOW_OT_Bake]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass        