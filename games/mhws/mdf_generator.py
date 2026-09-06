import bpy

from ...core.mdf_tex_processor_base import (
    BASE_SLOT_CHANNEL_MAPS, BASE_NULL_TEX_BY_TYPE, BASE_TEXTURE_TYPE_ABBREV,
    _CH_ENUM_ITEMS,
    octahedral_normals_prop,
)
from ...core.mdf_generator_base import (
    get_shader_source_items, shader_source_update,
    load_preset_enum_items,
    _find_meshes_by_material, mesh_collection_poll,
    MdfGenRefreshBase, MdfGenProcessBase,
)
from ...core.i18n import T
from ...core.color_grade import color_grade_items, DEFAULT_MODE_INDEX

# ── MHWS constants ─────────────────────────────────────────────────────────────

MHWS_TEX_VERSION  = 241106027
MHWS_GEN_GAME     = "MHWILDS"   # must match RE Mesh Editor Presets/ subfolder name


# ── Preset enum callback ───────────────────────────────────────────────────────

def _mhws_get_presets(self, context):
    return load_preset_enum_items(MHWS_GEN_GAME)


# ── PropertyGroups ─────────────────────────────────────────────────────────────



class MhwsGenMaterialEntry(bpy.types.PropertyGroup):
    blender_material: bpy.props.StringProperty(name="Blender Material")
    material_preset:  bpy.props.EnumProperty(
        name="Preset",
        description="MDF2 material preset from RE Mesh Editor",
        items=_mhws_get_presets,
    )
    expanded:         bpy.props.BoolProperty(default=False)
    strategy_display: bpy.props.StringProperty(default="")
    strat_color:      bpy.props.StringProperty(default="?")
    strat_metallic:   bpy.props.StringProperty(default="?")
    strat_roughness:  bpy.props.StringProperty(default="?")
    strat_normal:     bpy.props.StringProperty(default="?")
    strat_alpha:      bpy.props.StringProperty(default="?")
    strat_emissive:   bpy.props.StringProperty(default="?")
    use_toon:         bpy.props.BoolProperty(
        name="Use Toon Shading",
        description="Skip emissive texture processing; set the emissive slot path the same as the base color slot",
        default=False,
    )
    #: Set by Refresh: this material is driven by a packed shader, so the
    #: toon / AO options do not apply (AO comes from the shader) and a choice of
    #: which panel to read appears instead.
    uses_packed_shader: bpy.props.BoolProperty(default=False)
    #: Set by Refresh from the packed shader's own stamped choice (see
    #: core.mdf_generator_base._locked_preset_for_material) when the material
    #: was converted using a bundled prefab -- a path outside material_preset's
    #: own RE Mesh Editor Presets/ scan, so it cannot be an enum item at all.
    #: The UI shows this read-only instead of the dropdown; processing reads
    #: it ahead of material_preset.
    preset_locked: bpy.props.BoolProperty(default=False)
    preset_path_override: bpy.props.StringProperty(default="")
    shader_source: bpy.props.EnumProperty(
        name="Shader Source",
        items=get_shader_source_items,
        update=shader_source_update,
        default=0,   # dynamic items require an int index default
    )
    generate_mipmaps: bpy.props.BoolProperty(name="Generate MipMaps", default=True)
    skip_textures:    bpy.props.BoolProperty(
        name="Material Only",
        description="Skip texture composition/conversion; only create the material definition and fill in "
                    "texture paths",
        default=False,
    )
    use_ao:           bpy.props.BoolProperty(
        name="Add AO",
        description="Manually specify an AO texture (Blender has no built-in AO node)",
        default=False,
    )
    ao_image:         bpy.props.StringProperty(
        name="AO",
        description="AO texture path",
        subtype='FILE_PATH',
    )
    ao_ch:            bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    ao_inv:           bpy.props.BoolProperty(name="Invert", default=False)
    # Native pixel sizes detected at refresh (read-only, set by MdfGenRefreshBase)
    native_size_color:     bpy.props.IntProperty(default=0)
    native_size_normal:    bpy.props.IntProperty(default=0)
    native_size_roughness: bpy.props.IntProperty(default=0)
    native_size_metallic:  bpy.props.IntProperty(default=0)
    native_size_alpha:     bpy.props.IntProperty(default=0)
    native_size_emissive:  bpy.props.IntProperty(default=0)
    # User-set output size overrides (0 = use global bake_size / native)
    bake_size_color:       bpy.props.IntProperty(default=0)
    bake_size_normal:      bpy.props.IntProperty(default=0)
    bake_size_roughness:   bpy.props.IntProperty(default=0)
    bake_size_metallic:    bpy.props.IntProperty(default=0)
    bake_size_alpha:       bpy.props.IntProperty(default=0)
    bake_size_emissive:    bpy.props.IntProperty(default=0)


def _on_mhws_mesh_collection_update(self, context):
    if self.mesh_collection:
        bpy.ops.mhws.mdf_gen_refresh()


class MhwsGenSettings(bpy.types.PropertyGroup):
    octahedral_normals: octahedral_normals_prop()
    mesh_collection: bpy.props.PointerProperty(
        name="Mesh Collection",
        type=bpy.types.Collection,
        description="Source mesh collection containing objects with Blender materials",
        poll=mesh_collection_poll,
        update=_on_mhws_mesh_collection_update,
    )
    mdf_collection_name: bpy.props.StringProperty(
        name="MDF Collection",
        default="",
        description="Target MDF2 collection name (auto-derived from mesh collection if empty)",
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        default="",
        description="Path under natives/STM/Art/ (e.g. Author/CharacterName/)",
    )
    material_list:     bpy.props.CollectionProperty(type=MhwsGenMaterialEntry)
    material_list_idx: bpy.props.IntProperty()
    flip_normal_g:     bpy.props.BoolProperty(
        name="Normal OpenGL -> DirectX",
        description="When enabled, connected OpenGL normal maps are converted directly to DX format, without "
                    "needing to manually flip the G channel in the shader",
        default=False,
    )
    # 色彩类贴图的整体色调处理。默认 NONE：把 sRGB 源图原样搬进 .tex 在色彩学上
    # **是正确的**（实测原版 md_wood000_BML.tex 就是 BC1UNORMSRGB，和我们标的一致），
    # 这个选项补的是源游戏与本作之间的美术口径差，属于调色不是修正，所以必须由人选。
    # 三档的确切定义见 core/color_grade.py。
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
    global_use_toon:   bpy.props.BoolProperty(
        name="Use Toon Shading (Global)",
        description="Override every material's own Use Toon Shading checkbox and force it on for all of them",
        default=False,
    )


# ── Operators ──────────────────────────────────────────────────────────────────

class MHWS_OT_MdfGenRefresh(MdfGenRefreshBase):
    bl_idname      = "mhws.mdf_gen_refresh"
    _settings_attr = "mhws_mdf_generator"
    _game_name     = MHWS_GEN_GAME


class MHWS_OT_MdfGenProcess(MdfGenProcessBase):
    bl_idname         = "mhws.mdf_gen_process"
    _settings_attr    = "mhws_mdf_generator"
    _game_name        = MHWS_GEN_GAME
    _natives_root_key = "mhws_natives_root"
    _tex_version      = MHWS_TEX_VERSION
    _use_art_prefix   = True
    _abbrev_map       = BASE_TEXTURE_TYPE_ABBREV
    _channel_maps     = BASE_SLOT_CHANNEL_MAPS
    _null_tex_by_type = BASE_NULL_TEX_BY_TYPE
    _log_tag          = "MHWS Gen"


# ── Select Same Material operator ────────────────────────────────────────────────

class MHWS_OT_SelectSameMaterial(bpy.types.Operator):
    bl_idname  = "mhws.select_same_material"
    bl_label   = "Select Same Material Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    _log_tag = "MHWS Gen"

    @classmethod
    def description(cls, context, properties):
        return T("mhws.mdf_generator.select_same_material_desc")

    @classmethod
    def poll(cls, context):
        """必须有激活 MESH 物体，且其材质已设置，mesh_collection 已选择"""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if not obj.material_slots:
            return False
        settings = context.scene.mhws_mdf_generator
        if not settings.mesh_collection:
            return False
        mat = obj.material_slots[obj.active_material_index].material
        return mat is not None

    def execute(self, context):
        settings = context.scene.mhws_mdf_generator
        mesh_col = settings.mesh_collection
        if not mesh_col:
            self.report({'ERROR'}, T("mhws.mdf_generator.select_mesh_collection_first"))
            return {'CANCELLED'}

        active_obj = context.active_object
        target_mat = active_obj.material_slots[active_obj.active_material_index].material
        if not target_mat:
            self.report({'ERROR'}, T("core.mdf_generator_base.active_obj_no_material"))
            return {'CANCELLED'}

        # 查找同集合下共享相同材质的所有网格
        matched = _find_meshes_by_material(mesh_col, target_mat.name)

        # 取消所有选中
        for obj in context.view_layer.objects:
            obj.select_set(False)

        # 选中所有匹配的网格
        for obj in matched:
            obj.select_set(True)

        # 保持原物体激活
        if active_obj.name not in {o.name for o in matched}:
            active_obj.select_set(True)
        context.view_layer.objects.active = active_obj

        print(f"[{self._log_tag}] 智能筛选: 材质 '{target_mat.name}' → "
              f"{len(matched)} 个网格: {', '.join(o.name for o in matched)}")

        total = len(matched) if active_obj.name in {o.name for o in matched} else len(matched) + 1
        self.report(
            {'INFO'},
            T("mhws.mdf_generator.selected_meshes_report").format(
                count=len(matched), mat=target_mat.name, total=total),
        )
        return {'FINISHED'}


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MhwsGenMaterialEntry,
    MhwsGenSettings,
    MHWS_OT_MdfGenRefresh,
    MHWS_OT_MdfGenProcess,
    MHWS_OT_SelectSameMaterial,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhws_mdf_generator = bpy.props.PointerProperty(
        type=MhwsGenSettings)


def unregister():
    del bpy.types.Scene.mhws_mdf_generator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
