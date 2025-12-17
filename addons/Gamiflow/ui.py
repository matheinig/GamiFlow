import bpy
from . import geotags
from . import sets
from . import settings
from . import helpers
from bl_ui import anim
# Side panel
class GFLOW_PT_BASE_PANEL(bpy.types.Panel):
    bl_space_type = "VIEW_3D"  
    bl_region_type = "UI"
    bl_category = "Gamiflow"
    bl_context = "objectmode"   
    def draw(self, context):
        row = self.layout.row()
        pass        
class GFLOW_PT_Panel(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "Gamiflow"  
    bl_idname = "GFLOW_PT_PANEL"
    def draw(self, context):
        layout = self.layout
        layout.operator("gflow.clear_sets", icon='TRASH')
        
        row = layout.row()
        op = row.operator("gflow.toggle_set_visibility", text="Working", depress=sets.getCollectionVisibility(context, context.scene.gflow.workingCollection))
        op.collectionId = 0
        if context.scene.gflow.useCage:
            op = row.operator("gflow.toggle_set_visibility", text="Cage", depress=sets.getCollectionVisibility(context, context.scene.gflow.painterCageCollection))
            op.collectionId = 4        
        op = row.operator("gflow.toggle_set_visibility", text="Low", depress=sets.getCollectionVisibility(context, context.scene.gflow.painterLowCollection))
        op.collectionId = 1
        op = row.operator("gflow.toggle_set_visibility", text="High", depress=sets.getCollectionVisibility(context, context.scene.gflow.painterHighCollection))
        op.collectionId = 2
        op = row.operator("gflow.toggle_set_visibility", text="Final", depress=sets.getCollectionVisibility(context, context.scene.gflow.exportCollection))
        op.collectionId = 3
        
        layout.prop(context.scene.gflow.lod, "current")


class GFLOW_PT_WorkingSet(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "Working Set"
    bl_parent_id = "GFLOW_PT_PANEL"
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.gflow, "workingCollection")
        
        layout.separator()
        
        row = layout.row()
        row.prop(context.scene.gflow, "uvResolution")
        row.prop(context.scene.gflow, "uvMargin")
        row = layout.row()
        row.prop(context.scene.gflow, "uvPackSettings")
        row.prop(context.scene.gflow, "uvSnap")
        layout.operator("gflow.auto_unwrap")
        layout.operator("gflow.show_uv")
        

class GFLOW_PT_PainterPanel(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "Bake Sets"
    bl_parent_id = "GFLOW_PT_PANEL"
    def draw(self, context):
        layout = self.layout
        # Cage settings
        row = layout.row()
        row.prop(context.scene.gflow, "useCage")
        col = row.column()
        col.enabled = context.scene.gflow.useCage
        col.prop(context.scene.gflow, "cageOffset", text="Offset")
        layout.separator()
        # Bake sets buttons
        row = layout.row()
        row.operator("gflow.make_low")
        row.operator("gflow.make_high")
        stgs = settings.getSettings()
        if stgs.baker == 'BLENDER':
            layout.operator("gflow.bake")
        else:
            layout.operator("gflow.export_painter")
        
class GFLOW_PT_ExportPanel(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "Export Sets"
    bl_parent_id = "GFLOW_PT_PANEL"
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(context.scene.gflow, "exportTarget", text='')
        if context.scene.gflow.exportTarget != 'BLENDER_LIB':
            row.prop(context.scene.gflow, "exportFormat", text='')
        row = layout.row()
        row.prop(context.scene.gflow, "lightmapUvs")
        row = layout.row()
        row.prop(context.scene.gflow, "exportVertexColors")
        if context.scene.gflow.exportVertexColors:
            row = layout.row(align=False)
            row.prop(context.scene.gflow, "vertexChannelR", text="")
            row.prop(context.scene.gflow, "vertexChannelG", text="")
            row.prop(context.scene.gflow, "vertexChannelB", text="")
        layout.operator("gflow.make_export")
        layout.separator()
        row = layout.row()
        
        col = row.column()
        col.active = context.scene.gflow.exportFormat == 'FBX'
        col.prop(context.scene.gflow, "exportFlip")
        row.prop(context.scene.gflow, "exportAnimations")
        row = layout.row()
        row.prop(context.scene.gflow, "exportMethod", text="")
        row.operator("gflow.export_final")
        
   
        
class GFLOW_PT_UdimsPanel(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "UDIMs"
    bl_parent_id = "GFLOW_PT_PANEL"
    def draw(self, context):
        layout = self.layout

        gflow = context.scene.gflow

        row = self.layout.row()
        row.template_list("GFLOW_UL_udims", "", gflow, "udims", gflow, "ui_selectedUdim", rows=2)
        col = row.column(align=True)
        col.operator("gflow.add_udim", icon='ADD', text="")
        col.operator("gflow.remove_udim", icon='REMOVE', text="")
        if bpy.app.version < (4, 3, 0):
            col.prop(gflow, "mergeUdims", icon='MOD_OPACITY', text="")
        else:
            col.prop(gflow, "mergeUdims", icon='AREA_JOIN_DOWN', text="")
        
class GFLOW_UL_udims(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        layout.label(text="", icon="KEYFRAME")
        layout.prop(item, "name", text="")
        #if item.obj: layout.prop(item.obj.gflow, "objType", text="")
        
      
class GFLOW_PT_LodsPanel(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "LODs"
    bl_parent_id = "GFLOW_PT_PANEL"
    bl_options = {"DEFAULT_CLOSED"} 
    def draw(self, context):
        layout = self.layout

        gflow = context.scene.gflow

        row = self.layout.row()
        row.template_list("GFLOW_UL_lod", "", gflow.lod, "lods", gflow.lod, "current", rows=4)
        col = row.column(align=True)
        col.operator("gflow.add_lod", icon='ADD', text="")
        col.operator("gflow.remove_lod", icon='REMOVE', text="")
        
        DisplayLodMenu = False # currently we can fit everything in the list
        if gflow.lod.current<len(gflow.lod.lods) and DisplayLodMenu:
            lod = gflow.lod.lods[gflow.lod.current]
            row = self.layout.row()
            row.prop(lod, "decimate")
            row.prop(lod, "decimateAmount", text='')
            self.layout.prop(lod, "decimatePreserveSeams")
        
class GFLOW_UL_lod(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, index):
        split = layout.split(factor=0.1, align=True)
        split.label(text=str(index))
        row = split.row(align=True)
        if item.decimate:
            row.prop(item, "decimate", text="")
            row.prop(item, "decimateAmount")
            row.prop(item, "decimatePreserveSeams", text="", icon="STICKY_UVS_VERT")
        else:
            row.prop(item, "decimate")

# Object settings
class GFLOW_PT_OBJ_PANEL(bpy.types.Panel):
    bl_label = "Gamiflow"
    bl_idname = "GFLOW_PT_OBJ_PANEL"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    def draw(self, context):
        gflow = context.object.gflow

        # generic stuff  here
        # specific stuff handled in subpanels
        
class GamiflowObjPanel_UV(bpy.types.Panel):
    bl_label = "Texture Coordinates"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_parent_id = "GFLOW_PT_OBJ_PANEL"
    bl_idname = "OBJECT_PT_gamiflow_uv"
    
    def draw(self, context):
        obj = context.object
        gflow = obj.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.layout.enabled = gflow.objType == "STANDARD"
        if obj.type == 'MESH':
            # Unwrap
            col = self.layout.column(align=False, heading="Unwrap")
            row = col.row(align=True)
            sub = row.row(align=True)
            sub.prop(gflow, "unwrap", text="")
            sub = sub.row(align=True)
            sub.active = gflow.unwrap
            sub.prop(gflow, "unwrap_method", text="")
            if gflow.unwrap_method == 'MINIMUM_STRETCH':
                sub = sub.row(align=True)
                sub.active = gflow.unwrap
                sub.prop(gflow, "unwrap_extraParameter", text="x")
            
            # Fill Holes
            row = col.row(align=True)
            row.active = gflow.unwrap
            row.prop(gflow, "unwrap_fillHoles")
                
            # Smooth
            row = col.row(align=True)
            row.active = gflow.unwrap
            sub = row.row(align=True)
            sub.prop(gflow, "unwrap_smooth_iterations", text="Smooth")
            sub.prop(gflow, "unwrap_smooth_strength", text="x", slider=True)
            
            # Texture set
            self.layout.separator()
            self.layout.prop(gflow, "textureSetEnum")

class GFLOW_OT_ObjectActionSlotPopup(bpy.types.Operator):
    """Set Action Slot"""
    bl_idname = "gflow.action_slot_popup"
    bl_label = "Set Action Slot"
    bl_options = {'REGISTER', 'INTERNAL'}

    mode: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        obj = context.object
        gflow = obj.gflow
        if obj.animation_data and obj.animation_data.action_slot:
            if self.mode=='BAKE':
                gflow.bakeActionObjectSlotName = obj.animation_data.action_slot.identifier
            else:
                gflow.exportActionObjectSlotName = obj.animation_data.action_slot.identifier
        if obj.type == 'MESH' and obj.data.shape_keys and obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.action_slot:
            if self.mode=='BAKE':
                gflow.bakeActionShapekeySlotName = obj.data.shape_keys.animation_data.action_slot.identifier
            else:
                gflow.exportActionShapekeySlotName = obj.data.shape_keys.animation_data.action_slot.identifier
        context.area.tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        
        obj = context.object
    
        self.layout.template_action(obj, new="action.new", unlink="action.unlink")
    
        # Object action slot
        target = obj
        adt = target.animation_data
        if adt.action.is_action_layered:
            # pointer is maybe just for new/delete
            #self.layout.context_pointer_set("animated_id", target)
            self.layout.template_search(
                adt, "action_slot",
                adt, "action_suitable_slots",
                #new="anim.slot_new_for_id",
                #unlink="anim.slot_unassign_from_id",
                text="Object"
            )
        # Shapekey action slot
        if obj.type == 'MESH' and obj.data.shape_keys:
            target = obj.data.shape_keys
            adt = target.animation_data
            if adt.action.is_action_layered:
                #self.layout.context_pointer_set("animated_id", target)
                self.layout.template_search(
                    adt, "action_slot",
                    adt, "action_suitable_slots",
                    #new="anim.slot_new_for_id",
                    #unlink="anim.slot_unassign_from_id",
                    text="Shape key"
                )

class GamiflowObjPanel_Bake(bpy.types.Panel):
    bl_label = "Bake"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_parent_id = "GFLOW_PT_OBJ_PANEL"
    bl_idname = "OBJECT_PT_gamiflow_bake"
    
    def draw(self, context):
        obj = context.object
        gflow = obj.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        if obj.type == 'MESH':
            isStandard = gflow.objType == "STANDARD"
            isTrim = gflow.objType == "NON_BAKED"
     
            self.layout.prop(gflow, "objType")
            
            row = self.layout.row()
            row.prop(gflow, "includeSelf")
            row.enabled = isStandard or isTrim
            row = self.layout.row()
            row.enabled = gflow.includeSelf and isStandard
            row.prop(gflow, "removeHardEdges")
            row = self.layout.row()
            row.enabled = (gflow.includeSelf and isStandard) or gflow.objType == "PROJECTED"
            row.prop(gflow, "singleSided")
                    
            # Highpoly list
            row = self.layout.row()
            row.enabled = isStandard
            row.template_list("GFLOW_UL_highpolies", "", gflow, "highpolys", gflow, "ui_selectedHighPoly", rows=3)
            col = row.column(align=True)
            col.operator("gflow.add_high", icon='ADD', text="")
            col.operator("gflow.remove_high", icon='REMOVE', text="")
            row = col.row()
            row.enabled = len(gflow.highpolys)>0
            op = row.operator("gflow.select_by_name", icon='RESTRICT_SELECT_OFF', text="")
            if row.enabled and gflow.highpolys[gflow.ui_selectedHighPoly].obj is not None: op.name = gflow.highpolys[gflow.ui_selectedHighPoly].obj.name
            
            # Anchor
            self.layout.prop(gflow, "bakeAnchor")
            row = self.layout.row()
            row.enabled = gflow.bakeAnchor is not None
            row.prop(gflow, "bakeGhost")
            
            # Bake action
            if bpy.app.version >= (4,4,0):
                self.layout.separator()
                self.layout.prop(gflow, "bakeAction")
                self.layout.prop(gflow, "bakeActionObjectSlotName")
                self.layout.prop(gflow, "bakeActionShapekeySlotName")
                self.layout.operator("gflow.action_slot_popup", text="Set Bake Slot", icon='ACTION_SLOT').mode = 'BAKE'
            else:
                self.layout.prop(gflow, "bakeAction")            
            
            
            # Cage
            self.layout.separator()
            cageUsed = context.scene.gflow.useCage

            row = self.layout.row()
            row.enabled = cageUsed
            row.prop(gflow, "cageOffset")  
            if geotags.getCageDisplacementMap(obj, forceCreation=False) is None:
                row.operator("gflow.add_cage_displacement_map", icon="GROUP_VERTEX", text="Add tightness map")
            else:
                row.operator("gflow.remove_cage_displacement_map", icon="GROUP_VERTEX", text="Clear")

        elif obj.type == 'ARMATURE':
            # Bake action
            if bpy.app.version >= (4,4,0):
                self.layout.separator()
                self.layout.prop(gflow, "bakeAction")
                self.layout.prop(gflow, "bakeActionObjectSlotName")
                self.layout.operator("gflow.action_slot_popup", text="Set Bake Slot", icon='ACTION_SLOT').mode = 'BAKE'
            else:
                self.layout.prop(gflow, "bakeAction")  
        elif obj.type == 'EMPTY':
            self.layout.prop(gflow, "objType")
            row = self.layout.row()
            validInstancer = (obj.instance_type == 'COLLECTION' and (obj.instance_collection is not None))
            row.enabled = validInstancer
            row.prop(gflow, "instanceBake")
            row = self.layout.row()
            row.enabled = validInstancer and (gflow.instanceBake=='LOW' or gflow.instanceBake=='LOW_HIGH')
            row.prop(gflow, "instancePriority")
        
        
class GamiflowObjPanel_Export(bpy.types.Panel):
    bl_label = "Export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_parent_id = "GFLOW_PT_OBJ_PANEL"
    bl_idname = "OBJECT_PT_gamiflow_export"
    
    def draw(self, context):
        obj = context.object
        gflow = obj.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        if obj.type == 'MESH':
            self.layout.prop(gflow, "exportable")
            
            self.layout.separator()
            self.layout.prop(gflow, "maxLod")
            self.layout.prop(gflow, "allowDecimation")
            self.layout.separator()

            self.layout.prop(gflow, "exportAnchor")
            
            if bpy.app.version >= (4,4,0):
                self.layout.separator()
                self.layout.prop(gflow, "exportAction")
                self.layout.prop(gflow, "exportActionObjectSlotName")
                self.layout.prop(gflow, "exportActionShapekeySlotName")
                self.layout.operator("gflow.action_slot_popup", text="Set Export Slot", icon='ACTION_SLOT').mode = 'EXPORT'
            else:
                self.layout.prop(gflow, "exportAction")
            self.layout.separator()
            self.layout.prop(gflow, "mergeWithParent")
            self.layout.prop(gflow, "doubleSided")
        elif obj.type == 'ARMATURE':
            if bpy.app.version >= (4,4,0):
                self.layout.prop(gflow, "exportAction")
                self.layout.prop(gflow, "exportActionObjectSlotName")
                self.layout.operator("gflow.action_slot_popup", text="Set Export Slot", icon='ACTION_SLOT').mode = 'EXPORT'
            else:
                self.layout.prop(gflow, "exportAction")        
        elif obj.type == 'EMPTY':
            row = self.layout.row()
            self.layout.prop(gflow, "mergeWithParent")
            row.enabled = (obj.instance_type == 'COLLECTION' and (obj.instance_collection is not None))
            row.prop(gflow, "instanceAllowExport")            
       

class GFLOW_UL_highpolies(bpy.types.UIList):

    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        split = layout.split(factor=0.70)
        c = split.row()
        c.label(text="", icon="KEYFRAME")
        c.prop(item, "obj", text="")
        if item.obj: 
            c = split.row()
            c.prop(item.obj.gflow, "objType", text="")
        
# Edit mesh side panel
class GFLOW_PT_OBJ_EDIT_PANEL(bpy.types.Panel):
    bl_category = "Gamiflow"
    bl_label = "Gamiflow"
    bl_idname = "GFLOW_PT_OBJ_EDIT_PANEL"
    bl_space_type = "VIEW_3D"  
    bl_region_type = "UI"
    bl_context = 'mesh_edit'

    def draw(self, context):
        gflow = context.object.gflow
        #self.layout.use_property_split = True
        self.layout.use_property_decorate = False    
        
        self.layout.prop(context.scene.gflow.lod, "current")
        
        self.layout.label(text="UVs")
        # UV Scale
        row = self.layout.row(align=True)
        #row.use_property_split = False
        row.prop(context.scene.gflow, 'uvScaleFactor')
        row.operator("gflow.set_uv_scale", text="Scale", icon='MOD_MESHDEFORM').scale = context.scene.gflow.uvScaleFactor        
        # UV gridification
        row = self.layout.row(align=True)
        op = row.operator("gflow.uv_gridify", text="Grid", icon='VIEW_ORTHO')
        op = row.operator("gflow.uv_degridify", text="Natural", icon='CANCEL')    
        # UV orientation
        row = self.layout.row(align=True)
        row.operator("gflow.uv_orient_horizontal", text="Horizontal", icon='FORWARD')
        row.operator("gflow.uv_orient_vertical", text="Vertical", icon='SORT_DESC')
        row.operator("gflow.uv_orient_neutral", text="Neutral", icon='CANCEL')

        
        self.layout.separator()
        self.layout.label(text="Geo Dissolve")
        # Detail edges
        row = self.layout.row()
        op = row.operator("gflow.set_edge_level", text="Dissolve", icon='EDGESEL')
        op.level = geotags.GEO_EDGE_LEVEL_LOD0+context.scene.gflow.lod.current
        op = row.operator("gflow.set_edge_level", text="Clear")
        op.level = geotags.GEO_EDGE_LEVEL_DEFAULT        
        op = row.operator("gflow.select_edge_level", text="Select")
        op.level = 0
        # Detail Faces
        row = self.layout.row()
        op = row.operator("gflow.set_face_level", text="Dissolve", icon='FACESEL')
        op = row.operator("gflow.set_face_level", text="Clear")
        op.deleteFromLevel = -1       
        op = row.operator("gflow.select_face_level", text="Select detail")
          
# Context menus (right click in viewport)
class GFLOW_MT_MESH_CONTEXT(bpy.types.Menu):
    bl_label = "GamiFlow"
    bl_idname = "MESH_MT_gflow_mesh_menu"

    def draw(self, context):
        layout = self.layout
        layout.separator()
        
        lod = context.scene.gflow.lod
        
        # Edge mode
        if context.tool_settings.mesh_select_mode[1]: 
            layout.label(text="Edge Detail", icon="EDGESEL")
            layout.operator("gflow.set_checkered_ring_edge_level", text="Checkered ring dissolve").level = geotags.GEO_EDGE_LEVEL_LOD0+lod.current
            layout.operator("gflow.set_checkered_edge_collapse", text="Checkered loop collapse").level = geotags.GEO_EDGE_COLLAPSE_LOD0+lod.current
            layout.operator("gflow.collapse_edge_ring", text="Ring collapse").level = geotags.GEO_EDGE_COLLAPSE_LOD0+lod.current
            layout.separator()
            layout.operator("gflow.set_edge_level", text="Mark for Dissolve").level = geotags.GEO_EDGE_LEVEL_LOD0+lod.current
            layout.operator("gflow.set_edge_collapse_level", text="Mark for Collapse").level = geotags.GEO_EDGE_COLLAPSE_LOD0+lod.current
            layout.operator("gflow.set_edge_level", text="Mark as Cage").level = geotags.GEO_EDGE_LEVEL_CAGE
            layout.operator("gflow.unmark_edge", text="Clear")
            
            layout.label(text="UV Seams", icon="UV")
#BEGINTRIM --------------------------------------------------
            layout.operator("gflow.auto_seam")
            layout.operator("gflow.auto_uv")
#ENDTRIM ---            
            layout.operator("gflow.add_soft_seam")
            layout.operator("gflow.add_hard_seam")
            layout.operator("gflow.clear_seam")
        # Face mode
        if context.tool_settings.mesh_select_mode[2]: 
            layout.label(text="Face Detail", icon="FACESEL")
            layout.operator("gflow.set_face_level", text="Mark for Deletion")
            layout.operator("gflow.set_face_level", text="Clear").deleteFromLevel = -1               
            layout.separator()
            layout.label(text="Face Mirroring", icon="MOD_MIRROR")
            layout.operator("gflow.set_face_mirror", text="Mirror").mirror = "X"   
            layout.operator("gflow.set_face_mirror", text="Unmirror").mirror = "NONE" 

def draw_mesh_menu(self, context):
    self.layout.separator(factor=1.0)
    self.layout.menu(GFLOW_MT_MESH_CONTEXT.bl_idname)
    
class GFLOW_MT_OBJECT_CONTEXT(bpy.types.Menu):
    bl_label = "GamiFlow"
    bl_idname = "OBJECT_MT_gflow_object_menu"

    def draw(self, context):
        layout = self.layout
        layout.separator()
        
        layout.operator("gflow.set_smoothing")
        layout.operator("gflow.add_bevel") 
        layout.operator("gflow.set_udim")
        layout.label(text="Baking", icon="MESH_MONKEY")
        layout.operator("gflow.project_to_active")     
#BEGINTRIM --------------------------------------------------        
        layout.label(text="Unwrapping", icon="UV")
        layout.operator("gflow.set_unwrap_method")
        layout.operator("gflow.auto_seam")
        layout.operator("gflow.auto_uv")
#ENDTRIM ---            


def draw_object_menu(self, context):
    self.layout.separator(factor=1.0)
    self.layout.menu(GFLOW_MT_OBJECT_CONTEXT.bl_idname)

# Overlay
class GFLOW_PT_Overlays(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_idname = 'GFLOW_PT_overlays'
    bl_parent_id = 'VIEW3D_PT_overlay_edit_mesh'
    bl_label = "Gamiflow"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        overlays = context.scene.gflow.overlays
        
        row = layout.row(align=True)
        row.prop(overlays, "mirroring", text="Mirrors", toggle=True)
        row.prop(overlays, "uvGridification", text="UV Grid", toggle=True)
        row.prop(overlays, "uvScale", text="UV Scale", toggle=True)
        row.prop(overlays, "detailEdges", text="Edge Detail", toggle=True)
        
        layout.prop(overlays, "edgeOffset", text="Edge offset")
         
        
# Pie menus
class GFLOW_MT_PIE_Object(bpy.types.Menu):
    bl_label = "Gamiflow"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        # Pie order: west, east, south, north, north-west, north-east, south-west, south-east
        
        lod = context.scene.gflow.lod
        
        if context.mode == 'OBJECT':
            pie.operator("gflow.set_smoothing")     # W
            pie.operator("gflow.add_bevel")         # E
            pie.operator("gflow.set_udim")          # S
            pie.operator("gflow.project_to_active") # N
        elif context.mode == "EDIT_MESH":
            if bpy.context.tool_settings.mesh_select_mode[1]:
                # Edge mode
                pie.operator("gflow.set_edge_level", text="Mark Cage Detail").level = geotags.GEO_EDGE_LEVEL_CAGE # W
                pie.separator() # Empty E
                pie.operator("gflow.set_edge_collapse_level", text="Mark Collapse").level = geotags.GEO_EDGE_COLLAPSE_LOD0+lod.current
                pie.operator("gflow.add_soft_seam")
                pie.operator("gflow.add_hard_seam")
                pie.operator("gflow.clear_seam")
                pie.operator("gflow.set_edge_level", text="Mark Dissolve").level = geotags.GEO_EDGE_LEVEL_LOD0+lod.current
                pie.operator("gflow.unmark_edge", text="Unmark")
            if bpy.context.tool_settings.mesh_select_mode[2] and not bpy.context.tool_settings.mesh_select_mode[1]:
                pie.operator("gflow.set_face_mirror", text="Mirror", icon='MOD_MIRROR').mirror = "X"        # W
                pie.operator("gflow.set_face_mirror", text="Unmirror", icon='MOD_MIRROR').mirror = "NONE"   # E
                pie.separator() # Empty S
                pie.separator() # Empty N          
                pie.operator("gflow.uv_gridify", text="Gridify", icon='VIEW_ORTHO')
                pie.operator("gflow.uv_degridify", text="Ungridify", icon='CANCEL')       
                pie.operator("gflow.set_face_level", text="Mark for Deletion")
                pie.operator("gflow.set_face_level", text="Unmark deletion").deleteFromLevel = -1               

                             
                
                
class VIEW3D_OT_PIE_Obj_call(bpy.types.Operator):
    bl_idname = 'gamiflow.objpiecaller'
    bl_label = 'GamiFlow Pie Menu'
    bl_description = 'Calls pie menu'
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="GFLOW_MT_PIE_Object")
        return {'FINISHED'}
        

classes = [
    GFLOW_OT_ObjectActionSlotPopup,
    GFLOW_PT_Panel, GFLOW_PT_WorkingSet, GFLOW_PT_PainterPanel, GFLOW_PT_ExportPanel, GFLOW_PT_UdimsPanel, GFLOW_PT_LodsPanel,
    GFLOW_UL_highpolies, GFLOW_UL_udims, GFLOW_UL_lod,
    GFLOW_PT_OBJ_PANEL, GamiflowObjPanel_UV, GamiflowObjPanel_Bake, GamiflowObjPanel_Export,
    GFLOW_PT_OBJ_EDIT_PANEL,
    GFLOW_PT_Overlays,
    GFLOW_MT_MESH_CONTEXT, GFLOW_MT_OBJECT_CONTEXT,
    GFLOW_MT_PIE_Object, VIEW3D_OT_PIE_Obj_call]

addon_keymaps  = []

def register():
    for c in classes: 
        bpy.utils.register_class(c)
    
    # Register hotkeys
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    global addon_keymaps

    # object Mode
    km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
    kmi = km.keymap_items.new(VIEW3D_OT_PIE_Obj_call.bl_idname, 'V', 'PRESS', ctrl=False, shift=True)
    addon_keymaps.append((km, kmi))    
    # edit Mode
    km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new(VIEW3D_OT_PIE_Obj_call.bl_idname, 'V', 'PRESS', ctrl=False, shift=True)    
    addon_keymaps.append((km, kmi))   

    # Context menus
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(draw_mesh_menu)
    bpy.types.VIEW3D_MT_object_context_menu.append(draw_object_menu)

        
    pass
def unregister():
    global addon_keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    # Context menus
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(draw_mesh_menu)
    bpy.types.VIEW3D_MT_object_context_menu.remove(draw_object_menu)
    
    for c in reversed(classes): 
        helpers.safeUnregisterClass(c)
    pass