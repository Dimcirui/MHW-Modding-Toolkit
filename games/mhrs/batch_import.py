"""MHRS batch import: read an armour set back out of a mod folder.

The mirror of ``batch_export``, and deliberately shaped like ``games/mhws``'s
version of the same thing -- same engine, same RE Mesh Editor underneath, and a
second shape for the same job would only be a second thing to keep in step.

Two things differ from MHWS, both because MHRS is the simpler game:

* **Gender, not variants.**  MHWS crosses four body variants (``mm``/``mf``/
  ``fm``/``ff``) with a per-variant model prefix and base path, and that
  dimension leaks into the item, the group key and the labels.  MHRS has ``f``
  and ``m`` and one fixed path shape, so the whole thing is the gender already
  on the export panel.
* **Three importable types.**  ``user.2`` has no importer and is never authored
  by hand -- the export panel shows it as AUTO and copies a template -- so it
  cannot round-trip and is not offered.

Like MHWS this walks the armour pack rather than the disk: the pack is the list
of armour ids worth looking for, and every path is derived from an id the same
way the exporter derives it.  An id the pack does not list is therefore not
found, which is the accepted trade for the two sides agreeing by construction.
"""

import bpy
import os
import re
from collections import defaultdict

from ...core.i18n import T
from ...core.re_mesh_compat import call_re_mesh_op, re_mesh_op_available
from .batch_export import (
    MHRS_PARTS,
    _load_scheme, _resolve_part_file_types, _canonical_order_file_types,
    _make_filepath, set_binding, get_mhrs_genders,
)

#: ``user`` is absent on purpose -- see the module docstring.
IMPORT_FILE_TYPES = ["mesh", "mdf2", "chain"]
FT_ORDER = ["mesh", "mdf2", "chain"]


# ── CollectionProperty 数据结构 ────────────────────────────────────

class MHRS_ImportItem(bpy.types.PropertyGroup):
    """代表一个待导入文件"""
    filepath: bpy.props.StringProperty()
    armor_id: bpy.props.StringProperty()   # 装备包中的套装 id，如 "279"
    gender:   bpy.props.StringProperty()   # "f"/"m"
    part:     bpy.props.StringProperty()   # "body"/"helm"/"arm"/"wst"/"leg"
    filetype: bpy.props.StringProperty()   # "mesh"/"mdf2"/"chain"
    enabled:  bpy.props.BoolProperty(default=True)


class MHRS_ImportGroup(bpy.types.PropertyGroup):
    """代表一套装备的 UI 折叠状态"""
    group_key: bpy.props.StringProperty()   # armor_id
    expanded:  bpy.props.BoolProperty(default=False)


# ── 扫描 ──────────────────────────────────────────────────────────

def scan_mhrs_catalog(natives_root, scheme_filename, scene):
    """
    按装备包里的 id 逐一推算路径并检查磁盘上是否存在，而非遍历文件夹。
    结果写入 scene.mhrs_import_items 和 scene.mhrs_import_groups。
    返回找到的文件总数。

    路径一律走 batch_export 的 _make_filepath，导入和导出因此不可能各算各的。
    """
    items  = scene.mhrs_import_items
    groups = scene.mhrs_import_groups
    items.clear()
    groups.clear()

    scheme = _load_scheme(scheme_filename)
    if not scheme:
        return 0

    genders = [code for code, _label, *_ in get_mhrs_genders()]
    seen_groups = set()

    for armor_set in scheme.get("armor_sets", []):
        armor_id   = armor_set["id"]
        parts_mask = armor_set.get("parts_mask", 0b11111)

        for gender in genders:
            for idx, (part_id, _part_name) in enumerate(MHRS_PARTS):
                if not (parts_mask & (1 << idx)):
                    continue

                part_fts = [ft for ft in _resolve_part_file_types(armor_set, part_id)
                            if ft in IMPORT_FILE_TYPES]

                for filetype in _canonical_order_file_types(part_fts):
                    filepath = _make_filepath(natives_root, gender, armor_id, part_id, filetype)
                    if not os.path.isfile(filepath):
                        continue

                    if armor_id not in seen_groups:
                        g = groups.add()
                        g.group_key = armor_id
                        seen_groups.add(armor_id)

                    item          = items.add()
                    item.filepath = filepath
                    item.armor_id = armor_id
                    item.gender   = gender
                    item.part     = part_id
                    item.filetype = filetype
                    item.enabled  = True

    if len(groups) == 1:
        groups[0].expanded = True

    return len(items)


# ── 辅助：Chain 导入 operator 可用性 ────────────────────────────────
# MHRS 用的是 v1 的 .chain，命名空间 re_chain。注意这个名字可能由 RE Chain
# Editor 应答，也可能由 MHWilds 那个分支应答（两者以同名注册），所以这里只
# 探测“有没有”，不假设背后是哪一个实现 —— 和 ui/game_sections.py 的 GUARDS
# 一样，用 dir() 而不是 hasattr()：bpy.ops 的属性访问是惰性的，hasattr 永远为真。

def _chain_import_available():
    return hasattr(bpy.ops, 're_chain') and 'importfile' in dir(bpy.ops.re_chain)


#: Blender 给重名数据块追加的 ".001" 式后缀。
_DUP_SUFFIX = re.compile(r"\.\d{3}$")


def _strip_dup_suffix(name):
    return _DUP_SUFFIX.sub("", name)


def _collection_name(gender, part_id, armor_id, filetype):
    """RE Mesh/Chain Editor 导入后建出来的集合名。

    就是文件名去掉扩展名再接类型后缀，例如 ``f_body279.mesh``。这是这两个
    插件没写进文档的命名约定，所以调用方拿它去绑定之前一律先查存在性。
    """
    return f"{gender}_{part_id}{armor_id}.{filetype}"


# ── Operators ─────────────────────────────────────────────────────

class MHRS_OT_ScanImportFiles(bpy.types.Operator):
    bl_idname  = "mhrs.scan_import_files"
    bl_label   = "Scan"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_import.scan_desc")

    def execute(self, context):
        scene        = context.scene
        settings     = scene.mhw_suite_settings
        natives_root = scene.get("mhrs_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("core.export_prep.set_mod_root_first"))
            return {'CANCELLED'}

        count = scan_mhrs_catalog(natives_root, settings.mhrs_armor_scheme, scene)
        if count == 0:
            self.report({'WARNING'}, T("mhrs.batch_import.no_files_found"))
        else:
            self.report({'INFO'}, T("mhrs.batch_import.scan_done").format(n=count))
        return {'FINISHED'}


class MHRS_OT_ToggleImportGroup(bpy.types.Operator):
    bl_idname  = "mhrs.toggle_import_group"
    bl_label   = "Toggle Import Group"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_import.toggle_group_desc")

    group_key: bpy.props.StringProperty()

    def execute(self, context):
        for g in context.scene.mhrs_import_groups:
            if g.group_key == self.group_key:
                g.expanded = not g.expanded
                break
        return {'FINISHED'}


class MHRS_OT_SelectImportGroup(bpy.types.Operator):
    bl_idname  = "mhrs.select_import_group"
    bl_label   = "Select Import Group"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_import.select_group_desc")

    group_key: bpy.props.StringProperty()
    value:     bpy.props.BoolProperty()

    def execute(self, context):
        for item in context.scene.mhrs_import_items:
            if item.armor_id == self.group_key:
                item.enabled = self.value
        return {'FINISHED'}


class MHRS_OT_SelectAllImport(bpy.types.Operator):
    bl_idname  = "mhrs.select_all_import"
    bl_label   = "Select All Import"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_import.select_all_desc")

    value: bpy.props.BoolProperty()

    def execute(self, context):
        for item in context.scene.mhrs_import_items:
            item.enabled = self.value
        return {'FINISHED'}


class MHRS_OT_BatchImport(bpy.types.Operator):
    bl_idname  = "mhrs.batch_import"
    bl_label   = "MHRS Batch Import"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_import.batch_import_desc")

    def _import_mesh(self, mesh_item, mdf2_item, expected_armature):
        """导入 mesh（可选携带 mdf2 材质），返回新建骨架的数据块名，找不到则 None。

        名字优先按约定猜，猜不中就退到“这次导入新增的那一个骨架”—— RE Mesh
        Editor 的命名不是契约，但“导入前后的差集”一定是对的。
        """
        directory = os.path.dirname(mesh_item.filepath) + os.sep
        filename  = os.path.basename(mesh_item.filepath)
        kwargs = dict(
            directory=directory,
            files=[{"name": filename}],
            loadMaterials=bool(mdf2_item),
            loadMDFData=bool(mdf2_item),
            loadShellFur=True,
        )
        if mdf2_item:
            kwargs["mdfPath"] = mdf2_item.filepath

        before = set(bpy.data.armatures.keys())
        call_re_mesh_op('importfile', 'EXEC_DEFAULT', **kwargs)
        after = set(bpy.data.armatures.keys()) - before

        if expected_armature in after:
            return expected_armature
        if len(after) == 1:
            return next(iter(after))
        return expected_armature if expected_armature in bpy.data.armatures else None

    def _import_mdf_only(self, mdf2_item):
        """mesh 缺失但 mdf2 单独存在时的兜底：走 RE Mesh Editor 独立的 MDF 导入"""
        directory = os.path.dirname(mdf2_item.filepath) + os.sep
        filename  = os.path.basename(mdf2_item.filepath)
        bpy.ops.re_mdf.importfile('EXEC_DEFAULT', directory=directory,
                                  files=[{"name": filename}])

    def _import_chain(self, item, armature_name):
        bpy.ops.re_chain.importfile('EXEC_DEFAULT', filepath=item.filepath,
                                    targetArmature=armature_name)

    def _bind(self, scene, armor_id, gender, part_id, filetype, created):
        """导入成功后自动登记为导出绑定，省去手动 Pick Collection。

        认的是 *created* —— 这次导入新增出来的集合，而不是“叫这个名字的集合”。
        差别在重复导入时才显出来：场景里已经有 ``f_body279.mesh`` 时，RE Mesh
        Editor 会把新的建成 ``f_body279.mesh.001``，按名字查会绑上那个旧的，
        于是导出的是上一次的模型，而且看起来一切正常。

        名字仍然优先用来在多个新集合中挑对的那个，只是不再单独作数。
        """
        expected = _collection_name(gender, part_id, armor_id, filetype)
        # 重名时 Blender 会追加 ".001"，所以比较前先去掉它 —— 正是重复导入这个
        # 场景下新集合一定带后缀，直接比字符串会一个都认不出来。
        candidates = [c for c in created if _strip_dup_suffix(c) == expected]
        if len(candidates) != 1:
            # 退路：按类型后缀认。一次导入里每种类型只新增一个集合，所以“唯一
            # 那个”可靠；chain 会连带建出 "Chain Collisions - ..."，它的基名对不上
            # expected，因此在上一步就已经被排除，走到这里也不会把它数进来。
            candidates = [c for c in created
                          if _strip_dup_suffix(c).rsplit(".", 1)[-1] == filetype]
        if len(candidates) != 1:
            return False
        name = candidates[0]
        set_binding(scene, armor_id, gender, part_id, filetype, name)
        return True

    def execute(self, context):
        if not re_mesh_op_available('importfile'):
            self.report({'ERROR'}, T("mhrs.batch_import.mesh_editor_missing"))
            return {'CANCELLED'}

        items   = context.scene.mhrs_import_items
        enabled = [it for it in items if it.enabled]
        if not enabled:
            self.report({'WARNING'}, T("mhrs.batch_import.no_items_selected"))
            return {'CANCELLED'}

        has_chain = _chain_import_available()
        scene     = context.scene
        settings  = scene.mhw_suite_settings

        # 按 (armor_id, gender, part) 分组，确保同一部位的 mesh 先于 chain 导入
        # （chain 要绑到 mesh 导入时建出来的骨架上）
        unit_map = defaultdict(dict)
        for it in enabled:
            unit_map[(it.armor_id, it.gender, it.part)][it.filetype] = it

        ok = fail = skip = 0
        succeeded = {}   # (armor_id, gender) -> None，用 dict 保留插入顺序

        for (armor_id, gender, part_id), ft_map in unit_map.items():
            mesh_item = ft_map.get("mesh")
            mdf2_item = ft_map.get("mdf2")
            armature_name = None

            if mesh_item:
                try:
                    before = set(bpy.data.collections.keys())
                    armature_name = self._import_mesh(
                        mesh_item, mdf2_item, f"{gender}_{part_id}{armor_id} Armature")
                    created = set(bpy.data.collections.keys()) - before
                    ok += 1
                    succeeded[(armor_id, gender)] = None
                    self._bind(scene, armor_id, gender, part_id, "mesh", created)
                    if mdf2_item:
                        ok += 1
                        self._bind(scene, armor_id, gender, part_id, "mdf2", created)
                    print(f"[MHRS] Imported: {os.path.basename(mesh_item.filepath)}")
                except Exception as e:
                    print(f"[MHRS] Mesh import FAILED {mesh_item.filepath}: {e}")
                    fail += 1 + (1 if mdf2_item else 0)
            elif mdf2_item:
                try:
                    self._import_mdf_only(mdf2_item)
                    ok += 1
                    succeeded[(armor_id, gender)] = None
                    print(f"[MHRS] Imported (MDF2 only): {os.path.basename(mdf2_item.filepath)}")
                except Exception as e:
                    print(f"[MHRS] MDF2 import FAILED {mdf2_item.filepath}: {e}")
                    fail += 1

            chain_item = ft_map.get("chain")
            if chain_item:
                if not armature_name:
                    print(f"[MHRS] SKIP {chain_item.filepath}: no armature imported for this part")
                    skip += 1
                elif not has_chain:
                    print(f"[MHRS] SKIP {chain_item.filepath}: RE Chain Editor's importer not found")
                    skip += 1
                else:
                    try:
                        before = set(bpy.data.collections.keys())
                        self._import_chain(chain_item, armature_name)
                        created = set(bpy.data.collections.keys()) - before
                        self._bind(scene, armor_id, gender, part_id, "chain", created)
                        ok += 1
                        succeeded[(armor_id, gender)] = None
                        print(f"[MHRS] Imported: {os.path.basename(chain_item.filepath)} -> {armature_name}")
                    except Exception as e:
                        print(f"[MHRS] chain import FAILED {chain_item.filepath}: {e}")
                        fail += 1

        # 最后一套成功导入的装备/性别，设为批量导出面板的当前选中项
        if succeeded:
            last_armor_id, last_gender = list(succeeded)[-1]
            settings.mhrs_selected_armor = last_armor_id
            settings.mhrs_gender         = last_gender

        if fail:
            self.report({'WARNING'}, T("mhrs.batch_import.done_with_fail").format(
                ok=ok, fail=fail, skip=skip))
        else:
            self.report({'INFO'}, T("mhrs.batch_import.done").format(ok=ok, skip=skip))
        return {'FINISHED'}


classes = [
    MHRS_ImportItem,
    MHRS_ImportGroup,
    MHRS_OT_ScanImportFiles,
    MHRS_OT_ToggleImportGroup,
    MHRS_OT_SelectImportGroup,
    MHRS_OT_SelectAllImport,
    MHRS_OT_BatchImport,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhrs_import_items  = bpy.props.CollectionProperty(type=MHRS_ImportItem)
    bpy.types.Scene.mhrs_import_groups = bpy.props.CollectionProperty(type=MHRS_ImportGroup)


def unregister():
    del bpy.types.Scene.mhrs_import_items
    del bpy.types.Scene.mhrs_import_groups
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
