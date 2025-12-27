bl_info = {
    "name": "Modding Toolkit",
    "author": "Dimcirui",
    "version": (2, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > MOD Toolkit",
    "description": "Modular Toolkit for MHWI, MHWs, and RE4... maybe more games in the future",
    "category": "Object",
}

import bpy
from . import ui, games

# 注册顺序：先核心，再游戏逻辑，最后UI
modules = [
    games,
    ui,
]

def register():
    for mod in modules:
        mod.register()

def unregister():
    for mod in reversed(modules):
        mod.unregister()

if __name__ == "__main__":
    register()