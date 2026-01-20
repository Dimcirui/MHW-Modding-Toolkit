bl_info = {
    "name": "Modding Toolkit",
    "author": "Dimcirui",
    "version": (2, 1, 3),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > MOD Toolkit",
    "description": "Modular Toolkit for MHWI, MHRS, MHWs, and RE4...",
    "category": "Object",
}

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty, EnumProperty
from bpy.types import AddonPreferences

from . import addon_updater_ops 

from .core import standard_ops 
from .core import editor_props
from .core import editor_ops
from . import ui, games

class MT_Preferences(AddonPreferences):
    bl_idname = __name__
    
    auto_check_update: BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )
    updater_interval_months: IntProperty(
        name='Months', description="Number of months between checking for updates",
        default=0, min=0
    )
    updater_interval_days: IntProperty(
        name='Days', description="Number of days between checking for updates",
        default=7, min=0,
    )
    updater_interval_hours: IntProperty(
        name='Hours', description="Number of hours between checking for updates",
        default=0, min=0, max=23
    )
    updater_interval_minutes: IntProperty(
        name='Minutes', description="Number of minutes between checking for updates",
        default=0, min=0, max=59
    )
    
    def draw(self, context):
        layout = self.layout
        addon_updater_ops.update_settings_ui(self, context)


modules = [
    editor_props,
    editor_ops,
    standard_ops, 
    games,
    ui,
]

def register():
    addon_updater_ops.register(bl_info)
    
    bpy.utils.register_class(MT_Preferences)

    for mod in modules:
        mod.register()

def unregister():
    addon_updater_ops.unregister()
    bpy.utils.unregister_class(MT_Preferences)
    
    for mod in reversed(modules):
        mod.unregister()

if __name__ == "__main__":
    register()