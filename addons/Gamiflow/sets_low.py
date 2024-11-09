import bpy
from . import sets
from . import settings
from . import helpers
from . import uv

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterLowCollection
    name = sets.getSetName(context) + "_low"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_03"
        context.scene.gflow.painterLowCollection = c    
    if c: c.name = name
    
    return c

def processModifiers(context, obj):
    for m in obj.modifiers:
        # These modifiers need to offset their UV outside of the [0,1] range to avoid bade bakes in Substance Painter
        if m.type == "MIRROR" or m.type == "ARRAY":
            m.offset_u = 1.0
            m.offset_v = 1.0
    # TODO: apply all modifiers here
            

def generatePainterLow(context):
    lowCollection = getCollection(context, createIfNeeded=False)
    if lowCollection: sets.clearCollection(lowCollection)
    
    lowCollection = getCollection(context, createIfNeeded=True)
    
    # Visibility
    sets.setCollectionVisibility(context, lowCollection, True)
    sets.setCollectionVisibility(context, context.scene.gflow.workingCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.painterHighCollection, False)
    sets.setCollectionVisibility(context, context.scene.gflow.exportCollection, False)

    bpy.ops.object.select_all(action='DESELECT')  

    lpsuffix = settings.getSettings().lpsuffix

    # Go through all the objects of the working set
    knownMeshes = []
    gen = sets.GeneratorData()
    
    def populateLowList(objectsToDuplicate, namePrefix=""):
        roots = []
        parented = []
        instanceRootsTransforms = {}
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type=='EMPTY'): continue
            if o.gflow.objType != 'STANDARD': continue
            
            generateCopy = True
            if helpers.isObjectCollectionInstancer(o): generateCopy = False
            
            if generateCopy:
                # Make a copy the object
                newobj = sets.duplicateObject(o, lpsuffix, lowCollection)
                newobj.name = namePrefix+newobj.name
                gen.register(newobj, o)

                if o.parent != None: 
                    parented.append(newobj)
                    # Unparent for now
                    newobj.parent = None
                    newobj.matrix_world = o.matrix_world.copy()
                else:
                    roots.append(newobj)
                
                if not o.type=='EMPTY':
                    # Special handling of instanced meshes
                    # Painter doesn't like overlapping UVs when baking so we offset the UVs by 1
                    if o.data in knownMeshes:
                        # NOTE: Don't need to de-instantiate, the lowpoly copy has its own data
                        uv.offsetCoordinates(newobj)
                    else:
                        knownMeshes.append(o.data)            
                
                    bpy.ops.object.select_all(action='DESELECT')  
                    sets.removeEdgesForLevel(context, newobj, 0, keepPainter=True)
                    sets.deleteDetailFaces(context, newobj)
                    
                    # Set the material
                    material = sets.getTextureSetMaterial(o.gflow.textureSet)
                    sets.setMaterial(newobj, material)
                    
                    # Remove flagged modifiers
                    sets.removeLowModifiers(context, newobj)
                    # handle special modifiers like subdiv, mirrors, etc
                    processModifiers(context, newobj)
                    
                    # Add simple modifiers if need be
                    #TODO: check if modifiers already present
                    #sets.addWeightedNormals(context, newobj)
                    sets.triangulate(context, newobj)
            else:
                # Realise the instance
                if helpers.isObjectCollectionInstancer(o) and o.instance_collection:
                    if o.gflow.instanceBake == "LOW_HIGH":
                        instanced = o.instance_collection.all_objects
                        instanceRoots = populateLowList(instanced, o.name+"_")
                        # Keep track of where the instances should be located
                        for r in instanceRoots: instanceRootsTransforms[r] = o.matrix_world
        #endfor object duplication
  
        # Now that we have all the objects we can try rebuilding the intended hierarchy
        for newobj in parented:
            gen.reparent(newobj)
        
        # Put the realised instances back in their right place
        for instanceRoot, xform in instanceRootsTransforms.items():
            instanceRoot.matrix_world = xform @ instanceRoot.matrix_world                    
                
        return roots
                
    populateLowList(context.scene.gflow.workingCollection.all_objects)
     
    # Deal with anchors
    for o in gen.generated:
        if o.gflow.bakeAnchor:
            o.matrix_world = o.gflow.bakeAnchor.matrix_world.copy()

    return


class GFLOW_OT_MakeLow(bpy.types.Operator):
    bl_idname      = "gflow.make_low"
    bl_label       = "Make Low"
    bl_description = "Generate low-poly meshes for Painter"
    bl_options = {"REGISTER", "UNDO"}
    @classmethod
    def poll(cls, context):
        if not context.scene.gflow.workingCollection: 
            cls.poll_message_set("Set the working collection first")
            return False
        return True
    def execute(self, context):
        generatePainterLow(context)
        
        return {"FINISHED"} 

classes = [GFLOW_OT_MakeLow,
]


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass