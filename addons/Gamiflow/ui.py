import bpy
from . import geotags
from . import sets

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
        layout.operator("gflow.clear_sets")
        
        row = layout.row()
        op = row.operator("gflow.toggle_set_visibility", text="Working", depress=sets.getCollectionVisibility(context, context.scene.gflow.workingCollection))
        op.collectionId = 0
        op = row.operator("gflow.toggle_set_visibility", text="Low", depress=sets.getCollectionVisibility(context, context.scene.gflow.painterLowCollection))
        op.collectionId = 1
        op = row.operator("gflow.toggle_set_visibility", text="High", depress=sets.getCollectionVisibility(context, context.scene.gflow.painterHighCollection))
        op.collectionId = 2
        op = row.operator("gflow.toggle_set_visibility", text="Final", depress=sets.getCollectionVisibility(context, context.scene.gflow.exportCollection))
        op.collectionId = 3            


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

        row = layout.row()
        row.operator("gflow.make_low")
        row.operator("gflow.make_high")
        layout.operator("gflow.export_painter")
        
class GFLOW_PT_ExportPanel(GFLOW_PT_BASE_PANEL, bpy.types.Panel):
    bl_label = "Export Sets"
    bl_parent_id = "GFLOW_PT_PANEL"
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.gflow, "exportTarget")
        row = layout.row()
        row.prop(context.scene.gflow, "exportAnimations")
        row.prop(context.scene.gflow, "lightmapUvs")
        layout.operator("gflow.make_export")
        
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
        
class GFLOW_UL_udims(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        layout.label(text="", icon="KEYFRAME")
        layout.prop(item, "name", text="")
        #if item.obj: layout.prop(item.obj.gflow, "objType", text="")
        
      


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
        gflow = context.object.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.layout.enabled = gflow.objType == "STANDARD"
        
        # Unwrap
        col = self.layout.column(align=False, heading="Unwrap")
        row = col.row(align=True)
        sub = row.row(align=True)
        sub.prop(gflow, "unwrap", text="")
        sub = sub.row(align=True)
        sub.active = gflow.unwrap
        sub.prop(gflow, "unwrap_method", text="")
        
        # Smooth
        row = col.row(align=True)
        row.active = gflow.unwrap
        sub = row.row(align=True)
        sub.prop(gflow, "unwrap_smooth_iterations", text="Smooth")
        sub.prop(gflow, "unwrap_smooth_strength", text="x", slider=True)
        
        # Texture set
        self.layout.separator()
        self.layout.prop(gflow, "textureSetEnum")

class GamiflowObjPanel_Bake(bpy.types.Panel):
    bl_label = "Bake"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_parent_id = "GFLOW_PT_OBJ_PANEL"
    bl_idname = "OBJECT_PT_gamiflow_bake"
    
    def draw(self, context):    
        gflow = context.object.gflow
        isStandard = gflow.objType == "STANDARD"
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        self.layout.prop(gflow, "objType")
        
        row = self.layout.row()
        row.prop(gflow, "includeSelf")
        row.enabled = isStandard
        row = self.layout.row()
        row.enabled = gflow.includeSelf and isStandard
        row.prop(gflow, "removeHardEdges")
                
        # Highpoly list
        row = self.layout.row()
        row.enabled = isStandard
        row.template_list("GFLOW_UL_highpolies", "", gflow, "highpolys", gflow, "ui_selectedHighPoly", rows=3)
        col = row.column(align=True)
        col.operator("gflow.add_high", icon='ADD', text="")
        col.operator("gflow.remove_high", icon='REMOVE', text="")
        
        # Anchor
        self.layout.prop(gflow, "bakeAnchor")
        row = self.layout.row()
        row.enabled = gflow.bakeAnchor is not None
        row.prop(gflow, "bakeGhost")       
        
        
class GamiflowObjPanel_Export(bpy.types.Panel):
    bl_label = "Export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_parent_id = "GFLOW_PT_OBJ_PANEL"
    bl_idname = "OBJECT_PT_gamiflow_export"
    
    def draw(self, context):
        gflow = context.object.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False     
        self.layout.prop(gflow, "exportAnchor")        
        self.layout.prop(gflow, "mergeWithParent")
       

class GFLOW_UL_highpolies(bpy.types.UIList):

    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        layout.label(text="", icon="KEYFRAME")
        layout.prop(item, "obj", text="")
        if item.obj: layout.prop(item.obj.gflow, "objType", text="")
        

# Object settings
class GFLOW_PT_OBJ_EDIT_PANEL(bpy.types.Panel):
    bl_category = "Gamiflow"
    bl_label = "Gamiflow"
    bl_idname = "GFLOW_PT_OBJ_EDIT_PANEL"
    bl_space_type = "VIEW_3D"  
    bl_region_type = "UI"
    bl_context = 'mesh_edit'

    def draw(self, context):
        gflow = context.object.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False    
        row = self.layout.row(align=True)
        # UV gridification
        row.label(text="Gridify")
        op = row.operator("gflow.uv_gridify", text="On", icon='VIEW_ORTHO')
        op = row.operator("gflow.uv_degridify", text="Off", icon='CANCEL')    
        row.operator("gflow.uv_select_gridify", icon='RESTRICT_SELECT_OFF', text='Select')
        # UV orientation
        row = self.layout.row(align=True)
        row.label(text="Orient")
        row.operator("gflow.uv_orient_horizontal", text="Horizontal", icon='FORWARD')
        row.operator("gflow.uv_orient_vertical", text="Vertical", icon='SORT_DESC')
        row.operator("gflow.uv_orient_neutral", text="Neutral", icon='CANCEL')
        # UV Scale
        row = self.layout.row(align=False)
        row.prop(context.scene.gflow, 'uvScaleFactor')
        row.operator("gflow.set_uv_scale", text="Apply", icon='MOD_MESHDEFORM').scale = context.scene.gflow.uvScaleFactor
        # Detail edges
        self.layout.separator()
        op = self.layout.operator("gflow.set_edge_level", text="Mark as high poly")
        op.level = geotags.GEO_EDGE_LEVEL_LOD0
        op = self.layout.operator("gflow.select_edge_level", text="Select detail")
        op.level = 0

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
        row.prop(overlays, "uvGridification", text="UV Grid", toggle=True)
        row.prop(overlays, "uvScale", text="UV Scale", toggle=True)
        row.prop(overlays, "detailEdges", text="Edge Detail", toggle=True)
         
        
# Pie menus
class GFLOW_MT_PIE_Object(bpy.types.Menu):
    bl_label = "Gamiflow"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        # Pie order: west, east, south, north, north-west, north-east, south-west, south-east
        
        if context.mode == 'OBJECT':
            pie.operator("gflow.set_smoothing")
            pie.operator("gflow.add_bevel")
        elif context.mode == "EDIT_MESH":
            if bpy.context.tool_settings.mesh_select_mode[1]:
                # Edge mode
                pie.separator() # Empty W
                pie.separator() # Empty E
                pie.operator("gflow.set_edge_level", text="Mark Painter Detail").level = geotags.GEO_EDGE_LEVEL_PAINTER
                #pie.separator() # Empty S
                pie.operator("gflow.add_soft_seam")
                pie.operator("gflow.add_hard_seam")
                pie.operator("gflow.clear_seam")
                pie.operator("gflow.set_edge_level", text="Mark High Detail").level = geotags.GEO_EDGE_LEVEL_LOD0
                pie.operator("gflow.set_edge_level", text="Mark Regular Detail").level = geotags.GEO_EDGE_LEVEL_DEFAULT
            if bpy.context.tool_settings.mesh_select_mode[2]:
                pie.operator("gflow.uv_gridify", text="Gridify", icon='VIEW_ORTHO')
                pie.operator("gflow.uv_degridify", text="Ungridify", icon='CANCEL')    
                
                
class VIEW3D_OT_PIE_Obj_call(bpy.types.Operator):
    bl_idname = 'gamiflow.objpiecaller'
    bl_label = 'S.Menu Navigation'
    bl_description = 'Calls pie menu'
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name="GFLOW_MT_PIE_Object")
        return {'FINISHED'}
        

classes = [
    GFLOW_PT_Panel, GFLOW_PT_WorkingSet, GFLOW_PT_PainterPanel, GFLOW_PT_ExportPanel, GFLOW_PT_UdimsPanel,
    GFLOW_UL_highpolies, GFLOW_UL_udims,
    GFLOW_PT_OBJ_PANEL, GamiflowObjPanel_UV, GamiflowObjPanel_Bake, GamiflowObjPanel_Export,
    GFLOW_PT_OBJ_EDIT_PANEL,
    GFLOW_PT_Overlays,
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
    # edit Mode
    km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new(VIEW3D_OT_PIE_Obj_call.bl_idname, 'V', 'PRESS', ctrl=False, shift=True)    
    
    addon_keymaps.append((km, kmi))    
        
    pass
def unregister():
    global addon_keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass