import bpy

from ...core.mdf_tex_processor_base import (
    BASE_SLOT_CHANNEL_MAPS, BASE_NULL_TEX_BY_TYPE, BASE_TEXTURE_TYPE_ABBREV,
    BASE_COMMON_SLOT_TYPES,
    PBR_TYPES, PBR_TYPE_LABELS, PBR_CHANNEL_SELECTABLE, SRGB_SLOT_TYPES,
    _CH_ENUM_ITEMS,
    make_null_checker, make_collection_update_cb, mdf_collection_poll,
    MdfTexMaterialItem,
    MdfTexRefreshBase, MdfTexPickPBRBase, MdfTexPickDirectBase,
    MdfTexClearPBRBase, MdfTexClearDirectBase,
    MdfTexCopyMaterialBase, MdfTexPasteMaterialBase,
    MdfTexProcessBase,
    octahedral_normals_prop,
)
from ...core.color_grade import color_grade_items, DEFAULT_MODE_INDEX

# ── MHWS Constants ─────────────────────────────────────────────────────────────

MHWS_TEX_VERSION    = 241106027
COMMON_SLOT_TYPES   = BASE_COMMON_SLOT_TYPES
NULL_TEX_BY_TYPE    = BASE_NULL_TEX_BY_TYPE
TEXTURE_TYPE_ABBREV = BASE_TEXTURE_TYPE_ABBREV

# ── Null checker + collection update callback ──────────────────────────────────

_is_null_mhws             = make_null_checker(NULL_TEX_BY_TYPE)
_on_mhws_collection_update = make_collection_update_cb(_is_null_mhws)


# ── Settings PropertyGroup ─────────────────────────────────────────────────────



class MdfTexProcessorSettings(bpy.types.PropertyGroup):
    octahedral_normals: octahedral_normals_prop()
    mdf_collection: bpy.props.PointerProperty(
        name="MDF Collection",
        type=bpy.types.Collection,
        description="Target MDF2 collection to process",
        poll=mdf_collection_poll,
        update=_on_mhws_collection_update,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Path under natives/STM/Art/ (e.g. Dimcirui/ShinanoPB)",
        default="",
    )
    materials:             bpy.props.CollectionProperty(type=MdfTexMaterialItem)
    materials_index:       bpy.props.IntProperty()
    clipboard_json:        bpy.props.StringProperty(default="")
    mdf_loaded_collection: bpy.props.StringProperty(default="")
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


# ── Operators ──────────────────────────────────────────────────────────────────

class MHWS_OT_MdfTexRefresh(MdfTexRefreshBase):
    bl_idname      = "mhws.mdf_tex_refresh"
    _settings_attr = "mdf_tex_processor"
    _is_null_fn    = staticmethod(_is_null_mhws)


class MHWS_OT_MdfTexPickPBR(MdfTexPickPBRBase):
    bl_idname      = "mhws.mdf_tex_pick_pbr"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexPickDirect(MdfTexPickDirectBase):
    bl_idname      = "mhws.mdf_tex_pick_direct"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexClearPBR(MdfTexClearPBRBase):
    bl_idname      = "mhws.mdf_tex_clear_pbr"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexClearDirect(MdfTexClearDirectBase):
    bl_idname      = "mhws.mdf_tex_clear_direct"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexCopyMaterial(MdfTexCopyMaterialBase):
    bl_idname      = "mhws.mdf_tex_copy_material"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexPasteMaterial(MdfTexPasteMaterialBase):
    bl_idname      = "mhws.mdf_tex_paste_material"
    _settings_attr = "mdf_tex_processor"


class MHWS_OT_MdfTexProcess(MdfTexProcessBase):
    bl_idname         = "mhws.mdf_tex_process"
    _settings_attr    = "mdf_tex_processor"
    _natives_root_key = "mhws_natives_root"
    _null_tex_by_type = NULL_TEX_BY_TYPE
    _channel_maps     = BASE_SLOT_CHANNEL_MAPS
    _tex_version      = MHWS_TEX_VERSION
    _abbrev_map       = TEXTURE_TYPE_ABBREV
    _use_art_prefix   = True
    _log_tag          = "MDF Tex"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MdfTexProcessorSettings,
    MHWS_OT_MdfTexRefresh,
    MHWS_OT_MdfTexPickPBR,
    MHWS_OT_MdfTexPickDirect,
    MHWS_OT_MdfTexClearPBR,
    MHWS_OT_MdfTexClearDirect,
    MHWS_OT_MdfTexCopyMaterial,
    MHWS_OT_MdfTexPasteMaterial,
    MHWS_OT_MdfTexProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mdf_tex_processor = bpy.props.PointerProperty(
        type=MdfTexProcessorSettings)
    from ...core.mdf_port_tex import register_game_tex_config
    register_game_tex_config(
        "MHWS",
        abbrev_map=TEXTURE_TYPE_ABBREV,
        channel_maps=BASE_SLOT_CHANNEL_MAPS,
        tex_version=MHWS_TEX_VERSION,
        use_art_prefix=True,
        path_fixed_prefix="",
        null_tex_by_type=NULL_TEX_BY_TYPE,
        natives_root_key="mhws_natives_root",
        vanilla_asset_rel="assets/mhws/vanilla_tex_paths.txt",
    )


def unregister():
    from ...core.mdf_port_tex import unregister_game_tex_config
    unregister_game_tex_config("MHWS")
    del bpy.types.Scene.mdf_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
