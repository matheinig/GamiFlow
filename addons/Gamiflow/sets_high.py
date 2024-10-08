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
    generated = []
    newObjectToOriginalParent = {}     
    for o in context.scene.gflow.workingCollection.all_objects:
        if not (o.type == 'MESH' or o.type == 'FONT'): continue
        if not (o.gflow.objType == 'STANDARD' or o.gflow.objType == 'OCCLUDER'): continue
        
        # Make a copy the object
        suffix = stgs.hpsuffix
        if o.gflow.objType == 'OCCLUDER': suffix = "_occluder"
        
        newobj = None
        if o.gflow.includeSelf:
            newobj = sets.duplicateObject(o, suffix, highCollection)
            helpers.convertToMesh(context, newobj)
            generated.append(newobj)
            generateIdMap(stgs, newobj)
            
            if o.parent != None: 
                helpers.setParent(newobj, o.parent)
                newObjectToOriginalParent[newobj] = o.parent
        
            # handle special modifiers like subdiv
    
            sets.triangulate(context, newobj)
    
            # remove all hard edges
            if o.gflow.removeHardEdges: sets.removeSharpEdges(newobj)
        
        # Add all manually-linked highpolys
        for hp in o.gflow.highpolys:
            newhp = sets.duplicateObject(hp.obj, "_TEMP_", highCollection)
            helpers.convertToMesh(context, newhp)
            generateIdMap(stgs, newhp)
            hpsuffix = suffix
            if hp.obj.gflow.objType == 'DECAL': 
                hpsuffix = hpsuffix + decalsuffix
            newhp.name = sets.getNewName(o, hpsuffix) + "_" + hp.obj.name
            sets.triangulate(context, newhp)
            # parent them to the object (in case they get transformed with anchors)
            if newobj: helpers.setParent(newhp, newobj)


    # Now that we have all the objects we can try rebuilding the intended hierarchy
    for newobj, origParent in newObjectToOriginalParent.items():
        # Find new parent
        newParentName = sets.getNewName(origParent, suffix)
        newParent = helpers.findObjectByName(generated, newParentName)
        # Set new parent
        if newParent: 
            matrix = newobj.matrix_world.copy()
            newobj.parent = newParent
            newobj.matrix_world = matrix    

    # Deal with anchors
    for o in generated:
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