"""MHWI -> MHRS batch port, dialog layer.

One dialog for the whole job: scan a MHWI mod folder, pick which vanilla MHRS
armour the set replaces, and press OK.  Everything between -- import, the three
ports, the export -- is settled by ``core/mhwi_batch_port.py`` and never asked
about, because the audience for this is someone who wants their set in the other
game, not someone tuning a port.

**The scan result lives on the scene, not on the operator.**  A dialog opened with
``invoke_props_dialog`` redraws on every interaction but is invoked only once, so a
"Scan" button inside it cannot hand its findings back through operator properties --
those are re-read from the operator instance each draw, while a nested operator call
gets its own instance.  A scene key survives both, and survives the dialog being
cancelled and reopened, which is what makes scanning once and porting twice work.
"""

import json
import os

import bpy

from . import mhwi_batch_port as batch
from .i18n import T

#: Where the scan result is parked between the scan button and the draw that shows
#: it.  JSON rather than a PropertyGroup: it is written whole and read whole, never
#: edited item by item, so a collection property would be three registrations and a
#: pair of clear/extend loops to express the same thing.
SCAN_KEY = "mhwi_batch_port_scan"

#: The MHRS part-name and gender keys, borrowed rather than restated -- see the note
#: in ``core/i18n_strings/core.py``.
#:
#: Written out rather than built with an f-string over ``PART_CODES``: a key the
#: table check cannot read as a literal is a key it cannot verify exists, and it
#: says so (``tests/test_ui_translated.py``).  The same rule ``mrl3_port_ops``'s
#: target table follows.
_PART_LABEL = {
    "body": "mhrs.batch_export.part_body",
    "helm": "mhrs.batch_export.part_helm",
    "arm": "mhrs.batch_export.part_arm",
    "wst": "mhrs.batch_export.part_wst",
    "leg": "mhrs.batch_export.part_leg",
}

_GENDER_LABEL = {
    "f": "mhrs.batch_export.gender_f",
    "m": "mhrs.batch_export.gender_m",
}

_SKIP_LABEL = {
    batch.SKIP_NO_MOD3: "core.mhwi_batch_port_ops.skip_no_mod3",
    batch.SKIP_NO_MRL3: "core.mhwi_batch_port_ops.skip_no_mrl3",
}


def load_scan(scene):
    try:
        return json.loads(scene.get(SCAN_KEY, "") or "[]")
    except ValueError:
        return []


# ── 目标装备的搜索式选择 ──────────────────────────────────────────
#
# 装备包有 239 套，普通下拉在屏幕上放不下，滚动着找也不好找。面板那边用的是
# ``mhrs.pick_armor`` 的 ``invoke_search_popup``，但这里是 ``invoke_props_dialog``
# 开出来的对话框——弹窗里再开弹窗会把父对话框顶掉，用户得从头再来一遍。
# ``prop_search`` 是对话框里能用的那一种：内联输入框 + 自动补全，不用多点一次，
# 也不会把对话框关掉。``core/mesh_port_ops.py`` 的源骨架选择同理。

class MHWI_ArmorSearchItem(bpy.types.PropertyGroup):
    """搜索列表的一行。

    ``prop_search`` 只认 ``name``，所以把 id 和名字拼在一起——用户输 ``279``
    或者输装备名都能命中，而 id 恰恰是这个流程里最常用的检索方式（用户是奔着
    某个替换目标去的）。真正要回填的值另存在 ``armor_id``，不从 ``name`` 上
    反解，省得装备名里带空格时切错。
    """
    armor_id: bpy.props.StringProperty()


#: 当前列表是照哪个装备包填的。装备包可以换，换完列表就是过期的；记下来才能
#: 知道要不要重填，而不是每次重绘都无脑重建一遍 239 项。
_ARMOR_LIST_SIGNATURE = "mhwi_batch_port_armor_sig"


def _fill_armor_search(context, force=False):
    """按当前装备包填充搜索列表；已经是这个包的就原样返回。"""
    from ..games.mhrs.batch_export import get_mhrs_armor_callback

    wm = context.window_manager
    settings = context.scene.mhw_suite_settings
    sig = settings.mhrs_armor_scheme or ""
    if not force and wm.get(_ARMOR_LIST_SIGNATURE) == sig and len(wm.mhwi_armor_search):
        return

    wm.mhwi_armor_search.clear()
    for armor_id, label, *_ in get_mhrs_armor_callback(settings, context):
        if armor_id == 'NONE':
            continue
        # 面板用的那个枚举把 id 放在末尾（"公会十字  (279)"），这里放在开头，
        # 所以要去掉重复的那份——否则每一行都写着两遍 id。
        suffix = f"  ({armor_id})"
        if label.endswith(suffix):
            label = label[:-len(suffix)]
        item = wm.mhwi_armor_search.add()
        item.name = f"{armor_id}  {label}"
        item.armor_id = armor_id
    wm[_ARMOR_LIST_SIGNATURE] = sig


def _resolve_armor(context, query):
    """搜索框里的文字 -> 装备 id，认不出来就是 ``None``。

    只接受列表里真实存在的一行。用户可以在框里留下半截输入（``prop_search``
    不阻止），把半截当成 id 传下去会让导出写到一个不存在的装备号上。
    """
    for item in context.window_manager.mhwi_armor_search:
        if item.name == query:
            return item.armor_id
    return None


#: Persistent backing for the dynamic enum.  Blender's C side keeps the pointers to
#: these strings, so a list built inside the callback is freed the moment Python
#: drops it -- the same trap every other dynamic enum in this addon documents.
_group_item_cache = []


def _group_items(self, context):
    _group_item_cache.clear()
    for entry in load_scan(context.scene):
        key = f"{entry['gender']}/{entry['group']}"
        gender = T(_GENDER_LABEL.get(entry["gender"], "mhrs.batch_export.gender_f"))
        _group_item_cache.append((key, f"{entry['group']}  ({gender})", ""))
    if not _group_item_cache:
        _group_item_cache.append(
            ("NONE", T("core.mhwi_batch_port_ops.not_scanned"), ""))
    return _group_item_cache


def _selected_entry(context, key):
    for entry in load_scan(context.scene):
        if f"{entry['gender']}/{entry['group']}" == key:
            return entry
    return None


class MHWI_OT_BatchPortScan(bpy.types.Operator):
    bl_idname = "mhwi.batch_port_scan"
    bl_label = "Scan"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("core.mhwi_batch_port_ops.desc")

    def execute(self, context):
        root = context.scene.get("mhwi_natives_root", "")
        if not root or not os.path.isdir(root):
            self.report({'ERROR'}, T("core.mhwi_batch_port_ops.source_root_missing"))
            return {'CANCELLED'}
        found = batch.scan(root)
        context.scene[SCAN_KEY] = json.dumps(found)
        if not found:
            self.report({'WARNING'}, T("core.mhwi_batch_port_ops.nothing_found"))
        return {'FINISHED'}


class MHWI_OT_BatchPortMHRS(bpy.types.Operator):
    bl_idname = "mhwi.batch_port_mhrs"
    bl_label = "MHWI Batch Port to MHRS"
    #: No 'UNDO', like the three ports it drives: it creates collections, objects
    #: and files outside the undo stack, so a redo-panel re-run would build a second
    #: set rather than revise the first.
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.mhwi_batch_port_ops.desc")

    source_group: bpy.props.EnumProperty(name="Source", items=_group_items)
    dest_base_path: bpy.props.StringProperty(name="Base Path", default="")
    #: 目标装备的搜索框。字符串而非枚举：``prop_search`` 要的就是字符串，而且
    #: 动态枚举存的是一个会被重建的列表的下标，换装备包后同一个值指向的会是
    #: 另一套装备。
    armor_query: bpy.props.StringProperty(name="Target Armor", default="")

    def invoke(self, context, event):
        # Scanned on open, so the common case -- root already set, one set in the
        # folder -- needs no button press at all.  The button stays for the case it
        # cannot cover: the user setting the root from inside this dialog.
        if context.scene.get("mhwi_natives_root", ""):
            bpy.ops.mhwi.batch_port_scan('EXEC_DEFAULT')
        _fill_armor_search(context, force=True)
        # 上次选的装备回填进搜索框，重开对话框不用重选一遍。
        self.armor_query = ""
        current = context.scene.mhw_suite_settings.mhrs_selected_armor
        for item in context.window_manager.mhwi_armor_search:
            if item.armor_id == current:
                self.armor_query = item.name
                break
        return context.window_manager.invoke_props_dialog(self, width=420)

    def check(self, context):
        # 装备包是场景属性，改它不会触发 check；但用户改完包一定要回到搜索框，
        # 一碰搜索框就会走到这里，列表在他们输入被匹配之前就已经换好了。
        _fill_armor_search(context)
        armor_id = _resolve_armor(context, self.armor_query)
        if armor_id:
            context.scene.mhw_suite_settings.mhrs_selected_armor = armor_id
        return True

    def draw(self, context):
        from .mdf_port_ops import _draw_mod_root_row

        layout = self.layout
        settings = context.scene.mhw_suite_settings

        # ── source ──
        row = layout.row(align=True)
        _draw_mod_root_row(row, context, "MHWI", {"natives_root_key": "mhwi_natives_root"})
        row.operator("mhwi.batch_port_scan", text=T("core.mhwi_batch_port_ops.scan"),
                     icon='VIEWZOOM')

        entry = _selected_entry(context, self.source_group)
        layout.prop(self, "source_group", text=T("core.mhwi_batch_port_ops.source_group"))

        # ── what the scan found, part by part ──
        box = layout.box()
        if entry is None:
            box.label(text=T("core.mhwi_batch_port_ops.not_scanned"), icon='INFO')
        else:
            has_body_ctc = "ctc" in entry["parts"].get("body", {})
            for part in batch.PART_ORDER:
                files = entry["parts"].get(part)
                if files is None:
                    continue
                skip = batch.skip_reason("mod3" in files, "mrl3" in files)
                row = box.row(align=True)
                row.label(text=T(_PART_LABEL[part]),
                          icon='CHECKMARK' if not skip else 'X')
                if skip:
                    row.label(text=T(_SKIP_LABEL[skip]))
                elif "ctc" in files:
                    row.label(text=T("core.mhwi_batch_port_ops.full"))
                elif has_body_ctc and part != "body":
                    row.label(text=T("core.mhwi_batch_port_ops.no_physics"))
                else:
                    row.label(text=T("core.mhwi_batch_port_ops.no_physics_alone"))

        # ── destination ──
        layout.separator()
        _draw_mod_root_row(layout, context, "MHRS", {"natives_root_key": "mhrs_natives_root"})
        layout.label(text=T("core.mhwi_batch_port_ops.target_hint"), icon='INFO')
        row = layout.row(align=True)
        row.prop(settings, "mhrs_gender", text="")
        row.prop(settings, "mhrs_armor_scheme", text="")
        layout.prop_search(self, "armor_query", context.window_manager,
                           "mhwi_armor_search",
                           text=T("core.mhwi_batch_port_ops.target_armor"),
                           icon='VIEWZOOM')
        if _resolve_armor(context, self.armor_query) is None:
            layout.label(text=T("core.export_prep.select_armor_first"), icon='ERROR')
        layout.prop(self, "dest_base_path",
                    text=T("core.mrl3_port_ops.dest_base_path"))
        layout.label(text=T("core.mrl3_port_ops.base_path_example"))

    def execute(self, context):
        entry = _selected_entry(context, self.source_group)
        if entry is None:
            self.report({'ERROR'}, T("core.mhwi_batch_port_ops.not_scanned"))
            return {'CANCELLED'}

        settings = context.scene.mhw_suite_settings
        # 以搜索框为准，而不是读 mhrs_selected_armor：那是个共享的场景属性，
        # 面板那边也在写，而对话框里用户看到的、以为自己选中的是这个框。
        armor_id = _resolve_armor(context, self.armor_query)
        if not armor_id:
            self.report({'ERROR'}, T("core.export_prep.select_armor_first"))
            return {'CANCELLED'}
        settings.mhrs_selected_armor = armor_id
        dst_root = context.scene.get("mhrs_natives_root", "")
        if not dst_root or not os.path.isdir(dst_root):
            self.report({'ERROR'}, T("core.export_prep.set_mod_root_first"))
            return {'CANCELLED'}

        if not any(batch.skip_reason("mod3" in f, "mrl3" in f) is None
                   for f in entry["parts"].values()):
            self.report({'ERROR'}, T("core.mhwi_batch_port_ops.no_portable_part"))
            return {'CANCELLED'}

        group_col = batch.import_group(context, entry)
        if group_col is None:
            self.report({'ERROR'}, T("core.mhwi_batch_port_ops.import_failed"))
            return {'CANCELLED'}

        parts = batch.discover(group_col)
        results = batch.run(
            context, parts, target_game="MHRS",
            dest_base_path=self.dest_base_path.strip() or default_base_path(entry),
            src_root=context.scene.get("mhwi_natives_root", ""),
            dst_root=dst_root)

        exported = batch.export(context, results, armor_id=armor_id,
                                gender=settings.mhrs_gender, natives_root=dst_root)
        if exported["error"]:
            self.report({'ERROR'}, T(exported["error"]))
            return {'CANCELLED'}

        ported = sum(1 for r in results if not r["skip"] and r["mesh"] is not None)
        skipped = sum(1 for r in results if r["skip"])
        self.report({'INFO'}, T("core.mhwi_batch_port_ops.stat").format(
            ported=ported, skipped=skipped,
            armor=f"{settings.mhrs_gender}/pl{armor_id}"))
        return {'FINISHED'}


def default_base_path(entry):
    """``Toolkit/<set folder>`` when the user leaves the field empty.

    Named after the set rather than after the target armour: it is where the *mod's*
    textures live, and two ports of the same set to different armour slots should
    not each get their own copy of identical files.
    """
    return f"Toolkit/{entry['group']}"


classes = [MHWI_ArmorSearchItem, MHWI_OT_BatchPortScan, MHWI_OT_BatchPortMHRS]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # WindowManager 而不是 Scene：这是从装备包现算出来的缓存，存进 .blend 只会
    # 让下次打开时带着一份可能已经过期的副本。
    bpy.types.WindowManager.mhwi_armor_search = bpy.props.CollectionProperty(
        type=MHWI_ArmorSearchItem)


def unregister():
    del bpy.types.WindowManager.mhwi_armor_search
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
