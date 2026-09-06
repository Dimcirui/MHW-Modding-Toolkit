bl_info = {
    "name": "Modding Toolkit",
    "author": "Dimcirui",
    "version": (2, 7, 5),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > MOD Toolkit",
    "description": "Modding Toolkit for Capcom's games",
    "category": "Object",
}

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty, EnumProperty
from bpy.types import AddonPreferences

from . import addon_updater_ops 

from .core import migrate
from .core import i18n
from .core import standard_ops
from .core import pose_ops
from .core import bone_ops
from .core import mesh_ops
from .core import editor_props
from .core import editor_ops
from .core import mdf_tex_processor_base
from .core import tex_convert_base
from .core import shader_ops
from .core import chain_convert_ops
from .core import mesh_port_ops
from .core import port_consent
from .core import mhwi_port_ops
from .core import mdf_port_ops
from .core import mrl3_port_ops
from .core import ctc_port_ops
from .core import mhwi_batch_port_ops
from .core import pre_export_check_ops
from .core import ref_model_ops
from .core import stale_cleanup_ops
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

    show_console_on_batch_export: BoolProperty(
        name="Show Console During Batch Export",
        description=(
            "Opens the system console before a batch export and leaves it open "
            "afterward, so progress and per-file errors can be watched live.\n"
            "Windows only. If RE Mesh Editor's or MHW Model Editor's own 'Show "
            "Console' option is also enabled, it is temporarily disabled during "
            "the batch so it doesn't re-toggle (and hide) the console mid-export.\n"
            "Like those addons, this uses Blender's console_toggle(), which can't "
            "detect whether the console is already open -- if it's already open "
            "when the batch starts, this will close it instead"
        ),
        default=False,
    )

    # 作者自用工具的侧栏入口。默认关：这些操作符是给特定资产管线写的，对绝大多数
    # 使用者没有意义。以前的做法是把入口删掉、只留操作符注册着，结果是自己要用的
    # 时候得按 F3 敲 idname —— 这个开关就是那件事的替代品。见
    # ui/personal_tools_panel.py。
    show_personal_tools: BoolProperty(
        name="Show Personal Tools Panel",
        description=(
            "Adds a 'Personal Tools' panel to the MOD Toolkit sidebar, holding "
            "operators written for one specific asset pipeline (Endfield facial "
            "vertex-group renaming, and anything else added later).\n"
            "Off by default because these are of no use to most people. Addon "
            "preferences are keyed by module name, so this has to be ticked "
            "separately in each Blender install"
        ),
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "show_console_on_batch_export")
        layout.prop(self, "show_personal_tools")
        addon_updater_ops.update_settings_ui(self, context)
        # Under the updater UI, because it is the updater's merge-never-delete
        # behaviour that creates the leftovers -- see core/stale_cleanup.py.
        stale_cleanup_ops.draw_preferences_row(layout)


modules = [
    i18n,
    editor_props,
    editor_ops,
    standard_ops,
    pose_ops,
    # Registered here rather than by ui.main_panel, which is where these
    # operators used to live. They own no PropertyGroup and no scene property,
    # so their position relative to ui/ does not matter.
    bone_ops,
    mesh_ops,
    mdf_tex_processor_base,
    tex_convert_base,
    shader_ops,
    # Before every cross-game port operator: they read its consent state in
    # their poll, and its own operator has to exist for the locked panel to
    # have a button to draw.
    port_consent,
    chain_convert_ops,
    mesh_port_ops,
    # After mesh_port_ops: it reuses that module's plan execution helpers and its
    # collection picker rather than restating either.
    mhwi_port_ops,
    mdf_port_ops,
    # After mdf_port_ops: both reuse its prefab loader and shared "Mod Root" row.
    mrl3_port_ops,
    # The third MHWI -> MHWilds rebuild, after the other two for readability only;
    # it shares no state with them, and drives RE Chain Editor through
    # core/re_chain_utils.py rather than reimplementing the builders.
    ctc_port_ops,
    # Last of the MHWI ports: it drives all three above plus the MHWI importer
    # and the MHRS exporter, so it registers after every operator it calls.
    mhwi_batch_port_ops,
    # After mdf_port_ops: it imports that module's collection picker and shared
    # "Mod Root" row rather than restating either.
    pre_export_check_ops,
    ref_model_ops,
    stale_cleanup_ops,
    games,
    ui,
]

def register():
    addon_updater_ops.register(bl_info)
    migrate.run()

    bpy.utils.register_class(MT_Preferences)

    for mod in modules:
        mod.register()

    _start_chain_patch_timer()

#: Remaining deferred attempts at patching RE Chain's import (see below).
_chain_patch_retries = 20


def _patch_chain_import():
    """给 RE-Chain-Editor 的 chain/chain2 导入打上快速补丁。

    上游把 alignChains() 放在链组循环内部，而它扫全场景 + 每节点做一次全量依赖图求值，
    导入代价是 O(G²·m)。实测导入 196 组需约 78 分钟（因此容易被误当成卡死而中断，
    留下静态看不出异常的残缺数据）；补丁后约 32 秒。细节见 core/re_chain_utils.py。

    补丁靠扫 sys.modules 找目标，所以**依赖 RE-Chain-Editor 已经加载**。Blender 启用
    插件的顺序不保证，冷启动时很可能轮到我们时它还没加载 —— 那一次扫描会一无所获。
    因此这里用定时器重试，直到装上或次数用尽；否则补丁只在"先有 RE Chain、再重新启用
    本插件"时才生效，而那恰好不是用户的正常启动路径。

    RE-Chain-Editor 未安装时会把重试用完然后明确说一声（早先的版本在这条路径上完全
    不打日志，等于静默失败）。任何异常都不能影响本插件注册。
    """
    global _chain_patch_retries
    try:
        from .core.re_chain_utils import install_fast_chain_import
        n = install_fast_chain_import()
    except Exception as e:
        print(f"[Modding-Toolkit] fast chain import patch skipped: {e}")
        return None

    if n:
        print(f"[Modding-Toolkit] fast chain import patch applied to {n} binding(s)")
        return None

    _chain_patch_retries -= 1
    if _chain_patch_retries > 0:
        return 0.5      # timer: RE Chain Editor may still be loading
    print("[Modding-Toolkit] RE Chain Editor not found; its chain import stays "
          "unpatched (imports of large chain files will be very slow)")
    return None


def _start_chain_patch_timer():
    global _chain_patch_retries
    # 与上面的导入补丁无关，也不需要等 RE Chain Editor 加载完：订阅的是 Blender 自己
    # 的活动物体属性，回调里才去看 re_chain_toolpanel 在不在。
    try:
        from .core.re_chain_utils import install_chain_type_sync
        install_chain_type_sync()
    except Exception as e:
        print(f"[Modding-Toolkit] chain file type sync skipped: {e}")
    _chain_patch_retries = 20
    if _patch_chain_import() is not None and not bpy.app.timers.is_registered(
            _patch_chain_import):
        bpy.app.timers.register(_patch_chain_import, first_interval=0.5,
                                persistent=True)

def unregister():
    addon_updater_ops.unregister()
    bpy.utils.unregister_class(MT_Preferences)

    if bpy.app.timers.is_registered(_patch_chain_import):
        bpy.app.timers.unregister(_patch_chain_import)
    try:
        from .core.re_chain_utils import (uninstall_fast_chain_import,
                                          uninstall_chain_type_sync)
        uninstall_fast_chain_import()
        uninstall_chain_type_sync()
    except Exception:
        pass

    for mod in reversed(modules):
        mod.unregister()

if __name__ == "__main__":
    register()
