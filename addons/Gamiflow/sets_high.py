import bpy
from . import sets
from . import settings
from . import helpers

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

def generateIdMap(stgs, obj):
    if stgs.idMap == 'VERTEX': bakeVertexColours(obj)

def generatePainterHigh(context):
    highCollection = getCollection(context, createIfNeeded=False)
    if highCollection: sets.clearCollection(highCollection)
    highCollection = getCollection(context, createIfNeeded=True)
    
    # Visibility
    sets.setCollectionVisibility(context, highCollection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterLowCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.exportCollection, False)

    stgs = settings.getSettings()
    decalsuffix = stgs.decalsuffix

    # Go through all the objects of the working set
    gen = sets.GeneratorData()
    
    def populateHighList(objectsToDuplicate, namePrefix=""):
        localgen = sets.GeneratorData()
        roots = []
        parented = []
        instanceRootsTransforms = {}
    
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type == 'FONT' or o.type == 'CURVE' or o.type=='EMPTY'): continue
            if not (o.gflow.objType == 'STANDARD' or o.gflow.objType == 'OCCLUDER'): continue
            
            suffix = stgs.hpsuffix
            if o.gflow.objType == 'OCCLUDER': suffix = "_occluder"                

            

            # Collection instancing
            if helpers.isObjectCollectionInstancer(o) and o.instance_collection:
                newobj = sets.duplicateObject(o, suffix, highCollection)
                newobj.name = namePrefix + newobj.name
                newobj.instance_type = 'NONE'
                gen.register(newobj, o)
                localgen.register(newobj, o)
            
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
                newobj = sets.duplicateObject(o, suffix, highCollection)
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
                    generateIdMap(stgs, newobj)
                    sets.generatePartialSymmetryIfNeeded(context, newobj)
                    sets.triangulate(context, newobj)
                    # remove all hard edges
                    if o.gflow.removeHardEdges: sets.removeSharpEdges(newobj)
                        
            # But we can also have manually-linked high-polys that we have to add and parent
            for hp in o.gflow.highpolys:
                newhp = sets.duplicateObject(hp.obj, "_TEMP_", highCollection)
                helpers.convertToMesh(context, newhp)
                hpsuffix = suffix
                if hp.obj.gflow.objType == 'DECAL': 
                    hpsuffix = hpsuffix + decalsuffix
                newhp.name = namePrefix+sets.getNewName(o, hpsuffix) + "_" + hp.obj.name
                generateIdMap(stgs, newhp)
                sets.triangulate(context, newhp)
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
                        newhp.matrix_world = o.matrix_world.copy()
                        parented.append(newhp)                    

        # Now that we have all the objects we can try rebuilding the intended hierarchy
        for newobj in parented:
            localgen.reparent(newobj)
        # Put the realised instances back in their right place
        for instanceRoot, xform in instanceRootsTransforms.items():
            instanceRoot.matrix_world = xform @ instanceRoot.matrix_world
        return roots


        
    populateHighList(context.scene.gflow.workingCollection.all_objects)
        

    # Deal with anchors
    for o in gen.generated:
        if o.gflow.bakeAnchor:
            # Leave a ghost behind if need be
            ## TODO: maybe the children should also be ghosted
            ghost = sets.duplicateObject(o, "_ghost", highCollection)
            # Teleport
            o.matrix_world = o.gflow.bakeAnchor.matrix_world.copy()

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