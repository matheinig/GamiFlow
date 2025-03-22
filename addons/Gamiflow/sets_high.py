import bpy
from . import sets
from . import settings
from . import helpers
from . import geotags
from . import sets_cage

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterHighCollection
    name = sets.getSetName(context) + "_high"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_01"
        context.scene.gflow.painterHighCollection = c
    if c: c.name = name
    return c

def linearToGamma(lin):
    if lin > 0.0031308:
        s = 1.055 * (pow(lin, (1.0 / 2.4))) - 0.055
    else:
        s = 12.92 * lin
    return s

def bakeVertexColours(obj):
    # Any existing colour is assumed to be what we want to be exported
    if len(obj.data.color_attributes)>0: return
    
    # First, we need to find all the material colours
    materialColours = []
    for ms in obj.material_slots:
        material = ms.material
        colour = helpers.getMaterialColour(material)
        sRGB = [linearToGamma(colour[0]), linearToGamma(colour[1]), linearToGamma(colour[2]), 1.0]
        materialColours.append(sRGB)

    if len(materialColours) == 0: materialColours.append([1.0,1.0,1.0,1.0])

    # Create a suitable colour attribute
    attrName = "GFLOW_BakedMaterial"
    attribute = obj.data.color_attributes.new(attrName, type="BYTE_COLOR", domain="CORNER")
    
    # Fill in the data
    with helpers.objectModeBmesh(obj) as bm:
        layer = bm.loops.layers.color[attrName]
        for f in bm.faces:
            colour = materialColours[f.material_index]
            for loop in f.loops:
                loop[layer] = colour
    return

def bakeObjectsNeedsProcessing(obj, stgs):
    if len(obj.modifiers) != 0: return False
    if stgs.idMap == 'VERTEX' and len(obj.data.color_attributes)==0: return False
    with helpers.objectModeBmesh(obj) as bm:
        mirrorLayer = geotags.getMirrorLayer(bm)
        if mirrorLayer: return False
    return True

def generateIdMap(stgs, obj):
    if stgs.idMap == 'VERTEX': bakeVertexColours(obj)

def processNewObject(context, o, stgs, isBakeObject=False):
    generateIdMap(stgs, o)
    sets.generatePartialSymmetryIfNeeded(context, o)
    sets.removePainterModifiers(context, o)
    # We don't need to do this for bake objects,and it means that we don't always need to modify the mesh
    if (not isBakeObject):
        if o.gflow.removeHardEdges: sets.removeSharpEdges(o)
        triangulate: sets.triangulate(context, o)
        geotags.removeObjectLayers(o)
    
    # When using the blender baker we actually *need* the hp-only modifiers to have their visibility set back to render mode
    if stgs.baker == 'BLENDER':
        for m in o.modifiers:
            if m.show_viewport: m.show_render = True

def generatePainterHigh(context):
    highCollection = getCollection(context, createIfNeeded=False)
    if highCollection: sets.clearCollection(highCollection)
    highCollection = getCollection(context, createIfNeeded=True)
    
    # Visibility
    sets.setCollectionVisibility(context, highCollection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterLowCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterCageCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.exportCollection, False)

    stgs = settings.getSettings()
    decalsuffix = stgs.decalsuffix

    # Go through all the objects of the working set
    gen = sets.GeneratorData()
    
    def populateHighList(objectsToDuplicate, namePrefix=""):
        localgen = sets.GeneratorData()
        roots = []
        parented = []
    
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type == 'FONT' or o.type == 'CURVE' or o.type=='EMPTY'): continue
            if not (o.gflow.objType == 'STANDARD' or o.gflow.objType == 'OCCLUDER' or o.gflow.objType == 'NON_BAKED'): continue
            
            suffix = stgs.hpsuffix
            if o.gflow.objType == 'OCCLUDER': suffix = "_occluder"                

            

            # Collection instancing
            if helpers.isObjectCollectionInstancer(o) and o.instance_collection:
                newobj = sets.duplicateObject(o, highCollection, suffix=suffix)
                newobj.name = namePrefix + newobj.name
                newobj.instance_type = 'NONE'
                gen.register(newobj, o)
                localgen.register(newobj, o)
            
                if o.parent != None: 
                    parented.append(newobj)
                    # Unparent for now
                    newobj.parent = None
                    newobj.matrix_world = o.matrix_world.copy()
                else:
                    roots.append(newobj)            
            
                if o.gflow.instanceBake == "LOW_HIGH" or o.gflow.instanceBake == "HIGH":
                    instanced = o.instance_collection.all_objects
                    instanceRoots = populateHighList(instanced, o.name+"_")
                    # Keep track of where the instances should be located
                    for r in instanceRoots: 
                        helpers.setParent(r, newobj) # we can parent everything to the new empty
                        r.matrix_world = o.matrix_world @ r.matrix_world  # we also need to move the instances into world space   
                continue

            # Anything here is objects that are mesh-like
            newobj = None
            
            # Standard case: we just duplicate the working object and make minor adjustments
            if o.gflow.includeSelf:
                if o.gflow.singleSided: suffix += decalsuffix
                newobj = sets.duplicateObject(o, highCollection, suffix=suffix)
                newobj.name = namePrefix + newobj.name
                
                # Convert the 'mesh-adjacent' objects into actual meshes
                if o.type == 'FONT' or o.type == 'CURVE': 
                    helpers.convertToMesh(context, newobj)
                gen.register(newobj, o)
                localgen.register(newobj, o)
                
                if o.parent != None: 
                    newobj.parent = None
                    newobj.matrix_world = o.matrix_world.copy()
                    parented.append(newobj)
                else:
                    roots.append(newobj)
        
                if o.type == 'MESH':
                    processNewObject(context, newobj, stgs)
                        
            # But we can also have manually-linked high-polys that we have to add and parent
            for hp in o.gflow.highpolys:
                if hp.obj is None: continue
                canUseLinkedInstance = not bakeObjectsNeedsProcessing(o, stgs)
                newhp = sets.duplicateObject(hp.obj, highCollection, suffix="_TEMP_", link=canUseLinkedInstance)
                helpers.convertToMesh(context, newhp)
                hpsuffix = suffix
                if hp.obj.gflow.objType == 'DECAL' or hp.obj.gflow.singleSided: 
                    hpsuffix = hpsuffix + decalsuffix
                newhp.name = namePrefix+sets.getNewName(o, "", hpsuffix) + "_" + hp.obj.name
                processNewObject(context, newhp, stgs, isBakeObject=True)
                gen.register(newhp, hp.obj)
                localgen.register(newhp, hp.obj)
                if newobj: 
                    # if we had a base object, parent them to it (in case they get transformed with anchors)
                    helpers.setParent(newhp, newobj)
                else:
                    # Otherwise, assume they are like any other objects
                    ## TODO: this does not take into account that the base object might have had a bake anchor
                    if o.parent != None: 
                        newhp.parent = None
                        newhp.matrix_world = hp.obj.matrix_world.copy()
                        parented.append(newhp)
            #endfor custom highpolys
        #endfor object duplication

        # Now go back through all the objects and deal with their mesh data and modifiers
        # It is crucial to wait until the other objects have been created so that we can e.g. change what object is referenced in mirror or array modifiers
        for newobj in localgen.generated:
            sets.updateModifierDependencies(localgen, newobj)
        # Now that we have all the objects we can try rebuilding the intended hierarchy
        for newobj in parented:
            localgen.reparent(newobj)
        return roots


        
    populateHighList(list(context.scene.gflow.workingCollection.all_objects))
        

    # Deal with anchors
    for o in gen.generated:
        if o.gflow.bakeAnchor and o.gflow.bakeGhost:
            # Leave a ghost behind if need be
            ## TODO: maybe the children should also be ghosted
            ghost = sets.duplicateObject(o, highCollection, suffix="_ghost")
            # Teleport
            o.matrix_world = o.gflow.bakeAnchor.matrix_world.copy()
           
    # Remove cage modifiers in case the user played with them
    for o in gen.generated:
        sets_cage.removeCageModifier(context, o)
           
    return


class GFLOW_OT_MakeHigh(bpy.types.Operator):
    bl_idname      = "gflow.make_high"
    bl_label       = "Make High"
    bl_description = "Generate high-poly meshes for Painter"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):
        generatePainterHigh(context)
        
        return {"FINISHED"} 


classes = [GFLOW_OT_MakeHigh,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass