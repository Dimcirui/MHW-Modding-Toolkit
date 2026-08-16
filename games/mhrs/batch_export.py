import bpy
import contextlib
import json
import os
import shutil

from ...core.i18n import T
from ...core.re_mesh_compat import call_re_mesh_op, re_mesh_op_available
from ...core.bone_utils import align_armatures_by_name
from ...core import console_export
from ...core import export_prep
from ...core import lua_bone_system

# MHRS 游戏级文件后缀常量
MHRS_EXTS = {
    "mesh":  "mesh.2109148288",
    "mdf2":  "mdf2.23",
    "chain": "chain.48",
    "user":  "user.2",
}

# 5个固定部位（part id 直接用于文件名，如 f_body279）
MHRS_PARTS = [
    ("arm",  "护腕"),
    ("body", "躯干"),
    ("wst",  "腰带"),
    ("helm", "头盔"),
    ("leg",  "腿部"),
]

# part_id -> i18n key，供 batch_export_ui.py 在界面上显示双语部位名
# （MHRS_PARTS 里的中文名本身仅用于内部日志/print，不直接过 T()）
MHRS_PART_LABEL_KEYS = {
    "arm":  "mhrs.batch_export.part_arm",
    "body": "mhrs.batch_export.part_body",
    "wst":  "mhrs.batch_export.part_wst",
    "helm": "mhrs.batch_export.part_helm",
    "leg":  "mhrs.batch_export.part_leg",
}

# Hunter gender (2 options)
def get_mhrs_genders(self=None, context=None):
    return [
        ("f", T("mhrs.batch_export.gender_f"), ""),
        ("m", T("mhrs.batch_export.gender_m"), ""),
    ]

# 头盔部位代码（user.2 仅头盔存在，其余部位无此文件）
HELM_PART = "helm"

# 默认每套装备包含的文件类型
# user: 不可绑定集合，始终在"未选项使用空模型"开启时从内置模板复制并按目标路径改名（含id）
DEFAULT_FILE_TYPES = ["mesh", "mdf2", "chain", "user"]

# 使用空模型替换时不生成空文件的类型（chain 无空模意义，直接跳过）
NO_BLANK_FILE_TYPES = {"chain"}

# 规范导出顺序
_CANONICAL_FILE_TYPE_ORDER = ["mesh", "mdf2", "chain", "user"]
_CANONICAL_FILE_TYPE_INDEX = {ft: i for i, ft in enumerate(_CANONICAL_FILE_TYPE_ORDER)}


def _canonical_order_file_types(fts):
    """将 file_types 列表按规范顺序排列，未知类型追加到末尾"""
    return sorted(fts, key=lambda ft: _CANONICAL_FILE_TYPE_INDEX.get(ft, len(_CANONICAL_FILE_TYPE_ORDER)))


MESH_SETTINGS = {
    "exportAllLODs": True,
    "autoSolveRepeatedUVs": True,
    "preserveSharpEdges": True,
    "rotate90": True,
    "useBlenderMaterialName": False,
    "preserveBoneMatrices": False,
    "exportBoundingBoxes": False,
}


def _do_export_mesh(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    call_re_mesh_op('exportfile', filepath=filepath, targetCollection=collection_name, **MESH_SETTINGS)

def _do_export_mdf2(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_mdf.exportfile(filepath=filepath, targetCollection=collection_name)

def _do_export_chain(filepath, collection_name):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.re_chain.exportfile(filepath=filepath, targetCollection=collection_name)


_EXPORT_FUNCS = {
    "mesh":  _do_export_mesh,
    "mdf2":  _do_export_mdf2,
    "chain": _do_export_chain,
}


def _get_mhrs_schemes_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(addon_dir, "assets", "mhrs", "armor_sets")
    os.makedirs(d, exist_ok=True)
    return d


_scheme_cache = []

def get_mhrs_schemes_callback(self, context):
    global _scheme_cache
    _scheme_cache = []
    d = _get_mhrs_schemes_dir()
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            name = os.path.splitext(f)[0]
            _scheme_cache.append((f, name, ""))
    if not _scheme_cache:
        _scheme_cache.append(('NONE', T("core.export_prep.no_armor_pack"), ""))
    return _scheme_cache


def _load_scheme(filename):
    if not filename or filename == 'NONE':
        return None
    filepath = os.path.join(_get_mhrs_schemes_dir(), filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


_armor_cache = []

def get_mhrs_armor_callback(self, context):
    """动态回调：根据当前选中的 scheme 文件列出装备"""
    global _armor_cache
    _armor_cache = []
    settings = context.scene.mhw_suite_settings
    scheme = _load_scheme(settings.mhrs_armor_scheme)
    if scheme:
        for armor in scheme.get("armor_sets", []):
            armor_id = armor["id"]
            name = armor.get("name", armor_id)
            _armor_cache.append((armor_id, f"{name}  ({armor_id})", ""))
    if not _armor_cache:
        _armor_cache.append(('NONE', T("core.export_prep.no_armor"), ""))
    return _armor_cache


# ── Binding 存储（scene 自定义属性）────────────────────────────
# Key 格式：mhrs_{armor_id}_{gender}_{part}_{filetype}
# 注意：与 MHWS 不同，性别在此处代表不同的模型本体，因此绑定按性别区分。

def _make_key(armor_id, gender, part, filetype):
    return f"mhrs_{armor_id}_{gender}_{part}_{filetype}".replace(" ", "_")

def get_binding(scene, armor_id, gender, part, filetype):
    return scene.get(_make_key(armor_id, gender, part, filetype), "")

def set_binding(scene, armor_id, gender, part, filetype, value):
    scene[_make_key(armor_id, gender, part, filetype)] = value


def _get_blank_path(filetype):
    """Return the path to the built-in blank file for the given filetype."""
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(addon_dir, "assets", "blank_files", "mhrs", f"blank.{filetype}")


def _resolve_part_file_types(armor_set, part_id):
    """Resolve which file types apply to a specific part.
    Priority: armor_set.parts_file_types[part_id] >
              armor_set.file_types >
              DEFAULT_FILE_TYPES
    user.2 只存在于头盔，其余部位一律剔除（游戏本身就没有这个文件）。
    """
    parts_fts = armor_set.get("parts_file_types")
    if parts_fts and part_id in parts_fts:
        fts = parts_fts[part_id]
    else:
        fts = armor_set.get("file_types", DEFAULT_FILE_TYPES)
    if part_id != HELM_PART:
        fts = [ft for ft in fts if ft != "user"]
    return fts


def _make_filepath(natives_root, gender, code, part_id, filetype):
    ext = MHRS_EXTS[filetype]
    filename = f"{gender}_{part_id}{code}.{ext}"
    return os.path.join(natives_root, "natives", "STM", "player", "mod", gender, f"pl{code}", filename)


def _make_shadow_filepath(natives_root, gender):
    ext = MHRS_EXTS["mesh"]
    return os.path.join(natives_root, "natives", "STM", "player", "mod", gender, "bone", f"{gender}_shadow.{ext}")


# ── Shadow Mesh（作用类似 fbxskel 的影子网格）────────────────────

def _get_shadow_asset_path(gender):
    """内置的 f_shadow/m_shadow 参考模型（需要用户后续放入 assets/mhrs/shadow/）"""
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(addon_dir, "assets", "mhrs", "shadow", f"{gender}_shadow.{MHRS_EXTS['mesh']}")


def _get_armature_from_collection(col_name):
    if not col_name or col_name not in bpy.data.collections:
        return None
    arms = [o for o in bpy.data.collections[col_name].objects if o.type == 'ARMATURE']
    return arms[0] if len(arms) == 1 else None


def _find_auto_align_armature(scene, armor_id, gender, parts_mask):
    """
    未手动指定对齐骨架时的保险：若本次勾选的部位中，绑定的 mesh 集合
    实际只涉及同一个集合（不管绑定了几个部位），就自动取该集合中的
    唯一骨架作为对齐骨架；有 0 个或 >1 个不同集合时返回 None。
    """
    mesh_cols = set()
    for idx, (part_id, _name) in enumerate(MHRS_PARTS):
        if not (parts_mask & (1 << idx)):
            continue
        col_name = get_binding(scene, armor_id, gender, part_id, "mesh")
        if col_name:
            mesh_cols.add(col_name)
    if len(mesh_cols) != 1:
        return None
    return _get_armature_from_collection(next(iter(mesh_cols)))


@contextlib.contextmanager
def _imported_shadow(context, gender):
    """临时导入内置的 {gender}_shadow 参考模型，产出 (集合名, 骨架)，退出时清理。

    全局骨架导出要把它对齐后重新导出，LuaBoneSystem 导出要读它的骨骼静置坐标当
    基准——两者要的是同一个文件、同一次导入、同一套善后，所以放在一处。
    """
    prev_active   = context.view_layer.objects.active
    prev_selected = [o for o in context.selected_objects]
    for o in prev_selected:
        o.select_set(False)

    imported_col_name = None
    try:
        asset_path = _get_shadow_asset_path(gender)
        # 显式传入 createCollections=True / clearScene=False：
        # 脚本调用 bpy.ops 时未指定的属性会沿用 Blender 记住的“上次使用值”，
        # 而不是类声明的默认值，若之前手动导入时改过这些选项，
        # 会导致 REMeshLastImportedCollection 不被写入（甚至清空场景），必须显式指定。
        call_re_mesh_op(
            'importfile',
            directory=os.path.dirname(asset_path),
            files=[{"name": os.path.basename(asset_path)}],
            clearScene=False,
            createCollections=True,
            loadMaterials=False,
            loadMDFData=False,
            loadShellFur=False,
            importBoundingBoxes=False,
        )
        imported_col_name = context.scene.get("REMeshLastImportedCollection", "")
        if not imported_col_name or imported_col_name not in bpy.data.collections:
            raise RuntimeError(T("mhrs.batch_export.shadow_import_failed").format(path=asset_path))

        shadow_arm = _get_armature_from_collection(imported_col_name)
        if shadow_arm is None:
            raise RuntimeError(T("mhrs.batch_export.shadow_no_unique_armature"))

        yield imported_col_name, shadow_arm

    finally:
        if imported_col_name and imported_col_name in bpy.data.collections:
            col = bpy.data.collections[imported_col_name]
            for obj in list(col.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(col)
        context.view_layer.objects.active = prev_active
        for o in prev_selected:
            if o.name in bpy.data.objects:
                o.select_set(True)


def _check_shadow_asset(gender, align_arm):
    """两种骨架方案共同的前置条件，或 None。"""
    if not re_mesh_op_available('importfile'):
        return T("mhrs.batch_export.shadow_need_importer")
    if align_arm is None or align_arm.type != 'ARMATURE':
        return T("mhrs.batch_export.shadow_need_align_arm")
    asset_path = _get_shadow_asset_path(gender)
    if not os.path.isfile(asset_path):
        return T("mhrs.batch_export.shadow_missing_asset").format(
            name=os.path.basename(asset_path))
    return None


def _do_shadow_export(context, natives_root, gender, align_arm):
    """
    导入内置的 {gender}_shadow 参考模型，将其骨架对齐到 align_arm，
    导出到固定路径 natives/STM/player/mod/{gender}/bone/{gender}_shadow.mesh.###，
    然后清理临时导入的集合。

    返回 (ok: bool, message: str)。
    """
    err = _check_shadow_asset(gender, align_arm)
    if err:
        return False, err

    try:
        with _imported_shadow(context, gender) as (imported_col_name, shadow_arm):
            align_armatures_by_name(align_arm, shadow_arm, mode='FULL')

            dest_path = _make_shadow_filepath(natives_root, gender)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            call_re_mesh_op('exportfile', filepath=dest_path,
                            targetCollection=imported_col_name, **MESH_SETTINGS)

        return True, T("mhrs.batch_export.shadow_export_done").format(
            name=os.path.basename(dest_path))

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, T("mhrs.batch_export.shadow_export_failed").format(err=e)


def _do_lua_bone_export(context, natives_root, gender, armor_id, align_arm):
    """把 align_arm 相对内置 shadow 骨架的静置差写成 LuaBoneSystem 的五份 json。

    和全局骨架方案互斥，且解决的正是它的问题：全局方案覆盖 mod/{gender}/bone/ 下
    唯一的那份骨架，一套装备的体型会套到所有装备上；这里写的是按装备 id 索引的
    偏移表，只在穿着这套时生效。代价是玩家需要装 LuaBoneSystem 这个 REFramework
    脚本，而全局方案不需要。

    返回 (ok: bool, message: str)。
    """
    err = _check_shadow_asset(gender, align_arm)
    if err:
        return False, err

    try:
        with _imported_shadow(context, gender) as (_col_name, shadow_arm):
            base = lua_bone_system.local_rest_positions(shadow_arm)
        target = lua_bone_system.local_rest_positions(align_arm)
        offsets = lua_bone_system.build_offsets(target, base)
        written = lua_bone_system.write(natives_root, gender, armor_id, offsets)

        missing = sorted(set(base) - set(target) - lua_bone_system.ZERO_JOINTS)
        return True, T("mhrs.batch_export.lua_bone_export_done").format(
            count=len(written), dir=os.path.basename(os.path.dirname(written[0])),
            missing=len(missing))

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, T("mhrs.batch_export.lua_bone_export_failed").format(err=e)


# ── 导出 Operator ──────────────────────────────────────────────

class MHRS_OT_BatchExport(bpy.types.Operator):
    """Batch-export MHRS armor"""
    bl_idname = "mhrs.batch_export"
    bl_label = "MHRS Batch Export"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_export.batch_export_desc")

    def _bound_mesh_collections(self, scene, armor_id, gender):
        """Every distinct mesh collection bound to the selected armor set."""
        seen = set()
        mesh_collections = []
        for part_id, _name in MHRS_PARTS:
            col_name = get_binding(scene, armor_id, gender, part_id, "mesh")
            if col_name and col_name not in seen:
                col = bpy.data.collections.get(col_name)
                if col:
                    mesh_collections.append(col)
                    seen.add(col_name)
        return mesh_collections

    def _cleanup_mesh_collections(self, context, scene, settings, armor_id, gender):
        """Run RE Mesh cleanup operators on all bound mesh collections before export."""
        if not re_mesh_op_available('delete_loose'):
            self.report({'WARNING'}, T("mhrs.batch_export.remesh_not_installed"))
            return

        mesh_collections = self._bound_mesh_collections(scene, armor_id, gender)
        if not mesh_collections:
            return

        if context.view_layer.objects.active is not None and context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        for col in mesh_collections:
            for obj in [o for o in col.objects if o.type == 'MESH']:
                context.view_layer.objects.active = obj
                obj.select_set(True)
                try: call_re_mesh_op('delete_loose')
                except Exception: pass
                try: call_re_mesh_op('solve_repeated_uvs')
                except Exception: pass
                try: call_re_mesh_op('remove_zero_weight_vertex_groups')
                except Exception: pass
                try:
                    call_re_mesh_op('limit_total_normalize', maxWeights='12')
                except Exception:
                    try:
                        bpy.ops.object.vertex_group_limit_total(limit=12)
                        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
                    except Exception:
                        pass
                obj.select_set(False)

    def execute(self, context):
        show_console = console_export.get_preferences(context).show_console_on_batch_export
        with console_export.kept_open_for_export(show_console):
            return self._execute_with_triangulation(context)

    def _execute_with_triangulation(self, context):
        # Triangulation rides on the modifier stack: RE Mesh Editor exports
        # evaluated geometry, so the mesh data is never touched and the
        # modifiers come off again even if the export raises.
        settings = context.scene.mhw_suite_settings
        if not settings.mhrs_triangulate_face:
            return self._run_export(context)
        with export_prep.triangulated_for_export(context.scene.objects, 'mhrs') as touched:
            if touched:
                print("[MHRS] triangulating {n} face mesh(es) for export".format(n=len(touched)))
            return self._run_export(context)

    def _run_export(self, context):
        scene = context.scene
        settings = scene.mhw_suite_settings

        if not re_mesh_op_available('exportfile'):
            self.report({'ERROR'}, "RE Mesh Editor not installed")
            return {'CANCELLED'}

        natives_root = scene.get("mhrs_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("core.export_prep.set_mod_root_first"))
            return {'CANCELLED'}

        scheme = _load_scheme(settings.mhrs_armor_scheme)
        if not scheme:
            self.report({'ERROR'}, T("mhrs.batch_export.load_scheme_failed"))
            return {'CANCELLED'}

        armor_id = settings.mhrs_selected_armor
        if not armor_id or armor_id == 'NONE':
            self.report({'ERROR'}, T("core.export_prep.select_armor_first"))
            return {'CANCELLED'}

        armor_set = next((a for a in scheme.get("armor_sets", []) if a["id"] == armor_id), None)
        if not armor_set:
            self.report({'ERROR'}, T("mhrs.batch_export.armor_not_found_in_scheme").format(id=armor_id))
            return {'CANCELLED'}

        gender = settings.mhrs_gender
        parts_mask = armor_set.get("parts_mask", 0b11111)

        if settings.mhrs_cleanup_before_export:
            self._cleanup_mesh_collections(context, scene, settings, armor_id, gender)

        export_count = 0
        fail_count = 0
        skip_count = 0
        use_blank = settings.mhrs_use_blank_export

        for idx, (part_id, part_name) in enumerate(MHRS_PARTS):
            if not (parts_mask & (1 << idx)):
                continue
            part_fts = _canonical_order_file_types(
                _resolve_part_file_types(armor_set, part_id))
            for filetype in part_fts:
                filepath = _make_filepath(natives_root, gender, armor_id, part_id, filetype)
                label = f"{part_name} {filetype.upper()}"

                col = get_binding(scene, armor_id, gender, part_id, filetype)
                if not col:
                    if use_blank and filetype not in NO_BLANK_FILE_TYPES:
                        blank_src = _get_blank_path(filetype)
                        if os.path.isfile(blank_src):
                            os.makedirs(os.path.dirname(filepath), exist_ok=True)
                            shutil.copy2(blank_src, filepath)
                            print(f"[MHRS] {label}: BLANK -> {os.path.basename(filepath)}")
                            export_count += 1
                        else:
                            print(f"[MHRS] SKIP blank (file not found): {blank_src}")
                            skip_count += 1
                    else:
                        skip_count += 1
                    continue
                if col not in bpy.data.collections:
                    print(f"[MHRS] SKIP {label}: collection '{col}' not found")
                    skip_count += 1
                    continue
                try:
                    print(f"[MHRS] {label}: {col} -> {os.path.basename(filepath)}")
                    _EXPORT_FUNCS[filetype](filepath, col)
                    export_count += 1
                except Exception as err:
                    print(f"[MHRS] FAILED {label}: {err}")
                    fail_count += 1

        # ── 体型方案：全局骨架 / LuaBoneSystem，二选一 ──
        # 互斥不是取舍而是事实：两者都在改同一批关节，同时启用会让全局骨架先把
        # 体型烘进 shadow.mesh，脚本再在它之上叠一份同样的偏移，结果是加倍。
        mode = settings.mhrs_skeleton_mode      # ENUM_FLAG -> a set, possibly empty
        if mode:
            align_arm = settings.mhrs_shadow_armature
            if align_arm is None:
                align_arm = _find_auto_align_armature(scene, armor_id, gender, parts_mask)
            if 'SHADOW' in mode:
                ok, msg = _do_shadow_export(context, natives_root, gender, align_arm)
            else:
                ok, msg = _do_lua_bone_export(context, natives_root, gender,
                                              armor_id, align_arm)
            if ok:
                self.report({'INFO'}, msg)
                export_count += 1
            else:
                self.report({'WARNING'}, msg)
                fail_count += 1

        if fail_count > 0:
            self.report({'WARNING'}, T("core.export_prep.export_done_with_fail").format(
                export=export_count, fail=fail_count, skip=skip_count))
        else:
            self.report({'INFO'}, T("core.export_prep.export_done").format(
                export=export_count, skip=skip_count))
        return {'FINISHED'}


class MHRS_OT_SetNativesRoot(bpy.types.Operator):
    """Select the MHRS mod root folder (the parent of natives). If the selected folder is itself
    named natives, its parent is used automatically"""
    bl_idname = "mhrs.set_natives_root"
    bl_label = "Set Mod Root"
    bl_options = {'REGISTER'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    @classmethod
    def description(cls, context, properties):
        return T("mhrs.batch_export.set_natives_root_desc")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    def execute(self, context):
        path = self.directory.rstrip("/\\")
        if os.path.basename(path).lower() == "natives":
            path = os.path.dirname(path)
        context.scene["mhrs_natives_root"] = path
        self.report({'INFO'}, f"MHRS Mod root: {path}")
        return {'FINISHED'}


classes = [
    MHRS_OT_BatchExport,
    MHRS_OT_SetNativesRoot,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
