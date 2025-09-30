import bpy
from . import sets
from . import settings
from . import helpers
from . import uv
from . import geotags
from . import sets_cage

def getCollection(context, createIfNeeded=False):
    c = context.scene.gflow.painterLowCollection
    name = sets.getSetName(context) + "_low"

    if not c and createIfNeeded:
        c = sets.createCollection(context, name)
        c.color_tag = "COLOR_03"
        context.scene.gflow.painterLowCollection = c    
    if c: c.name = name
    
    return c

def processModifiers(context, generatorData, obj):
    for m in obj.modifiers:
        # These modifiers need to offset their UV outside of the [0,1] range to avoid bade bakes in Substance Painter
        if m.type == "MIRROR" or m.type == "ARRAY":
            m.offset_u = 1.0
            m.offset_v = 1.0
    sets.updateModifierDependencies(generatorData, obj)
def applyModifiers(context, obj):
    if obj.type != 'MESH': return
    modsToKeep = []
    modifiers = [m for m in obj.modifiers if m.type not in modsToKeep]
    helpers.applyModifiers(context, obj, modifiers)            

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

    stgs = settings.getSettings()
    lpsuffix = stgs.lpsuffix

    # Go through all the objects of the working set
    knownMeshes = []
    knownObjectsWithMeshInUvSquare = {}
    gen = sets.GeneratorData()
    
    def populateLowList(objectsToDuplicate, namePrefix="", allowUvOffset=True):
        localGen = sets.GeneratorData()
        roots = []
        parented = []
        instanceRootsTransforms = {}
        for o in objectsToDuplicate:
            if not (o.type == 'MESH' or o.type=='EMPTY' or o.type=='ARMATURE'): continue
            if o.gflow.objType != 'STANDARD': continue
            
            # Make a copy the object
            newobj = sets.duplicateObject(o, lowCollection, suffix=lpsuffix)
            newobj.name = namePrefix+newobj.name
            gen.register(newobj, o)
            localGen.register(newobj, o)

            if o.type=='MESH':
                # Special handling of instanced meshes
                # Painter doesn't like overlapping UVs when baking so we offset the UVs by 1
                if o.data in knownMeshes:
                    if allowUvOffset:
                        # So in case of conflict, if we are allowed to, we just offset the UVs by exactly one UV square
                        # NOTE: Don't need to de-instantiate, the lowpoly copy has its own data
                        uv.offsetCoordinates(newobj)
                    else:
                        # However, there are times we absolutely want one specific instance to be the one staying in the main uv square
                        # So instead we leave the current one where it is, but move whatever instance was there before outside
                        try:
                            uv.offsetCoordinates(knownObjectsWithMeshInUvSquare[o.data])
                            knownObjectsWithMeshInUvSquare[o.data] = newobj
                        except:
                            # Turns out there was nothing in the uv square
                            pass
                else:
                    knownMeshes.append(o.data)
                    knownObjectsWithMeshInUvSquare[o.data]= newobj
            
                # Set the material
                material = sets.getTextureSetMaterial(o.gflow.textureSet, context.scene.gflow.mergeUdims)
                sets.setMaterial(newobj, material)
                
                
            elif o.type == 'EMPTY':
                newobj.instance_type = 'NONE'

            if o.parent != None: 
                parented.append(newobj)
                # Unparent for now
                newobj.parent = None
                newobj.matrix_world = o.matrix_world.copy()
            else:
                roots.append(newobj)

            # Realise the instance
            if helpers.isObjectCollectionInstancer(o) and o.instance_collection:
                if o.gflow.instanceBake == "LOW" or o.gflow.instanceBake == "LOW_HIGH":
                    instanced = o.instance_collection.all_objects
                    instanceRoots = populateLowList(instanced, namePrefix = o.name+"_", allowUvOffset = not o.gflow.instancePriority) 
                    for r in instanceRoots: 
                        helpers.setParent(r, newobj) # we can parent everything to the new empty
                        r.matrix_world = o.matrix_world @ r.matrix_world  # we also need to move the instances into world space
        #endfor object duplication
  
        # Apply bake actions before we apply the armature modifiers
        for newobj in localGen.generated:
            sets.setObjectAction(newobj, newobj.gflow.bakeAction, newobj.gflow.bakeActionObjectSlotName)
            sets.setShapekeyAction(newobj, newobj.gflow.bakeAction, newobj.gflow.bakeActionShapekeySlotName)
  
        # Now go back through all the objects and deal with their mesh data and modifiers
        # It is crucial to wait until the other objects have been created so that we can e.g. change what object is referenced in mirror or array modifiers
        for newobj in localGen.generated:
            if newobj.type == 'MESH':
                helpers.setSelected(context, newobj)
                sets.collapseEdges(context, newobj)
                sets.removeEdgesForLevel(context, newobj, 0, keepPainter=True)
                sets.deleteDetailFaces(context, newobj)
                sets.generatePartialSymmetryIfNeeded(context, newobj, offsetUvs=True)
                
                # Process modifiers
                processModifiers(context, localGen, newobj)
                sets.removeLowModifiers(context, newobj)
                sets.triangulate(context, newobj)
                sets.enforceModifiersOrder(context, newobj)
                sets.removePainterModifiers(context, newobj)
                sets.applyPainterModifiers(context, newobj, False)
                sets.enforceModifiersOrder(context, newobj)
                applyModifiers(context, newobj) # needs to be done if we use any shapekeys
                helpers.setDeselected(newobj)            
  
        # Now that we have all the objects we can try rebuilding the intended hierarchy
        for newobj in parented:
            localGen.reparent(newobj)
                
        return roots
                
    bpy.ops.object.select_all(action='DESELECT')  
    populateLowList(list(context.scene.gflow.workingCollection.all_objects))
     
    # Deal with anchors
    for o in gen.generated:
        if o.gflow.bakeAnchor:
            o.matrix_world = o.gflow.bakeAnchor.matrix_world.copy()        

    # Generate the cage
    if context.scene.gflow.useCage:
        sets_cage.generatePainterCage(context)

    # Clean up metadata and dissolve geo used to generate the cage
    for o in gen.generated:
        if o.type == 'MESH': 
            sets.removeCageEdges(o)
            geotags.removeObjectLayers(o)
            sets_cage.removeCageModifier(context, o)
        
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