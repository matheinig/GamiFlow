import bpy
import bmesh
import contextlib



def setSelected(context, obj):
    obj.select_set(True)
    context.view_layer.objects.active = obj
def setDeselected(obj):
    obj.select_set(False)

@contextlib.contextmanager
def objectModeBmesh(obj):
    bm = bmesh.new()
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

classes = []


def register():
    for c in classes: 
        bpy.utils.register_class(c)
    pass
def unregister():
    for c in reversed(classes): 
        bpy.utils.unregister_class(c)
    pass