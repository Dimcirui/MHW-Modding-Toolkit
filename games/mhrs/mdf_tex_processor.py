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

# ── MHRS Constants ─────────────────────────────────────────────────────────────

MHRS_TEX_VERSION = 28
MHRS_COMMON_SLOT_TYPES   = BASE_COMMON_SLOT_TYPES
MHRS_TEXTURE_TYPE_ABBREV = BASE_TEXTURE_TYPE_ABBREV
MHRS_SLOT_CHANNEL_MAPS   = BASE_SLOT_CHANNEL_MAPS

# RE Mesh Editor's tex_bindings_null.json has MHRSB-specific overrides for these two
# (rather than the "generic" fallback baked into BASE_NULL_TEX_BY_TYPE).
MHRS_NULL_TEX_BY_TYPE = {
    **BASE_NULL_TEX_BY_TYPE,
    'AlphaMap': 'MasterMaterial/Textures/NullMSK1.tex',
    'FxMap':    'systems/rendering/NullBlack.tex',
}

# ── Null checker + collection update callback ──────────────────────────────────

_is_null_mhrs              = make_null_checker(MHRS_NULL_TEX_BY_TYPE)
_on_mhrs_collection_update  = make_collection_update_cb(_is_null_mhrs)


# ── Settings PropertyGroup ─────────────────────────────────────────────────────



class MHRSMdfTexProcessorSettings(bpy.types.PropertyGroup):
    octahedral_normals: octahedral_normals_prop()
    mdf_collection: bpy.props.PointerProperty(
        name="MDF Collection",
        type=bpy.types.Collection,
        description="Target MDF2 collection to process",
        poll=mdf_collection_poll,
        update=_on_mhrs_collection_update,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Path under natives/STM/ (e.g. player/mod/f/pl279)",
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

class MHRS_OT_MdfTexRefresh(MdfTexRefreshBase):
    bl_idname      = "mhrs.mdf_tex_refresh"
    _settings_attr = "mhrs_mdf_tex_processor"
    _is_null_fn    = staticmethod(_is_null_mhrs)


class MHRS_OT_MdfTexPickPBR(MdfTexPickPBRBase):
    bl_idname      = "mhrs.mdf_tex_pick_pbr"
    _settings_attr = "mhrs_mdf_tex_processor"


class MHRS_OT_MdfTexPickDirect(MdfTexPickDirectBase):
    bl_idname      = "mhrs.mdf_tex_pick_direct"
    _settings_attr = "mhrs_mdf_tex_processor"


class MHRS_OT_MdfTexClearPBR(MdfTexClearPBRBase):
    bl_idname      = "mhrs.mdf_tex_clear_pbr"
    _settings_attr = "mhrs_mdf_tex_processor"


class MHRS_OT_MdfTexClearDirect(MdfTexClearDirectBase):
    bl_idname      = "mhrs.mdf_tex_clear_direct"
    _settings_attr = "mhrs_mdf_tex_processor"


class MHRS_OT_MdfTexCopyMaterial(MdfTexCopyMaterialBase):
    bl_idname      = "mhrs.mdf_tex_copy_material"
    _settings_attr = "mhrs_mdf_tex_processor"


class MHRS_OT_MdfTexPasteMaterial(MdfTexPasteMaterialBase):
    bl_idname      = "mhrs.mdf_tex_paste_material"
    _settings_attr = "mhrs_mdf_tex_processor"


class MHRS_OT_MdfTexProcess(MdfTexProcessBase):
    bl_idname         = "mhrs.mdf_tex_process"
    _settings_attr    = "mhrs_mdf_tex_processor"
    _natives_root_key = "mhrs_natives_root"
    _null_tex_by_type = MHRS_NULL_TEX_BY_TYPE
    _channel_maps     = MHRS_SLOT_CHANNEL_MAPS
    _tex_version      = MHRS_TEX_VERSION
    _abbrev_map       = MHRS_TEXTURE_TYPE_ABBREV
    _use_art_prefix   = False
    _log_tag          = "MHRS MDF Tex"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MHRSMdfTexProcessorSettings,
    MHRS_OT_MdfTexRefresh,
    MHRS_OT_MdfTexPickPBR,
    MHRS_OT_MdfTexPickDirect,
    MHRS_OT_MdfTexClearPBR,
    MHRS_OT_MdfTexClearDirect,
    MHRS_OT_MdfTexCopyMaterial,
    MHRS_OT_MdfTexPasteMaterial,
    MHRS_OT_MdfTexProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhrs_mdf_tex_processor = bpy.props.PointerProperty(
        type=MHRSMdfTexProcessorSettings)
    # MHRS is not in PORTABLE_GAMES and has no cross-game port, so this registry
    # entry is not about porting -- it is how any tool asks "what is this game's
    # mod root / texture version / shipped asset list" from one place. The
    # pre-export check's texture pass needs exactly that, and without the entry
    # it would have to skip MHRS entirely (every vanilla path would classify as
    # a missing custom one).
    from ...core.mdf_port_tex import register_game_tex_config
    register_game_tex_config(
        "MHRS",
        abbrev_map=MHRS_TEXTURE_TYPE_ABBREV,
        channel_maps=MHRS_SLOT_CHANNEL_MAPS,
        tex_version=MHRS_TEX_VERSION,
        use_art_prefix=False,
        path_fixed_prefix="",
        null_tex_by_type=MHRS_NULL_TEX_BY_TYPE,
        natives_root_key="mhrs_natives_root",
        vanilla_asset_rel="assets/mhrs/vanilla_tex_paths.txt",
    )


def unregister():
    from ...core.mdf_port_tex import unregister_game_tex_config
    unregister_game_tex_config("MHRS")
    del bpy.types.Scene.mhrs_mdf_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
