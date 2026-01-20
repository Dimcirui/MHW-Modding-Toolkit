import bpy
from . import updater_ops  # 确保导入了刚才保存的 updater_ops.py

class MT_Preferences(bpy.types.AddonPreferences):
    # 动态获取包名，确保与 __init__.py 所在的文件夹名称一致
    bl_idname = __package__.split(".")[0]

    # ==========================================================
    # Updater 配置属性 (必须存在，updater_ops 会调用它们)
    # ==========================================================
    
    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using the interval below",
        default=False,
    )

    updater_interval_months: bpy.props.IntProperty(
        name='Months',
        description="Number of months between the auto-update checks",
        default=0,
        min=0
    )

    updater_interval_days: bpy.props.IntProperty(
        name='Days',
        description="Number of days between the auto-update checks",
        default=7,
        min=0,
    )

    updater_interval_hours: bpy.props.IntProperty(
        name='Hours',
        description="Number of hours between the auto-update checks",
        default=0,
        min=0,
        max=23
    )

    updater_interval_minutes: bpy.props.IntProperty(
        name='Minutes',
        description="Number of minutes between the auto-update checks",
        default=0,
        min=0,
        max=59
    )

    # ==========================================================
    # 你自己的其他插件设置可以写在这里
    # ==========================================================
    # example_prop: bpy.props.BoolProperty(name="Example Setting", default=True)

    def draw(self, context):
        layout = self.layout

        # 1. 可以在这里绘制你原本的插件设置
        # layout.prop(self, "example_prop")
        # layout.separator()

        # 2. 绘制 Updater 的界面
        # 这个函数会自动画出：“检查更新按钮”、“自动检查开关”、“版本信息”等
        updater_ops.update_settings_ui(self, context)

def register():
    bpy.utils.register_class(MT_Preferences)

def unregister():
    bpy.utils.unregister_class(MT_Preferences)