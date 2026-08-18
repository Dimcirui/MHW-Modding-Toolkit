"""
MDF2 Generator base — creates MDF2 + textures from Blender mesh materials.

Analyzes Principled BSDF node trees with three strategies per PBR input:
  DIRECT  — Image Texture (or Normal Map → Image Texture) directly connected
  SOLID   — Constant value / unlinked socket → generates 256×256 solid texture
  BAKE    — Complex node chain → uses Cycles to bake the result

Parallel to mdf_tex_processor_base but starts from Blender materials instead
of existing MDF2 materials.
"""

import bpy
import os
import json
import re
import tempfile
import shutil
import time

from .i18n import T
from .mdf_tex_processor_base import (
    BASE_SLOT_CHANNEL_MAPS, BASE_NULL_TEX_BY_TYPE, BASE_TEXTURE_TYPE_ABBREV,
    SRGB_SLOT_TYPES, PBR_DEFAULTS, PBR_TYPES, PBR_CHANNEL_SELECTABLE, _CH,
    _import_tex_utils, _compose_channels, channel_maps_consume_ao,
    make_mdf_path, make_disk_path,
)
from .slot_sources import (
    find_slot_sources, stage_source_file,
    find_shader_socket_image, find_shader_socket_value,
    find_shader_slot_supplies, shader_pbr_contributions, shader_slot_contributions,
    find_shader_slot_images, find_packed_shader_node,
)
from .slot_resolver import resolve_dds_format, write_slot_tex
from .shader_pack import PRESET_PATH_KEY, PRESET_LOCKED_KEY

# ── Principled BSDF socket → PBR type mapping ─────────────────────────────────

PRINCIPLED_INPUT_MAP = {
    'color':     'Base Color',
    'metallic':  'Metallic',
    'roughness': 'Roughness',
    'normal':    'Normal',
    'alpha':     'Alpha',
    'emissive':  'Emission Color',
    # 'ao' has no Principled BSDF socket — always defaults to SOLID 1.0
}

BAKE_SIZE_DEFAULT = 1024
SOLID_SIZE        = 8


# ── Node analysis ──────────────────────────────────────────────────────────────

def _find_principled_bsdf(material):
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    return None


def _find_emission_shader(material):
    """Return the first Emission shader node in the material, or None."""
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'EMISSION':
            return node
    return None


_MMD_DEV_NAME_HINTS = ('mmdshaderdev', 'mmd_shader', 'mmd shader')
_MMD_COLOR_SOCKET   = 'Base Tex'
_MMD_ALPHA_SOCKET   = 'Base Alpha'


def _find_mmd_shader_dev(material):
    """Return the MMDShaderDev node group if present, or None."""
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree:
            if any(hint in node.node_tree.name.lower() for hint in _MMD_DEV_NAME_HINTS):
                return node
    return None


SHADER_MTK_PACK   = 'mtk_packed'
SHADER_PRINCIPLED = 'principled'
SHADER_EMISSION   = 'emission'
SHADER_MMD_DEV    = 'mmd_shader_dev'
SHADER_UNKNOWN    = 'unknown'


def _find_connected_shader(material):
    """Return (node, SHADER_*) for the shader wired to Material Output's Surface.

    Traverses through Mix Shader / Add Shader combinators via BFS so indirect
    connections are also resolved.  When no Material Output exists (e.g. a
    material with no output node at all) returns (None, SHADER_UNKNOWN).
    """
    if not material or not material.use_nodes:
        return None, SHADER_UNKNOWN

    nodes = material.node_tree.nodes
    output_node = next(
        (n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output),
        None,
    ) or next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)

    if output_node is None:
        return None, SHADER_UNKNOWN

    surface = output_node.inputs.get('Surface')
    if not surface or not surface.is_linked:
        return None, SHADER_UNKNOWN

    visited = set()
    queue = [surface.links[0].from_node]
    while queue:
        node = queue.pop(0)
        if id(node) in visited:
            continue
        visited.add(id(node))
        if node.type == 'GROUP' and node.node_tree is not None:
            # Tag on the datablock, not the node/group name: a user may rename
            # either.  Imported lazily to keep shader_pack out of this module's
            # import chain.
            from .shader_pack import TAG as _MTK_TAG
            if node.node_tree.get(_MTK_TAG):
                return node, SHADER_MTK_PACK
        if node.type == 'BSDF_PRINCIPLED':
            return node, SHADER_PRINCIPLED
        if node.type == 'EMISSION':
            return node, SHADER_EMISSION
        if node.type == 'GROUP' and node.node_tree:
            if any(h in node.node_tree.name.lower() for h in _MMD_DEV_NAME_HINTS):
                return node, SHADER_MMD_DEV
        # Recurse through shader combinators
        if node.type in ('MIX_SHADER', 'ADD_SHADER'):
            for inp in node.inputs:
                if inp.type == 'SHADER' and inp.is_linked:
                    queue.append(inp.links[0].from_node)

    return None, SHADER_UNKNOWN


def detect_shader_type(material):
    """Return SHADER_* constant for the dominant shader in the material.

    Prefers the shader actually connected to the Material Output so that idle
    nodes (e.g. a disconnected Principled BSDF sitting next to a connected
    MMDShaderDev group) are not mistaken for the active shader.
    Falls back to a tree-scan when no Material Output is present.
    """
    _, shader_type = _find_connected_shader(material)
    if shader_type != SHADER_UNKNOWN:
        return shader_type
    # Fallback: no Material Output node — check for any shader in tree
    if _find_principled_bsdf(material) is not None:
        return SHADER_PRINCIPLED
    if _find_emission_shader(material) is not None:
        return SHADER_EMISSION
    if _find_mmd_shader_dev(material) is not None:
        return SHADER_MMD_DEV
    return SHADER_UNKNOWN


def _collect_tex_images(node, found, visited):
    """Depth-first traversal collecting all TEX_IMAGE nodes upstream of *node*.
    Stops recursing when a TEX_IMAGE is reached (does not enter its own inputs).
    The *visited* set prevents re-visiting nodes in cyclic graphs."""
    if id(node) in visited:
        return
    visited.add(id(node))
    if node.type == 'TEX_IMAGE':
        found.append(node)
        return  # Don't recurse into TEX_IMAGE's own inputs (UV map, etc.)
    for inp in node.inputs:
        if inp.is_linked:
            _collect_tex_images(inp.links[0].from_node, found, visited)


def _find_single_tex_image_upstream(node):
    """Return the filepath if exactly one valid TEX_IMAGE is reachable upstream
    of *node*; return None if zero, two or more images are found.

    Used for normal-map aggressive penetration: any single-source chain
    (add-Z, Y-flip, Sep/Comb nodes, etc.) is treated as DIRECT.
    Multi-source chains (mix of two maps) correctly fall back to BAKE."""
    found = []
    _collect_tex_images(node, found, set())
    if len(found) != 1:
        return None
    img_node = found[0]
    if not img_node.image:
        return None
    path = bpy.path.abspath(img_node.image.filepath)
    return path if (path and os.path.isfile(path)) else None


def _analyze_principled_input(principled_node, input_name, mat_name=None, pbr_type=None):
    """
    Returns ('DIRECT', filepath, source_channel) | ('SOLID', value) | ('BAKE', None).

    DIRECT:  Image Texture directly connected, via a Normal Map node, via a
             Separate Color/RGB node (functional channels), or — for normal maps
             only — via any single-source chain (aggressive penetration).
             Third element is 'R' (Color/RGB output) or 'A' (Alpha output).
    SOLID:   Socket unlinked — use default_value as a constant solid texture.
    BAKE:    Complex node chain — Cycles bake required.

    Normal map special rules
    ────────────────────────
    • NORMAL_MAP node Strength = 0 or 1  → penetrate (treat as DIRECT).
    • NORMAL_MAP node Strength in (0, 1) or linked → BAKE.
    • Any node chain with exactly one upstream TEX_IMAGE → DIRECT.
    • Two or more upstream TEX_IMAGEs (e.g. mix node) → BAKE.
    """
    _tag = f"[MDF Gen]   STRATEGY {mat_name}/{pbr_type}" if mat_name and pbr_type else "[MDF Gen]"

    socket = principled_node.inputs.get(input_name)
    if socket is None:
        # print(f"{_tag}: 输入端 '{input_name}' 不存在 → SOLID(0.0)", flush=True)
        return ('SOLID', 0.0)
    if not socket.is_linked:
        # print(f"{_tag}: '{input_name}' 未连接 → SOLID", flush=True)
        if pbr_type == 'normal':
            # Principled BSDF Normal socket's default_value is (0,0,0) — a meaningless
            # zero vector.  Blender uses the geometry normal at render time when this
            # socket is unlinked, which in tangent space encodes as (0.5, 0.5, 1.0).
            # Return that flat-normal constant so packed textures (NRR, RMT…) are
            # correct.  Matches the fallback already used for the Normal Map node path.
            return ('SOLID', (0.5, 0.5, 1.0, 1.0))
        return ('SOLID', socket.default_value)

    src = socket.links[0].from_node

    if src.type == 'TEX_IMAGE':
        if not src.image:
            # print(f"{_tag}: TEX_IMAGE({src.name}) 无图片数据 → BAKE", flush=True)
            return ('BAKE', None)
        path = bpy.path.abspath(src.image.filepath)
        if not path:
            # print(f"{_tag}: TEX_IMAGE({src.name}) 路径为空 → BAKE", flush=True)
            return ('BAKE', None)
        if not os.path.isfile(path):
            # print(f"{_tag}: TEX_IMAGE({src.name}) 文件不存在 → BAKE (路径: {path})", flush=True)
            return ('BAKE', None)
        from_sock = socket.links[0].from_socket
        src_ch = 'A' if from_sock.name == 'Alpha' else 'R'
        # print(f"{_tag}: TEX_IMAGE({src.name}) 文件有效 → DIRECT(ch={src_ch})", flush=True)
        return ('DIRECT', path, src_ch)

    if src.type == 'NORMAL_MAP':
        nm_color = src.inputs.get('Color')
        if not nm_color or not nm_color.is_linked:
            # print(f"{_tag}: Normal Map({src.name}) Color 未连接 → SOLID (默认法线 0.5,0.5,1.0)", flush=True)
            return ('SOLID', (0.5, 0.5, 1.0, 1.0))
        # Strength = 0 or 1 → treat as DIRECT (viewport-only scaling);
        # 0 < Strength < 1 or linked → bake required to capture the scaling.
        strength_inp = src.inputs.get('Strength')
        if strength_inp and strength_inp.is_linked:
            # print(f"{_tag}: Normal Map({src.name}) Strength 已连接 → BAKE", flush=True)
            return ('BAKE', None)
        sv = float(strength_inp.default_value) if strength_inp else 1.0
        if 0.0 < sv < 1.0:
            # print(f"{_tag}: Normal Map({src.name}) Strength={sv:.3f} ∈ (0,1) → BAKE", flush=True)
            return ('BAKE', None)
        # Penetrate through the Color input chain; succeed only if exactly one
        # source TEX_IMAGE is found (two or more means a mix/blend is in play).
        path = _find_single_tex_image_upstream(nm_color.links[0].from_node)
        if path:
            # print(f"{_tag}: Normal Map({src.name}) → DIRECT (穿透, Strength={sv})", flush=True)
            return ('DIRECT', path, 'R')
        # print(f"{_tag}: Normal Map({src.name}) → BAKE (多源或无效链路)", flush=True)
        return ('BAKE', None)

    if src.type in ('SEPCOLOR', 'SEPRGB'):
        sock_name = socket.links[0].from_socket.name
        ch = {'Red': 'R', 'R': 'R', 'Green': 'G', 'G': 'G', 'Blue': 'B', 'B': 'B'}.get(sock_name)
        if ch is not None:
            sep_in = src.inputs.get('Color') or src.inputs.get('Image')
            if sep_in and sep_in.is_linked:
                tex_src = sep_in.links[0].from_node
                if tex_src.type == 'TEX_IMAGE' and tex_src.image:
                    path = bpy.path.abspath(tex_src.image.filepath)
                    if path and os.path.isfile(path):
                        # print(f"{_tag}: SEPCOLOR({src.name}) ch={ch} → TEX_IMAGE({tex_src.name}) → DIRECT", flush=True)
                        return ('DIRECT', path, ch)
        # print(f"{_tag}: SEPCOLOR({src.name}) → BAKE (Alpha输出或链路不满足)", flush=True)
        return ('BAKE', None)

    # Normal maps: catch-all aggressive penetration for chains that don't go
    # through a NORMAL_MAP node (e.g. Combine Color with white B slot,
    # or any other single-source chain the user built for viewport display).
    if pbr_type == 'normal':
        path = _find_single_tex_image_upstream(src)
        if path:
            # print(f"{_tag}: normal 穿透 ({src.type}({src.name})) → DIRECT", flush=True)
            return ('DIRECT', path, 'R')

    # print(f"{_tag}: '{input_name}' ← 未识别节点类型 '{src.type}'({src.name}) → BAKE", flush=True)
    return ('BAKE', None)


def analyze_material_strategies(material):
    """
    Returns dict {pbr_type: (strategy, value_or_path)} for all PBR types.
    'ao' always returns ('SOLID', 1.0).

    Handles three shader types:
      Principled BSDF — full PBR analysis per socket
      Emission        — color/emissive from Color socket; others SOLID defaults
      MMDShaderDev    — color from Base Tex, alpha from Base Alpha; others SOLID defaults
    Both non-Principled types are treated as toon-style emissive shaders.
    """
    # Resolve the shader that is actually wired to the Material Output so that
    # idle nodes (e.g. a disconnected Principled next to a connected MMDShaderDev)
    # do not shadow the real shader.
    shader_node, shader_type = _find_connected_shader(material)

    # No Material Output present — fall back to any shader found in the tree
    if shader_type == SHADER_UNKNOWN:
        from .slot_sources import find_packed_shader_node
        shader_node = find_packed_shader_node(material)
        if shader_node is not None:
            shader_type = SHADER_MTK_PACK
    if shader_type == SHADER_UNKNOWN:
        shader_node = _find_principled_bsdf(material)
        if shader_node is not None:
            shader_type = SHADER_PRINCIPLED
        else:
            shader_node = _find_emission_shader(material)
            if shader_node is not None:
                shader_type = SHADER_EMISSION
            else:
                shader_node = _find_mmd_shader_dev(material)
                if shader_node is not None:
                    shader_type = SHADER_MMD_DEV

    result = {}

    if shader_type == SHADER_MTK_PACK and shader_node is not None:
        # The packed shader declares which socket carries which quantity, so the
        # same per-socket analysis applies: a texture is DIRECT, a typed value is
        # SOLID, anything else needs a bake.  Without this the group's PBR panel
        # was invisible to the generator and every channel fell back to a neutral
        # default -- an albedo typed into the panel exported as black.
        from .slot_sources import find_shader_pbr_map
        _node, pbr_map = find_shader_pbr_map(material)
        for pbr_type, socket_name in pbr_map.items():
            result[pbr_type] = _analyze_principled_input(
                shader_node, socket_name, material.name, pbr_type)
        # Any quantity the spec does not expose (MHWI has no AO slot socket for
        # 'ao' to write back to, for instance) keeps its neutral value.
        for pbr_type in PBR_TYPES:
            if pbr_type not in result:
                neutral = PBR_DEFAULTS.get(pbr_type, [1.0])
                result[pbr_type] = ('SOLID', tuple(neutral)
                                    if pbr_type in ('color', 'emissive', 'normal')
                                    else neutral[0])
        return result

    if shader_type == SHADER_PRINCIPLED and shader_node is not None:
        for pbr_type, input_name in PRINCIPLED_INPUT_MAP.items():
            result[pbr_type] = _analyze_principled_input(shader_node, input_name, material.name, pbr_type)
        result['ao'] = ('SOLID', 1.0)
        return result

    # Non-Principled defaults (neutral values for unused channels)
    _NON_PBR_DEFAULTS = {
        'metallic':  0.0,
        'roughness': 1.0,
        'normal':    (0.5, 0.5, 1.0, 1.0),
        'alpha':     1.0,
        'emissive':  (0.0, 0.0, 0.0, 1.0),
        'color':     (0.0, 0.0, 0.0, 1.0),
    }
    for pbr_type in PRINCIPLED_INPUT_MAP:
        result[pbr_type] = ('SOLID', _NON_PBR_DEFAULTS.get(pbr_type, 0.0))

    if shader_type == SHADER_EMISSION and shader_node is not None:
        color_strat        = _analyze_principled_input(shader_node, 'Color', material.name, 'emissive')
        result['color']    = color_strat
        result['emissive'] = color_strat
    elif shader_type == SHADER_MMD_DEV and shader_node is not None:
        result['color']    = _analyze_principled_input(shader_node, _MMD_COLOR_SOCKET, material.name, 'color')
        result['alpha']    = _analyze_principled_input(shader_node, _MMD_ALPHA_SOCKET, material.name, 'alpha')
        result['emissive'] = result['color']

    result['ao'] = ('SOLID', 1.0)
    return result


def strategy_label(strategy):
    return {'DIRECT': 'Direct', 'SOLID': 'Solid', 'BAKE': 'Bake'}.get(strategy, '?')


def _slot_side_strategies(material):
    """Per-PBR-type strategy read from the packed shader's game-slot group,
    the SLOT counterpart to analyze_material_strategies()'s PBR-panel reading.

    shader_source is a hard switch: whichever side the user picks is what gets
    analysed and exported, full stop -- no falling back to the other side just
    because it happens to have data and this one doesn't.
    """
    supplies = find_shader_slot_supplies(material)
    slot_images = find_shader_slot_images(material, list(supplies.keys())) if supplies else {}
    result = {}
    for slot_type, pbr_types in supplies.items():
        path = slot_images.get(slot_type)
        for pt in pbr_types:
            if path:
                result[pt] = ('DIRECT', path, 'R')
            elif pt not in result:
                result[pt] = ('SOLID', PBR_DEFAULTS.get(pt, [1.0])[0] if pt not in ('color', 'emissive', 'normal')
                              else tuple(PBR_DEFAULTS.get(pt, [1.0])))
    for pt in PBR_TYPES:
        if pt not in result:
            neutral = PBR_DEFAULTS.get(pt, [1.0])
            result[pt] = ('SOLID', tuple(neutral) if pt in ('color', 'emissive', 'normal') else neutral[0])
    return result


def packed_shader_strategies(material, shader_source):
    """PBR-panel or game-slot analysis, whichever `shader_source` names."""
    return _slot_side_strategies(material) if shader_source == 'SLOT' else analyze_material_strategies(material)


def guess_shader_source_default(material):
    """Which side to preselect for a freshly refreshed packed-shader material.

    A strict waterfall, most deliberate connection first: a game-slot image
    beats a PBR image (a slot socket is a more deliberate, single-purpose
    connection than a Principled-style input), which beats a hand-typed
    non-default PBR value, which beats a hand-typed non-default slot value,
    which beats bare defaults everywhere -- a tie with nothing touched at all
    keeps the historical PBR default since nothing is lost either way.
    """
    supplies = find_shader_slot_supplies(material)
    slot_names = list(supplies.keys())
    slot_images = find_shader_slot_images(material, slot_names) if slot_names else {}
    if slot_images:
        return 'SLOT'

    pbr_given = shader_pbr_contributions(material)
    if any(v == 'IMAGE' for v in pbr_given.values()):
        return 'PBR'
    if any(v == 'VALUE' for v in pbr_given.values()):
        return 'PBR'

    slot_values = shader_slot_contributions(material, slot_names) if slot_names else {}
    if slot_values:
        return 'SLOT'

    return 'PBR'


def shader_source_update(self, context):
    """Recompute the strategy-analysis display when the PBR/Slot toggle flips.

    Refresh only snapshots strat_* once, so without this the grid stayed
    stuck on whatever it showed at refresh time no matter what the user
    picked afterward.
    """
    mat = bpy.data.materials.get(self.blender_material)
    if not mat:
        return
    strategies = packed_shader_strategies(mat, self.shader_source)
    parts = []
    for pt in ('color', 'normal', 'roughness', 'metallic', 'alpha', 'emissive'):
        sv = strategies.get(pt, ('?', None))
        parts.append(f"{pt[0].upper()}:{strategy_label(sv[0])}")
    self.strategy_display = '  '.join(parts)
    for pt in ('color', 'metallic', 'roughness', 'normal', 'alpha', 'emissive'):
        sv = strategies.get(pt, ('?', None))
        setattr(self, f"strat_{pt}", strategy_label(sv[0]))


def _emissive_strength_is_zero(material):
    """True if the active shader has no meaningful emission strength.

    For Principled BSDF: checks the Emission Strength socket.
    For Emission / MMDShaderDev shaders: always False (they are inherently emissive).
    """
    shader_type = detect_shader_type(material)
    if shader_type in (SHADER_EMISSION, SHADER_MMD_DEV):
        return False
    principled = _find_principled_bsdf(material)
    if principled is None:
        return True
    sock = principled.inputs.get('Emission Strength')
    if sock is None:
        return True
    return not sock.is_linked and float(sock.default_value) == 0.0


def _is_emissive_slot(slot_type):
    return 'missive' in slot_type.lower()


def _is_albedo_slot(slot_type, channel_maps):
    """True if any channel of this slot maps from the 'color' PBR type."""
    return any(
        isinstance(v, tuple) and v[0] == 'color'
        for v in channel_maps.get(slot_type, {}).values()
    )


#: ``{path: (mtime_ns, value)}`` -- keyed by content age, not just by path.
#:
#: A preset is a file the *user* edits, in RE Mesh Editor's own Presets folder, and
#: they edit it precisely when they are unhappy with what it produces.  A cache that
#: only keys on the path answers from the version they were unhappy with for the rest
#: of the session, with nothing on screen saying so.
_PRESET_EMISSIVE_CACHE: dict = {}
_PRESET_SNOW_MAP_CACHE: dict = {}


def _file_stamp(path):
    """``(mtime_ns, size)`` for a preset file, or None when it cannot be stat'd.

    Size is in there because **mtime alone does not detect an in-place rewrite**:
    measured on this project's own filesystem, 169 of 199 consecutive rewrites left
    ``st_mtime_ns`` unchanged, the timestamp being bucketed at roughly a millisecond
    and updated lazily.  Two saves seconds apart -- what a user actually does -- move
    it; two in the same millisecond do not.

    So this is a heuristic, deliberately, and it is only used where a miss is
    cosmetic: these answers decide whether the generator panel draws one extra row.
    The preset *contents* that reach an export are read fresh at execute time, never
    from here.  Re-reading a 40 KB JSON on every redraw to close the remaining gap
    would cost more than the gap is worth.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _cached_by_stamp(cache, path, compute):
    """*compute(path)*, remembered until the file's ``_file_stamp`` changes."""
    stamp = _file_stamp(path)
    hit = cache.get(path)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    value = compute(path)
    cache[path] = (stamp, value)
    return value


def preset_has_emissive_slots(preset_path, is_mrl3=False):
    """True if the preset JSON includes any emissive texture slot."""
    if not preset_path or preset_path == 'NONE' or not os.path.isfile(preset_path):
        return False
    return _cached_by_stamp(
        _PRESET_EMISSIVE_CACHE, preset_path,
        lambda p: _read_emissive_slots(p, is_mrl3))


def _read_emissive_slots(preset_path, is_mrl3=False):
    try:
        with open(preset_path, encoding='utf-8') as f:
            data = json.load(f)
        if is_mrl3:
            result = any(_is_emissive_slot(e.get('name', ''))
                         for e in data.get('Map List', []))
        else:
            result = any(_is_emissive_slot(b.get('Texture Type', ''))
                         for b in data.get('Texture Bindings', []))
    except Exception:
        result = False
    return result


def preset_has_albedo_blend_map(preset_path):
    """True if the preset JSON includes an AlbedoBlendMap slot (MRL3 only)."""
    if not preset_path or preset_path == 'NONE' or not os.path.isfile(preset_path):
        return False
    return _cached_by_stamp(_PRESET_SNOW_MAP_CACHE, preset_path,
                            _read_albedo_blend_map)


def _read_albedo_blend_map(preset_path):
    try:
        with open(preset_path, encoding='utf-8') as f:
            data = json.load(f)
        result = any(e.get('name', '') == 'AlbedoBlendMap'
                     for e in data.get('Map List', []))
    except Exception:
        result = False
    return result


# ── Preset loading ─────────────────────────────────────────────────────────────

_addon_dir_cache   = None
_addon_dir_cached  = False
_preset_dir_cache  = {}
_preset_items_cache = {}


def _get_re_mesh_editor_addon_dir():
    """Locate RE Mesh Editor add-on directory. Result is cached for the session.

    Detection is driven by a signature file unique to RE Mesh Editor
    (``modules/mdf/re_mdf_presets.py``) rather than the bl_info name or the
    package name.  The root folder name and bl_info name vary between releases
    and community forks (e.g. "RE-Mesh-Editor-main", "REME"), but the internal
    module layout — and therefore this file — is stable across them.  An enabled
    add-on is preferred over a merely-installed one.  The bl_info/package name
    heuristic is kept only as a last-resort fallback.
    """
    global _addon_dir_cache, _addon_dir_cached
    if _addon_dir_cached:
        return _addon_dir_cache
    import addon_utils

    sig_rel = os.path.join('modules', 'mdf', 're_mdf_presets.py')
    sig_match = None        # enabled add-on with signature file (best)
    sig_fallback = None     # installed-but-disabled add-on with signature file
    name_fallback = None    # name/package heuristic only (weakest)

    for mod in addon_utils.modules():
        mod_file = getattr(mod, '__file__', None)
        if not mod_file:
            continue
        addon_dir = os.path.dirname(mod_file)

        if os.path.isfile(os.path.join(addon_dir, sig_rel)):
            try:
                is_enabled = addon_utils.check(mod.__name__)[1]
            except Exception:
                is_enabled = False
            if is_enabled:
                sig_match = addon_dir
                break
            if sig_fallback is None:
                sig_fallback = addon_dir
            continue

        if name_fallback is None:
            pkg  = getattr(mod, '__package__', '') or getattr(mod, '__name__', '')
            try:
                name = mod.bl_info.get('name', '')
            except Exception:
                name = ''
            if ('RE Mesh' in name or 'REMeshEditor' in pkg
                    or 're_mesh_editor' in pkg.lower() or 'reme' in pkg.lower()):
                name_fallback = addon_dir

    _addon_dir_cache  = sig_match or sig_fallback or name_fallback
    _addon_dir_cached = True   # cache the miss too
    return _addon_dir_cache


_shader_source_items_cache = []


def get_shader_source_items(self, context):
    """Which of the packed shader's two panels this material exports from.

    Defined here rather than per game so the five generators share one set of
    labels.  A callback, not a literal list, because the labels go through T()
    and must follow a language switch.
    """
    global _shader_source_items_cache
    _shader_source_items_cache = [
        ('PBR',  T("core.mdf_generator_base.shader_source_pbr"),
                 T("core.mdf_generator_base.shader_source_pbr_desc"), 0),
        ('SLOT', T("core.mdf_generator_base.shader_source_slot"),
                 T("core.mdf_generator_base.shader_source_slot_desc"), 1),
    ]
    return _shader_source_items_cache


def mesh_collection_poll(self, col):
    """Restrict the Generator's Mesh Collection picker to RE Mesh collections
    (same filter used by batch export's collection pickers), so the ID
    browse dropdown doesn't get cluttered with MDF2/Chain/unrelated collections."""
    return col.get("~TYPE") == "RE_MESH_COLLECTION" or col.name.endswith(".mesh")


def get_preset_dir_for_game(game_name):
    """Return path to RE Mesh Editor's Presets/{game_name}/ directory, or None."""
    if game_name in _preset_dir_cache:
        return _preset_dir_cache[game_name]
    addon_dir = _get_re_mesh_editor_addon_dir()
    if not addon_dir:
        _preset_dir_cache[game_name] = None
        return None
    d = os.path.join(addon_dir, 'Presets', game_name)
    result = d if os.path.isdir(d) else None
    _preset_dir_cache[game_name] = result
    return result


def load_preset_enum_items(game_name):
    """EnumProperty items for one game's presets, rescanned when the folder changes.

    **The folder is rescanned on every call**, and the cached list is returned only
    when the scan finds the same names.  These are RE Mesh Editor's presets, i.e. the
    user's own folder, and they add to it mid-session -- ``invalidate_preset_cache``
    existed from the start for exactly that and **was never called from anywhere**,
    so the first scan of a session was in practice the only one and a preset saved
    afterwards stayed invisible until Blender restarted.

    Rescanning rather than trusting the directory's mtime, which is not a reliable
    signal for this: measured here, a second create and a delete both left it
    unchanged, being bucketed at roughly a millisecond and updated lazily.  It is not
    even a cheap signal -- ``stat`` on the folder costs 57 us against 87 us for the
    whole ``scandir``, so keying on it would buy 30 us and a class of misses.

    The cache is still worth having, for identity rather than for speed: Blender's C
    side keeps the pointers a dynamic ``items=`` callback returns, so an unchanged
    folder has to hand back the *same list object* rather than an equal one.
    """
    preset_dir = get_preset_dir_for_game(game_name)
    if not preset_dir:
        items = [('NONE', 'RE Mesh Editor presets not found', '')]
        _preset_items_cache[game_name] = (None, items)
        return items

    try:
        names = sorted(e.name for e in os.scandir(preset_dir)
                       if e.is_file() and e.name.endswith('.json'))
    except OSError:
        names = []

    hit = _preset_items_cache.get(game_name)
    if hit is not None and hit[0] == names:
        return hit[1]

    items = [(os.path.join(preset_dir, n), n[:-5], os.path.join(preset_dir, n))
             for n in names]
    if not items:
        items = [('NONE', f'No presets found for {game_name}', '')]
    _preset_items_cache[game_name] = (names, items)
    return items


def invalidate_preset_cache():
    """Clear all preset caches so the next draw() triggers a fresh filesystem scan."""
    global _addon_dir_cache, _addon_dir_cached
    _addon_dir_cache  = None
    _addon_dir_cached = False
    _preset_dir_cache.clear()
    _preset_items_cache.clear()
    _PRESET_EMISSIVE_CACHE.clear()
    _PRESET_SNOW_MAP_CACHE.clear()


#: Slot types with no PBR composition recipe *and* no vanilla null texture at
#: all (see core.mdf_tex_processor_base.BASE_SLOT_CHANNEL_MAPS /
#: BASE_NULL_TEX_BY_TYPE -- SkinMap/BlendNormalMap only, so far). Left
#: unoverridden by the user, _resolve_placeholder_slot below writes the
#: bundled placeholder DDS through the same per-material make_disk_path/
#: make_mdf_path convention every other slot uses -- *not* the preset's own
#: embedded literal Texture Path (MK_MODS/Eku/Public/...), which belongs to
#: whichever mod that preset was originally authored for, not this export.
PLACEHOLDER_SLOT_TYPES = {'SkinMap', 'BlendNormalMap'}


def _prefab_placeholder_dds(slot_type):
    """Bundled placeholder DDS for a slot type in PLACEHOLDER_SLOT_TYPES, or
    None if there is none (any other slot type, or the asset is missing)."""
    if slot_type not in PLACEHOLDER_SLOT_TYPES:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "assets", "mdf_presets", "mhws", f"{slot_type}.dds")
    return path if os.path.isfile(path) else None


def _resolve_placeholder_slot(slot_type, tex_name, natives_root, base_path, temp_dir,
                              abbrev_map, tex_version, use_art_prefix,
                              image_to_dds, dds_to_tex, comp_cache):
    """Write the bundled placeholder DDS for a PLACEHOLDER_SLOT_TYPES slot
    nothing overrode, and return the resulting mdf path -- same
    make_disk_path/make_mdf_path convention every other slot in this export
    uses, so the binding ends up pointing at this mod's own natives/STM/
    tree instead of the preset's borrowed literal path.

    Cached by (slot_type, source) exactly like the direct-slot-source branch
    above: every material in this batch that leaves this slot at its default
    points at the one shared physical file instead of each carrying its own
    copy of the same placeholder image.
    """
    src = _prefab_placeholder_dds(slot_type)
    if src is None:
        return None

    cache_key = (slot_type, 'MHWS_PLACEHOLDER', src)
    cached = comp_cache.get(cache_key)
    if cached is not None:
        return cached[2]

    disk_path = make_disk_path(
        natives_root, base_path, tex_name, slot_type,
        abbrev_map, tex_version, use_art_prefix,
    )
    write_slot_tex(
        src, disk_path, temp_dir,
        dds_fmt=None, generate_mipmaps=True,
        image_to_dds=image_to_dds,
        dds_to_tex=lambda p, o: dds_to_tex(p, tex_version, o),
    )
    mdf_path = make_mdf_path(base_path, tex_name, slot_type, abbrev_map, use_art_prefix)
    comp_cache[cache_key] = (src, disk_path, mdf_path)
    return mdf_path


def _locked_preset_for_material(material):
    """(preset_path, locked) stamped on ``material``'s packed-shader node by
    MTK_OT_ConvertToPackedShader (core/shader_ops.py), or (None, False) when
    the material was never converted through that dialog -- hand-authored,
    converted via MHWI's plain (dialog-less) path, or added via
    Add > MOD Toolkit rather than Convert.

    ``locked`` True means the path is a bundled prefab outside RE Mesh
    Editor's own Presets/ directory, so it cannot be represented by
    material_preset's own EnumProperty items at all -- the generator has to
    carry it separately (see MhwsGenMaterialEntry.preset_path_override) and
    show it read-only rather than as a re-pickable dropdown. False means an
    external preset the user picked in that same dialog: it *is* one of
    material_preset's own valid items, so it can just be assigned there
    directly and stay a normal, editable dropdown.
    """
    node = find_packed_shader_node(material)
    if node is None:
        return None, False
    return node.get(PRESET_PATH_KEY), bool(node.get(PRESET_LOCKED_KEY, False))


def guess_best_preset(material_name, preset_items):
    """Keyword-scoring heuristic — returns the best matching preset path."""
    if not preset_items or preset_items[0][0] == 'NONE':
        return 'NONE'

    mat_lower = material_name.lower()
    SCORES = {
        3: ['body', 'skin', 'eye', 'hair', 'face', 'decal', 'emissive', 'cloth'],
        2: ['_emi', 'emit', 'weapon', 'armor'],
        1: ['wp', 'ch', 'pl', 'em', 'sm', 'st', 'gm'],
    }

    best_score, best_len, best_path = -1, 9999, preset_items[0][0]
    for preset_path, preset_name, _ in preset_items:
        if preset_path == 'NONE':
            continue
        score = 0
        pl = preset_name.lower()
        for pts, kws in SCORES.items():
            for kw in kws:
                if kw in mat_lower and kw in pl:
                    score += pts
        if score > best_score or (score == best_score and len(preset_name) < best_len):
            best_score, best_len, best_path = score, len(preset_name), preset_path

    return best_path


# ── Solid texture generation ───────────────────────────────────────────────────

def _generate_solid_texture_path(value, tmp_dir, name_hint, size=SOLID_SIZE):
    """
    Write a solid-colour PNG to tmp_dir and return its path.
    value: float scalar (greyscale) or colour sequence (r,g,b[,a]).
    """
    img_name = f"__gen_solid_{name_hint}"
    if img_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[img_name])

    img = bpy.data.images.new(img_name, width=size, height=size, alpha=True)

    if isinstance(value, (int, float)):
        v = float(max(0.0, min(1.0, value)))
        pixel = [v, v, v, 1.0]
    else:
        vals = [float(max(0.0, min(1.0, c))) for c in list(value)[:4]]
        while len(vals) < 4:
            vals.append(1.0)
        pixel = vals

    img.pixels[:] = pixel * (size * size)
    out_path = os.path.join(tmp_dir, f"_solid_{name_hint}.png")
    img.filepath_raw = out_path
    img.file_format  = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return out_path


# ── Composition cache helpers ───────────────────────────────────────────────────

def _make_source_id(strat_val):
    """Return a hashable identifier for a PBR source, or None if uncacheable (BAKE).

    DIRECT → ('DIRECT', normalised_path)
    SOLID  → ('SOLID', (r, g, b, a))
    BAKE   → None
    """
    if not strat_val:
        return None
    strategy = strat_val[0]
    value    = strat_val[1]
    if strategy == 'DIRECT':
        return ('DIRECT', os.path.normpath(value))
    if strategy == 'SOLID':
        if isinstance(value, (int, float)):
            v = round(float(value), 6)
            return ('SOLID', (v, v, v, 1.0))
        else:
            vals = [round(float(max(0.0, min(1.0, c))), 6) for c in list(value)[:4]]
            while len(vals) < 4:
                vals.append(1.0)
            return ('SOLID', tuple(vals))
    return None


def _resolve_solid_rgba(strat_val):
    """Return the 4-channel pixel value from a SOLID strategy, or None."""
    if not strat_val or strat_val[0] != 'SOLID':
        return None
    value = strat_val[1]
    if isinstance(value, (int, float)):
        v = float(max(0.0, min(1.0, value)))
        return (v, v, v, 1.0)
    else:
        vals = [float(max(0.0, min(1.0, c))) for c in list(value)[:4]]
        while len(vals) < 4:
            vals.append(1.0)
        return tuple(vals)


def _try_downgrade_slot(slot_type, strategies, pbr_channels, channel_maps):
    """If every PBR source used by *slot_type* is a constant, return the
    resulting RGBA pixel value as a 4-tuple; otherwise return None."""
    ch_map = channel_maps.get(slot_type)
    if ch_map is None:
        return None

    rgba = [0.0, 0.0, 0.0, 0.0]
    for out_ch_name, src in ch_map.items():
        out_i = _CH.get(out_ch_name)
        if out_i is None:
            return None

        if src is None:
            # Alpha channel (index 3) defaults to opaque to avoid premultiplied-alpha
            # issues when texconv converts the PNG to DDS (A=0 would zero all channels).
            rgba[out_i] = 1.0 if out_i == 3 else 0.0
        elif isinstance(src, (int, float)):
            rgba[out_i] = float(src)
        elif isinstance(src, tuple):
            pbr_type = src[0]
            in_ch_i  = src[1]
            invert   = len(src) > 2 and src[2] is True

            strat_val = strategies.get(pbr_type)
            if strat_val is None or strat_val[0] != 'SOLID':
                return None

            solid_rgba = _resolve_solid_rgba(strat_val)
            if solid_rgba is None:
                return None

            if pbr_type in PBR_CHANNEL_SELECTABLE:
                override = pbr_channels.get(pbr_type)
                if override:
                    in_ch_i = _CH.get(override, in_ch_i)

            val = solid_rgba[in_ch_i]
            if invert:
                val = 1.0 - val
            rgba[out_i] = val
        else:
            return None

    return tuple(rgba)


# Pre-built "all PBR-default" strategy dict, used to test whether a downgraded
# slot RGBA is indistinguishable from the game's null texture.
_DEFAULT_STRATEGIES = {pt: ('SOLID', tuple(vals)) for pt, vals in PBR_DEFAULTS.items()}


# ── Cycles baking ──────────────────────────────────────────────────────────────

def _bake_pbr_channel(material, pbr_type, mesh_obj, size, tmp_dir, context,
                      mesh_objects=None):
    """
    Bake one PBR channel from a Blender material via Cycles.
    Returns path to the saved PNG, or None on failure.

    Special handling:
      metallic    — temporarily routes Metallic link → Roughness, bakes as ROUGHNESS
      alpha       — temporarily routes Alpha link → Emission Color, bakes as EMIT
      emission/MMDShaderDev color/emissive — bakes as EMIT directly (no Principled needed)

    mesh_objects — optional list of mesh objects that share the same material;
                   all are selected during baking so Cycles covers every UV layout.
                   Falls back to mesh_obj when omitted / empty.
    """
    tree = material.node_tree
    shader_type = detect_shader_type(material)
    principled = _find_principled_bsdf(material) if shader_type == SHADER_PRINCIPLED else None

    if principled is None:
        # Emission / MMDShaderDev: can bake color/emissive channels as EMIT pass
        if pbr_type not in ('color', 'emissive'):
            return None
        if shader_type not in (SHADER_EMISSION, SHADER_MMD_DEV):
            return None

    img_name = f"__gen_bake_{pbr_type}"
    if img_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[img_name])
    bake_img = bpy.data.images.new(img_name, width=size, height=size,
                                   alpha=False, float_buffer=True)

    orig_active_node = tree.nodes.active
    bake_node = tree.nodes.new('ShaderNodeTexImage')
    bake_node.image = bake_img
    tree.nodes.active = bake_node

    tmp_remove  = []   # new links to remove afterward
    tmp_restore = []   # (kind, ...) tuples describing what to undo

    orig_engine = context.scene.render.engine
    # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 原始引擎={orig_engine}", flush=True)

    # ── Save Cycles GPU / device state ──────────────────────────────────────
    cycles_scene = context.scene.cycles
    orig_device  = cycles_scene.device
    orig_samples = cycles_scene.samples
    orig_compute_device_type = None
    orig_dev_use = {}
    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
        orig_compute_device_type = cprefs.compute_device_type
        for d in cprefs.devices:
            orig_dev_use[d.name] = d.use
#         print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 原始GPU后端={orig_compute_device_type}, "
#               f"活跃设备={[d.name for d in cprefs.devices if d.use]}", flush=True)
    except Exception:
        pass

    try:
        context.scene.render.engine = 'CYCLES'
        # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 切换后引擎={context.scene.render.engine}", flush=True)

        # ── Force GPU compute ───────────────────────────────────────────────
        try:
            cycles_scene.device = 'GPU'
            cycles_scene.samples = 1
            cprefs = bpy.context.preferences.addons['cycles'].preferences
            # Pick the first available GPU backend
            for dt in ('OPTIX', 'CUDA', 'HIP', 'METAL'):
                try:
                    cprefs.compute_device_type = dt
                    cprefs.get_devices()
                    if any(d.type == dt for d in cprefs.devices):
                        break
                except Exception:
                    continue
            for d in cprefs.devices:
                d.use = (d.type == cprefs.compute_device_type)
#             print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: "
#                   f"GPU后端={cprefs.compute_device_type}, "
#                   f"已启用={[d.name for d in cprefs.devices if d.use]}", flush=True)
        except Exception:
            pass

        bake_type   = 'EMIT' if principled is None else 'DIFFUSE'
        bake_kwargs = {}

        if principled is not None:
            if pbr_type == 'color':
                bake_type   = 'DIFFUSE'
                bake_kwargs = {'pass_filter': {'COLOR'}}
                # Zero metallic temporarily so it doesn't darken the diffuse bake
                m_sock = principled.inputs.get('Metallic')
                if m_sock and not m_sock.is_linked:
                    orig_val = m_sock.default_value
                    m_sock.default_value = 0.0
                    tmp_restore.append(('default', m_sock, orig_val))

            elif pbr_type == 'normal':
                bake_type = 'NORMAL'

            elif pbr_type == 'roughness':
                bake_type = 'ROUGHNESS'

            elif pbr_type == 'metallic':
                # Route Metallic source → Roughness socket, bake as ROUGHNESS
                bake_type   = 'ROUGHNESS'
                m_sock = principled.inputs.get('Metallic')
                r_sock = principled.inputs.get('Roughness')
                if m_sock and r_sock and m_sock.is_linked:
                    metal_from = m_sock.links[0].from_socket
                    if r_sock.is_linked:
                        rough_from = r_sock.links[0].from_socket
                        tmp_restore.append(('link', rough_from, r_sock))
                        tree.links.remove(r_sock.links[0])
                    lnk = tree.links.new(metal_from, r_sock)
                    tmp_remove.append(lnk)

            elif pbr_type == 'alpha':
                # Route Alpha source → Emission Color socket, bake as EMIT
                bake_type = 'EMIT'
                a_sock  = principled.inputs.get('Alpha')
                e_sock  = principled.inputs.get('Emission Color')
                if a_sock and e_sock and a_sock.is_linked:
                    alpha_from = a_sock.links[0].from_socket
                    if e_sock.is_linked:
                        emit_from = e_sock.links[0].from_socket
                        tmp_restore.append(('link', emit_from, e_sock))
                        tree.links.remove(e_sock.links[0])
                    lnk = tree.links.new(alpha_from, e_sock)
                    tmp_remove.append(lnk)

            elif pbr_type == 'emissive':
                bake_type = 'EMIT'

        # Activate all meshes that share this material (or just the single one)
        prev_active   = context.view_layer.objects.active
        prev_selected = list(context.selected_objects)
        for o in prev_selected:
            o.select_set(False)
        if mesh_objects:
            for mo in mesh_objects:
                mo.select_set(True)
            context.view_layer.objects.active = mesh_objects[0]
        else:
            mesh_obj.select_set(True)
            context.view_layer.objects.active = mesh_obj

        # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 开始 (type={bake_type}, size={size}, samples={cycles_scene.samples})", flush=True)
        bpy.ops.object.bake(type=bake_type, **bake_kwargs)

        out_path = os.path.join(tmp_dir, f"_baked_{_slugify(material.name)}_{pbr_type}.png")
        bake_img.filepath_raw = out_path
        bake_img.file_format  = 'PNG'
        bake_img.save()

        # Restore selection
        for o in prev_selected:
            o.select_set(True)
        context.view_layer.objects.active = prev_active

        return out_path

    except Exception as e:
        print(f"[MDF Gen] Bake failed {material.name}/{pbr_type}: {e}")
        return None

    finally:
        for lnk in tmp_remove:
            try:
                tree.links.remove(lnk)
            except Exception:
                pass
        for item in tmp_restore:
            if item[0] == 'link':
                _, from_sock, to_sock = item
                tree.links.new(from_sock, to_sock)
            elif item[0] == 'default':
                _, sock, val = item
                sock.default_value = val
        tree.nodes.remove(bake_node)
        try:
            tree.nodes.active = orig_active_node
        except Exception:
            pass
        if img_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[img_name])
        context.scene.render.engine = orig_engine
        try:
            material.node_tree.update_tag()
        except Exception:
            pass
        # print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: 已恢复引擎={context.scene.render.engine}", flush=True)
        # Restore Cycles GPU / device state
        try:
            cycles_scene.device = orig_device
            cycles_scene.samples = orig_samples
        except Exception:
            pass
        if orig_compute_device_type is not None:
            try:
                cprefs = bpy.context.preferences.addons['cycles'].preferences
                cprefs.compute_device_type = orig_compute_device_type
                cprefs.get_devices()
                for d in cprefs.devices:
                    if d.name in orig_dev_use:
                        d.use = orig_dev_use[d.name]
#                 print(f"[MDF Gen]   烘培 {material.name}/{pbr_type}: "
#                       f"已恢复GPU后端={orig_compute_device_type}", flush=True)
            except Exception:
                pass


def _detect_max_tex_size(material):
    """扫描节点树，返回所有已加载图像中的最大边长；无贴图时返回 BAKE_SIZE_DEFAULT。"""
    max_size = 0
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                w, h = node.image.size
                max_size = max(max_size, w, h)
    return max_size if max_size > 0 else BAKE_SIZE_DEFAULT


_PBR_CHANNELS = ('color', 'normal', 'roughness', 'metallic', 'alpha', 'emissive')


def detect_native_sizes(mat, strategies):
    """
    Return {channel: native_pixel_size} for all PBR channels.

    SOLID  → SOLID_SIZE (8)
    BAKE   → max texture size found in the material node tree
    DIRECT → size of the source image if loaded in bpy.data.images,
             otherwise falls back to the material's max texture size
    """
    mat_max = _detect_max_tex_size(mat)
    sizes = {}
    for ch in _PBR_CHANNELS:
        sv = strategies.get(ch, ('SOLID', None))
        strat = sv[0]
        if strat == 'SOLID':
            sizes[ch] = SOLID_SIZE
        elif strat == 'BAKE':
            sizes[ch] = mat_max
        else:  # DIRECT
            path = sv[1] if len(sv) > 1 else None
            img_size = 0
            if path:
                for img in bpy.data.images:
                    if bpy.path.abspath(img.filepath) == path and img.size[0] > 0:
                        img_size = max(img.size[0], img.size[1])
                        break
            sizes[ch] = img_size if img_size > 0 else mat_max
    return sizes


def _nearest_pow2_leq(value, min_size=256):
    """Return the largest power-of-2 that is ≤ value and ≥ min_size."""
    if value <= min_size:
        return min_size
    p = 1
    while p * 2 <= value:
        p *= 2
    return p


def _maybe_resize_direct(src_path, target_size, tmp_dir):
    """
    If the source image is larger than target_size, save a scaled copy to
    tmp_dir and return its path.  Otherwise return src_path unchanged.
    Uses bpy.data.images so no Pillow dependency is required.
    """
    try:
        img = bpy.data.images.load(src_path, check_existing=True)
        native = max(img.size[0], img.size[1])
        if native <= target_size:
            return src_path

        import hashlib
        tag = hashlib.md5(f"{src_path}_{target_size}".encode()).hexdigest()[:8]
        ext = os.path.splitext(src_path)[1] or '.png'
        out_path = os.path.join(tmp_dir, f"resized_{tag}{ext}")

        img_copy = img.copy()
        try:
            img_copy.scale(target_size, target_size)
            img_copy.filepath_raw = out_path
            img_copy.save()
        finally:
            bpy.data.images.remove(img_copy)
        return out_path
    except Exception as e:
        print(f"[MDF Gen] resize failed for {src_path} → {target_size}px: {e}")
        return src_path


# ── Channel size override operator ─────────────────────────────────────────────

_VALID_POW2_SIZES = [256, 512, 1024, 2048, 4096, 8192]
_set_channel_size_items_cache: list = []


def _channel_size_enum_items(self, context):
    """Enum items callback for MHW_OT_SetChannelSize — avoids GC of string list."""
    global _set_channel_size_items_cache
    ns = self.native_size
    _set_channel_size_items_cache = [
        (str(s), f"{s}×{s}", "")
        for s in _VALID_POW2_SIZES
        if s <= ns
    ]
    return _set_channel_size_items_cache


class MHW_OT_SetChannelSize(bpy.types.Operator):
    bl_idname  = "mhw.set_channel_size"
    bl_label   = "Set Output Size"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.mdf_generator_base.set_channel_size_desc")

    settings_attr: bpy.props.StringProperty()
    mat_name:      bpy.props.StringProperty()
    channel:       bpy.props.StringProperty()
    native_size:   bpy.props.IntProperty(default=1024)
    size:          bpy.props.EnumProperty(
        name="Output Size",
        description="Final output resolution for the baked/direct channel (square side length)",
        items=_channel_size_enum_items,
    )

    def invoke(self, context, event):
        settings = getattr(context.scene, self.settings_attr, None)
        current  = 0
        if settings:
            for entry in settings.material_list:
                if entry.blender_material == self.mat_name:
                    current = getattr(entry, f"bake_size_{self.channel}", 0)
                    break
        # Pre-select current override, or fall back to native (clamped to valid)
        target = current if current > 0 else self.native_size
        valid  = [s for s in _VALID_POW2_SIZES if s <= self.native_size]
        if valid:
            best = max((s for s in valid if s <= target), default=valid[0])
            self.size = str(best)
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        col = self.layout.column()
        col.label(text=T("core.mdf_generator_base.native_size_label").format(size=self.native_size))
        col.prop(self, "size", text=T("core.mdf_generator_base.output_size_label"))

    def execute(self, context):
        settings = getattr(context.scene, self.settings_attr, None)
        if not settings:
            return {'CANCELLED'}
        for entry in settings.material_list:
            if entry.blender_material == self.mat_name:
                setattr(entry, f"bake_size_{self.channel}", int(self.size))
                return {'FINISHED'}
        return {'CANCELLED'}


# ── Shader source toggle operator ───────────────────────────────────────────
# Plain prop(expand=True) on a *dynamic* items= enum renders blank button text
# in Blender (works fine as a dropdown, only breaks in expand mode) -- so the
# PBR/Slot choice is drawn as two of these buttons instead, matching the
# toggle_blank/toggle_ccl/watermark_toggle pattern used elsewhere.

class MHW_OT_SetShaderSource(bpy.types.Operator):
    bl_idname  = "mhw.set_shader_source"
    bl_label   = "Set Shader Source"
    bl_options = {'INTERNAL', 'UNDO'}

    settings_attr: bpy.props.StringProperty()
    mat_name:      bpy.props.StringProperty()
    value:         bpy.props.StringProperty()

    def execute(self, context):
        settings = getattr(context.scene, self.settings_attr, None)
        if not settings:
            return {'CANCELLED'}
        for entry in settings.material_list:
            if entry.blender_material == self.mat_name:
                entry.shader_source = self.value
                return {'FINISHED'}
        return {'CANCELLED'}


def _get_pbr_paths(material, strategies, tmp_dir, bake_size, context, mesh_obj,
                   channel_sizes=None, mesh_objects=None):
    """
    Resolve each PBR strategy to a file path.
    Returns dict {pbr_type: path_or_None}.

    mesh_objects — optional list of mesh objects sharing the same material;
                   forwarded to _bake_pbr_channel so every UV layout is baked.
    """
    paths = {}
    for pbr_type, strat_val in strategies.items():
        strategy    = strat_val[0]
        value       = strat_val[1]
        # Per-channel size override: 0 means "use global bake_size"
        ch_override = (channel_sizes or {}).get(pbr_type, 0)
        ch_size     = ch_override if ch_override > 0 else bake_size

        if strategy == 'DIRECT':
            src = value
            if ch_override > 0:
                src = _maybe_resize_direct(src, ch_override, tmp_dir)
            paths[pbr_type] = src

        elif strategy == 'SOLID':
            hint = f"{_slugify(material.name)}_{pbr_type}"
            paths[pbr_type] = _generate_solid_texture_path(
                value, tmp_dir, hint, size=SOLID_SIZE)

        elif strategy == 'BAKE':
            if mesh_obj:
                _t_bake = time.time()
                paths[pbr_type] = _bake_pbr_channel(
                    material, pbr_type, mesh_obj, ch_size, tmp_dir, context,
                    mesh_objects=mesh_objects)
                print(f"[MDF Gen]   烘培 {pbr_type}: {time.time() - _t_bake:.2f}s", flush=True)
            else:
                print(f"[MDF Gen] No mesh found for baking {material.name}/{pbr_type}, skipping")
                paths[pbr_type] = None
    return paths


# ── Mesh helpers ───────────────────────────────────────────────────────────────

def _slugify(name):
    """Convert to filesystem-safe slug (ASCII, no spaces)."""
    slug = re.sub(r'[^\w\-]', '_', name)
    return slug.strip('_') or 'material'


def _strip_blender_suffix(name):
    """
    Strip Blender's auto-generated duplicate suffix (.001, .002, …) from a
    material name so that 'MyMat.001' resolves to the same tex_name as 'MyMat'.
    Only strips when the suffix is purely numeric (Blender's pattern).
    """
    return re.sub(r'\.\d+$', '', name)


# ── RE Engine Group_G_Sub_S__Name mesh naming ───────────────────────────────

_GROUP_SUB_RE = re.compile(r'^Group_(\d+)_Sub_(\d+)__(.+)$')


def _parse_group_sub_name(obj_name):
    """The embedded material name from an already-separated RE Engine mesh
    name (Group_G_Sub_S__Name), or None when obj_name doesn't match that
    shape at all, or when Name itself carries a Blender collision suffix
    (Name.001) -- that marks this particular object as a duplicate/copy
    whose embedded name is not trustworthy as *the* name for its material
    (see _material_name_for)."""
    m = _GROUP_SUB_RE.match(obj_name)
    if not m:
        return None
    name = m.group(3)
    if re.search(r'\.\d+$', name):
        return None
    return name


def _material_name_for(mat_name, mesh_objects):
    """The name to give this material's MDF2 materialName -- and, when it
    came from a mesh, the reason _separate_mesh_by_material below leaves
    that mesh's own name alone instead of churning it every generator run.

    Prefers the embedded name from an already-separated, standard-format
    mesh (Group_G_Sub_S__Name) over a slug of the Blender material's own
    name: an import that already split per material can carry the real
    intended name there even when the material datablock itself only has a
    generic one (e.g. "Material.003" after a merge that did not preserve
    names). Falls back to the original scheme -- a slug of the material's
    own name -- when no mesh has a trustworthy embedded name.

    _UseSC is deliberately *not* stripped here: that only ever affects the
    generated texture filenames/paths (see tex_name in
    _process_one_material), never the material's own name.
    """
    for obj in mesh_objects:
        name = _parse_group_sub_name(obj.name)
        if name is not None:
            return name
    return _slugify(_strip_blender_suffix(mat_name))


def import_read_preset_json():
    """Locate and return readPresetJSON from RE Mesh Editor."""
    import sys, importlib, inspect

    def _wrap_if_needed(fn):
        # Old RE Mesh Editor versions only accept (filepath,); wrap for compatibility.
        try:
            nparams = len(inspect.signature(fn).parameters)
        except (ValueError, TypeError):
            nparams = 2
        if nparams >= 2:
            return fn
        def _compat(filepath, targetCollection=None):
            return fn(filepath)
        return _compat

    for key, mod in sys.modules.items():
        if key.endswith('.modules.mdf.re_mdf_presets'):
            fn = getattr(mod, 'readPresetJSON', None)
            if fn:
                return _wrap_if_needed(fn)
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mdf.re_mdf_presets")
            fn = getattr(m, 'readPresetJSON', None)
            if fn:
                return _wrap_if_needed(fn)
        except Exception:
            continue
    return None


def _import_create_mdf_collection():
    """Locate createMDFCollection from RE Mesh Editor's blender_re_mdf module."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mdf.blender_re_mdf'):
            fn = getattr(mod, 'createMDFCollection', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mdf.blender_re_mdf")
            fn = getattr(m, 'createMDFCollection', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


# ── MHWI (MHW Model Editor) utilities ─────────────────────────────────────────

def _get_mhwi_module_file():
    """Return the __file__ of MHW Model Editor's mrl3_presets module, or None."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mrl3.mrl3_presets'):
            return mod.__file__
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mrl3.mrl3_presets")
            return m.__file__
        except Exception:
            continue
    return None


def get_mhwi_preset_dir():
    """Return path to MHW Model Editor's MaterialPresets/ directory, or None."""
    f = _get_mhwi_module_file()
    if not f:
        return None
    d = os.path.join(os.path.dirname(f), 'MaterialPresets')
    return d if os.path.isdir(d) else None


def bundled_mhwi_preset():
    """This addon's own copy of MHW Model Editor's ``Standard.json``, or None.

    MHW Model Editor ships ``MaterialPresets/`` empty, so a fresh install has no
    preset to pick and the generator refused to run at all.  The bundled copy is
    the floor under that: a generic ``PL_Mt`` material, which is what the user
    would have picked anyway.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'assets', 'mhwi', 'mrl3_presets', 'Standard.json')
    return path if os.path.isfile(path) else None


def load_mhwi_preset_enum_items():
    """EnumProperty items from MHW Model Editor's MaterialPresets, else the
    bundled fallback.  'NONE' is only reached when even that is missing."""
    items = []
    preset_dir = get_mhwi_preset_dir()
    if preset_dir:
        try:
            for entry in sorted(os.scandir(preset_dir), key=lambda e: e.name):
                if entry.is_file() and entry.name.endswith('.json'):
                    items.append((entry.path, entry.name[:-5], entry.path))
        except Exception:
            pass
    if items:
        return items
    fallback = bundled_mhwi_preset()
    if fallback:
        return [(fallback, T("core.mdf_generator_base.mhwi_preset_bundled"), fallback)]
    return [('NONE', T("core.mdf_generator_base.mhwi_preset_none"), '')]


def _import_mhwi_create_collection():
    """Locate createCollection from MHW Model Editor's blender_functions module."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.common.blender_functions'):
            fn = getattr(mod, 'createCollection', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.common.blender_functions")
            fn = getattr(m, 'createCollection', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def _import_mhwi_tex_convert():
    """Locate convertDDSFileToTex from MHW Model Editor."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.tex.tex_function'):
            fn = getattr(mod, 'convertDDSFileToTex', None)
            if fn:
                return fn
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


def _import_mhwi_read_preset():
    """Locate readPresetJSON from MHW Model Editor's mrl3_presets module."""
    import sys, importlib
    for key, mod in sys.modules.items():
        if key.endswith('.modules.mrl3.mrl3_presets'):
            fn = getattr(mod, 'readPresetJSON', None)
            if fn:
                return fn
    import addon_utils
    for mod in addon_utils.modules():
        pkg = getattr(mod, '__package__', None) or getattr(mod, '__name__', '')
        if not pkg:
            continue
        try:
            m = importlib.import_module(f"{pkg}.modules.mrl3.mrl3_presets")
            fn = getattr(m, 'readPresetJSON', None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def _call_mhwi_read_preset(filepath, target_col):
    """
    Call MHW Model Editor's readPresetJSON with a specific target collection.

    readPresetJSON() reads from bpy.context.scene.mhw_mrl3_toolpanel.mrl3Collection
    and returns True/False instead of the new object.  We temporarily override the
    collection pointer, diff collection contents before/after, and return the new obj.
    """
    readPresetJSON = _import_mhwi_read_preset()
    if readPresetJSON is None:
        raise RuntimeError("Cannot find readPresetJSON from MHW Model Editor")

    before = {obj.name for obj in target_col.all_objects}

    toolpanel = bpy.context.scene.mhw_mrl3_toolpanel
    original_col = toolpanel.mrl3Collection
    toolpanel.mrl3Collection = target_col
    try:
        result = readPresetJSON(filepath)
    finally:
        toolpanel.mrl3Collection = original_col

    if not result:
        raise RuntimeError(f"readPresetJSON returned False for '{filepath}'")

    after = {obj.name for obj in target_col.all_objects}
    new_names = after - before
    if not new_names:
        raise RuntimeError("readPresetJSON succeeded but no new object in collection")

    return target_col.all_objects[next(iter(new_names))]


# ── Mesh helpers ───────────────────────────────────────────────────────────────

def _find_meshes_by_material(collection, material_name):
    """
    在指定集合中查找所有使用指定材质的 MESH 物体。
    返回 list，可能为空。

    借鉴 SmartBatchBake 阶段二的 find_same_material_objects 思路：
    遍历集合 → 检查每个物体的材质槽 → 收集匹配的网格。
    """
    if not collection or not material_name:
        return []
    matched = []
    for obj in collection.all_objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            if slot.material and slot.material.name == material_name:
                matched.append(obj)
                break
    return matched


def _separate_mesh_by_material(context, mesh_col):
    """
    Separate every multi-material mesh in the collection by material, then
    rename the resulting objects to RE Engine format: Group_0_Sub_N__MatName
    -- except ones that already are (_parse_group_sub_name), which are left
    untouched rather than churned (renumbered and possibly reslugified) on
    every single generator run. That is also what makes _material_name_for
    above trustworthy: a mesh this function leaves alone keeps the same name
    the material was just given.
    """
    # Snapshot — the list grows during separation
    initial = [o for o in mesh_col.all_objects if o.type == 'MESH']

    for obj in context.scene.objects:
        obj.select_set(False)

    for obj in initial:
        if not obj.data or len(obj.data.materials) <= 1:
            continue
        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')
        obj.select_set(False)

    for obj in context.scene.objects:
        obj.select_set(False)

    all_mesh_objs = [o for o in mesh_col.all_objects if o.type == 'MESH']

    # Sub-indices already spoken for by objects being left alone, so the
    # freshly (re)named ones below don't collide with them.
    used_subs = set()
    to_rename = []
    for obj in all_mesh_objs:
        if _parse_group_sub_name(obj.name) is not None:
            used_subs.add(int(_GROUP_SUB_RE.match(obj.name).group(2)))
        else:
            to_rename.append(obj)

    sub_index = 0
    for obj in sorted(to_rename, key=lambda o: o.name):
        while sub_index in used_subs:
            sub_index += 1
        mat  = obj.data.materials[0] if obj.data.materials else None
        slug = _slugify(_strip_blender_suffix(mat.name)) if mat else f"unnamed_{sub_index}"
        new_name      = f"Group_0_Sub_{sub_index}__{slug}"
        obj.name      = new_name
        obj.data.name = new_name
        used_subs.add(sub_index)
        sub_index    += 1


# ── Base operator: Refresh ─────────────────────────────────────────────────────

# User-editable fields on a material_list entry. Preserved by name across a
# refresh instead of being wiped by clear()-and-rebuild; everything else
# (strategy_display, strat_*, native_size_*, uses_packed_shader,
# preset_locked, preset_path_override) is re-derived from the material every
# time since it reflects current material/shader state, not a user choice.
# Not every game's entry PropertyGroup has every field (e.g. only MHWI has
# hide_snow_overlay/ao_strength) -- getattr(..., None) below skips the rest.
_PRESERVED_ENTRY_FIELDS = (
    'expanded', 'material_preset', 'shader_source', 'use_toon',
    'generate_mipmaps', 'skip_textures',
    'use_ao', 'ao_image', 'ao_ch', 'ao_inv', 'ao_strength',
    'hide_snow_overlay',
    'bake_size_color', 'bake_size_normal', 'bake_size_roughness',
    'bake_size_metallic', 'bake_size_alpha', 'bake_size_emissive',
)


class MdfGenRefreshBase(bpy.types.Operator):
    bl_label   = "Refresh"
    bl_options = {'INTERNAL'}
    _settings_attr = ""
    _game_name     = ""

    @classmethod
    def _load_preset_items(cls):
        """Override in subclasses that use a different preset system (e.g. MHWI)."""
        return load_preset_enum_items(cls._game_name)

    def execute(self, context):
        cls      = type(self)
        settings = getattr(context.scene, cls._settings_attr)

        mesh_col = settings.mesh_collection
        if not mesh_col:
            self.report({'ERROR'}, T("core.mdf_generator_base.select_mesh_collection"))
            return {'CANCELLED'}

        mat_names = set()
        for obj in mesh_col.all_objects:
            if obj.type == 'MESH':
                for mat in obj.data.materials:
                    if mat:
                        mat_names.add(mat.name)

        if not mat_names:
            self.report({'ERROR'}, T("core.mdf_generator_base.no_materials_in_collection"))
            return {'CANCELLED'}

        preset_items = cls._load_preset_items()

        # Snapshot user-adjusted settings before rebuilding, keyed by material
        # name, so they can be re-applied instead of lost to clear().
        preserved = {}
        for old in settings.material_list:
            preserved[old.blender_material] = {
                field: getattr(old, field, None) for field in _PRESERVED_ENTRY_FIELDS
            }

        settings.material_list.clear()

        for mat_name in sorted(mat_names):
            mat = bpy.data.materials.get(mat_name)
            if not mat:
                continue

            shader_type  = detect_shader_type(mat)
            item = settings.material_list.add()
            item.blender_material = mat_name
            # Recorded once here rather than probed on every UI redraw.
            try:
                item.uses_packed_shader = (shader_type == SHADER_MTK_PACK)
            except AttributeError:
                pass

            if shader_type == SHADER_MTK_PACK:
                try:
                    item.shader_source = guess_shader_source_default(mat)
                except Exception:
                    pass
                strategies = packed_shader_strategies(mat, item.shader_source)
            else:
                strategies = analyze_material_strategies(mat)

            locked_path, locked = _locked_preset_for_material(mat)
            if locked and locked_path:
                # A bundled prefab -- not one of preset_items, so it cannot go
                # through material_preset at all. Carried separately; the
                # dropdown itself is left at whatever guess_best_preset would
                # give it (inert -- _process_one_material reads the override
                # first) and the UI shows a read-only label instead.
                try:
                    item.preset_locked = True
                    item.preset_path_override = locked_path
                except AttributeError:
                    pass
                best = guess_best_preset(mat_name, preset_items)
            elif locked_path:
                # An external preset picked in the same dialog -- a real
                # entry in preset_items, so it can be assigned normally and
                # stays a live, re-editable dropdown.
                try:
                    item.preset_locked = False
                    item.preset_path_override = ""
                except AttributeError:
                    pass
                best = locked_path
            else:
                try:
                    item.preset_locked = False
                    item.preset_path_override = ""
                except AttributeError:
                    pass
                best = guess_best_preset(mat_name, preset_items)
            try:
                item.material_preset = best
            except Exception:
                pass

            # Auto-enable toon for emissive-style shaders
            if shader_type in (SHADER_EMISSION, SHADER_MMD_DEV):
                try:
                    item.use_toon = True
                except Exception:
                    pass

            # Strategy summary shown in collapsed view
            parts = []
            for pt in ('color', 'normal', 'roughness', 'metallic', 'alpha', 'emissive'):
                sv = strategies.get(pt, ('?', None))
                parts.append(f"{pt[0].upper()}:{strategy_label(sv[0])}")
            item.strategy_display = '  '.join(parts)

            # Per-channel strategy labels (for expanded view)
            for pt in ('color', 'metallic', 'roughness', 'normal', 'alpha', 'emissive'):
                sv = strategies.get(pt, ('?', None))
                setattr(item, f"strat_{pt}", strategy_label(sv[0]))

            # Per-channel native sizes (for the resize button in the UI)
            native_sizes = detect_native_sizes(mat, strategies)
            for pt in _PBR_CHANNELS:
                try:
                    setattr(item, f"native_size_{pt}", native_sizes.get(pt, 0))
                except Exception:
                    pass

            # Re-apply this material's own previous adjustments, if any,
            # over the freshly-guessed defaults set above.
            old_values = preserved.get(mat_name)
            if old_values:
                for field, value in old_values.items():
                    if value is None:
                        continue
                    try:
                        setattr(item, field, value)
                    except Exception:
                        pass

        self.report({'INFO'}, T("core.mdf_generator_base.scanned_materials").format(n=len(settings.material_list)))
        return {'FINISHED'}


# ── Base operator: Process ─────────────────────────────────────────────────────

class MdfGenProcessBase(bpy.types.Operator):
    bl_label   = "Generate MDF2 + Textures"
    bl_options = {'REGISTER'}

    _settings_attr     = ""
    _game_name         = ""
    _natives_root_key  = ""
    _tex_version       = 0
    _use_art_prefix    = True
    _path_fixed_prefix = ""   # Optional path segment prepended to texture_base_path (e.g. RE4)
    _abbrev_map        = {}
    _channel_maps      = {}
    _null_tex_by_type  = {}
    _log_tag           = "MDF Gen"
    _bake_size         = BAKE_SIZE_DEFAULT

    def execute(self, context):
        _t_total = time.time()
        cls      = type(self)
        settings = getattr(context.scene, cls._settings_attr)

        natives_root = context.scene.get(cls._natives_root_key, "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("core.mdf_generator_base.set_natives_root"))
            return {'CANCELLED'}

        mesh_col = settings.mesh_collection
        if not mesh_col:
            self.report({'ERROR'}, T("core.mdf_generator_base.select_mesh_collection"))
            return {'CANCELLED'}

        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, T("core.mdf_generator_base.fill_base_path"))
            return {'CANCELLED'}

        if cls._path_fixed_prefix:
            base_path = cls._path_fixed_prefix.strip('/') + '/' + base_path.strip('/')

        if not settings.material_list:
            self.report({'ERROR'}, T("core.mdf_generator_base.click_refresh_first"))
            return {'CANCELLED'}

        print(f"[{cls._log_tag}] {'='*40}", flush=True)

        ImageListToDDS, DDSToTex = _import_tex_utils()

        _t_import = time.time()
        readPresetJSON = import_read_preset_json()
        # print(f"[{cls._log_tag}] 加载 Preset 模块: {time.time() - _t_import:.2f}s", flush=True)
        if readPresetJSON is None:
            self.report({'ERROR'}, T("core.mdf_generator_base.cannot_load_preset_tool"))
            return {'CANCELLED'}

        mdf_col = self._get_or_create_mdf_collection(context, mesh_col, settings)

        temp_dir = tempfile.mkdtemp(prefix="mdf_gen_")
        comp_cache = {}  # (slot_type, source_ids, pbr_channels) → (composed, disk, mdf)
        export_count = fail_count = 0

        try:
            for mat_entry in settings.material_list:
                try:
                    _t_mat = time.time()
                    self._process_one_material(
                        context, mat_entry, settings, mdf_col,
                        natives_root, base_path, temp_dir,
                        ImageListToDDS, DDSToTex, readPresetJSON, cls, mesh_col,
                        comp_cache,
                    )
                    export_count += 1
                    print(f"[{cls._log_tag}] OK: {mat_entry.blender_material} ({time.time() - _t_mat:.2f}s)")
                except Exception as e:
                    import traceback
                    print(f"[{cls._log_tag}] FAIL {mat_entry.blender_material}: {e}")
                    traceback.print_exc()
                    fail_count += 1
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        _t_sep = time.time()
        try:
            _separate_mesh_by_material(context, mesh_col)
            print(f"[{cls._log_tag}] 分离网格: {time.time() - _t_sep:.2f}s", flush=True)
        except Exception as e:
            print(f"[{cls._log_tag}] Mesh separate/rename warning: {e}")

        print(f"[{cls._log_tag}] ★ 总耗时: {time.time() - _t_total:.2f}s ★", flush=True)
        if fail_count:
            self.report({'WARNING'}, T("core.mdf_generator_base.process_done_with_fail").format(
                export=export_count, fail=fail_count))
        else:
            self.report({'INFO'}, T("core.mdf_generator_base.process_done").format(n=export_count))
        return {'FINISHED'}  # MdfGenProcessBase

    # ── helpers ────────────────────────────────────────────────────────────────

    def _get_or_create_mdf_collection(self, context, mesh_col, settings):
        mdf_name = settings.mdf_collection_name.strip()
        if not mdf_name:
            mdf_name = (mesh_col.name.replace('.mesh', '.mdf2')
                        if '.mesh' in mesh_col.name
                        else mesh_col.name + ".mdf2")

        if mdf_name in bpy.data.collections:
            return bpy.data.collections[mdf_name]

        parent = next(
            (c for c in bpy.data.collections
             if mesh_col.name in [ch.name for ch in c.children]),
            None,
        )

        createMDFCollection = _import_create_mdf_collection()
        if createMDFCollection:
            return createMDFCollection(mdf_name, parent)

        # Fallback if RE Mesh Editor function is unavailable
        col = bpy.data.collections.new(mdf_name)
        col["~TYPE"] = "RE_MDF_COLLECTION"
        col.color_tag = "COLOR_05"
        if parent:
            parent.children.link(col)
        else:
            context.scene.collection.children.link(col)
        return col

    def _process_one_material(self, context, mat_entry, settings, mdf_col,
                               natives_root, base_path, temp_dir,
                               ImageListToDDS, DDSToTex, readPresetJSON, cls, mesh_col,
                               comp_cache):
        mat_name = mat_entry.blender_material
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            raise ValueError(f"Material '{mat_name}' not found")

        # A locked prefab lives outside preset_items entirely (see
        # _locked_preset_for_material) and cannot be represented by
        # material_preset's own EnumProperty -- read the override first.
        if getattr(mat_entry, 'preset_locked', False) and mat_entry.preset_path_override:
            preset_path = mat_entry.preset_path_override
        else:
            preset_path = mat_entry.material_preset
        if not preset_path or preset_path == 'NONE':
            raise ValueError(f"No preset selected for '{mat_name}'")
        if not os.path.isfile(preset_path):
            raise FileNotFoundError(f"Preset not found: {preset_path}")

        # Find all mesh objects sharing this material (for baking across all UV layouts)
        mesh_objects = _find_meshes_by_material(mesh_col, mat_name)
        mesh_obj = mesh_objects[0] if mesh_objects else None
        if mesh_objects:
            print(f"[{cls._log_tag}]   '{mat_name}' → {len(mesh_objects)} 个网格: "
                  f"{', '.join(o.name for o in mesh_objects)}")

        _t = time.time()
        strategies = packed_shader_strategies(mat, getattr(mat_entry, 'shader_source', 'PBR'))
        # print(f"[{cls._log_tag}]   分析材质节点: {time.time() - _t:.2f}s", flush=True)
        bake_size  = max(_detect_max_tex_size(mat), cls._bake_size)

        # Collect per-channel user size overrides (0 = use global bake_size)
        channel_sizes = {}
        for pt in _PBR_CHANNELS:
            override = getattr(mat_entry, f"bake_size_{pt}", 0)
            if override > 0:
                channel_sizes[pt] = override

        _t = time.time()
        pbr_paths  = _get_pbr_paths(
            mat, strategies, temp_dir, bake_size, context, mesh_obj,
            channel_sizes=channel_sizes or None,
            mesh_objects=mesh_objects)
        # print(f"[{cls._log_tag}]   解析PBR路径 (含烘培): {time.time() - _t:.2f}s", flush=True)

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
                print(f"[{cls._log_tag}]   AO from packed shader: "
                      f"{os.path.basename(shader_ao)} (strength {strength:.2f})")
            except Exception as e:
                print(f"[{cls._log_tag}]   could not adopt the shader's AO: {e}")

        # User-provided AO override (Blender has no built-in AO node). Channel
        # and invert are explicit UI choices here rather than node-analysed,
        # since there is no node chain to analyse for a plain file path --
        # mirrors the channel/invert pair core.mdf_tex_processor_base's own
        # PBR panel already offers for its (also manually-provided) AO input.
        pbr_inv = {}
        if getattr(mat_entry, 'use_ao', False):
            ao_path_raw = getattr(mat_entry, 'ao_image', '')
            if ao_path_raw:
                ao_path = bpy.path.abspath(ao_path_raw)
                if ao_path and os.path.isfile(ao_path):
                    strategies['ao'] = ('DIRECT', ao_path, getattr(mat_entry, 'ao_ch', 'R'))
                    pbr_paths['ao'] = ao_path
                    pbr_inv['ao'] = getattr(mat_entry, 'ao_inv', False)

        # Build source-channel overrides from DIRECT strategies where the
        # Image Texture's Alpha output (not Color) was connected — this
        # ensures alpha data is read from the A channel instead of R.
        pbr_channels = {}
        for pbr_type, strat_val in strategies.items():
            if strat_val[0] == 'DIRECT' and len(strat_val) > 2 and strat_val[2] != 'R':
                pbr_channels[pbr_type] = strat_val[2]

        # materialName keeps _UseSC (it is a marker on the material itself);
        # tex_name feeds every texture filename/binding path below and must
        # not carry it -- mirrors core.mdf_tex_processor_base's own
        # mat_item.material_name.removesuffix('_UseSC').
        material_name = _material_name_for(mat_name, mesh_objects)
        tex_name = material_name.removesuffix('_UseSC')

        # Determine which slot types the preset expects
        _t = time.time()
        with open(preset_path, encoding='utf-8') as f:
            preset_data = json.load(f)
        # print(f"[{cls._log_tag}]   加载Preset JSON: {time.time() - _t:.2f}s", flush=True)
        slot_types = [b["Texture Type"] for b in preset_data.get("Texture Bindings", [])]

        # A slot socket and the PBR inputs it covers can both be filled, and the
        # material's own shader_source is a hard switch between them -- not a
        # tie-break that lets whichever side has data win regardless of the
        # pick, which used to silently ignore the choice whenever only one
        # side was actually filled in. Per material, not global: one export
        # can mix materials that want the PBR panel with materials that want
        # the game slots.
        prefer_slots = getattr(mat_entry, 'shader_source', 'PBR') == 'SLOT'
        _supplies = find_shader_slot_supplies(mat)
        _pbr_given = shader_pbr_contributions(mat)
        contested_slots = {
            slot for slot, quantities in _supplies.items()
            if any(q in _pbr_given for q in quantities)
        }
        if contested_slots:
            print(f"[{cls._log_tag}]   both panels filled for "
                  f"{', '.join(sorted(contested_slots))} -> using the "
                  f"{'game slots' if prefer_slots else 'PBR inputs'}")

        # {slot: (path, authority)} — see slot_sources.  SHADER authority means
        # the user plugged the texture into that slot's socket on the packed
        # shader, which is an explicit instruction rather than a convention.
        slot_direct = find_slot_sources(mat, slot_types)
        prefer_direct = prefer_slots

        # Global toggles on the settings object override every material's own
        # checkbox -- "disable" forces mipmaps off regardless of what a
        # material asks for, "use toon" forces it on the same way.
        use_toon         = (getattr(mat_entry, 'use_toon', False)
                            or getattr(settings, 'global_use_toon', False))
        effective_mipmaps = (mat_entry.generate_mipmaps
                            and not getattr(settings, 'global_disable_mipmaps', False))
        emi_zero         = _emissive_strength_is_zero(mat)
        emissive_slots   = {st for st in slot_types if _is_emissive_slot(st)}
        albedo_slots     = {st for st in slot_types if _is_albedo_slot(st, cls._channel_maps)}

        # With no AO slot in this game's channel maps, an AO map can only survive
        # by being multiplied into the albedo. Where a slot does store it, that
        # path is used instead -- doing both would darken twice.
        bake_ao = (bool(pbr_paths.get('ao'))
                   and not channel_maps_consume_ao(cls._channel_maps))

        slot_mdf_paths = {}

        for slot_type in slot_types:
            # Emissive: skip composition if toon mode or strength is zero
            if slot_type in emissive_slots:
                if use_toon:
                    continue  # filled from albedo path after loop
                if emi_zero:
                    null = cls._null_tex_by_type.get(slot_type)
                    if null:
                        slot_mdf_paths[slot_type] = null
                    continue

            # --- direct slot source (BY_SLOT_NAME) ---------------------------
            # Lossless: the packed file goes to the slot as-is, no unpack →
            # recompose round-trip.  Applied unconditionally for slots absent
            # from _channel_maps (AO-bearing maps, detail maps — these have no
            # PBR composition recipe and currently fall through to a null
            # texture, so sourcing them can only be an improvement).  For slots
            # that *do* have a recipe it is opt-in, because a user who edited
            # roughness via nodes would otherwise have that edit silently
            # discarded in favour of the original packed file.
            direct_src, direct_auth = slot_direct.get(slot_type, (None, None))
            # shader_source is a hard switch, not a tie-break: a slot-named node
            # (not a shader socket) only wins where there is no composition
            # recipe to override (those slots used to write a null texture
            # regardless); an actual shader-socket connection is honoured only
            # when the user picked "game slots" for this material.
            if direct_src is not None and (
                    slot_type not in cls._channel_maps
                    or prefer_direct):
                if getattr(mat_entry, 'skip_textures', False):
                    slot_mdf_paths[slot_type] = make_mdf_path(
                        base_path, tex_name, slot_type,
                        cls._abbrev_map, cls._use_art_prefix,
                    )
                    continue

                direct_key = (slot_type, 'DIRECT_SLOT', direct_src)
                cached = comp_cache.get(direct_key)
                if cached is not None:
                    slot_mdf_paths[slot_type] = cached[2]
                    continue

                disk_path = make_disk_path(
                    natives_root, base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._tex_version, cls._use_art_prefix,
                )
                # Staged under a slot-unique stem: the source lives outside
                # temp_dir, and texconv names its output after the input.
                staged = stage_source_file(
                    direct_src, temp_dir, tex_name, slot_type)
                write_slot_tex(
                    staged, disk_path, temp_dir,
                    dds_fmt=resolve_dds_format(slot_type, SRGB_SLOT_TYPES),
                    generate_mipmaps=effective_mipmaps,
                    image_to_dds=ImageListToDDS,
                    dds_to_tex=lambda p, o: DDSToTex(p, cls._tex_version, o),
                )

                mdf_path = make_mdf_path(
                    base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._use_art_prefix,
                )
                slot_mdf_paths[slot_type] = mdf_path
                comp_cache[direct_key] = (staged, disk_path, mdf_path)
                print(f"[{cls._log_tag}]   {slot_type} -> "
                      f"{os.path.basename(disk_path)} (槽位直连/{direct_auth})")
                continue

            if slot_type not in cls._channel_maps:
                null = cls._null_tex_by_type.get(slot_type)
                if null:
                    slot_mdf_paths[slot_type] = null
                elif slot_type in PLACEHOLDER_SLOT_TYPES:
                    placeholder_path = _resolve_placeholder_slot(
                        slot_type, tex_name, natives_root, base_path, temp_dir,
                        cls._abbrev_map, cls._tex_version, cls._use_art_prefix,
                        ImageListToDDS, DDSToTex, comp_cache)
                    if placeholder_path:
                        slot_mdf_paths[slot_type] = placeholder_path
                        print(f"[{cls._log_tag}]   {slot_type} -> "
                              f"{os.path.basename(placeholder_path)} (占位贴图)")
                continue

            # --- skip_textures: just compute the binding path ---
            if getattr(mat_entry, 'skip_textures', False):
                slot_mdf_paths[slot_type] = make_mdf_path(
                    base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._use_art_prefix,
                )
                continue

            # --- cache key construction ---
            ch_map = cls._channel_maps[slot_type]
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
                    slot_mdf_paths[slot_type] = cached[2]
                    continue

                # Only attempt downgrade for cacheable slots (no BAKE involved)
                rgba = _try_downgrade_slot(slot_type, strategies, pbr_channels, cls._channel_maps)
                if rgba is not None:
                    # If every channel is at its PBR default value the slot carries
                    # no meaningful data — redirect to the null texture directly
                    # instead of generating a solid PNG/DDS/TEX.
                    null = cls._null_tex_by_type.get(slot_type)
                    if null:
                        default_rgba = _try_downgrade_slot(
                            slot_type, _DEFAULT_STRATEGIES, {}, cls._channel_maps)
                        if default_rgba is not None and all(
                                abs(a - b) < 1e-4 for a, b in zip(rgba, default_rgba)):
                            slot_mdf_paths[slot_type] = null
                            if cache_key is not None:
                                comp_cache[cache_key] = (None, None, null)
                            print(f"[{cls._log_tag}]   {slot_type} -> NULL (all-default)")
                            continue

                    hint = f"{tex_name}_{slot_type.lower()}_dg"
                    composed = _generate_solid_texture_path(rgba, temp_dir, hint, size=256)
                    if composed:
                        disk_path = make_disk_path(
                            natives_root, base_path, tex_name, slot_type,
                            cls._abbrev_map, cls._tex_version, cls._use_art_prefix,
                        )
                        write_slot_tex(
                            composed, disk_path, temp_dir,
                            dds_fmt=resolve_dds_format(slot_type, SRGB_SLOT_TYPES),
                            generate_mipmaps=effective_mipmaps,
                            image_to_dds=ImageListToDDS,
                            dds_to_tex=lambda p, o: DDSToTex(p, cls._tex_version, o),
                        )

                        mdf_path = make_mdf_path(
                            base_path, tex_name, slot_type,
                            cls._abbrev_map, cls._use_art_prefix,
                        )
                        slot_mdf_paths[slot_type] = mdf_path
                        comp_cache[cache_key] = (composed, disk_path, mdf_path)
                        continue

            # --- full composition path ---
            _t_comp = time.time()
            normal_flip_g = getattr(settings, 'flip_normal_g', False)
            composed = _compose_channels(
                slot_type, pbr_paths, pbr_channels, temp_dir, tex_name,
                pbr_inv=pbr_inv,
                channel_maps=cls._channel_maps,
                normal_flip_g=normal_flip_g,
                bake_ao_into_color=bake_ao,
                ao_strength=getattr(mat_entry, 'ao_strength', 1.0),
                octahedral=getattr(settings, 'octahedral_normals', False),
            )
            # print(f"[{cls._log_tag}]   合成通道 {slot_type}: {time.time() - _t_comp:.2f}s", flush=True)
            if composed:
                disk_path = make_disk_path(
                    natives_root, base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._tex_version, cls._use_art_prefix,
                )
                write_slot_tex(
                    composed, disk_path, temp_dir,
                    dds_fmt=resolve_dds_format(slot_type, SRGB_SLOT_TYPES),
                    generate_mipmaps=effective_mipmaps,
                    image_to_dds=ImageListToDDS,
                    dds_to_tex=lambda p, o: DDSToTex(p, cls._tex_version, o),
                )

                mdf_path = make_mdf_path(
                    base_path, tex_name, slot_type,
                    cls._abbrev_map, cls._use_art_prefix,
                )
                slot_mdf_paths[slot_type] = mdf_path

                if cache_key is not None:
                    comp_cache[cache_key] = (composed, disk_path, mdf_path)
                print(f"[{cls._log_tag}]   {slot_type} -> {os.path.basename(disk_path)}")
            else:
                null = cls._null_tex_by_type.get(slot_type)
                if null:
                    slot_mdf_paths[slot_type] = null

        # Toon shading: copy albedo binding path to all emissive slots
        if use_toon and emissive_slots:
            albedo_path = next(
                (slot_mdf_paths[st] for st in albedo_slots if st in slot_mdf_paths),
                None,
            )
            for st in emissive_slots:
                if albedo_path:
                    slot_mdf_paths[st] = albedo_path
                else:
                    null = cls._null_tex_by_type.get(st)
                    if null:
                        slot_mdf_paths[st] = null

        # Create MDF2 material from preset and update texture binding paths
        _t = time.time()
        mat_obj = readPresetJSON(preset_path, mdf_col)
        # print(f"[{cls._log_tag}]   创建MDF2材质: {time.time() - _t:.2f}s", flush=True)
        if mat_obj is None:
            raise RuntimeError(f"readPresetJSON returned None for '{mat_name}'")

        mat_obj.re_mdf_material.materialName = material_name
        for binding in mat_obj.re_mdf_material.textureBindingList_items:
            if binding.textureType in slot_mdf_paths:
                binding.path = slot_mdf_paths[binding.textureType]
