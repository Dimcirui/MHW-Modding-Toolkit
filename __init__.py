bl_info = {
    "name": "Modding Toolkit",
    "author": "Dimcirui",
    "version": (2, 1, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > MOD Toolkit",
    "description": "Modular Toolkit for MHWI, MHRS, MHWs, and RE4...",
    "category": "Object",
}

import bpy
from .core import standard_ops 
from .core import editor_props
from .core import editor_ops
from .core import addon_updater_ops 
from . import ui, games

modules = [
    editor_props,
    editor_ops,
    standard_ops, 
    games,
    ui,
]

def register():
    for mod in modules:
        mod.register()
    
    addon_updater_ops.register(bl_info)

def unregister():
    addon_updater_ops.unregister()
    
    for mod in reversed(modules):
        mod.unregister()

if __name__ == "__main__":
    register()