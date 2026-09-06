"""ui/personal_tools_panel.py — 作者自用工具的侧栏入口。

为什么单独开一个面板
--------------------
有些操作符是给**特定资产管线**写的（比如把终末地的面部顶点组批量改成荒野的名字），
对绝大多数使用者没有意义，放进主面板只会让界面更难懂。以前的做法是把入口直接删掉、
只留操作符注册着——结果是自己要用的时候得按 F3 敲 idname，而且过一阵就忘了还有这
东西。

现在改成：**默认不画，由插件偏好设置里的一个开关放出来**。释出版本里看不见，自己
要用的时候勾一下。操作符本身一直是注册着的，这个面板只是入口。

一个已知的小麻烦
----------------
``AddonPreferences`` 是按模块名索引的，而这个插件在 4.3 和 5.1 下分别装成
``Modding-Toolkit`` 和 ``Modding-Toolkit-dev``（见 core/port_consent.py 的说明），
所以这个开关**两边要各勾一次**，重装之后也要重勾。对自用工具来说这个代价可以接受；
真要跨安装保持，得学 port_consent 写到 Blender 配置目录里去。
"""

import bpy

from ..core.i18n import T


def _enabled(context):
    """偏好设置里的开关；取不到偏好时（例如模块名对不上）一律当作关闭。"""
    try:
        from ..core.console_export import get_preferences
        return bool(getattr(get_preferences(context), "show_personal_tools", False))
    except Exception:
        return False


class MHW_PT_PersonalTools(bpy.types.Panel):
    bl_label = "Personal Tools"
    bl_idname = "MHW_PT_personal_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 90

    @classmethod
    def poll(cls, context):
        return _enabled(context)

    def draw_header(self, context):
        self.layout.label(text="", icon='TOOL_SETTINGS')

    def draw(self, context):
        layout = self.layout
        layout.label(text=T("ui.personal_tools.blurb"), icon='INFO')

        box = layout.box()
        box.label(text=T("ui.personal_tools.endfield_header"), icon='OUTLINER_OB_ARMATURE')

        # 面部改名：两家的表各自独立（面部骨集合不同，推不出彼此），所以是两个按钮
        # 而不是一个带下拉的。
        col = box.column(align=True)
        col.label(text=T("mhws.operators.endfield_face_rename_label"), icon='GROUP_VERTEX')
        row = col.row(align=True)
        row.operator("mhws.endfield_face_rename", text=T("ui.personal_tools.to_mhws"))
        row.operator("mhwi.endfield_face_rename", text=T("ui.personal_tools.to_mhwi"))

        # 面部权重简化：目前只有荒野一份。它的合并组与 60% 分配比例是**按荒野的
        # 面部骨集合设计的**，不能靠表复合搬到世界上 —— 复合出来 59 个骨名里 10 个
        # 有歧义，而且其中两个还是合并的目标骨。见 assets/facial_maps/README.md。
        col = box.column(align=True)
        col.operator("mhws.face_weight_simplify",
                     text=T("mhws.operators.face_weight_simplify_label"),
                     icon='MOD_SMOOTH')


classes = (MHW_PT_PersonalTools,)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
