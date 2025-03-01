import bpy
from . import geotags
from . import sets
from . import settings

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
        if bpy.app.version <= (4, 2, 0):
            col.prop(gflow, "mergeUdims", icon='MOD_OPACITY', text="")
        else:
            col.prop(gflow, "mergeUdims", icon='AREA_JOIN_DOWN', text="")
        
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
        obj = context.object
        gflow = obj.gflow
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False           
        if obj.type == 'MESH':
            isStandard = gflow.objType == "STANDARD"
            isTrim = gflow.objType == "TRIM"
     
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

            
        elif obj.type == 'EMPTY':
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
            self.layout.prop(gflow, "exportAnchor")        
            self.layout.prop(gflow, "mergeWithParent")
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
        op.level = geotags.GEO_EDGE_LEVEL_LOD0
        op = row.operator("gflow.set_edge_level", text="Clear")
        op.level = geotags.GEO_EDGE_LEVEL_DEFAULT        
        op = row.operator("gflow.select_edge_level", text="Select")
        op.level = 0
        # Detail Faces
        row = self.layout.row()
        op = row.operator("gflow.set_face_level", text="Dissolve", icon='FACESEL')
        op.detail = True
        op = row.operator("gflow.set_face_level", text="Clear")
        op.detail = False        
        op = row.operator("gflow.select_face_level", text="Select detail")
          
# Context menus
class GFLOW_MT_MESH_CONTEXT(bpy.types.Menu):
    bl_label = "GamiFlow"
    bl_idname = "MESH_MT_gflow_mesh_menu"

    def draw(self, context):
        layout = self.layout
        layout.separator()
        
        # Edge mode
        if context.tool_settings.mesh_select_mode[1]: 
            layout.label(text="Edge Detail", icon="EDGESEL")
            layout.operator("gflow.set_checkered_ring_edge_level", text="Checkered ring dissolve")
            layout.operator("gflow.set_checkered_edge_collapse", text="Checkered loop collapse")
            layout.separator()
            layout.operator("gflow.set_edge_level", text="Mark for Dissolve").level = geotags.GEO_EDGE_LEVEL_LOD0
            layout.operator("gflow.set_edge_collapse_level", text="Mark for Collapse").level = geotags.GEO_EDGE_COLLAPSE_LOD0
            layout.operator("gflow.set_edge_level", text="Mark as Cage").level = geotags.GEO_EDGE_LEVEL_CAGE
            layout.operator("gflow.unmark_edge", text="Clear")
        # Face mode
        if context.tool_settings.mesh_select_mode[2]: 
            layout.label(text="Face Detail", icon="FACESEL")
            layout.operator("gflow.set_face_level", text="Mark for Deletion").detail = True
            layout.operator("gflow.set_face_level", text="Clear").detail = False               
            layout.separator()
            layout.label(text="Face Mirroring", icon="MOD_MIRROR")
            layout.operator("gflow.set_face_mirror", text="Mirror").mirror = "X"   
            layout.operator("gflow.set_face_mirror", text="Unmirror").mirror = "NONE" 
        

def draw_mesh_menu(self, context):
    self.layout.separator(factor=1.0)
    self.layout.menu(GFLOW_MT_MESH_CONTEXT.bl_idname)

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
        
        if context.mode == 'OBJECT':
            pie.operator("gflow.set_smoothing") # W
            pie.operator("gflow.add_bevel")     # E
            pie.operator("gflow.set_udim")      # S
            # N
        elif context.mode == "EDIT_MESH":
            if bpy.context.tool_settings.mesh_select_mode[1]:
                # Edge mode
                pie.operator("gflow.set_edge_level", text="Mark Cage Detail").level = geotags.GEO_EDGE_LEVEL_CAGE # W
                pie.separator() # Empty E
                pie.operator("gflow.set_edge_collapse_level", text="Mark Collapse").level = geotags.GEO_EDGE_COLLAPSE_LOD0
                pie.operator("gflow.add_soft_seam")
                pie.operator("gflow.add_hard_seam")
                pie.operator("gflow.clear_seam")
                pie.operator("gflow.set_edge_level", text="Mark Dissolve").level = geotags.GEO_EDGE_LEVEL_LOD0
                pie.operator("gflow.unmark_edge", text="Unmark")
            if bpy.context.tool_settings.mesh_select_mode[2] and not bpy.context.tool_settings.mesh_select_mode[1]:
                pie.operator("gflow.set_face_mirror", text="Mirror", icon='MOD_MIRROR').mirror = "X"        # W
                pie.operator("gflow.set_face_mirror", text="Unmirror", icon='MOD_MIRROR').mirror = "NONE"   # E
                pie.separator() # Empty S
                pie.separator() # Empty N          
                pie.operator("gflow.uv_gridify", text="Gridify", icon='VIEW_ORTHO')
                pie.operator("gflow.uv_degridify", text="Ungridify", icon='CANCEL')       
                pie.operator("gflow.set_face_level", text="Mark for Deletion").detail = True
                pie.operator("gflow.set_face_level", text="Unmark deletion").detail = False               

                             
                
                
class VIEW3D_OT_PIE_Obj_call(bpy.types.Operator):
    bl_idname = 'gamiflow.objpiecaller'
    bl_label = 'GamiFlow Pie Menu'
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
    GFLOW_MT_MESH_CONTEXT,
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

        
    pass
def unregister():
    global addon_keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    # Context menus
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(draw_mesh_menu)

    
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass