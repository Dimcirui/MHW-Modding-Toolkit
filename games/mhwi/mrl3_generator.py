import bpy
import os
import json
import tempfile
import shutil
import time

from ...core.i18n import T
from ...core.color_grade import color_grade_items, DEFAULT_MODE_INDEX
from ...core.mdf_generator_base import (
    get_shader_source_items, shader_source_update,
    MdfGenRefreshBase,
    packed_shader_strategies,
    _get_pbr_paths, _slugify, _strip_blender_suffix, _separate_mesh_by_material,
    _emissive_strength_is_zero, _is_emissive_slot, _is_albedo_slot,
    _make_source_id, _try_downgrade_slot, _generate_solid_texture_path,
    _detect_max_tex_size, _find_meshes_by_material,
    load_mhwi_preset_enum_items, bundled_mhwi_preset,
    _import_mhwi_tex_convert, _call_mhwi_read_preset, _import_mhwi_create_collection,
    BAKE_SIZE_DEFAULT,
)
from ...core.mdf_tex_processor_base import (
    _import_tex_utils, _compose_channels, channel_maps_consume_ao, _CH_ENUM_ITEMS,
)
from ...core.slot_sources import (
    find_slot_sources, stage_source_file,
    find_shader_socket_image, find_shader_socket_value,
    find_shader_slot_supplies, shader_pbr_contributions,
)
from ...core.slot_resolver import resolve_dds_format, write_slot_tex
from .mrl3_coef_rules import transparent_coefs
from .mrl3_tex_processor import (
    MHWI_SLOT_CHANNEL_MAPS, MHWI_NULL_TEX,
    MHWI_SRGB_SLOT_TYPES,
    _mhwi_tex_binding, _mhwi_disk_path,
)


def _mhwi_get_presets(self, context):
    return load_mhwi_preset_enum_items()


#: {(path, mtime, size): bool} -- alpha measurement is per file and a batch
#: reuses the same albedo across materials, so measuring once is worth caching.
_ALPHA_WHITE_CACHE = {}

#: Below this the alpha counts as painted rather than as 8-bit rounding noise
#: (254/255 = 0.996).
_ALPHA_WHITE_EPS = 0.99

#: The measurement is a yes/no question, so it is taken on a downscaled copy --
#: a 4K albedo is 67 million floats to read in full, and any transparent region
#: big enough to matter survives the scale.
_ALPHA_PROBE_SIZE = 128


def _albedo_alpha_is_white(path):
    """True if the image's alpha is uniformly white, False if not, None if it
    could not be read.  Never raises: a failed probe must not fail a generate."""
    if not path or not os.path.isfile(path):
        return None
    try:
        st = os.stat(path)
        key = (os.path.normcase(os.path.abspath(path)), st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if key in _ALPHA_WHITE_CACHE:
        return _ALPHA_WHITE_CACHE[key]

    from ...core.mdf_tex_processor_base import image_to_array

    img = None
    try:
        img = bpy.data.images.load(path, check_existing=False)
        if not img.has_data or img.channels < 4:
            result = True
        else:
            w, h = img.size
            if max(w, h) > _ALPHA_PROBE_SIZE:
                scale = _ALPHA_PROBE_SIZE / max(w, h)
                img.scale(max(1, int(w * scale)), max(1, int(h * scale)))
            result = bool(image_to_array(img)[..., 3].min() >= _ALPHA_WHITE_EPS)
    except Exception as e:
        print(f"[MRL3 Gen]   could not read the albedo alpha of "
              f"{os.path.basename(path)}: {e}")
        result = None
    finally:
        if img is not None:
            try:
                bpy.data.images.remove(img)
            except Exception:
                pass

    _ALPHA_WHITE_CACHE[key] = result
    return result


def _mhwi_find_meshes_by_material(mod3_col, material_name):
    """
    在 MOD3 集合中查找所有使用指定材质的 MESH 物体。
    委托给 core 共享的 _find_meshes_by_material。
    """
    return _find_meshes_by_material(mod3_col, material_name)


# ── PropertyGroups ─────────────────────────────────────────────────────────────



class MhwiGenMaterialEntry(bpy.types.PropertyGroup):
    blender_material: bpy.props.StringProperty()
    material_preset:  bpy.props.EnumProperty(
        name="Preset", items=_mhwi_get_presets)
    expanded:         bpy.props.BoolProperty(default=True)
    strategy_display: bpy.props.StringProperty()
    strat_color:      bpy.props.StringProperty(default="?")
    strat_metallic:   bpy.props.StringProperty(default="?")
    strat_roughness:  bpy.props.StringProperty(default="?")
    strat_normal:     bpy.props.StringProperty(default="?")
    strat_alpha:      bpy.props.StringProperty(default="?")
    strat_emissive:   bpy.props.StringProperty(default="?")
    use_toon:         bpy.props.BoolProperty(
        name="Toon Shading",
        description="Skip emissive texture processing; set the emissive slot path to match the albedo slot",
        default=False,
    )
    #: Set by Refresh: this material is driven by a packed shader, so the
    #: toon / AO options do not apply (AO comes from the shader) and a choice of
    #: which panel to read appears instead.
    uses_packed_shader: bpy.props.BoolProperty(default=False)
    shader_source: bpy.props.EnumProperty(
        name="Shader Source",
        items=get_shader_source_items,
        update=shader_source_update,
        default=0,   # dynamic items require an int index default
    )
    generate_mipmaps: bpy.props.BoolProperty(name="Generate MipMaps", default=True)
    skip_textures:    bpy.props.BoolProperty(
        name="Materials Only",
        description="Skip texture composition/conversion; only create the material definition and fill in texture paths",
        default=False,
    )
    use_ao:           bpy.props.BoolProperty(
        name="Add AO",
        description="Manually specify an AO texture (Blender has no built-in AO node)",
        default=False,
    )
    hide_snow_overlay: bpy.props.BoolProperty(
        name="Hide Snow Overlay (fixes black legs in snow)",
        description="Set the AlbedoBlendMap slot to a fully transparent texture (snow_Col_CMM), "
                    "eliminating the black-leg artifact caused by snow blending",
        default=True,
    )
    ao_image:         bpy.props.StringProperty(
        name="AO",
        description="AO texture path",
        subtype='FILE_PATH',
    )
    ao_strength:      bpy.props.FloatProperty(
        name="AO Strength",
        description="How strongly the AO map is multiplied into the albedo. "
                    "MHWI has no AO slot, so this is baked into the texture at "
                    "generation time -- it matches the packed shader's AO Strength",
        default=0.5, min=0.0, max=1.0, subtype='FACTOR',
    )
    ao_ch:            bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    ao_inv:           bpy.props.BoolProperty(name="Invert", default=False)
    native_size_color:     bpy.props.IntProperty(default=0)
    native_size_normal:    bpy.props.IntProperty(default=0)
    native_size_roughness: bpy.props.IntProperty(default=0)
    native_size_metallic:  bpy.props.IntProperty(default=0)
    native_size_alpha:     bpy.props.IntProperty(default=0)
    native_size_emissive:  bpy.props.IntProperty(default=0)
    bake_size_color:       bpy.props.IntProperty(default=0)
    bake_size_normal:      bpy.props.IntProperty(default=0)
    bake_size_roughness:   bpy.props.IntProperty(default=0)
    bake_size_metallic:    bpy.props.IntProperty(default=0)
    bake_size_alpha:       bpy.props.IntProperty(default=0)
    bake_size_emissive:    bpy.props.IntProperty(default=0)


def _mhwi_mod3_col_poll(self, col):
    # MHWI 走的是 MHW Model Editor 的 MOD3 体系，不是 RE Engine 的 .mesh
    return col.get("~TYPE") == "MHW_MOD3_COLLECTION" or col.name.endswith(".mod3")


def _on_mhwi_mesh_collection_update(self, context):
    if self.mesh_collection:
        bpy.ops.mhwi.mrl3_gen_refresh()


class MhwiGenSettings(bpy.types.PropertyGroup):
    # 属性名保留 mesh_collection 以兼容 MdfGenRefreshBase；MHWI 实际填的是 MOD3 集合
    mesh_collection: bpy.props.PointerProperty(
        name="Mod3 Collection",
        type=bpy.types.Collection,
        poll=_mhwi_mod3_col_poll,
        update=_on_mhwi_mesh_collection_update,
    )
    mrl3_collection_name: bpy.props.StringProperty(
        name="MRL3 Collection Name",
        description="Leave blank to auto-infer from the MOD3 collection name",
        default="",
    )
    texture_base_path: bpy.props.StringProperty(
        name="Base Path",
        description="Texture directory under nativePC/, e.g. pl/f_equip/pl042_0500/helm/tex",
        default="",
    )
    material_list:    bpy.props.CollectionProperty(type=MhwiGenMaterialEntry)
    flip_normal_g:    bpy.props.BoolProperty(
        name="Normal Map OpenGL -> DirectX",
        description="When enabled, connected OpenGL normal maps are directly converted to DX format, "
                    "removing the need to manually invert the G channel in the shader",
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
    global_use_toon: bpy.props.BoolProperty(
        name="Use Toon Shading (Global)",
        description="Override every material's own Use Toon Shading checkbox and force it on for all of them",
        default=False,
    )


# ── Refresh operator ───────────────────────────────────────────────────────────

class MHWI_OT_Mrl3GenRefresh(MdfGenRefreshBase):
    bl_idname      = "mhwi.mrl3_gen_refresh"
    _settings_attr = "mhwi_mrl3_generator"
    _game_name     = "MHWI"

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.mrl3_generator.refresh_desc")

    @classmethod
    def _load_preset_items(cls):
        return load_mhwi_preset_enum_items()


# ── Process operator ───────────────────────────────────────────────────────────

class MHWI_OT_Mrl3GenProcess(bpy.types.Operator):
    bl_idname  = "mhwi.mrl3_gen_process"
    bl_label   = "Generate MRL3 + Textures"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.mrl3_generator.process_desc")

    _log_tag  = "MRL3 Gen"
    _bake_size = BAKE_SIZE_DEFAULT

    def execute(self, context):
        _t_total = time.time()
        self._unresolved_channels = []
        settings = context.scene.mhwi_mrl3_generator

        natives_root = context.scene.get("mhwi_natives_root", "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("mhwi.mrl3_generator.set_mod_root_first"))
            return {'CANCELLED'}

        mod3_col = settings.mesh_collection
        if not mod3_col:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.select_mod3_collection_first"))
            return {'CANCELLED'}

        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.fill_base_path"))
            return {'CANCELLED'}

        if not settings.material_list:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.click_refresh_first"))
            return {'CANCELLED'}

        print(f"[{self._log_tag}] {'='*40}", flush=True)

        _t_import = time.time()
        ConvertDDSToTex = _import_mhwi_tex_convert()
        # print(f"[{self._log_tag}] 加载 MHW Model Editor 模块: {time.time() - _t_import:.2f}s", flush=True)
        if ConvertDDSToTex is None:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.cannot_load_tex_convert"))
            return {'CANCELLED'}

        _t_import = time.time()
        ImageListToDDS, _ddstotex = _import_tex_utils()
        # print(f"[{self._log_tag}] 加载 RE Mesh Editor 模块: {time.time() - _t_import:.2f}s", flush=True)
        if ImageListToDDS is None:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.cannot_load_tex_utils"))
            return {'CANCELLED'}

        mrl3_col = self._get_or_create_mrl3_collection(context, mod3_col, settings)

        temp_dir = tempfile.mkdtemp(prefix="mhwi_mrl3_gen_")
        comp_cache = {}  # (slot_type, source_ids, pbr_channels) → (composed, disk, binding)
        export_count = fail_count = 0

        try:
            for mat_entry in settings.material_list:
                try:
                    _t_mat = time.time()
                    self._process_one_material(
                        context, mat_entry, settings, mrl3_col,
                        natives_root, base_path, temp_dir,
                        ImageListToDDS, ConvertDDSToTex, mod3_col,
                        comp_cache,
                    )
                    export_count += 1
                    print(f"[{self._log_tag}] OK: {mat_entry.blender_material} ({time.time() - _t_mat:.2f}s)")
                except Exception as e:
                    import traceback
                    print(f"[{self._log_tag}] FAIL {mat_entry.blender_material}: {e}")
                    traceback.print_exc()
                    fail_count += 1
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        _t_sep = time.time()
        try:
            _separate_mesh_by_material(context, mod3_col)
            print(f"[{self._log_tag}] 分离网格: {time.time() - _t_sep:.2f}s", flush=True)
        except Exception as e:
            print(f"[{self._log_tag}] Mesh separate/rename warning: {e}")

        print(f"[{self._log_tag}] ★ 总耗时: {time.time() - _t_total:.2f}s ★", flush=True)
        if self._unresolved_channels:
            _n = sum(len(c) for _m, c in self._unresolved_channels)
            _detail = "; ".join("%s: %s" % (m, ", ".join(c))
                                for m, c in self._unresolved_channels[:3])
            self.report({'WARNING'}, T("core.mdf_generator_base.unresolved_channels")
                        .format(n=_n, names=_detail))
        if fail_count:
            self.report({'WARNING'}, T("mhwi.mrl3_generator.process_done_with_fail").format(
                success=export_count, fail=fail_count))
        else:
            self.report({'INFO'}, T("mhwi.mrl3_generator.process_done").format(n=export_count))
        return {'FINISHED'}

    def _get_or_create_mrl3_collection(self, context, mod3_col, settings):
        mrl3_name = settings.mrl3_collection_name.strip()
        if not mrl3_name:
            # MHWI 的源集合后缀是 .mod3（MHW Model Editor 体系），不是 .mesh
            mrl3_name = (mod3_col.name.replace('.mod3', '.mrl3')
                         if '.mod3' in mod3_col.name
                         else mod3_col.name + ".mrl3")

        if mrl3_name in bpy.data.collections:
            return bpy.data.collections[mrl3_name]

        parent = next(
            (c for c in bpy.data.collections
             if mod3_col.name in [ch.name for ch in c.children]),
            None,
        )

        createCollection = _import_mhwi_create_collection()
        if createCollection:
            return createCollection(mrl3_name, "COLOR_05", "MHW_MRL3_COLLECTION", parent)

        # Fallback if MHW Model Editor function is unavailable
        col = bpy.data.collections.new(mrl3_name)
        col["~TYPE"] = "MHW_MRL3_COLLECTION"
        col.color_tag = "COLOR_05"
        if parent:
            parent.children.link(col)
        else:
            context.scene.collection.children.link(col)
        return col

    def _process_one_material(self, context, mat_entry, settings, mrl3_col,
                               natives_root, base_path, temp_dir,
                               ImageListToDDS, ConvertDDSToTex, mod3_col,
                               comp_cache):
        mat_name = mat_entry.blender_material
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            raise ValueError(f"Material '{mat_name}' not found")

        preset_path = mat_entry.material_preset
        if not preset_path or preset_path == 'NONE':
            # Nothing to pick from -- MHW Model Editor ships MaterialPresets/
            # empty -- so use the copy this addon bundles rather than refusing.
            preset_path = bundled_mhwi_preset()
            if not preset_path:
                raise ValueError(f"No preset selected for '{mat_name}'")
            print(f"[{self._log_tag}]   '{mat_name}': no preset selected, "
                  f"using the bundled {os.path.basename(preset_path)}")
        if not os.path.isfile(preset_path):
            raise FileNotFoundError(f"Preset not found: {preset_path}")

        # ── 阶段二：查找 MOD3 集合中所有使用该材质的网格 ──
        mesh_objects = _mhwi_find_meshes_by_material(mod3_col, mat_name)
        mesh_obj = mesh_objects[0] if mesh_objects else None
        if mesh_objects:
            print(f"[{self._log_tag}]   '{mat_name}' → {len(mesh_objects)} 个网格: "
                  f"{', '.join(o.name for o in mesh_objects)}")

        _t = time.time()
        strategies = packed_shader_strategies(mat, getattr(mat_entry, 'shader_source', 'PBR'))
        # print(f"[{self._log_tag}]   分析材质节点: {time.time() - _t:.2f}s", flush=True)
        bake_size  = max(_detect_max_tex_size(mat), self._bake_size)
        _t = time.time()
        pbr_paths  = _get_pbr_paths(
            mat, strategies, temp_dir, bake_size, context, mesh_obj,
            mesh_objects=mesh_objects)

        # 解析不出源的通道要报出来 —— 见 core/mdf_generator_base 里同样的一段。
        _no_source = sorted(pt for pt, sv in strategies.items()
                            if sv and sv[0] == 'BAKE' and not pbr_paths.get(pt))
        if _no_source:
            self._unresolved_channels.append((mat_name, _no_source))
            print(f"[{self._log_tag}]   !! no source for {mat_name}: "
                  f"{', '.join(_no_source)} -> these fall back to a null texture")
        # print(f"[{self._log_tag}]   解析PBR路径 (含烘培): {time.time() - _t:.2f}s", flush=True)

        # A shader with AO plugged in is the user already saying "use this AO",
        # so honour it without making them tick the box again. Explicit settings
        # win: only an unset ao_image is filled in.
        shader_ao = find_shader_socket_image(mat, 'AO')
        if shader_ao and not getattr(mat_entry, 'ao_image', ''):
            try:
                mat_entry.use_ao  = True
                mat_entry.ao_image = shader_ao
                strength = find_shader_socket_value(mat, 'AO Strength', 1.0)
                if hasattr(mat_entry, 'ao_strength'):
                    mat_entry.ao_strength = strength
                print(f"[{self._log_tag}]   AO from packed shader: "
                      f"{os.path.basename(shader_ao)} (strength {strength:.2f})")
            except Exception as e:
                print(f"[{self._log_tag}]   could not adopt the shader's AO: {e}")

        # User-provided AO override (Blender has no built-in AO node). Channel
        # and invert are explicit UI choices -- see core.mdf_generator_base's
        # own _process_one_material for the same fix on the other 4 games.
        pbr_inv = {}
        if getattr(mat_entry, 'use_ao', False):
            ao_path_raw = getattr(mat_entry, 'ao_image', '')
            if ao_path_raw:
                ao_path = bpy.path.abspath(ao_path_raw)
                if ao_path and os.path.isfile(ao_path):
                    strategies['ao'] = ('DIRECT', ao_path, getattr(mat_entry, 'ao_ch', 'R'))
                    pbr_paths['ao'] = ao_path
                    pbr_inv['ao'] = getattr(mat_entry, 'ao_inv', False)

        pbr_channels = {}
        for pbr_type, strat_val in strategies.items():
            if strat_val[0] != 'DIRECT':
                continue
            if len(strat_val) > 2 and strat_val[2] != 'R':
                pbr_channels[pbr_type] = strat_val[2]
            # 1-x 那种接法（光泽度当粗糙度用）在这里变成一个取反标志，
            # 合成时由 pbr_inv 执行，不必烘培。
            if len(strat_val) > 3 and strat_val[3]:
                pbr_inv[pbr_type] = True

        tex_name = _slugify(_strip_blender_suffix(mat_name))

        _t = time.time()
        with open(preset_path, encoding='utf-8') as f:
            preset_data = json.load(f)
        # print(f"[{self._log_tag}]   加载Preset JSON: {time.time() - _t:.2f}s", flush=True)
        slot_types = [entry["name"] for entry in preset_data.get("Map List", [])]

        # A slot socket and the PBR inputs it covers can both be filled, and the
        # material's own shader_source is a hard switch between them -- not a
        # tie-break that lets whichever side has data win regardless of the
        # pick (see mdf_generator_base for the same fix on the other 4 games).
        prefer_slots = getattr(mat_entry, 'shader_source', 'PBR') == 'SLOT'
        _supplies = find_shader_slot_supplies(mat)
        _pbr_given = shader_pbr_contributions(mat)
        contested_slots = {
            slot for slot, quantities in _supplies.items()
            if any(q in _pbr_given for q in quantities)
        }
        if contested_slots:
            print(f"[{self._log_tag}]   both panels filled for "
                  f"{', '.join(sorted(contested_slots))} -> using the "
                  f"{'game slots' if prefer_slots else 'PBR inputs'}")

        # {slot: (path, authority)} — see core.slot_sources.
        slot_direct   = find_slot_sources(mat, slot_types)
        prefer_direct = prefer_slots

        # Global toggles on the settings object override every material's own
        # checkbox -- see core.mdf_generator_base's _process_one_material for
        # the same fix on the other 4 games.
        use_toon       = (getattr(mat_entry, 'use_toon', False)
                         or getattr(settings, 'global_use_toon', False))
        effective_mipmaps = (mat_entry.generate_mipmaps
                            and not getattr(settings, 'global_disable_mipmaps', False))
        # 色调处理是全局档，没有逐材质开关 —— 它补的是整套素材的口径差，
        # 一张一张设只会让同一个模型的各部件对不上。
        grade_mode = getattr(settings, 'global_color_grade', 'NONE')
        emi_zero       = _emissive_strength_is_zero(mat)
        emissive_slots = {st for st in slot_types if _is_emissive_slot(st)}
        albedo_slots   = {st for st in slot_types if _is_albedo_slot(st, MHWI_SLOT_CHANNEL_MAPS)}

        # With no AO slot in this game's channel maps, an AO map can only survive
        # by being multiplied into the albedo. Where a slot does store it, that
        # path is used instead -- doing both would darken twice.
        bake_ao = (bool(pbr_paths.get('ao'))
                   and not channel_maps_consume_ao(MHWI_SLOT_CHANNEL_MAPS))

        slot_binding_values = {}
        #: {slot: source file on disk} -- only the albedo is read back (for
        #: the transparency rule below), but recording every slot keeps the
        #: write sites uniform.
        slot_files = {}

        for slot_type in slot_types:
            # Emissive: skip composition if toon mode or strength is zero
            if slot_type in emissive_slots:
                if use_toon:
                    continue  # filled from albedo binding after loop
                if emi_zero:
                    null = MHWI_NULL_TEX.get(slot_type)
                    if null:
                        slot_binding_values[slot_type] = null
                    continue

            # --- direct slot source (BY_SLOT_NAME) ---------------------------
            # See mdf_generator_base for the rationale.  MHWI benefits more
            # than the RE games: only 4 of its 7 slots have a composition
            # recipe, so ColorMaskMap / FxMap / FurVelocityMap were previously
            # unreachable and always wrote a null texture.
            direct_src, direct_auth = slot_direct.get(slot_type, (None, None))
            # See mdf_generator_base: shader_source is a hard switch, so a slot
            # socket only wins unconditionally when there is no PBR recipe to
            # fall back to at all; otherwise it needs the explicit pick.
            if direct_src is not None and (
                    slot_type not in MHWI_SLOT_CHANNEL_MAPS
                    or prefer_direct):
                if getattr(mat_entry, 'skip_textures', False):
                    slot_binding_values[slot_type] = _mhwi_tex_binding(
                        base_path, tex_name, slot_type)
                    continue

                direct_key = (slot_type, 'DIRECT_SLOT', direct_src)
                cached = comp_cache.get(direct_key)
                if cached is not None:
                    slot_binding_values[slot_type] = cached[2]
                    slot_files[slot_type] = cached[0]
                    continue

                disk_path = _mhwi_disk_path(natives_root, base_path, tex_name, slot_type)
                # Staged under a slot-unique stem: the source lives outside
                # temp_dir, and texconv names its output after the input.
                staged = stage_source_file(
                    direct_src, temp_dir, tex_name, slot_type)
                write_slot_tex(
                    staged, disk_path, temp_dir,
                    dds_fmt=resolve_dds_format(
                        slot_type, MHWI_SRGB_SLOT_TYPES),
                    generate_mipmaps=effective_mipmaps,
                    image_to_dds=ImageListToDDS,
                    dds_to_tex=ConvertDDSToTex,
                    grade_mode=grade_mode,
                )

                binding = _mhwi_tex_binding(base_path, tex_name, slot_type)
                slot_binding_values[slot_type] = binding
                slot_files[slot_type] = staged
                comp_cache[direct_key] = (staged, disk_path, binding)
                print(f"[{self._log_tag}]   {slot_type} -> "
                      f"{os.path.basename(disk_path)} (槽位直连/{direct_auth})")
                continue

            if slot_type not in MHWI_SLOT_CHANNEL_MAPS:
                null = MHWI_NULL_TEX.get(slot_type)
                if null:
                    slot_binding_values[slot_type] = null
                continue

            # --- skip_textures: just compute the binding path ---
            if getattr(mat_entry, 'skip_textures', False):
                slot_binding_values[slot_type] = _mhwi_tex_binding(
                    base_path, tex_name, slot_type)
                continue

            # --- cache key construction ---
            ch_map = MHWI_SLOT_CHANNEL_MAPS[slot_type]
            needed_pt = {src[0] for src in ch_map.values()
                         if src is not None and isinstance(src, tuple)}
            key_parts = []
            cache_ok = True
            for pt in sorted(needed_pt):
                sv = strategies.get(pt)
                if sv:
                    sid = _make_source_id(sv)
                    if sid is not None:
                        key_parts.append((pt, sid))
                    else:
                        cache_ok = False
                        break
                else:
                    cache_ok = False
                    break

            cache_key = None
            if cache_ok:
                ch_ov = frozenset((k, v) for k, v in pbr_channels.items() if k in needed_pt)
                cache_key = (slot_type, tuple(key_parts), ch_ov)
                cached = comp_cache.get(cache_key)
                if cached is not None:
                    slot_binding_values[slot_type] = cached[2]
                    slot_files[slot_type] = cached[0]
                    continue

                # Only attempt downgrade for cacheable slots (no BAKE involved)
                rgba = _try_downgrade_slot(slot_type, strategies, pbr_channels, MHWI_SLOT_CHANNEL_MAPS)
                if rgba is not None:
                    hint = f"{tex_name}_{slot_type.lower()}_dg"
                    composed = _generate_solid_texture_path(rgba, temp_dir, hint, size=256)
                    if composed:
                        disk_path = _mhwi_disk_path(natives_root, base_path, tex_name, slot_type)
                        write_slot_tex(
                            composed, disk_path, temp_dir,
                            dds_fmt=resolve_dds_format(
                                slot_type, MHWI_SRGB_SLOT_TYPES),
                            generate_mipmaps=effective_mipmaps,
                            image_to_dds=ImageListToDDS,
                            dds_to_tex=ConvertDDSToTex,
                            grade_mode=grade_mode,
                        )

                        binding = _mhwi_tex_binding(base_path, tex_name, slot_type)
                        slot_binding_values[slot_type] = binding
                        slot_files[slot_type] = composed
                        comp_cache[cache_key] = (composed, disk_path, binding)
                        continue

            # --- full composition path ---
            _t_comp = time.time()
            normal_flip_g = getattr(settings, 'flip_normal_g', False)
            composed = _compose_channels(
                slot_type, pbr_paths, pbr_channels, temp_dir, tex_name,
                pbr_inv=pbr_inv,
                channel_maps=MHWI_SLOT_CHANNEL_MAPS,
                normal_flip_g=normal_flip_g,
                bake_ao_into_color=bake_ao,
                ao_strength=getattr(mat_entry, 'ao_strength', 1.0),
            )
            # print(f"[{self._log_tag}]   合成通道 {slot_type}: {time.time() - _t_comp:.2f}s", flush=True)

            if composed:
                disk_path = _mhwi_disk_path(natives_root, base_path, tex_name, slot_type)
                write_slot_tex(
                    composed, disk_path, temp_dir,
                    dds_fmt=resolve_dds_format(
                        slot_type, MHWI_SRGB_SLOT_TYPES),
                    generate_mipmaps=effective_mipmaps,
                    image_to_dds=ImageListToDDS,
                    dds_to_tex=ConvertDDSToTex,
                    grade_mode=grade_mode,
                )

                binding = _mhwi_tex_binding(base_path, tex_name, slot_type)
                slot_binding_values[slot_type] = binding
                slot_files[slot_type] = composed

                if cache_key is not None:
                    comp_cache[cache_key] = (composed, disk_path, binding)
                print(f"[{self._log_tag}]   {slot_type} -> {os.path.basename(disk_path)}")
            else:
                null = MHWI_NULL_TEX.get(slot_type)
                if null:
                    slot_binding_values[slot_type] = null

        # Toon shading: copy albedo binding value to all emissive slots
        if use_toon and emissive_slots:
            albedo_binding = next(
                (slot_binding_values[st] for st in albedo_slots if st in slot_binding_values),
                None,
            )
            for st in emissive_slots:
                if albedo_binding:
                    slot_binding_values[st] = albedo_binding
                else:
                    null = MHWI_NULL_TEX.get(st)
                    if null:
                        slot_binding_values[st] = null

        # Snow overlay: override AlbedoBlendMap with fully-transparent solid texture
        if getattr(mat_entry, 'hide_snow_overlay', False) and "AlbedoBlendMap" in slot_types:
            _base_norm = base_path.strip('/\\').replace('/', '\\')
            slot_binding_values["AlbedoBlendMap"] = f"{_base_norm}\\snow_Col_CMM"

            if not getattr(mat_entry, 'skip_textures', False):
                snow_disk = os.path.join(
                    natives_root, 'nativePC',
                    base_path.strip('/\\').replace('\\', os.sep).replace('/', os.sep),
                    'snow_Col_CMM.tex',
                )
                os.makedirs(os.path.dirname(snow_disk), exist_ok=True)
                # RGB white + alpha black (fully transparent); must use alpha=True
                # so the PNG is saved as RGBA rather than RGB-only
                _snow_img_name = '__gen_solid_snow_Col_CMM'
                # Not via Image.save(): it rewrites the buffer through an
                # sRGB->linear pass, so the bytes on disk are not the numbers
                # assigned here (see _write_exact_rgba in core/mdf_generator_base).
                # White/0 happen to be the two values that survive it, but there
                # is no reason to keep the one call that only works by accident.
                snow_png = _generate_solid_texture_path(
                    (1.0, 1.0, 1.0, 0.0), temp_dir, 'snow_Col_CMM', size=256)
                snow_dds = os.path.join(
                    temp_dir, os.path.splitext(os.path.basename(snow_png))[0] + '.dds')
                ImageListToDDS([(snow_png, 'BC7_UNORM_SRGB')], temp_dir,
                               effective_mipmaps)
                if os.path.isfile(snow_dds):
                    ConvertDDSToTex([snow_dds], snow_disk)
                    print(f"[{self._log_tag}]   AlbedoBlendMap (snow) -> {os.path.basename(snow_disk)}")

        _t = time.time()
        mat_obj = _call_mhwi_read_preset(preset_path, mrl3_col)
        # print(f"[{self._log_tag}]   创建MRL3材质: {time.time() - _t:.2f}s", flush=True)
        mat_obj.mhw_mrl3_material.materialName = tex_name
        for map_item in mat_obj.mhw_mrl3_material.mapList_items:
            if map_item.name in slot_binding_values:
                map_item.value = slot_binding_values[map_item.name]

        # A preset carries one fixed pair of coefficients, and every preset in
        # circulation is an opaque one -- so an albedo that came out with real
        # transparency needs the transparent pair written over them.  See
        # mrl3_coef_rules for why the rule is this narrow.
        albedo_file = next((slot_files[st] for st in slot_types
                            if st in albedo_slots and st in slot_files), None)
        mmtr = (getattr(mat_obj.mhw_mrl3_material, 'mmtrName', '')
                or preset_data.get("Material Header", {}).get("mmtrName", ""))
        override = transparent_coefs(mmtr, _albedo_alpha_is_white(albedo_file))
        if override:
            surface_coef, alpha_coef = override
            mat_obj.mhw_mrl3_material.surfaceCoef = surface_coef
            mat_obj.mhw_mrl3_material.alphaCoef = alpha_coef
            print(f"[{self._log_tag}]   '{mat_name}': albedo alpha is not white "
                  f"and mmtr is {mmtr} -> surfaceCoef {list(surface_coef)}, "
                  f"alphaCoef {list(alpha_coef)}")


# ── Select Same Material operator ────────────────────────────────────────────────

class MHWI_OT_SelectSameMaterial(bpy.types.Operator):
    bl_idname  = "mhwi.select_same_material"
    bl_label   = "Select Same Material Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.mrl3_generator.select_same_material_desc")

    _log_tag = "MRL3 Gen"

    @classmethod
    def poll(cls, context):
        """必须有激活 MESH 物体，且其材质在 material_list 中有对应条目"""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if not obj.material_slots:
            return False
        settings = context.scene.mhwi_mrl3_generator
        if not settings.mesh_collection:
            return False
        mat = obj.material_slots[obj.active_material_index].material
        return mat is not None

    def execute(self, context):
        settings = context.scene.mhwi_mrl3_generator
        mod3_col = settings.mesh_collection
        if not mod3_col:
            self.report({'ERROR'}, T("mhwi.mrl3_generator.select_mod3_collection_first"))
            return {'CANCELLED'}

        active_obj = context.active_object
        target_mat = active_obj.material_slots[active_obj.active_material_index].material
        if not target_mat:
            self.report({'ERROR'}, T("core.mdf_generator_base.active_obj_no_material"))
            return {'CANCELLED'}

        # 查找同集合下共享相同材质的所有网格
        matched = _mhwi_find_meshes_by_material(mod3_col, target_mat.name)

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

        total_with_self = (len(matched) if active_obj.name in {o.name for o in matched}
                           else len(matched) + 1)
        self.report(
            {'INFO'},
            T("mhwi.mrl3_generator.selected_matching_meshes").format(
                n=len(matched), name=target_mat.name, total=total_with_self),
        )
        return {'FINISHED'}


# ── Registration ───────────────────────────────────────────────────────────────

classes = [
    MhwiGenMaterialEntry,
    MhwiGenSettings,
    MHWI_OT_Mrl3GenRefresh,
    MHWI_OT_Mrl3GenProcess,
    MHWI_OT_SelectSameMaterial,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhwi_mrl3_generator = bpy.props.PointerProperty(
        type=MhwiGenSettings)


def unregister():
    del bpy.types.Scene.mhwi_mrl3_generator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
