import bpy
import os
import json
import tempfile
import shutil
import time

from .i18n import T
from .slot_resolver import resolve_dds_format, write_slot_tex
from .re_normal_pack import encode_normal_ga

# ── PBR Constants ──────────────────────────────────────────────────────────────

#: cavity/translucency: RE4/RE9's ATOC/ACOT/SCOT/NRRC/NRRT slots genuinely
#: pack these into previously-assumed-constant channels (confirmed against
#: real presets, not a guess -- see games/re4/shader_defs.py and
#: games/re9/shader_defs.py's module docstrings). MHWS's
#: AlphaTranslucentOcclusionSSSMap shares the same engine-wide convention on
#: its G channel (confirmed by the user), so this is a shared-engine fact,
#: not an RE4/RE9-only one, and belongs in the global list rather than a
#: per-game addition.
PBR_TYPES = ['color', 'alpha', 'emissive', 'normal', 'roughness', 'metallic', 'ao',
             'cavity', 'translucency']

_PBR_TYPE_LABEL_KEYS = {
    'color':        "core.mdf_tex_processor_base.pbr_color",
    'alpha':        "core.mdf_tex_processor_base.pbr_alpha",
    'emissive':     "core.mdf_tex_processor_base.pbr_emissive",
    'normal':       "core.mdf_tex_processor_base.pbr_normal",
    'roughness':    "core.mdf_tex_processor_base.pbr_roughness",
    'metallic':     "core.mdf_tex_processor_base.pbr_metallic",
    'ao':           "core.mdf_tex_processor_base.pbr_ao",
    'cavity':       "core.mdf_tex_processor_base.pbr_cavity",
    'translucency': "core.mdf_tex_processor_base.pbr_translucency",
}

class _LiveTranslatedLabels(dict):
    """dict whose __getitem__ re-evaluates T() on every access.

    PBR_TYPE_LABELS is consumed elsewhere as a plain subscript
    (``PBR_TYPE_LABELS[pt]``) by files outside this migration's scope
    (core/mdf_tex_processor_ui_base.py, games/*/mrl3_tex_processor_ui.py).
    Subclassing dict and overriding __getitem__ lets those call sites keep
    working unchanged while still picking up a language switch at draw time,
    instead of requiring every caller to switch to a get_..._callback()
    function call (pattern 7 doesn't fit here since callers use [] indexing,
    not an items= callback)."""
    def __getitem__(self, key):
        return T(dict.__getitem__(self, key))

PBR_TYPE_LABELS = _LiveTranslatedLabels(_PBR_TYPE_LABEL_KEYS)

PBR_DEFAULTS = {
    'color':        [0.0, 0.0, 0.0, 1.0],
    'alpha':        [1.0, 1.0, 1.0, 1.0],
    'emissive':     [0.0, 0.0, 0.0, 0.0],
    'normal':       [0.5, 0.5, 1.0, 1.0],
    'roughness':    [1.0, 1.0, 1.0, 1.0],
    'metallic':     [0.0, 0.0, 0.0, 1.0],
    'ao':           [1.0, 1.0, 1.0, 1.0],
    # 1-neutral (multiplicative, like roughness/ao): unconnected means "no
    # extra darkening".
    'cavity':       [1.0, 1.0, 1.0, 1.0],
    # 0-neutral (additive, like metallic): unconnected means "none".
    'translucency': [0.0, 0.0, 0.0, 1.0],
}

# Only these PBR types expose a per-channel selector in the UI
PBR_CHANNEL_SELECTABLE = {'alpha', 'roughness', 'metallic', 'ao', 'cavity', 'translucency'}

# Slot types that should be converted as BC7_UNORM_SRGB (colour / emissive data)
SRGB_SLOT_TYPES = {'BaseDielectricMap', 'BaseAlphaMap', 'EmissiveMap', 'Emissive_ColorMap', 'BaseShiftMap'}

# Slot types whose G/A pair needs the hemi-octahedral encode (core/re_normal_pack.py)
# rather than a plain channel copy -- the ones that pack a third quantity (AO,
# cavity) into B, leaving no room for a conventional two-channel normal.
# NormalRoughness/NormalRoughnessMap/NRMR_NRRTMap keep their normal in R/G and
# are correctly a plain copy already; not game-specific, RE Mesh Editor's own
# texture packer branches on this same slot distinction, not on which game.
NORMAL_OCTAHEDRAL_SLOT_TYPES = {'NormalRoughnessOcclusionMap', 'NormalRoughnessCavityMap',
                                'NormalRoughnessTranslucentMap'}


def octahedral_normals_prop():
    """The "my normals are hemi-octahedral encoded" opt-in, shared verbatim by
    every processor, every generator and the MDF port.

    **Default off, and that is the point** (user's decision, 2026-08-15): the
    encoding is real and the engine does use it, but hardly anyone authoring for
    these games applies it -- they feed an ordinary normal map into the slot and
    never notice. Encoding by default would silently mangle that common case,
    so this is opt-in for the people who know they need it.

    The description carries both languages: a BoolProperty's tooltip is baked at
    registration, before the UI language is known, so it cannot go through T().
    """
    return bpy.props.BoolProperty(
        name="Hemi-Octahedral Normals",
        description=(
            "Do not enable this if you do not know what it is.\n"
            "From Wilds onward, the non-standard normal slots (NRRO, NRRC, NRRT) hold "
            "hemi-octahedral encoded normals, which preserve normal detail better.\n"
            "如果你不知道这是什么，不要勾选。\n"
            "从荒野起，NRRO、NRRC、NRRT 等非常规法线槽都使用半八面体编码的法线，"
            "这会让法线的细节表现更好。"
        ),
        default=False,
    )

_CH           = {'R': 0, 'G': 1, 'B': 2, 'A': 3}
_CH_ENUM_ITEMS = [('R', 'R', ''), ('G', 'G', ''), ('B', 'B', ''), ('A', 'A', '')]

# ── Base texture data (all RE Engine games) ────────────────────────────────────

BASE_TEXTURE_TYPE_ABBREV = {
    'BaseDielectricMap':               'ALBD',
    'BaseAlphaMap':                    'BaseAlpha',
    'BaseShiftMap':                    'BaseShift',
    'NormalRoughnessOcclusionMap':     'NRRO',
    'NormalRoughness':                 'NRMR',
    'NormalRoughnessCavityMap':        'NRRC',
    'EmissiveMap':                     'EMI',
    'Emissive_ColorMap':               'EMIC',
    'AlphaTranslucentOcclusionSSSMap': 'ATOS',
    'NormalRoughnessMap':              'NRMR',
    'SSSCavityOcclusionTranslucentMap': 'SCOT',
    'AlphaCavityOcclusionTranslucentMap': 'ACOT',
    'AlphaTranslucentOcclusionCavityMap': 'ATOC',
    # MHRS
    'NRMR_NRRTMap':                    'NRMR',   # same layout/abbrev as NormalRoughnessMap
    'AlphaMap':                        'ALPHA',
    'UserColorchangeMap':              'UCC',
    'FurVelocityMap':                  'FVEL',   # matches games/mhwi/mrl3_tex_processor.py's MHWI_ABBREV_MAP
    'FxMap':                           'FX',      # matches games/mhwi/mrl3_tex_processor.py's MHWI_ABBREV_MAP
    'FurTex':                          'FUR',
}

# Channel composition maps.  Values may be:
#   (pbr_type, channel_index[, True=invert]) — source from PBR image
#   None                                     — constant 0.0
#   float/int                                — constant value (e.g. 1.0 = white)
BASE_SLOT_CHANNEL_MAPS = {
    'BaseDielectricMap': {
        'R': ('color',    0),
        'G': ('color',    1),
        'B': ('color',    2),
        'A': ('metallic', 0, True),
    },
    'BaseAlphaMap': {
        'R': ('color', 0),
        'G': ('color', 1),
        'B': ('color', 2),
        'A': ('alpha', 0),
    },
    'BaseShiftMap': {
        'R': ('color', 0),
        'G': ('color', 1),
        'B': ('color', 2),
        'A': None,
    },
    'NormalRoughnessOcclusionMap': {
        'R': ('roughness', 0),
        'G': ('normal',    1),
        'B': ('ao',        0),
        'A': ('normal',    0),
    },
    # B is **not** the normal's Z component; it is normally just white. The
    # shader does read it -- writing 0, which is what `None` means in this
    # table, renders the whole model as grey metal -- so it cannot be left to a
    # default either.
    #
    # Both of the more "correct-sounding" alternatives were measured against
    # vanilla textures from three games and rejected:
    #
    # * *Reconstruct Z from X/Y.* Vanilla does not do this. RE9's B is flat
    #   white (std 0.0016), RE4's is 97% white; MHRS varies most, but its B
    #   histogram is bimodal (12% at 0.2-0.3, 82% at 0.9-1.0), which sqrt(1 -
    #   x^2 - y^2) cannot produce -- that tapers smoothly from 1. Among the
    #   pixels that are not white, B does not track z at all (mean|B - z| 0.19
    #   for RE4, 0.30 for MHRS). Reconstructing would write a third thing that
    #   matches neither white nor whatever those pixels really are.
    # * *Carry the source slot's own B across.* Actively dangerous: in NRRO
    #   that channel is AO. It only appears to work when the AO map is near
    #   white, and puts dark values into B wherever the AO has real creases --
    #   a localised failure that reads as "shadows look a bit heavy" rather
    #   than an obvious break.
    #
    # White matches vanilla RE9 to 0.0002 and RE4 to 0.013, is what Capcom's
    # texture documentation says to do, and is what the reporter's own working
    # RE4 mod ships across a whole character. The minority of non-white pixels
    # in vanilla MHRS/RE4 is unexplained; it is a minority, and guessing at it
    # with z would not reproduce it anyway.
    'NormalRoughness': {
        'R': ('normal',    0),
        'G': ('normal',    1),
        'B': 1.0,
        'A': ('roughness', 0),
    },
    'NormalRoughnessMap': {
        'R': ('normal',    0),
        'G': ('normal',    1),
        'B': 1.0,
        'A': ('roughness', 0),
    },
    'NRMR_NRRTMap': {   # MHRS — same layout as NormalRoughnessMap
        'R': ('normal',    0),
        'G': ('normal',    1),
        'B': 1.0,
        'A': ('roughness', 0),
    },
    # RE4/RE9's NRRC (see games/re4/shader_defs.py's module docstring): B
    # genuinely packs cavity data -- an earlier version of this dict assumed
    # RE4/RE9 forced B to a constant, which was wrong (confirmed by the user).
    'NormalRoughnessCavityMap': {
        'R': ('roughness', 0),
        'G': ('normal',    1),
        'B': ('cavity',    0),
        'A': ('normal',    0),
    },
    # NormalRoughnessCavityMap's twin: identical layout, B carries
    # translucency instead of cavity.
    'NormalRoughnessTranslucentMap': {
        'R': ('roughness',    0),
        'G': ('normal',       1),
        'B': ('translucency', 0),
        'A': ('normal',       0),
    },
    'EmissiveMap': {
        'R': ('emissive', 0),
        'G': ('emissive', 1),
        'B': ('emissive', 2),
        'A': ('emissive', 3),
    },
    'Emissive_ColorMap': {
        'R': ('emissive', 0),
        'G': ('emissive', 1),
        'B': ('emissive', 2),
        'A': ('emissive', 3),
    },
    # G genuinely carries translucency (confirmed by the user, and confirmed
    # to be a shared engine convention -- MHWS's own AlphaTranslucentOcclusionSSSMap
    # is this exact slot too, not just RE4/RE9's Emissive one). A stays a
    # constant -- no further quantity confirmed there.
    'AlphaTranslucentOcclusionSSSMap': {
        'R': ('alpha', 0),
        'G': ('translucency', 0),
        'B': ('ao',   0),
        'A': 1.0,
    },
    # G genuinely carries cavity (confirmed by the user). R/A stay constants
    # -- SSSCavityOcclusionTranslucentMap has no real opacity data (R) and no
    # confirmed translucency channel (A).
    'SSSCavityOcclusionTranslucentMap': {
        'R': 1.0,
        'G': ('cavity', 0),
        'B': ('ao', 0),
        'A': 1.0,
    },
    # G/A genuinely carry cavity/translucency respectively (confirmed by the user).
    'AlphaCavityOcclusionTranslucentMap': {
        'R': ('alpha', 0),
        'G': ('cavity', 0),
        'B': ('ao', 0),
        'A': ('translucency', 0),
    },
    # Same four quantities as AlphaCavityOcclusionTranslucentMap, but G/A
    # swapped (translucency/cavity respectively) -- confirmed by the user.
    'AlphaTranslucentOcclusionCavityMap': {
        'R': ('alpha', 0),
        'G': ('translucency', 0),
        'B': ('ao', 0),
        'A': ('cavity', 0),
    },
}

BASE_COMMON_SLOT_TYPES = {
    'BaseDielectricMap',
    'BaseAlphaMap',
    'BaseShiftMap',
    'EmissiveMap',
    'Emissive_ColorMap',
    'NormalRoughnessOcclusionMap',
    'NormalRoughnessCavityMap',
    'NormalRoughnessTranslucentMap',
    'NormalRoughness',
    'NormalRoughnessMap',
    'AlphaTranslucentOcclusionSSSMap',
    'AlphaTranslucentOcclusionCavityMap',
    'AlphaCavityOcclusionTranslucentMap',
    'SSSCavityOcclusionTranslucentMap',
    # MHRS
    'NRMR_NRRTMap',
    'AlphaMap',
    'UserColorchangeMap',
    'FurVelocityMap',
    'FxMap',
    'FurTex',
}

BASE_NULL_TEX_BY_TYPE = {
    'MP_noise':                      'MasterMaterial/Textures/MP_noise_MSK4.tex',
    'Wind_Effect_VolumeMap':         'RE_ENGINE_LIBRARY/VFX_Library/Texture/TEX_Vectorfield/tex_capcom_vectorfield_0003_MSK4.tex',
    'BaseDielectricMap':             'systems/rendering/NullBlack.tex',
    'BaseAlphaMap':                  'systems/rendering/NullBlack.tex',
    'NormalRoughnessOcclusionMap':   'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'NormalRoughnessCavityMap':      'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'NormalRoughnessTranslucentMap': 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    # NRMR, not NRRO. Two different slots with two different channel layouts,
    # so the NRRO null is the wrong texture here even though every game ships
    # it (checked against assets/<game>/vanilla_tex_paths.txt, which is the
    # authoritative list -- a pak extract on disk can be partial and is not).
    # Reported from a MHWS -> RE4 port that would not load in game.
    'NormalRoughnessMap':            'systems/rendering/NullNormalRoughness.tex',
    'EmissiveMap':                   'systems/rendering/NullBlack.tex',
    'Emissive_ColorMap':             'systems/rendering/NullBlack.tex',
    'FxMap':                         'MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex',
    'AlphaTranslucentOcclusionSSSMap': 'systems/rendering/NullATOS.tex',
    'AlphaTranslucentOcclusionCavityMap': 'systems/rendering/NullATOS.tex',
    'SSSCavityOcclusionTranslucentMap': 'systems/rendering/NullATOS.tex',
    'AlphaCavityOcclusionTranslucentMap': 'systems/rendering/NullATOS.tex',
    'noisemap':                      'MasterMaterial/Textures/bluenoise_msk1.tex',
    'DetailMaskMap':                 'systems/rendering/NullBlack.tex',
    'Detail_ALBD_R':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_R':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'Detail_ALBD_G':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_G':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'Detail_ALBD_B':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_B':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'Detail_ALBD_A':                 'systems/rendering/NullGray.tex',
    'Detail_NRRH_A':                 'systems/rendering/NullNormalRoughnessOcclusion.tex',
    'PanoramaMap':                   'MasterMaterial/Textures/kirakira_PAN_ALB.tex',
    'VectorEmitMap':                 'MasterMaterial/Textures/eye_VectorEmit_MSK3.tex',
    'VFX_Texture2D':                 'MasterMaterial/Textures/VFX_Uber/VFX_Uber_MSK4.tex',
    'VFX_Texture3D':                 'MasterMaterial/Textures/VFX_Uber/VFX_Uber3D_MSK4.tex',
    'Hair_Height_SpecMask_Shift_Map':'systems/rendering/NullWhite.tex',
    'HairOverMap':                   'systems/rendering/NullGray.tex',
    'MultiBlend_ALBDMap':            'systems/rendering/NullGray.tex',
    'MultiBlend_NRMMap':             'systems/rendering/NullNormal.tex',
    'GpuWind_MaskMap':               'systems/rendering/NullWhite.tex',
    'ColorLayer_MaskMap':            'systems/rendering/NullBlack.tex',
    'ColorLayer_DetailMaskMap':      'systems/rendering/NullBlack.tex',
    'Ripple_1Dtex':                  'MasterMaterial/Textures/hagitori_ripple_ALB.tex',
    'Ripple_Texture3D':              'MasterMaterial/Textures/Noise3D_MSK3.tex',
    'MaskMap':                       'systems/rendering/NullBlack.tex',
    'DetailMap':                     'systems/rendering/NullGray.tex',
    'BaseShiftMap':                  'systems/rendering/NullBlack.tex',
    # MHRS (per RE Mesh Editor's tex_bindings_null.json, "generic"/MHRSB entries)
    'NRMR_NRRTMap':                  'systems/rendering/NullNormalRoughness.tex',
    'AlphaMap':                      'systems/rendering/NullWhite.tex',
    'UserColorchangeMap':            'systems/rendering/NullBlack.tex',
    'FurVelocityMap':                'MasterMaterial/Textures/NullFurVelocity.tex',
    'FurTex':                        'systems/rendering/NullBlack.tex',
}

# ── Factory helpers ────────────────────────────────────────────────────────────

def make_null_checker(null_tex_by_type):
    """Return an is_null(path) -> bool for the given null_tex_by_type dict."""
    paths_set = {v.replace('\\', '/').lower() for v in null_tex_by_type.values()}
    def is_null(binding_path):
        p = binding_path.replace('\\', '/').lower()
        if p.startswith('natives/stm/'):
            p = p[len('natives/stm/'):]
        return p in paths_set
    return is_null

def make_collection_update_cb(is_null_fn):
    """Return an update callback for a mdf_collection PointerProperty."""
    def _on_collection_update(self, context):
        try:
            col = self.mdf_collection
            if col:
                _do_refresh(self, col, context.scene, is_null_fn=is_null_fn)
            else:
                if self.mdf_loaded_collection:
                    _save_col_state(context.scene, self.mdf_loaded_collection,
                                    {m.material_name: _capture_material_state(m)
                                     for m in self.materials})
                self.materials.clear()
                self.mdf_loaded_collection = ""
        except Exception as e:
            print(f"[MDF Tex] Auto-refresh error: {e}")
    return _on_collection_update


def make_mdf_path(base_path, tex_name, slot_type, abbrev_map, use_art_prefix=True):
    """Path string stored in the MDF2 binding (no version suffix)."""
    abbrev = abbrev_map.get(slot_type, slot_type)
    base   = base_path.strip('/\\').replace('\\', '/')
    return f"Art/{base}/{tex_name}_{abbrev}.tex" if use_art_prefix else f"{base}/{tex_name}_{abbrev}.tex"


def make_disk_path(natives_root, base_path, tex_name, slot_type, abbrev_map, tex_version,
                   use_art_prefix=True):
    """Absolute filesystem path for the .tex file."""
    abbrev = abbrev_map.get(slot_type, slot_type)
    parts  = base_path.strip('/\\').replace('\\', '/').split('/')
    mid    = os.path.join('Art', *parts) if use_art_prefix else os.path.join(*parts)
    rel    = os.path.join('natives', 'STM', mid, f"{tex_name}_{abbrev}.tex.{tex_version}")
    return os.path.join(natives_root, rel)


# ── Native texture conversion (no external addon) ──────────────────────────────
# Drop-in replacements for RE Mesh Editor's re_tex_utils.ImageListToDDS/DDSToTex,
# backed by our own bundled texconv + .tex writer (core/texconv_native.py,
# core/tex_file.py) instead of the external RE Mesh Editor addon.

def _ImageListToDDS(imageConvertList, outDir, generateMipMaps, mipQuality='FAST'):
    """mipQuality: 'FAST' (texconv's own recursive CUBIC pass) or 'QUALITY'
    (core.texconv_native.convert_to_dds_area_mips -- box-averages every level
    straight from the source instead of recursively re-filtering, see that
    function's docstring). QUALITY needs power-of-two dimensions; falls back
    to FAST automatically otherwise (that requirement is already the norm for
    these game textures, so this is the rare case, not the common one)."""
    from . import texconv_native
    for in_path, dds_format in imageConvertList:
        try:
            if generateMipMaps and mipQuality == 'QUALITY':
                try:
                    texconv_native.convert_to_dds_area_mips(in_path, dds_format, outDir)
                    continue
                except ValueError as err:
                    print(f"[mip quality] falling back to Fast for {in_path}: {err}")
            texconv_native.convert_to_dds(in_path, dds_format, outDir, generate_mips=generateMipMaps)
        except Exception as err:
            print(f"Failed to convert {in_path} - {err}")


def _DDSToTex(ddsPathList, texVersion, outPath):
    from . import tex_file
    if len(ddsPathList) != 1:
        raise NotImplementedError("Texture arrays are not supported")
    tex_file.write_tex_from_dds(ddsPathList[0], texVersion, outPath)


def _import_tex_utils():
    """Return (ImageListToDDS, DDSToTex) — Modding-Toolkit's own native
    implementation; no external addon required."""
    return _ImageListToDDS, _DDSToTex


# ── Pixel buffer transfer ──────────────────────────────────────────────────────
# bpy's pixel access has one fast path and one very slow one, and the difference
# dominates every compose.  ``img.pixels[:]`` materialises one Python float per
# channel -- 67 million objects for a 4K texture -- and ``pixels[:] = arr.tolist()``
# builds the same list in reverse.  foreach_get/foreach_set move the identical
# bytes through a preallocated buffer in C instead.

def image_to_array(img):
    """An image's pixels as an ``(h, w, 4)`` float32 array."""
    import numpy as np
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(h, w, 4)


def array_to_image(img, arr):
    """Write an ``(h, w, 4)`` array back into *img*."""
    import numpy as np
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())


# ── Channel composition ────────────────────────────────────────────────────────

def channel_maps_consume_ao(channel_maps):
    """True when this game has a slot that actually stores AO.

    MHWI does not: MHWI_SLOT_CHANNEL_MAPS never references 'ao', and RMTMap's
    blue channel is translucency.  The RE games do, via NRRO.B.  That difference
    decides whether an AO map has to be baked into the albedo instead — doing
    both would darken the result twice.
    """
    for ch_map in (channel_maps or {}).values():
        for src in ch_map.values():
            if isinstance(src, tuple) and src and src[0] == 'ao':
                return True
    return False


def _compose_channels(slot_type, pbr_paths, pbr_channels, temp_dir, tex_name, pbr_inv=None,
                       channel_maps=None, normal_flip_g=False,
                       bake_ao_into_color=False, ao_strength=1.0,
                       pbr_arrays=None, octahedral=True):
    """Compose a packed texture from PBR inputs for the given slot type.
    channel_maps: optional override; defaults to BASE_SLOT_CHANNEL_MAPS.
    Channel map values: tuple (pbr_type, ch_idx[, True]) | None (=0.0) | float (constant).
    normal_flip_g: when True, inverts the G channel of the normal map (OpenGL to DirectX).
    bake_ao_into_color: multiply the AO map into this slot's colour channels.  For
        a game with no AO slot that is the only way to keep an AO map at all --
        see channel_maps_consume_ao.  ao_strength lerps white -> map, matching
        the packed shader's AO Strength so preview and export agree.
    pbr_arrays: ``{pbr_type: (h, w, 4) float32}`` supplied in process, used instead
        of loading *pbr_paths* from disk.  For a caller that just produced the
        planes itself (the cross-game port) this skips writing each one to an
        8-bit PNG and reading it back -- which is not only the slower path but a
        lossier one, since values that are genuinely continuous (a decoded
        octahedral normal) get quantised on the way through.
    """
    if pbr_inv is None:
        pbr_inv = {}
    if channel_maps is None:
        channel_maps = BASE_SLOT_CHANNEL_MAPS
    import numpy as np

    ch_map = channel_maps.get(slot_type)
    if ch_map is None:
        print(f"[MDF Tex] No channel map for slot type: {slot_type}")
        return None

    needed_types = {src[0] for src in ch_map.values()
                    if src is not None and isinstance(src, tuple)}
    # No channel map references 'ao' when it is being baked into the colour, so
    # it has to be requested explicitly or the loader would skip it.
    if bake_ao_into_color:
        needed_types.add('ao')
    loaded = {}

    if pbr_arrays:
        # Handed straight over in memory, skipping a round trip through 8-bit PNGs.
        #
        # Planes are scaled to the largest, exactly as the disk path below does.
        # They used to be *dropped* instead, on the grounds that a caller decoding
        # one image can only produce one size -- true of core/mdf_port_tex.py, and
        # not true in general: the MRL3 port decodes a material's several packed
        # slots, and MHWI is free to give a 512px RMT to a 2048px albedo.  Dropping
        # there costs the material its roughness and metallic with nothing logged,
        # which is the worst way for this to fail.
        for pbr_type in needed_types:
            arr = pbr_arrays.get(pbr_type)
            if arr is not None:
                loaded[pbr_type] = arr
        if not loaded:
            return None
        ref_h, ref_w = max((a.shape[:2] for a in loaded.values()),
                           key=lambda hw: hw[0] * hw[1])
        for pbr_type, arr in list(loaded.items()):
            h, w = arr.shape[:2]
            if (h, w) == (ref_h, ref_w):
                continue
            print(f"[MDF Tex] scaling {pbr_type} plane {w}x{h} -> {ref_w}x{ref_h}")
            rows = (np.arange(ref_h) * h // ref_h).clip(0, h - 1)
            cols = (np.arange(ref_w) * w // ref_w).clip(0, w - 1)
            loaded[pbr_type] = arr[rows[:, None], cols[None, :]]
    else:
        # First pass: load all images and determine the largest size as reference.
        # Using the largest (not the first) avoids 256×256 SOLID images accidentally
        # shrinking larger baked or source textures due to non-deterministic set order.
        raw_imgs = {}
        ref_w = ref_h = 0
        for pbr_type in needed_types:
            img_path = pbr_paths.get(pbr_type, '')
            if not img_path or not os.path.isfile(img_path):
                continue
            tmp_name = f"__mdf_compose_tmp_{pbr_type}"
            if tmp_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[tmp_name])
            img = bpy.data.images.load(img_path, check_existing=False)
            img.name = tmp_name
            img.colorspace_settings.name = 'Non-Color'
            iw, ih = img.size
            if iw > ref_w:
                ref_w, ref_h = iw, ih
            raw_imgs[pbr_type] = img

        if not raw_imgs:
            return None

        if ref_w == 0:
            ref_w = ref_h = 1024

        # Second pass: scale down any smaller images and convert to numpy arrays.
        for pbr_type, img in raw_imgs.items():
            iw, ih = img.size
            if iw != ref_w or ih != ref_h:
                img.scale(ref_w, ref_h)
            loaded[pbr_type] = image_to_array(img)
            bpy.data.images.remove(img)

    result = np.zeros((ref_h, ref_w, 4), dtype=np.float32)

    for out_ch, src in ch_map.items():
        out_i = _CH[out_ch]
        if src is None:
            # Alpha channel (index 3) defaults to opaque to avoid premultiplied-alpha
            # issues when texconv converts the PNG to DDS (A=0 would zero all channels).
            result[:, :, out_i] = 1.0 if out_i == 3 else 0.0
            continue
        if isinstance(src, (int, float)):
            result[:, :, out_i] = float(src)
            continue
        pbr_type = src[0]
        in_ch_i  = src[1]
        invert   = len(src) > 2 and src[2] is True
        if pbr_type in PBR_CHANNEL_SELECTABLE:
            override = pbr_channels.get(pbr_type)
            if override:
                in_ch_i = _CH.get(override, in_ch_i)
        pix = loaded.get(pbr_type)
        if pix is None:
            val = PBR_DEFAULTS.get(pbr_type, [0.0]*4)[in_ch_i]
            if invert:
                val = 1.0 - val
            result[:, :, out_i] = val
        else:
            data = pix[:, :, in_ch_i].copy()
            if invert:
                data = 1.0 - data
            if pbr_type in PBR_CHANNEL_SELECTABLE and pbr_inv.get(pbr_type):
                data = 1.0 - data
            if normal_flip_g and pbr_type == 'normal' and in_ch_i == 1:
                data = 1.0 - data
            result[:, :, out_i] = data

    if octahedral and slot_type in NORMAL_OCTAHEDRAL_SLOT_TYPES:
        # These pack a third quantity (AO/cavity) into B, which a plain
        # two-channel normal has no room for -- see core/re_normal_pack.py.
        # Runs after normal_flip_g above, so that toggle still corrects a
        # source authored in the other Y convention before this encodes it.
        g = result[:, :, _CH['G']]
        a = result[:, :, _CH['A']]
        result[:, :, _CH['G']], result[:, :, _CH['A']] = encode_normal_ga(g, a)

    if bake_ao_into_color:
        ao_pix = loaded.get('ao')
        if ao_pix is not None:
            strength = min(max(float(ao_strength), 0.0), 1.0)
            # Same channel/invert override as the channel-map path above --
            # this branch has no ch_map entry for 'ao' to read them from
            # (that's the whole reason it exists: games with no AO-consuming
            # slot at all), so it has to consult pbr_channels/pbr_inv itself.
            ao_ch_i = _CH.get(pbr_channels.get('ao'), 0)
            ao_data = ao_pix[:, :, ao_ch_i]
            if pbr_inv.get('ao'):
                ao_data = 1.0 - ao_data
            # lerp(white, ao, strength): strength 0 leaves the colour untouched,
            # which is the same curve the shader's AO Strength slider follows.
            occl = 1.0 - strength * (1.0 - ao_data)
            # Colour channels only. Alpha carries opacity or metallic depending
            # on the slot, and darkening either would be wrong.
            colour_channels = [
                _CH[ch] for ch, src in ch_map.items()
                if isinstance(src, tuple) and src and src[0] == 'color'
            ]
            for out_i in colour_channels:
                result[:, :, out_i] = result[:, :, out_i] * occl
            print(f"[MDF Tex] {slot_type}: AO baked into "
                  f"{len(colour_channels)} colour channel(s) at strength {strength:.2f}")

    abbrev   = BASE_TEXTURE_TYPE_ABBREV.get(slot_type, slot_type)
    # Staged as TGA rather than PNG: this file exists only to hand the buffer to
    # texconv, and a zlib round trip is by far the most expensive thing that
    # happened to it.  Same 8 bits per channel either way, so the compressor sees
    # identical bytes -- see core/tga_file.py for why not DDS.
    out_name = f"{tex_name}_{abbrev}_composed.tga"
    out_path = os.path.join(temp_dir, out_name)

    from . import tga_file
    tga_file.write_tga_rgba8(out_path, result)
    return out_path


# ── State persistence ──────────────────────────────────────────────────────────

def _capture_material_state(m):
    return {
        'pbr':            {pt: getattr(m.pbr, pt) for pt in PBR_TYPES},
        'pbr_chs':        {pt: getattr(m.pbr, f"{pt}_ch") for pt in PBR_CHANNEL_SELECTABLE},
        'pbr_inv':        {pt: getattr(m.pbr, f"{pt}_inv") for pt in PBR_CHANNEL_SELECTABLE},
        'normal_flip_g':  m.pbr.normal_flip_g,
        'slots':          {s.texture_type: {'mode': s.mode, 'direct_image': s.direct_image}
                           for s in m.slots},
    }

def _save_col_state(scene, col_name, state):
    scene[f"mdf_tex_saved__{col_name}"] = json.dumps(state)

def _load_col_state(scene, col_name):
    raw = scene.get(f"mdf_tex_saved__{col_name}", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _do_refresh(settings, col, scene, is_null_fn=None):
    """Populate settings.materials from an MDF2 collection, preserving prior config."""
    if is_null_fn is None:
        is_null_fn = make_null_checker(BASE_NULL_TEX_BY_TYPE)

    loaded_name = settings.mdf_loaded_collection
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

    for obj in col.objects:
        if obj.get("~TYPE") != "RE_MDF_MATERIAL":
            continue
        mat_data = getattr(obj, 're_mdf_material', None)
        if mat_data is None:
            continue

        item = settings.materials.add()
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

        for binding in mat_data.textureBindingList_items:
            slot               = item.slots.add()
            slot.texture_type  = binding.textureType
            slot.original_path = binding.path
            if binding.textureType in prev_slots:
                sd = prev_slots[binding.textureType]
                if isinstance(sd, dict):
                    slot.mode         = sd.get('mode', 'SKIP')
                    slot.direct_image = sd.get('direct_image', '')
                else:
                    slot.mode, slot.direct_image = sd
            elif is_null_fn(binding.path):
                slot.mode = 'DEFAULT'
        count += 1

    _save_col_state(scene, new_name,
                    {m.material_name: _capture_material_state(m) for m in settings.materials})
    settings.mdf_loaded_collection = new_name
    return count


# ── MDF collection poll ────────────────────────────────────────────────────────

def mdf_collection_poll(self, col):
    return col.get("~TYPE") == "RE_MDF_COLLECTION" or col.name.endswith(".mdf2")


# ── Shared PropertyGroups ──────────────────────────────────────────────────────

class MdfTexPBRInputs(bpy.types.PropertyGroup):
    color:        bpy.props.StringProperty(name="Base Color (Albedo)", subtype='FILE_PATH')
    alpha:        bpy.props.StringProperty(name="Alpha Mask",          subtype='FILE_PATH')
    emissive:     bpy.props.StringProperty(name="Emissive",            subtype='FILE_PATH')
    normal:       bpy.props.StringProperty(name="Normal",              subtype='FILE_PATH')
    roughness:    bpy.props.StringProperty(name="Roughness",           subtype='FILE_PATH')
    metallic:     bpy.props.StringProperty(name="Metallic",            subtype='FILE_PATH')
    ao:           bpy.props.StringProperty(name="AO",                  subtype='FILE_PATH')
    cavity:       bpy.props.StringProperty(name="Cavity",               subtype='FILE_PATH')
    translucency: bpy.props.StringProperty(name="Translucency",         subtype='FILE_PATH')
    alpha_ch:        bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    roughness_ch:    bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    metallic_ch:     bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    ao_ch:           bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    cavity_ch:       bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    translucency_ch: bpy.props.EnumProperty(name="", items=_CH_ENUM_ITEMS, default='R')
    alpha_inv:        bpy.props.BoolProperty(name="Invert", default=False)
    roughness_inv:    bpy.props.BoolProperty(name="Invert", default=False)
    metallic_inv:     bpy.props.BoolProperty(name="Invert", default=False)
    ao_inv:           bpy.props.BoolProperty(name="Invert", default=False)
    cavity_inv:       bpy.props.BoolProperty(name="Invert", default=False)
    translucency_inv: bpy.props.BoolProperty(name="Invert", default=False)
    normal_flip_g: bpy.props.BoolProperty(name="GL>DX", default=False,
                                          description="Flip the normal map's G channel when composing (OpenGL to DirectX)")


_mdf_tex_slot_mode_items_cache = []

def get_mdf_tex_slot_mode_items(self, context):
    global _mdf_tex_slot_mode_items_cache
    _mdf_tex_slot_mode_items_cache = [
        ('COMPOSE', T("core.mdf_tex_processor_base.mode_compose"),
                    T("core.mdf_tex_processor_base.mode_compose_desc"), 'NODE_COMPOSITING', 0),
        ('DIRECT',  T("core.mdf_tex_processor_base.mode_direct"),
                    T("core.mdf_tex_processor_base.mode_direct_desc"),  'IMAGE_DATA',       1),
        ('DEFAULT', T("core.mdf_tex_processor_base.mode_default"),
                    T("core.mdf_tex_processor_base.mode_default_desc"), 'LINKED',           2),
        ('SKIP',    T("core.mdf_tex_processor_base.mode_skip"),
                    T("core.mdf_tex_processor_base.mode_skip_desc"),    'RADIOBUT_OFF',     3),
    ]
    return _mdf_tex_slot_mode_items_cache


class MdfTexSlotItem(bpy.types.PropertyGroup):
    texture_type:  bpy.props.StringProperty(name="Texture Type")
    original_path: bpy.props.StringProperty(name="Original Path")
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=get_mdf_tex_slot_mode_items,
        default=3,  # 'SKIP' — dynamic items require an int index default
    )
    direct_image: bpy.props.StringProperty(name="Direct Image", subtype='FILE_PATH')


class MdfTexMaterialItem(bpy.types.PropertyGroup):
    material_obj_name: bpy.props.StringProperty()
    material_name:     bpy.props.StringProperty()
    expanded:          bpy.props.BoolProperty(default=False)
    pbr_expanded:      bpy.props.BoolProperty(default=False)
    other_expanded:    bpy.props.BoolProperty(default=False)
    generate_mipmaps:  bpy.props.BoolProperty(name="Generate MipMaps", default=True)
    mipmap_strategy:   bpy.props.EnumProperty(
        name="Mipmap Strategy",
        items=lambda self, ctx: [
            ('FAST', T("core.mip_strategy.fast"), T("core.mip_strategy.fast_desc")),
            ('QUALITY', T("core.mip_strategy.quality"), T("core.mip_strategy.quality_desc")),
        ],
        default=0,  # 'FAST' -- dynamic items need an int index default
    )
    skip_textures:     bpy.props.BoolProperty(
        name="Material Only",
        description="Skip texture composition/conversion; only update texture paths in the material definition",
        default=False,
    )
    pbr:   bpy.props.PointerProperty(type=MdfTexPBRInputs)
    slots: bpy.props.CollectionProperty(type=MdfTexSlotItem)


# ── Base operator classes (NOT registered; subclasses must define bl_idname) ───

class MdfTexRefreshBase(bpy.types.Operator):
    bl_label   = "Refresh"
    bl_options = {'INTERNAL'}
    _settings_attr = ""
    _is_null_fn    = staticmethod(lambda p: False)

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        col = settings.mdf_collection
        if not col:
            self.report({'ERROR'}, T("core.mdf_tex_processor_base.select_mdf_collection"))
            return {'CANCELLED'}
        count = _do_refresh(settings, col, context.scene, is_null_fn=type(self)._is_null_fn)
        self.report({'INFO'}, T("core.mdf_tex_processor_base.loaded_materials").format(n=count))
        return {'FINISHED'}


class MdfTexPickPBRBase(bpy.types.Operator):
    bl_label   = "Pick Image"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index:   bpy.props.IntProperty()
    pbr_type:    bpy.props.StringProperty()
    filepath:    bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.tif;*.tiff;*.dds", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            setattr(mats[self.mat_index].pbr, self.pbr_type, self.filepath)
        return {'FINISHED'}


class MdfTexPickDirectBase(bpy.types.Operator):
    bl_label   = "Pick Image"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index:   bpy.props.IntProperty()
    slot_index:  bpy.props.IntProperty()
    filepath:    bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.png;*.tga;*.tif;*.tiff;*.dds", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            slots = mats[self.mat_index].slots
            if 0 <= self.slot_index < len(slots):
                slots[self.slot_index].direct_image = self.filepath
                slots[self.slot_index].mode = 'DIRECT'
        return {'FINISHED'}


class MdfTexClearPBRBase(bpy.types.Operator):
    bl_label   = "Clear"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index: bpy.props.IntProperty()
    pbr_type:  bpy.props.StringProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            setattr(mats[self.mat_index].pbr, self.pbr_type, '')
        return {'FINISHED'}


class MdfTexClearDirectBase(bpy.types.Operator):
    bl_label   = "Clear"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index:  bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if 0 <= self.mat_index < len(mats):
            slots = mats[self.mat_index].slots
            if 0 <= self.slot_index < len(slots):
                slots[self.slot_index].direct_image = ''
                slots[self.slot_index].mode = 'SKIP'
        return {'FINISHED'}


class MdfTexCopyMaterialBase(bpy.types.Operator):
    bl_label   = "Copy"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        mats = settings.materials
        if not (0 <= self.mat_index < len(mats)):
            return {'CANCELLED'}
        mat = mats[self.mat_index]
        data = {
            'pbr':           {pt: getattr(mat.pbr, pt) for pt in PBR_TYPES},
            'pbr_chs':       {pt: getattr(mat.pbr, f"{pt}_ch") for pt in PBR_CHANNEL_SELECTABLE},
            'pbr_inv':       {pt: getattr(mat.pbr, f"{pt}_inv") for pt in PBR_CHANNEL_SELECTABLE},
            'normal_flip_g': mat.pbr.normal_flip_g,
            'slots':         {s.texture_type: {'mode': s.mode, 'direct_image': s.direct_image}
                              for s in mat.slots},
        }
        settings.clipboard_json = json.dumps(data)
        self.report({'INFO'}, T("core.mdf_tex_processor_base.copied_material").format(name=mat.material_name))
        return {'FINISHED'}


class MdfTexPasteMaterialBase(bpy.types.Operator):
    bl_label   = "Paste"
    bl_options = {'INTERNAL'}
    _settings_attr = ""

    mat_index: bpy.props.IntProperty()

    def execute(self, context):
        settings = getattr(context.scene, type(self)._settings_attr)
        if not settings.clipboard_json:
            self.report({'WARNING'}, T("core.mdf_tex_processor_base.clipboard_empty"))
            return {'CANCELLED'}
        mats = settings.materials
        if not (0 <= self.mat_index < len(mats)):
            return {'CANCELLED'}
        data = json.loads(settings.clipboard_json)
        mat  = mats[self.mat_index]
        for pt, path in data.get('pbr', {}).items():
            if pt in PBR_TYPES:
                setattr(mat.pbr, pt, path)
        for pt, ch in data.get('pbr_chs', {}).items():
            if pt in PBR_CHANNEL_SELECTABLE:
                try:
                    setattr(mat.pbr, f"{pt}_ch", ch)
                except Exception:
                    pass
        for pt, inv in data.get('pbr_inv', {}).items():
            if pt in PBR_CHANNEL_SELECTABLE:
                setattr(mat.pbr, f"{pt}_inv", bool(inv))
        if 'normal_flip_g' in data:
            mat.pbr.normal_flip_g = bool(data['normal_flip_g'])
        slot_data = data.get('slots', {})
        for slot in mat.slots:
            if slot.texture_type in slot_data:
                sd = slot_data[slot.texture_type]
                slot.mode         = sd.get('mode', 'SKIP')
                slot.direct_image = sd.get('direct_image', '')
        self.report({'INFO'}, T("core.mdf_tex_processor_base.pasted_to_material").format(name=mat.material_name))
        return {'FINISHED'}


class MdfTexProcessBase(bpy.types.Operator):
    """Process MDF2 texture bindings: compose/convert images and update paths"""
    bl_label   = "Process"
    bl_options = {'REGISTER'}

    _settings_attr    = ""
    _natives_root_key = ""
    _null_tex_by_type = {}
    _channel_maps     = {}
    _tex_version      = 0
    _abbrev_map       = {}
    _use_art_prefix   = True
    _path_fixed_prefix = ""   # Optional path segment prepended to texture_base_path
    _log_tag          = "MDF Tex"

    def execute(self, context):
        _t_total = time.time()
        scene    = context.scene
        cls      = type(self)
        settings = getattr(scene, cls._settings_attr)

        natives_root = scene.get(cls._natives_root_key, "")
        if not natives_root or not os.path.isdir(natives_root):
            self.report({'ERROR'}, T("core.mdf_tex_processor_base.set_natives_root"))
            return {'CANCELLED'}
        if not settings.mdf_collection:
            self.report({'ERROR'}, T("core.mdf_tex_processor_base.select_mdf_collection"))
            return {'CANCELLED'}
        base_path = settings.texture_base_path.strip()
        if not base_path:
            self.report({'ERROR'}, T("core.mdf_tex_processor_base.fill_base_path"))
            return {'CANCELLED'}
        if cls._path_fixed_prefix:
            base_path = cls._path_fixed_prefix.strip('/') + '/' + base_path.strip('/')
        if not settings.materials:
            self.report({'ERROR'}, T("core.mdf_tex_processor_base.click_refresh_first"))
            return {'CANCELLED'}

        print(f"[{cls._log_tag}] {'='*40}", flush=True)

        ImageListToDDS, DDSToTex = _import_tex_utils()

        temp_dir = tempfile.mkdtemp(prefix="mdf_tex_")
        export_count = fail_count = skip_count = 0

        try:
            for mat_item in settings.materials:
                _t_mat = time.time()
                mat_obj = settings.mdf_collection.objects.get(mat_item.material_obj_name)
                if mat_obj is None:
                    continue
                mat_data = getattr(mat_obj, 're_mdf_material', None)
                if mat_data is None:
                    continue

                tex_name     = mat_item.material_name.removesuffix('_UseSC')
                # The global toggle overrides this material's own checkbox,
                # same as core.mdf_generator_base's effective_mipmaps.
                effective_mipmaps = (mat_item.generate_mipmaps
                                    and not getattr(settings, 'global_disable_mipmaps', False))
                grade_mode = getattr(settings, 'global_color_grade', 'NONE')
                pbr_paths      = {pt: getattr(mat_item.pbr, pt) for pt in PBR_TYPES}
                pbr_channels   = {pt: getattr(mat_item.pbr, f"{pt}_ch")
                                  for pt in PBR_CHANNEL_SELECTABLE}
                pbr_inv        = {pt: getattr(mat_item.pbr, f"{pt}_inv")
                                  for pt in PBR_CHANNEL_SELECTABLE}
                normal_flip_g  = mat_item.pbr.normal_flip_g

                color_path    = pbr_paths.get('color', '')
                emissive_path = pbr_paths.get('emissive', '')
                share_emi     = bool(color_path and emissive_path and color_path == emissive_path)
                albd_path_out = None

                for slot in mat_item.slots:
                    if slot.mode == 'SKIP':
                        skip_count += 1
                        continue
                    binding = next(
                        (b for b in mat_data.textureBindingList_items
                         if b.textureType == slot.texture_type), None)
                    if binding is None:
                        skip_count += 1
                        continue

                    mdf_path = make_mdf_path(base_path, tex_name, slot.texture_type,
                                             cls._abbrev_map, cls._use_art_prefix)

                    if slot.mode == 'DEFAULT':
                        null_rel = cls._null_tex_by_type.get(slot.texture_type)
                        if null_rel:
                            binding.path = null_rel
                            print(f"[{cls._log_tag}] NULL {slot.texture_type}: {null_rel}")
                            export_count += 1
                        else:
                            print(f"[{cls._log_tag}] SKIP (no null) {slot.texture_type}")
                            skip_count += 1
                        continue

                    if (slot.mode == 'COMPOSE'
                            and slot.texture_type == 'EmissiveMap'
                            and share_emi and albd_path_out):
                        binding.path = albd_path_out
                        print(f"[{cls._log_tag}] EMI reuse ALBD: {albd_path_out}")
                        export_count += 1
                        continue

                    try:
                        if slot.mode == 'COMPOSE':
                            if mat_item.skip_textures:
                                binding.path = mdf_path
                                if slot.texture_type == 'BaseDielectricMap':
                                    albd_path_out = mdf_path
                                export_count += 1
                                continue
                            _t_comp = time.time()
                            src_img = _compose_channels(
                                slot.texture_type, pbr_paths, pbr_channels,
                                temp_dir, tex_name, pbr_inv,
                                channel_maps=cls._channel_maps,
                                normal_flip_g=normal_flip_g,
                                octahedral=getattr(settings, 'octahedral_normals', False))
                            # print(f"[{cls._log_tag}]   合成通道 {slot.texture_type}: {time.time() - _t_comp:.2f}s", flush=True)
                            if src_img is None:
                                null_rel = cls._null_tex_by_type.get(slot.texture_type)
                                if null_rel:
                                    binding.path = null_rel
                                    print(f"[{cls._log_tag}] NULL (empty inputs) {slot.texture_type}: {null_rel}")
                                    export_count += 1
                                else:
                                    print(f"[{cls._log_tag}] SKIP (empty inputs, no null) {slot.texture_type}")
                                    skip_count += 1
                                continue
                        else:  # DIRECT
                            if mat_item.skip_textures:
                                binding.path = mdf_path
                                export_count += 1
                                continue
                            src_img = bpy.path.abspath(slot.direct_image)
                            if not src_img or not os.path.isfile(src_img):
                                print(f"[{cls._log_tag}] SKIP direct {slot.texture_type}: not found")
                                skip_count += 1
                                continue

                        disk_path = make_disk_path(
                            natives_root, base_path, tex_name, slot.texture_type,
                            cls._abbrev_map, cls._tex_version, cls._use_art_prefix)

                        write_slot_tex(
                            src_img, disk_path, temp_dir,
                            dds_fmt=resolve_dds_format(
                                slot.texture_type, SRGB_SLOT_TYPES),
                            generate_mipmaps=effective_mipmaps,
                            mip_quality=mat_item.mipmap_strategy,
                            image_to_dds=ImageListToDDS,
                            dds_to_tex=lambda p, o: DDSToTex(p, cls._tex_version, o),
                            grade_mode=grade_mode,
                        )

                        binding.path = mdf_path
                        if slot.texture_type == 'BaseDielectricMap':
                            albd_path_out = mdf_path
                        print(f"[{cls._log_tag}] OK {slot.texture_type} -> {os.path.basename(disk_path)}")
                        export_count += 1

                    except Exception as err:
                        print(f"[{cls._log_tag}] FAIL {slot.texture_type}: {err}")
                        fail_count += 1

            print(f"[{cls._log_tag}] 材质耗时: {mat_item.material_name} {time.time() - _t_mat:.2f}s", flush=True)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        print(f"[{cls._log_tag}] ★ 总耗时: {time.time() - _t_total:.2f}s ★", flush=True)

        if fail_count > 0:
            self.report({'WARNING'}, T("core.mdf_tex_processor_base.process_done_with_fail").format(
                export=export_count, fail=fail_count, skip=skip_count))
        else:
            self.report({'INFO'}, T("core.mdf_tex_processor_base.process_done").format(
                export=export_count, skip=skip_count))
        return {'FINISHED'}


# ── Registration (shared PropertyGroups only) ──────────────────────────────────

_base_classes = [MdfTexPBRInputs, MdfTexSlotItem, MdfTexMaterialItem]


def register():
    for cls in _base_classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_base_classes):
        bpy.utils.unregister_class(cls)
