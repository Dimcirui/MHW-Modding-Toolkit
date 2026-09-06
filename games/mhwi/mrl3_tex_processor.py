import bpy
import os
import tempfile
import shutil
import time

from ...core.i18n import T
from ...core.color_grade import color_grade_items, DEFAULT_MODE_INDEX
from ...core.slot_resolver import grade_source_file
from ...core.mdf_tex_processor_base import (
    PBR_TYPES, PBR_CHANNEL_SELECTABLE,
    MdfTexMaterialItem,
    _compose_channels, make_null_checker,
    _save_col_state, _load_col_state, _capture_material_state,
    MdfTexPickPBRBase, MdfTexPickDirectBase,
    MdfTexClearPBRBase, MdfTexClearDirectBase,
    MdfTexCopyMaterialBase, MdfTexPasteMaterialBase,
    _import_tex_utils,
)


# ── MHWI MRL3 constants ───────────────────────────────────────────────────────

# (slot_type, label, pbr_composable) -- label is currently unused for display
# (UI draws slot.texture_type directly); kept in English for documentation value.
MHWI_MRL3_SLOT_DEFS = [
    ("AlbedoMap",      "BaseAlpha",     True),
    ("NormalMap",      "Normal",        True),
    ("RMTMap",         "RMT",           True),
    ("EmissiveMap",    "Emissive",      True),
    ("ColorMaskMap",   "Color Mask",    False),
    ("FxMap",          "FX",            False),
    ("FurVelocityMap", "Fur Velocity",  False),
]

MHWI_PBR_SLOT_TYPES = {s for s, _, pbr in MHWI_MRL3_SLOT_DEFS if pbr}
MHWI_ALL_SLOT_TYPES = {s for s, _, _  in MHWI_MRL3_SLOT_DEFS}

# BML and EMI are the only colour data in MRL3; everything else (Alpha, RMT,
# CMM, XM, FM, ...) is non-colour. Normals used to go out as BC5_UNORM, but the
# MRL3 shader never reads B from an NM, so BC7_UNORM is the safer four-channel
# choice at the same cost — and it matches REE-Content-Editor, which never picks
# BC5 for any slot.
MHWI_SRGB_SLOT_TYPES = {'AlbedoMap', 'EmissiveMap'}

MHWI_ABBREV_MAP = {
    'AlbedoMap':      'BML',
    'NormalMap':      'NM',
    'RMTMap':         'RMT',
    'EmissiveMap':    'EMI',
    'ColorMaskMap':   'MSK',
    'FxMap':          'FX',
    'FurVelocityMap': 'FVEL',
}

MHWI_NULL_TEX = {
    'AlbedoMap':      'Assets\\default_tex\\null_black',
    'NormalMap':      'Assets\\default_tex\\null_NM',
    'RMTMap':         'Assets\\default_tex\\null_RMT',
    'EmissiveMap':    'Assets\\default_tex\\null_black',
    'ColorMaskMap':   'Assets\\default_tex\\null_black',
    'FxMap':          'Assets\\default_tex\\null_black',
    'FurVelocityMap': 'Assets\\default_tex\\null_black',
}

# Channel composition maps for PBR-composable slots
MHWI_SLOT_CHANNEL_MAPS = {
    'AlbedoMap': {
        'R': ('color',    0),
        'G': ('color',    1),
        'B': ('color',    2),
        'A': ('alpha',    0),
    },
    'NormalMap': {
        'R': ('normal',   0),
        'G': ('normal',   1),
        'B': None,
        'A': 1.0,
    },
    'RMTMap': {
        'R': ('roughness', 0),
        'G': ('metallic',  0),
        'B': None,
        'A': 1.0,
    },
    'EmissiveMap': {
        'R': ('emissive', 0),
        'G': ('emissive', 1),
        'B': ('emissive', 2),
        'A': ('emissive', 3),
    },
}

_is_null_mhwi = make_null_checker(MHWI_NULL_TEX)


# ── Path helpers ──────────────────────────────────────────────────────────────

def _mhwi_tex_binding(base_path, tex_name, slot_type):
    """Value written to MRL3 mapList (no nativePC prefix, no extension, backslashes)."""
    abbrev = MHWI_ABBREV_MAP.get(slot_type, slot_type)
    base   = base_path.strip('/\\').replace('/', '\\')
    return f"{base}\\{tex_name}_{abbrev}"


def _mhwi_disk_path(natives_root, base_path, tex_name, slot_type):
    """Absolute filesystem path for the .tex output file."""
    abbrev = MHWI_ABBREV_MAP.get(slot_type, slot_type)
    base   = base_path.strip('/\\').replace('\\', os.sep).replace('/', os.sep)
    return os.path.join(natives_root, 'nativePC', base, f"{tex_name}_{abbrev}.tex")


# ── MHW Model Editor tex import ───────────────────────────────────────────────

def _import_mhwtex_convert():
    """Locate convertDDSFileToTex from MHW Model Editor."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.tex.tex_function'):
            fn = getattr(mod, 'convertDDSFileToTex', None)
            if fn:
                return fn
    if not hasattr(bpy.ops, 'mhw_tex'):
        return None
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            tm = importlib.import_module(f"{pkg}.modules.tex.tex_function")
            fn = getattr(tm, 'convertDDSFileToTex', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


# ── Collection refresh ────────────────────────────────────────────────────────

def _do_mhwi_refresh(settings, col, scene):
    """Populate settings.materials from an MRL3 collection."""
    loaded_name = settings.mrl3_loaded_collection
    new_name    = col.name

    if loaded_name == new_name:
        saved = {m.material_name: _capture_material_state(m) for m in settings.materials}
        for k, v in _load_col_state(scene, new_name).items():
            saved.setdefault(k, v)
    else:
        if loaded_name:
            _save_col_state(scene, loaded_name,
                            {m.material_name: _capture_material_state(m)
                             for m in settings.materials})
        saved = _load_col_state(scene, new_name)

    settings.materials.clear()
    count = 0

    for obj in col.all_objects:
        if obj.get("~TYPE") != "MHW_MRL3_MATERIAL":
            continue
        mat_data = getattr(obj, 'mhw_mrl3_material', None)
        if mat_data is None:
            continue

        item                   = settings.materials.add()
        item.material_obj_name = obj.name
        item.material_name     = mat_data.materialName

        prev       = saved.get(mat_data.materialName, {})
        prev_pbr   = prev.get('pbr',     {})
        prev_chs   = prev.get('pbr_chs', {})
        prev_inv   = prev.get('pbr_inv', {})
        prev_slots = prev.get('slots',   {})

        for pt in PBR_TYPES:
            setattr(item.pbr, pt, prev_pbr.get(pt, ''))
        for pt in PBR_CHANNEL_SELECTABLE:
            setattr(item.pbr, f"{pt}_ch",  prev_chs.get(pt, 'R'))
            setattr(item.pbr, f"{pt}_inv", prev_inv.get(pt, False))
        item.pbr.normal_flip_g = prev.get('normal_flip_g', False)

        present_maps = {mi.name for mi in mat_data.mapList_items}

        for slot_type, _, _ in MHWI_MRL3_SLOT_DEFS:
            if slot_type not in present_maps:
                continue
            map_item = next(
                (mi for mi in mat_data.mapList_items if mi.name == slot_type), None)
            if map_item is None:
                continue

            slot               = item.slots.add()
            slot.texture_type  = slot_type
            slot.original_path = map_item.value

            if slot_type in prev_slots:
                sd = prev_slots[slot_type]
                if isinstance(sd, dict):
                    slot.mode         = sd.get('mode', 'SKIP')
                    slot.direct_image = sd.get('direct_image', '')
                else:
                    slot.mode, slot.direct_image = sd
            elif _is_null_mhwi(map_item.value):
                slot.mode = 'DEFAULT'

        count += 1

    _save_col_state(scene, new_name,
                    {m.material_name: _capture_material_state(m)
                     for m in settings.materials})
    settings.mrl3_loaded_collection = new_name
    return count


# ── PropertyGroup ─────────────────────────────────────────────────────────────

def _mrl3_collection_poll(self, col):
    return col.get("~TYPE") == "MHW_MRL3_COLLECTION" or col.name.endswith(".mrl3")


def _on_mrl3_collection_update(self, context):
    try:
        col = self.mrl3_collection
        if col:
            _do_mhwi_refresh(self, col, context.scene)
        else:
            if self.mrl3_loaded_collection:
                _save_col_state(
                    context.scene, self.mrl3_loaded_collection,
                    {m.material_name: _capture_material_state(m)
                     for m in self.materials})
            self.materials.clear()
            self.mrl3_loaded_collection = ""
    except Exception as e:
        print(f"[MHWI Tex] Auto-refresh error: {e}")




class Mrl3TexProcessorSettings(bpy.types.PropertyGroup):
    mrl3_collection: bpy.props.PointerProperty(
        name="MRL3 Collection",
        type=bpy.types.Collection,
        poll=_mrl3_collection_poll,
        update=_on_mrl3_collection_update,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Texture directory under nativePC/, e.g. pl/f_equip/pl042_0500/helm/tex",
        default="",
    )
    materials:              bpy.props.CollectionProperty(type=MdfTexMaterialItem)
    materials_index:        bpy.props.IntProperty()
    clipboard_json:         bpy.props.StringProperty(default="")
    mrl3_loaded_collection: bpy.props.StringProperty(default="")
    # 与生成器同名同义的全局档，见 core/color_grade.py。默认 NONE。
    global_color_grade: bpy.props.EnumProperty(
        name="Colour Grade (Global)",
        description="Tone adjustment applied to every colour (sRGB) texture before encoding",
        items=lambda self, ctx: color_grade_items(),
        default=DEFAULT_MODE_INDEX,
    )
    global_disable_mipmaps: bpy.props.BoolProperty(
        name="Disable MipMaps (Global)",
        description="Override every material's own Generate MipMaps checkbox and skip mipmap generation entirely",
        default=False,
    )


# ── Operators ─────────────────────────────────────────────────────────────────

class MHWI_OT_Mrl3TexRefresh(bpy.types.Operator):
    bl_idname  = "mhwi.mrl3_tex_refresh"
    bl_label   = "Refresh"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        settings = context.scene.mhwi_mrl3_tex_processor
        col = settings.mrl3_collection
        if not col:
            self.report({'ERROR'}, T("mhwi.mrl3_tex_processor.select_mrl3_collection_first"))
            return {'CANCELLED'}
        count = _do_mhwi_refresh(settings, col, context.scene)
        self.report({'INFO'}, T("mhwi.mrl3_tex_processor.materials_loaded").format(n=count))
        return {'FINISHED'}


class MHWI_OT_Mrl3TexPickPBR(MdfTexPickPBRBase):
    bl_idname      = "mhwi.mrl3_tex_pick_pbr"
    _settings_attr = "mhwi_mrl3_tex_processor"


class MHWI_OT_Mrl3TexPickDirect(MdfTexPickDirectBase):
    bl_idname      = "mhwi.mrl3_tex_pick_direct"
    _settings_attr = "mhwi_mrl3_tex_processor"


class MHWI_OT_Mrl3TexClearPBR(MdfTexClearPBRBase):
    bl_idname      = "mhwi.mrl3_tex_clear_pbr"
    _settings_attr = "mhwi_mrl3_tex_processor"


class MHWI_OT_Mrl3TexClearDirect(MdfTexClearDirectBase):
    bl_idname      = "mhwi.mrl3_tex_clear_direct"
    _settings_attr = "mhwi_mrl3_tex_processor"


class MHWI_OT_Mrl3TexCopyMaterial(MdfTexCopyMaterialBase):
    bl_idname      = "mhwi.mrl3_tex_copy_material"
    _settings_attr = "mhwi_mrl3_tex_processor"


class MHWI_OT_Mrl3TexPasteMaterial(MdfTexPasteMaterialBase):
    bl_idname      = "mhwi.mrl3_tex_paste_material"
    _settings_attr = "mhwi_mrl3_tex_processor"


class MHWI_OT_Mrl3TexProcess(bpy.types.Operator):
    bl_idname  = "mhwi.mrl3_tex_process"
    bl_label   = "Process"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.mrl3_tex_processor.process_desc")

    def execute(self, context):
        _t_total = time.time()
        scene    = context.scene
        settings = scene.mhwi_mrl3_tex_processor

        natives_root = scene.get("mhwi_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("mhwi.mrl3_generator.set_mod_root_first"))
            return {'CANCELLED'}
        if not settings.mrl3_collection:
            self.report({'ERROR'}, T("mhwi.mrl3_tex_processor.select_mrl3_collection_first"))
            return {'CANCELLED'}
        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.fill_base_path"))
            return {'CANCELLED'}
        if not settings.materials:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.click_refresh_first"))
            return {'CANCELLED'}

        print("[MHWI Tex] ========================================", flush=True)

        _t_import = time.time()
        ConvertDDSToTex = _import_mhwtex_convert()
        # print(f"[MHWI Tex] 加载 MHW Model Editor 模块: {time.time() - _t_import:.2f}s", flush=True)
        if ConvertDDSToTex is None:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.cannot_load_tex_convert"))
            return {'CANCELLED'}

        ImageListToDDS, __ = _import_tex_utils()

        temp_dir     = tempfile.mkdtemp(prefix="mhwi_tex_")
        export_count = fail_count = skip_count = 0

        try:
            for mat_item in settings.materials:
                _t_mat = time.time()
                mat_obj = settings.mrl3_collection.all_objects.get(
                    mat_item.material_obj_name)
                if mat_obj is None:
                    continue
                mat_data = getattr(mat_obj, 'mhw_mrl3_material', None)
                if mat_data is None:
                    continue

                tex_name      = mat_item.material_name
                # The global toggle overrides this material's own checkbox,
                # same as core.mdf_tex_processor_base's execute().
                effective_mipmaps = (mat_item.generate_mipmaps
                                    and not getattr(settings, 'global_disable_mipmaps', False))
                grade_mode = getattr(settings, 'global_color_grade', 'NONE')
                pbr_paths     = {pt: getattr(mat_item.pbr, pt) for pt in PBR_TYPES}
                pbr_channels  = {pt: getattr(mat_item.pbr, f"{pt}_ch")
                                 for pt in PBR_CHANNEL_SELECTABLE}
                pbr_inv       = {pt: getattr(mat_item.pbr, f"{pt}_inv")
                                 for pt in PBR_CHANNEL_SELECTABLE}
                normal_flip_g = mat_item.pbr.normal_flip_g

                color_path    = pbr_paths.get('color', '')
                emissive_path = pbr_paths.get('emissive', '')
                share_emi     = bool(color_path and emissive_path and color_path == emissive_path)
                bml_value_out = None

                for slot in mat_item.slots:
                    if slot.mode == 'SKIP':
                        skip_count += 1
                        continue

                    map_item = next(
                        (mi for mi in mat_data.mapList_items
                         if mi.name == slot.texture_type), None)
                    if map_item is None:
                        skip_count += 1
                        continue

                    if slot.mode == 'DEFAULT':
                        null_val = MHWI_NULL_TEX.get(slot.texture_type)
                        if null_val:
                            map_item.value = null_val
                            print(f"[MHWI Tex] NULL  {slot.texture_type}: {null_val}")
                            export_count += 1
                        else:
                            skip_count += 1
                        continue

                    if (slot.mode == 'COMPOSE'
                            and slot.texture_type == 'EmissiveMap'
                            and share_emi and bml_value_out):
                        map_item.value = bml_value_out
                        print(f"[MHWI Tex] EMI reuse BML: {bml_value_out}")
                        export_count += 1
                        continue

                    # COMPOSE or DIRECT
                    try:
                        if slot.mode == 'COMPOSE':
                            if mat_item.skip_textures:
                                map_item.value = _mhwi_tex_binding(
                                    base_path, tex_name, slot.texture_type)
                                export_count += 1
                                continue
                            if slot.texture_type not in MHWI_PBR_SLOT_TYPES:
                                print(f"[MHWI Tex] SKIP  {slot.texture_type}: "
                                      "非 PBR 合成槽位，请改用 DIRECT 模式")
                                skip_count += 1
                                continue
                            _t_comp = time.time()
                            src_img = _compose_channels(
                                slot.texture_type, pbr_paths, pbr_channels,
                                temp_dir, tex_name, pbr_inv,
                                channel_maps=MHWI_SLOT_CHANNEL_MAPS,
                                normal_flip_g=normal_flip_g,
                            )
                            # print(f"[MHWI Tex]   合成通道 {slot.texture_type}: {time.time() - _t_comp:.2f}s", flush=True)
                            if src_img is None:
                                null_val = MHWI_NULL_TEX.get(slot.texture_type)
                                if null_val:
                                    map_item.value = null_val
                                    print(f"[MHWI Tex] NULL (empty inputs) {slot.texture_type}: {null_val}")
                                    export_count += 1
                                else:
                                    print(f"[MHWI Tex] SKIP  {slot.texture_type}: 无 PBR 输入图片")
                                    skip_count += 1
                                continue
                        else:  # DIRECT
                            if mat_item.skip_textures:
                                map_item.value = _mhwi_tex_binding(
                                    base_path, tex_name, slot.texture_type)
                                export_count += 1
                                continue
                            src_img = bpy.path.abspath(slot.direct_image)
                            if not src_img or not os.path.isfile(src_img):
                                print(f"[MHWI Tex] SKIP  {slot.texture_type}: "
                                      "文件未找到")
                                skip_count += 1
                                continue

                        disk_path = _mhwi_disk_path(
                            natives_root, base_path, tex_name, slot.texture_type)
                        os.makedirs(os.path.dirname(disk_path), exist_ok=True)

                        src_name  = os.path.basename(src_img)
                        src_lower = src_img.lower()

                        if '.tex' in src_name.lower():
                            shutil.copy2(src_img, disk_path)
                        elif src_lower.endswith('.dds'):
                            _t_tex = time.time()
                            ConvertDDSToTex([src_img], disk_path)
                            # print(f"[MHWI Tex]   DDS→TEX {slot.texture_type}: {time.time() - _t_tex:.2f}s", flush=True)
                        else:
                            dds_fmt = (
                                'BC7_UNORM_SRGB' if slot.texture_type in MHWI_SRGB_SLOT_TYPES
                                else 'BC7_UNORM'
                            )
                            # 这条路没走 slot_resolver.write_slot_tex（它自己内联了
                            # 一份），所以色调处理得在这里显式接一下，用的是同一个函数。
                            _g = grade_source_file(src_img, temp_dir, dds_fmt, grade_mode)
                            if _g is not None:
                                src_img, src_name = _g, os.path.basename(_g)
                            dds_stem = os.path.splitext(src_name)[0]
                            dds_path = os.path.join(temp_dir, dds_stem + '.dds')
                            _t_dds = time.time()
                            ImageListToDDS(
                                [(src_img, dds_fmt)], temp_dir,
                                effective_mipmaps)
                            # print(f"[MHWI Tex]   PNG→DDS {slot.texture_type}: {time.time() - _t_dds:.2f}s", flush=True)
                            if not os.path.isfile(dds_path):
                                raise FileNotFoundError(
                                    f"texconv 输出未找到: {dds_path}")
                            _t_tex = time.time()
                            ConvertDDSToTex([dds_path], disk_path)
                            # print(f"[MHWI Tex]   DDS→TEX {slot.texture_type}: {time.time() - _t_tex:.2f}s", flush=True)

                        map_item.value = _mhwi_tex_binding(
                            base_path, tex_name, slot.texture_type)
                        if slot.texture_type == 'AlbedoMap':
                            bml_value_out = map_item.value
                        print(f"[MHWI Tex] OK    {slot.texture_type} -> "
                              f"{os.path.basename(disk_path)}")
                        export_count += 1

                    except Exception as err:
                        print(f"[MHWI Tex] FAIL  {slot.texture_type}: {err}")
                        fail_count += 1

            print(f"[MHWI Tex] 材质耗时: {mat_item.material_name} {time.time() - _t_mat:.2f}s", flush=True)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print(f"[MHWI Tex] ★ 总耗时: {time.time() - _t_total:.2f}s ★", flush=True)

        if fail_count > 0:
            self.report({'WARNING'},
                        T("mhwi.mrl3_tex_processor.process_done_with_fail").format(
                            n=export_count, fail=fail_count, skip=skip_count))
        else:
            self.report({'INFO'}, T("mhwi.mrl3_tex_processor.process_done").format(
                n=export_count, skip=skip_count))
        return {'FINISHED'}


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    Mrl3TexProcessorSettings,
    MHWI_OT_Mrl3TexRefresh,
    MHWI_OT_Mrl3TexPickPBR,
    MHWI_OT_Mrl3TexPickDirect,
    MHWI_OT_Mrl3TexClearPBR,
    MHWI_OT_Mrl3TexClearDirect,
    MHWI_OT_Mrl3TexCopyMaterial,
    MHWI_OT_Mrl3TexPasteMaterial,
    MHWI_OT_Mrl3TexProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhwi_mrl3_tex_processor = bpy.props.PointerProperty(
        type=Mrl3TexProcessorSettings)


def unregister():
    del bpy.types.Scene.mhwi_mrl3_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
