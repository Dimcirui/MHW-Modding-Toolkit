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

# ── RE4 Constants ──────────────────────────────────────────────────────────────

RE4_TEX_VERSION = 143221013

RE4_TEXTURE_TYPE_ABBREV = {
    **BASE_TEXTURE_TYPE_ABBREV,
    'OcclusionMap': 'OCC',
}

# RE4 channel maps: same as RE9 -- BASE_SLOT_CHANNEL_MAPS's own
# NormalRoughnessCavityMap entry already applies unmodified (its B genuinely
# carries cavity data, confirmed by the user; an earlier version of this
# override wrongly forced it to a constant). Only RE4's own OcclusionMap
# slot (AO packed into RGB) needs adding.
RE4_SLOT_CHANNEL_MAPS = {
    **BASE_SLOT_CHANNEL_MAPS,
    'OcclusionMap': {
        'R': ('ao', 0),
        'G': ('ao', 0),
        'B': ('ao', 0),
        'A': 1.0,
    },
}

RE4_COMMON_SLOT_TYPES = BASE_COMMON_SLOT_TYPES | {'OcclusionMap'}

RE4_NULL_TEX_BY_TYPE = {
    **BASE_NULL_TEX_BY_TYPE,
    'OcclusionMap': 'systems/rendering/NullWhite.tex',
}

# ── Null checker + collection update callback ──────────────────────────────────

_is_null_re4              = make_null_checker(RE4_NULL_TEX_BY_TYPE)
_on_re4_collection_update = make_collection_update_cb(_is_null_re4)


# ── Settings PropertyGroup ─────────────────────────────────────────────────────



class RE4MdfTexProcessorSettings(bpy.types.PropertyGroup):
    octahedral_normals: octahedral_normals_prop()
    mdf_collection: bpy.props.PointerProperty(
        name="MDF Collection",
        type=bpy.types.Collection,
        description="Target MDF2 collection to process",
        poll=mdf_collection_poll,
        update=_on_re4_collection_update,
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Path under natives/STM/_Chainsaw/Character/ch/ (e.g. Author/Name)",
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

class RE4_OT_MdfTexRefresh(MdfTexRefreshBase):
    bl_idname      = "re4.mdf_tex_refresh"
    _settings_attr = "re4_mdf_tex_processor"
    _is_null_fn    = staticmethod(_is_null_re4)


class RE4_OT_MdfTexPickPBR(MdfTexPickPBRBase):
    bl_idname      = "re4.mdf_tex_pick_pbr"
    _settings_attr = "re4_mdf_tex_processor"


class RE4_OT_MdfTexPickDirect(MdfTexPickDirectBase):
    bl_idname      = "re4.mdf_tex_pick_direct"
    _settings_attr = "re4_mdf_tex_processor"


class RE4_OT_MdfTexClearPBR(MdfTexClearPBRBase):
    bl_idname      = "re4.mdf_tex_clear_pbr"
    _settings_attr = "re4_mdf_tex_processor"


class RE4_OT_MdfTexClearDirect(MdfTexClearDirectBase):
    bl_idname      = "re4.mdf_tex_clear_direct"
    _settings_attr = "re4_mdf_tex_processor"


class RE4_OT_MdfTexCopyMaterial(MdfTexCopyMaterialBase):
    bl_idname      = "re4.mdf_tex_copy_material"
    _settings_attr = "re4_mdf_tex_processor"


class RE4_OT_MdfTexPasteMaterial(MdfTexPasteMaterialBase):
    bl_idname      = "re4.mdf_tex_paste_material"
    _settings_attr = "re4_mdf_tex_processor"


class RE4_OT_MdfTexProcess(MdfTexProcessBase):
    bl_idname         = "re4.mdf_tex_process"
    _settings_attr    = "re4_mdf_tex_processor"
    _natives_root_key = "re4_natives_root"
    _null_tex_by_type = RE4_NULL_TEX_BY_TYPE
    _channel_maps     = RE4_SLOT_CHANNEL_MAPS
    _tex_version      = RE4_TEX_VERSION
    _abbrev_map       = RE4_TEXTURE_TYPE_ABBREV
    _use_art_prefix    = False
    _path_fixed_prefix = "_Chainsaw/Character/ch"
    _log_tag           = "RE4 MDF Tex"


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    RE4MdfTexProcessorSettings,
    RE4_OT_MdfTexRefresh,
    RE4_OT_MdfTexPickPBR,
    RE4_OT_MdfTexPickDirect,
    RE4_OT_MdfTexClearPBR,
    RE4_OT_MdfTexClearDirect,
    RE4_OT_MdfTexCopyMaterial,
    RE4_OT_MdfTexPasteMaterial,
    RE4_OT_MdfTexProcess,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.re4_mdf_tex_processor = bpy.props.PointerProperty(
        type=RE4MdfTexProcessorSettings)
    from ...core.mdf_port_tex import register_game_tex_config
    register_game_tex_config(
        "RE4",
        abbrev_map=RE4_TEXTURE_TYPE_ABBREV,
        channel_maps=RE4_SLOT_CHANNEL_MAPS,
        tex_version=RE4_TEX_VERSION,
        use_art_prefix=False,
        path_fixed_prefix="_Chainsaw/Character/ch",
        null_tex_by_type=RE4_NULL_TEX_BY_TYPE,
        natives_root_key="re4_natives_root",
        vanilla_asset_rel="assets/re4/vanilla_tex_paths.txt",
    )


def unregister():
    from ...core.mdf_port_tex import unregister_game_tex_config
    unregister_game_tex_config("RE4")
    del bpy.types.Scene.re4_mdf_tex_processor
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
