"""RE Mdf port, texture repack: carry one custom texture's pixels across the
channel-layout change a cross-game slot swap can involve.

The planning layer (``core/mdf_port.py``) decides which prefab material a source
material becomes; this module does the one piece that decision doesn't cover on its
own -- a source slot and its destination counterpart do not always pack the same
quantities into the same channels (MHWS's NRRO vs. RE4/RE9's NRMR is the case that
forced this: the ``_NRRO``/``_NRMR`` filename difference is a *consequence* of a real
channel-layout difference, not just a naming one -- see project memory
``project_mdf_port_feature``).  So a ported texture has to be decoded back to its
semantic channels (colour, normal, roughness, ...) and re-composed for the
destination slot's own layout, using the exact same channel tables
(``core/mdf_tex_processor_base.py::BASE_SLOT_CHANNEL_MAPS`` and its per-game
overrides) the existing PBR-input compose path already uses -- not a second,
independently-maintained table.

Not every slot swap needs that, though: when the source and destination slots
happen to pack the same quantities into the same channels (e.g. ``BaseDielectricMap``
on both sides), splitting into semantic channels and recomposing would be pure
overhead and a needless second lossy round trip -- so ``layouts_equal`` gates a
plain passthrough (format conversion only) before any channel math runs.
"""

import glob
import os


# ── Per-game texture pipeline config registry ───────────────────────────────
# Populated by each game's mdf_tex_processor.register() with the same constants
# its own MdfTexProcessBase subclass already uses (see e.g. games/re4/
# mdf_tex_processor.py's RE4_TEXTURE_TYPE_ABBREV / RE4_SLOT_CHANNEL_MAPS / etc.) --
# this module borrows them rather than restating them, so a per-game override
# only ever has one home.

_GAME_TEX_CONFIG = {}


def register_game_tex_config(game_code, **cfg):
    """cfg keys: abbrev_map, channel_maps, tex_version, use_art_prefix,
    path_fixed_prefix, null_tex_by_type, natives_root_key, vanilla_asset_rel."""
    _GAME_TEX_CONFIG[game_code] = cfg


def unregister_game_tex_config(game_code):
    _GAME_TEX_CONFIG.pop(game_code, None)


def get_game_tex_config(game_code):
    return _GAME_TEX_CONFIG.get(game_code)


def full_base_path(cfg, base_path):
    """*base_path* with the game's own fixed path segment in front of it.

    RE4 keeps character textures under ``_Chainsaw/Character/ch/``, which the user
    is not asked to type -- MdfTexProcessBase.execute prepends it the same way
    (mdf_tex_processor_base.py:913).  Without this the port wrote to
    ``natives/STM/<base>`` while telling the user, correctly, that it writes to
    ``natives/STM/_Chainsaw/Character/ch/<base>``.
    """
    prefix = (cfg.get("path_fixed_prefix") or "").strip('/')
    base = (base_path or "").strip('/')
    return f"{prefix}/{base}" if prefix and base else (base or prefix)


# ── Cross-game slot correspondence ──────────────────────────────────────────
# Which destination slot a source slot's *texture* becomes -- a different question
# from plan_material's archetype mapping. Some slot type strings are shared
# verbatim across every RE Engine game's presets (BaseDielectricMap, EmissiveMap),
# but the "normal + roughness (+ a third quantity)" and "alpha + cavity/
# translucency/AO" roles are filled by a *different* slot type string per game --
# MHWS's NormalRoughnessOcclusionMap packs AO where RE4R/RE9's NormalRoughnessMap
# has no AO channel at all, and the three games each pick a different member of
# AlphaTranslucentOcclusionSSSMap/AlphaCavityOcclusionTranslucentMap/
# AlphaTranslucentOcclusionCavityMap for the alpha role. So this maps by role
# (which BASE_SLOT_CHANNEL_MAPS already groups these into, see that table's own
# comments), not a hardcoded per-game-pair table.
_SLOT_FAMILY = {
    'BaseDielectricMap': 'albedo', 'BaseAlphaMap': 'albedo', 'BaseShiftMap': 'albedo',
    'NormalRoughnessOcclusionMap': 'normal', 'NormalRoughness': 'normal',
    'NormalRoughnessMap': 'normal', 'NRMR_NRRTMap': 'normal',
    'NormalRoughnessCavityMap': 'normal', 'NormalRoughnessTranslucentMap': 'normal',
    'EmissiveMap': 'emissive', 'Emissive_ColorMap': 'emissive',
    'AlphaTranslucentOcclusionSSSMap': 'alpha_pack', 'SSSCavityOcclusionTranslucentMap': 'alpha_pack',
    'AlphaCavityOcclusionTranslucentMap': 'alpha_pack', 'AlphaTranslucentOcclusionCavityMap': 'alpha_pack',
    'OcclusionMap': 'occlusion',
}


def find_dst_slot_type(src_slot_type, dst_slot_types):
    """The destination binding this source texture should land on, or None.

    Exact string match first (the shared-vocabulary slots), then exactly-one
    same-family candidate. More than one family match is ambiguous -- the
    caller skips it rather than guessing, same as an unmatched slot today."""
    if src_slot_type in dst_slot_types:
        return src_slot_type
    family = _SLOT_FAMILY.get(src_slot_type)
    if family is None:
        return None
    candidates = [t for t in dst_slot_types if _SLOT_FAMILY.get(t) == family]
    return candidates[0] if len(candidates) == 1 else None


# ── Channel layout comparison ───────────────────────────────────────────────

def layouts_equal(src_slot, dst_slot, src_channel_maps, dst_channel_maps):
    """True when the source and destination slot pack the same quantities into
    the same channels, so a plain format conversion is enough. Mechanical
    comparison against the channel tables -- no maintained list of "which
    slots happen to match", per the user's 2026-08-14 decision."""
    a = src_channel_maps.get(src_slot)
    b = dst_channel_maps.get(dst_slot)
    return a is not None and a == b


# ── .tex -> PNG decode ───────────────────────────────────────────────────────

def decode_tex_to_png(tex_path, temp_dir):
    """A source .tex's mip 0, decoded to a plain PNG for pixel access."""
    from . import tex_file, dds_file, texconv_native

    dds = tex_file.read_tex_to_dds(tex_path)
    # A binding's real filename is "<name>.tex.<version>" -- os.path.splitext
    # would treat ".<version>" as the extension and leave "<name>.tex" as the
    # stem, and that leftover ".tex" then false-triggers slot_resolver.
    # write_slot_tex's own "is this source already a .tex" substring check
    # once it survives into the decoded PNG's filename (see
    # write_ported_tex -> write_slot_tex downstream).
    base = os.path.basename(tex_path)
    tex_idx = base.lower().find('.tex')
    stem = base[:tex_idx] if tex_idx >= 0 else os.path.splitext(base)[0]
    dds_tmp = os.path.join(temp_dir, f"{stem}_port_src.dds")
    dds_file.write_dds(dds, dds_tmp)
    return texconv_native.convert_to_png(dds_tmp, temp_dir)


# ── Channel unpack (inverse of _compose_channels) ───────────────────────────

def unpack_channels(png_path, slot_type, channel_maps=None, octahedral=False):
    """A decoded slot PNG -> ``{pbr_type: (h, w, 4) float32}``, one plane per
    semantic channel group the slot actually carries. Mirrors
    mdf_tex_processor_base._compose_channels in reverse, including the
    octahedral normal decode for the 3-in-1 normal slots.

    Returned in memory rather than as PNGs on disk: _compose_channels takes
    these straight back (``pbr_arrays=``), so a round trip through 8-bit files
    would only cost time and precision -- the octahedral decode produces
    genuinely continuous values that a PNG would quantise.
    """
    import bpy
    import numpy as np

    from .mdf_tex_processor_base import (BASE_SLOT_CHANNEL_MAPS, NORMAL_OCTAHEDRAL_SLOT_TYPES,
                                         _CH, image_to_array)
    from .re_normal_pack import decode_normal_ga

    if channel_maps is None:
        channel_maps = BASE_SLOT_CHANNEL_MAPS
    ch_map = channel_maps.get(slot_type)
    if ch_map is None:
        return {}

    tmp_name = "__mdf_port_unpack_src"
    if tmp_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[tmp_name])
    img = bpy.data.images.load(png_path, check_existing=False)
    img.name = tmp_name
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    pix = image_to_array(img)
    bpy.data.images.remove(img)

    pbr_arrays = {}

    def _plane(pbr_type):
        return pbr_arrays.setdefault(pbr_type, np.zeros((h, w, 4), dtype=np.float32))

    is_octahedral = octahedral and slot_type in NORMAL_OCTAHEDRAL_SLOT_TYPES
    if is_octahedral:
        x, y = decode_normal_ga(pix[:, :, _CH['G']], pix[:, :, _CH['A']])
        _plane('normal')[:, :, 0] = np.clip((x + 1.0) * 0.5, 0.0, 1.0)
        _plane('normal')[:, :, 1] = np.clip((y + 1.0) * 0.5, 0.0, 1.0)

    for out_ch, src in ch_map.items():
        if is_octahedral and out_ch in ('G', 'A'):
            # Already decoded above -- these two channels carry the packed
            # normal pair, not a plain per-channel value.
            continue
        if src is None or isinstance(src, (int, float)):
            continue
        pbr_type, ch_idx = src[0], src[1]
        invert = len(src) > 2 and src[2] is True
        data = pix[:, :, _CH[out_ch]].copy()
        if invert:
            data = 1.0 - data
        _plane(pbr_type)[:, :, ch_idx] = data

    return pbr_arrays


# ── Orchestration ────────────────────────────────────────────────────────────

def repack_slot(src_tex_path, src_slot_type, dst_slot_type, temp_dir, tex_name,
                src_channel_maps=None, dst_channel_maps=None, octahedral=False):
    """A source .tex, ported onto a (possibly different) destination slot type.

    Returns ``(kind, payload)``:

    * ``("tex", src_path)`` -- the two slots pack the same quantities into the
      same channels, so the pixels do not change at all and only the container
      has to.  Going through the codec anyway would spend a BC7 decode and a
      slower BC7 encode to arrive at *worse* data: block compression is lossy,
      so re-encoding an already-compressed texture loses a second generation
      for nothing.
    * ``("png", composed_path)`` -- layouts differ, so the channels genuinely
      have to be taken apart and rebuilt, and the result must be encoded.
      The tag is historical: the payload is whatever staging format
      ``_compose_channels`` writes (a TGA since the PNG round trip was dropped),
      and nothing dispatches on it beyond "is this already a .tex" --
      ``slot_resolver.write_slot_tex`` goes by the real extension.
    """
    from .mdf_tex_processor_base import BASE_SLOT_CHANNEL_MAPS, _compose_channels

    src_maps = src_channel_maps or BASE_SLOT_CHANNEL_MAPS
    dst_maps = dst_channel_maps or BASE_SLOT_CHANNEL_MAPS

    if layouts_equal(src_slot_type, dst_slot_type, src_maps, dst_maps):
        return "tex", src_tex_path

    png_path = decode_tex_to_png(src_tex_path, temp_dir)
    planes = unpack_channels(png_path, src_slot_type, channel_maps=src_maps,
                             octahedral=octahedral)
    composed = _compose_channels(dst_slot_type, {}, {}, temp_dir, tex_name,
                                 channel_maps=dst_maps, pbr_arrays=planes,
                                 octahedral=octahedral)
    if composed is None:
        raise ValueError(f"no channel map for destination slot type: {dst_slot_type}")
    return "png", composed


def rewrite_tex_container(src_tex_path, dst_tex_version, out_path):
    """Copy a .tex across to another game's container, pixels untouched.

    The two games' containers differ in version and in whether the mip data is
    GDeflate-compressed, but the compressed *pixel* payload is the same bytes,
    so this reads every mip and rewrites the wrapper.  All mips are carried:
    re-deriving them from mip 0 would quietly replace the ones the author
    shipped.
    """
    from . import tex_file

    dds = tex_file.read_tex_to_dds(src_tex_path, all_mips=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(tex_file.build_tex_from_dds(dds, dst_tex_version))
    return out_path


# ── Path resolution + write-out ──────────────────────────────────────────────

def resolve_source_disk_path(natives_root, mdf_path, tex_version):
    """Absolute path of a binding's on-disk .tex. Bindings store the mdf path
    with no natives/STM/ prefix and no version suffix (confirmed in
    mdf_material_convert_base.is_custom_tex_path's docstring) -- the inverse
    of make_disk_path, but from the stored string rather than its parts.

    Prefers the addon's own known tex_version for this game, but falls back
    to whatever version suffix is actually on disk when that exact file isn't
    there -- a game patch can bump the serializer version, or a file can have
    been written by an older/newer export tool, and a mod's natives/STM tree
    can genuinely carry more than one version side by side (confirmed on a
    real install: BaseName.tex.241106027 next to BaseName.tex.250813143).
    Insisting on the one version this addon happens to know about would
    report "not found" for a texture that is right there under a different
    number.
    """
    rel = mdf_path.strip('/\\').replace('\\', '/')
    base = os.path.join(natives_root, 'natives', 'STM', *rel.split('/'))
    exact = f"{base}.{tex_version}"
    if os.path.isfile(exact):
        return exact
    candidates = sorted(glob.glob(f"{base}.*"))
    return candidates[0] if candidates else exact


def write_ported_tex(source, dst_slot_type, dst_cfg, tex_name, dst_natives_root,
                     dst_base_path, temp_dir):
    """Write a ported slot out under the destination game's own on-disk
    convention.  *source* is repack_slot's ``(kind, payload)``.

    Returns (mdf_path, written) -- mdf_path is set (and the binding can point
    at it) even when dst_natives_root is empty; only the on-disk .tex write is
    skipped, per the "mod root is optional" decision."""
    from .mdf_tex_processor_base import make_mdf_path, make_disk_path, SRGB_SLOT_TYPES, _import_tex_utils
    from .slot_resolver import resolve_dds_format, write_slot_tex

    kind, payload = source
    mdf_path = make_mdf_path(dst_base_path, tex_name, dst_slot_type,
                             dst_cfg['abbrev_map'], dst_cfg['use_art_prefix'])
    if not dst_natives_root:
        return mdf_path, False

    disk_path = make_disk_path(dst_natives_root, dst_base_path, tex_name, dst_slot_type,
                               dst_cfg['abbrev_map'], dst_cfg['tex_version'], dst_cfg['use_art_prefix'])
    tex_version = dst_cfg['tex_version']

    if kind == "tex":
        rewrite_tex_container(payload, tex_version, disk_path)
        return mdf_path, True

    png_path = payload
    image_to_dds, dds_to_tex = _import_tex_utils()
    write_slot_tex(
        png_path, disk_path, temp_dir,
        dds_fmt=resolve_dds_format(dst_slot_type, SRGB_SLOT_TYPES),
        generate_mipmaps=True,
        image_to_dds=image_to_dds,
        dds_to_tex=lambda p, o: dds_to_tex(p, tex_version, o),
    )
    return mdf_path, True
