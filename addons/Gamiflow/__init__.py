bl_info = {
    "name"        : "Gamiflow",
    "description" : "Workflow improvements for game assets",
    "author"      : "Mathieu Einig",
    "version"     : (1, 7),
    "blender"     : (3, 6, 0),
    "location"    : "Wherever",
    "warning"     : "",
    "wiki_url"    : "https://github.com/matheinig/GamiFlow",
    "tracker_url" : "https://github.com/matheinig/GamiFlow/issues",
    "category"    : "Object"
}



# Trick to properly reload other files
if "bpy" in locals():
    import importlib
    importlib.reload(enums)
    importlib.reload(data)
    importlib.reload(settings)
    importlib.reload(ui)
    importlib.reload(display)
    importlib.reload(helpers)
    importlib.reload(geotags)
    importlib.reload(uv)
    importlib.reload(sets)
    importlib.reload(sets_low)
    importlib.reload(sets_high)
    importlib.reload(sets_cage)
    importlib.reload(sets_export)
    importlib.reload(export)
    importlib.reload(baker)

import bpy
from . import enums
from . import data
from . import settings
from . import ui
from . import display
from . import helpers
from . import geotags
from . import uv
from . import sets
from . import sets_low
from . import sets_high
from . import sets_cage
from . import sets_export
from . import export
from . import baker

    
modules = [
    data, settings, ui, display, helpers,
    geotags,
    uv, 
    sets, sets_low, sets_high, sets_cage, sets_export,
    export, baker]
    
def register():
    print("-------Registering gflow-------")
    for m in modules:
        m.register()
    pass
    
def unregister():
    print("-------Unregistering gflow-------")
    for m in reversed(modules):
        m.unregister()
    pass