"""Standalone image -> game .tex converter.

Unlike core/mdf_tex_processor_base.py (which auto-derives DXGI format and disk
path from a known MDF2/MRL3 slot type), this tool lets the user pick the format
and output path manually — for textures with no known slot mapping (CMM, XM,
Detail NM, etc.). One shared Scene singleton + one operator serve all five
games; the only per-game variance (tex version, MHWI's external .tex writer)
is a small lookup keyed by the operator's `game` property.
"""

import bpy
import os
import tempfile
import shutil

from .i18n import T
from .color_grade import color_grade_items, DEFAULT_MODE_INDEX
# Same two helpers the MDF processor uses, for the same reason: img.pixels[:]
# materialises one Python float per channel (67 million objects for a 4K
# texture) and `pixels[:] = arr.flatten().tolist()` builds the same list going
# the other way.  This module had kept the slow form on every one of its six
# pixel transfers, and a single convert can chain three of them.
from .mdf_tex_processor_base import image_to_array
from .tga_file import write_tga_rgba8

_CH = {'R': 0, 'G': 1, 'B': 2, 'A': 3}
_CH_ITEMS = [('R', 'R', ''), ('G', 'G', ''), ('B', 'B', ''), ('A', 'A', '')]


def get_src_items(self=None, context=None):
    """Dynamic items= callback so channel-source labels follow the addon's
    own language toggle instead of being fixed at registration time."""
    return [
        ('A', T("core.tex_convert_base.src_image_a"), ''),
        ('B', T("core.tex_convert_base.src_image_b"), ''),
        ('CONST0', T("core.tex_convert_base.src_const0"), ''),
        ('CONST1', T("core.tex_convert_base.src_const1"), ''),
    ]


# Common entries listed in kagenocookie/REE-Content-Editor's priority order
# (TextureViewer.DxgiFormats), then the formats it doesn't offer at all. The two
# pinned entries carry a use-case hint; the rest are bare format codes.
_FORMAT_COMMON = [
    ('R8G8B8A8_UNORM',      'R8G8B8A8_Linear', ''),
    ('R8G8B8A8_UNORM_SRGB', 'R8G8B8A8_sRGB', ''),
    ('BC1_UNORM',           'BC1_Linear', ''),
    ('BC1_UNORM_SRGB',      'BC1_sRGB', ''),
    ('BC2_UNORM',           'BC2_Linear', ''),
    ('BC2_UNORM_SRGB',      'BC2_sRGB', ''),
    ('BC3_UNORM',           'BC3_Linear', ''),
    ('BC3_UNORM_SRGB',      'BC3_sRGB', ''),
    ('BC4_UNORM',           'BC4_Linear', ''),
    ('BC5_SNORM',           'BC5_Signed', ''),
    ('BC5_UNORM',           'BC5_Linear', ''),
]
_FORMAT_EXTRA = [
    ('BC4_SNORM',           'BC4_Signed', ''),
    ('BC6H_UF16',           'BC6H_UF16 (HDR)', ''),
    ('BC6H_SF16',           'BC6H_SF16 (HDR)', ''),
    ('R8_UNORM',            'R8_Linear', ''),
    ('A8_UNORM',            'A8', ''),
    ('R8G8_UNORM',          'R8G8_Linear', ''),
    ('B8G8R8A8_UNORM_SRGB', 'B8G8R8A8_sRGB', ''),
    ('B8G8R8A8_UNORM',      'B8G8R8A8_Linear', ''),
]
def get_format_items(self=None, context=None):
    """Dynamic items= callback: the pinned entries have translatable use-case
    hints, the rest are bare format codes with no hint text.

    Pinned set mirrors REE-Content-Editor's two main presets — colour data is
    BC7_UNORM_SRGB, everything else is BC7_UNORM. Nothing pins BC5: RE Engine
    normal maps are *packed* (NRRO = normal.RG + roughness + AO) so two channels
    can't hold them, and MHWI's MRL3 shader ignores B in an NM, so BC7 there is
    strictly safer at the same size. REE likewise never defaults to BC5.
    """
    pinned = [
        ('BC7_UNORM_SRGB', T("core.tex_convert_base.format_bc7_srgb"), ''),
        ('BC7_UNORM', T("core.tex_convert_base.format_bc7_linear"), ''),
    ]
    return pinned + _FORMAT_COMMON + _FORMAT_EXTRA

# Non-colour name hints. RE Engine slot abbreviations (_nrr/_nro packed normals,
# _aco/_ato masks, trailing _n) come from REE-Content-Editor's
# Texture.GuessIsSrgbFromFilename; the MRL3 ones (_rmt/_cmm/_xm/_fm/_msk/_fvel)
# are MHWI's non-colour slots.
_NORMAL_NAME_HINTS = ('_nm', '_nrm', '_nrr', '_nro', '_normal', 'normal_',
                      '_aco', '_ato', '_alpha',
                      '_rmt', '_cmm', '_xm', '_fm', '_msk', '_fvel')
# MRL3 colour data is BML and EMI only; RE Engine's is ALBD/ALBM/_COL/emissive.
_COLOR_NAME_HINTS  = ('_alb', '_albd', '_bml', '_emi', '_diffuse', '_basecolor',
                      '_col', 'albedo')

# .tex container version per game (RE Engine games only; MHWI uses its own
# MRL3-era format written by the external MHW Model Editor addon instead).
_GAME_TEX_VERSION = {
    'MHWS': 241106027,
    'MHRS': 28,
    'RE4':  143221013,
    'RE9':  250813143,
}
#: Conversion target. Everything runs through the same DXGI/mipmap pipeline and
#: produces a DDS; the game entries then wrap that DDS in the game's .tex
#: container, and 'DDS' simply stops one step earlier.
def get_target_items(self=None, context=None):
    return [
        ('DDS',  T("core.tex_convert_base.target_dds"), T("core.tex_convert_base.target_dds_desc")),
        ('MHWI', 'MHWI', ''), ('MHWS', 'MHWS', ''), ('MHRS', 'MHRS', ''),
        ('RE4', 'RE4', ''), ('RE9', 'RE9', ''),
    ]


def guess_dxgi_format(filepath):
    """Best-effort DXGI format guess from filename; None if not recognized.

    Follows REE-Content-Editor: the filename only decides *colour vs non-colour*,
    and that single bit picks between BC7_UNORM_SRGB and BC7_UNORM — same rule for
    every game, MHWI included. Colour is checked first so an `_albd`-style name
    can't be swallowed by a mask hint.
    """
    stem = os.path.splitext(os.path.basename(filepath))[0].lower()
    if any(h in stem for h in _COLOR_NAME_HINTS):
        return 'BC7_UNORM_SRGB'
    if any(h in stem for h in _NORMAL_NAME_HINTS) or stem.endswith('_n'):
        return 'BC7_UNORM'
    return None


# Only BC7 (colour or linear) benefits from the box-average mip rebuild in
# core.texconv_native.convert_to_dds_area_mips -- everything else here is
# either uncompressed (nothing to alias) or a format this addon's own presets
# never emit, so gating the "High Quality" option to these two keeps the UI
# honest about where it actually does something.
_QUALITY_MIP_FORMATS = {'BC7_UNORM', 'BC7_UNORM_SRGB'}


# ── Format presets ───────────────────────────────────────────────────────────
# REE-Content-Editor's TextureViewer.Presets model: one combo that sets both the
# DXGI format and what to do with mipmaps, and drops to "custom" as soon as the
# user edits either value by hand.
_PRESET_SETTINGS = {
    'COLOR':    ('BC7_UNORM_SRGB', True),
    'NONCOLOR': ('BC7_UNORM',      True),
    # Same format/mipmap combo as NONCOLOR -- differs from it only in the extra
    # hemi-octahedral encode step _compose_channels applies to G/A, see
    # _preset_needs_octahedral_encode. One entry for both NRRO and NRRC: the
    # encode is identical either way, and this tool has no PBR semantics to
    # tell them apart by anyway -- R/B are just whatever the user wires up
    # (single-image passthrough, or their own RGB_A/RGBA channel picks), same
    # as every other preset here.
    'NRRO':     ('BC7_UNORM',      True),
    # UI art and decals are sampled at a fixed on-screen size, so mips would only
    # blur them — REE's "UI (compressed)" preset strips them for the same reason.
    'UI':       ('BC7_UNORM_SRGB', False),
}

#: Every game whose normal-roughness slots use the hemi-octahedral G/A packing
#: (see core.mdf_tex_processor_base.NORMAL_OCTAHEDRAL_SLOT_TYPES) -- shared by
#: MHWS/MHRS/RE4/RE9's BASE_SLOT_CHANNEL_MAPS. MHWI's MRL3 slots never pack a
#: normal this way, so it keeps the plain "Non-Color / Normal Map" preset and
#: never offers NRRO. 'DDS' (no specific game) offers it too: the encoding is
#: a property of which shader will read the texture, not of whether this tool
#: also wraps the result in a .tex container.
_OCTAHEDRAL_TARGET_GAMES = {'DDS', 'MHWS', 'MHRS', 'RE4', 'RE9'}


def _preset_needs_octahedral_encode(preset):
    return preset == 'NRRO'


def get_preset_items(self=None, context=None):
    """Fixed shape/order regardless of target -- only the NONCOLOR entry's
    label text varies. A dynamic EnumProperty's current value is stored as an
    index into whatever this returns, not as the string key, so changing the
    *count* of items when target changes would have Blender silently
    reinterpret a stale index as a different entry the moment target updates
    (observed: picking NRRO under MHWS, then switching target to MHWI, landed
    on UI -- the item that happened to share NRRO's index in the shorter
    MHWI-shaped list -- with no update callback firing to catch it, since
    nothing was actually re-*assigned*). NRRO stays selectable even for MHWI
    as the lesser problem: its own label already names the RE Engine slots
    it's for, which is enough signal, and a user's mistake there is silently
    wrong pixels, not a silently wrong format/mipmap combo.
    """
    if getattr(self, 'target', 'DDS') in _OCTAHEDRAL_TARGET_GAMES:
        noncolor = ('NONCOLOR', T("core.tex_convert_base.preset_noncolor_nrmr"),
                               T("core.tex_convert_base.preset_noncolor_nrmr_desc"))
    else:
        noncolor = ('NONCOLOR', T("core.tex_convert_base.preset_noncolor"),
                               T("core.tex_convert_base.preset_noncolor_desc"))
    return [
        ('COLOR', T("core.tex_convert_base.preset_color"), T("core.tex_convert_base.preset_color_desc")),
        noncolor,
        ('NRRO', T("core.tex_convert_base.preset_nrro"), T("core.tex_convert_base.preset_nrro_desc")),
        ('UI',     T("core.tex_convert_base.preset_ui"),     T("core.tex_convert_base.preset_ui_desc")),
        ('CUSTOM', T("core.tex_convert_base.preset_custom"), T("core.tex_convert_base.preset_custom_desc")),
    ]


# Guard so applying a preset doesn't bounce back through format/generate_mipmaps'
# own update callbacks and immediately reset the preset to CUSTOM.
_applying_preset = False


def _on_preset_update(self, context):
    global _applying_preset
    combo = _PRESET_SETTINGS.get(self.preset)
    if combo is None or _applying_preset:
        return
    _applying_preset = True
    try:
        self.format, self.generate_mipmaps = combo
    finally:
        _applying_preset = False


def _on_format_or_mips_update(self, context):
    """Hand-editing either value means the selection is no longer a preset."""
    if _applying_preset:
        return
    if _PRESET_SETTINGS.get(self.preset) != (self.format, self.generate_mipmaps):
        self.preset = 'CUSTOM'




def _apply_guess(settings, filepath):
    """Point the preset at whatever the filename suggests. Returns the guessed
    DXGI format, or None when no hint matched (the caller reports that)."""
    guessed = guess_dxgi_format(filepath)
    settings.format_guess_ok = guessed is not None
    if guessed == 'BC7_UNORM_SRGB':
        # UI is also sRGB, so a colour hint shouldn't knock the user off it.
        if settings.preset != 'UI':
            settings.preset = 'COLOR'
    elif guessed:
        settings.preset = 'NONCOLOR'
    return guessed


def _on_src_a_update(self, context):
    if not self.src_a:
        return
    _apply_guess(self, self.src_a)



# ── Output size ──────────────────────────────────────────────────────────────
# Reading an image's dimensions means loading it, which is far too expensive to
# repeat on every redraw, so results are memoised per path for the session.
_size_cache = {}


def image_size(path):
    """(width, height) of the image at *path*, or None if it can't be read."""
    if not path:
        return None
    abspath = bpy.path.abspath(path)
    if not os.path.isfile(abspath):
        return None
    if abspath in _size_cache:
        return _size_cache[abspath]
    img = None
    try:
        img = bpy.data.images.load(abspath, check_existing=False)
        size = tuple(img.size)
    except Exception:
        size = None
    finally:
        if img is not None:
            bpy.data.images.remove(img)
    # Failures are cached too: draw() runs constantly, and a file Blender
    # cannot decode would otherwise be re-loaded on every redraw
    _size_cache[abspath] = size if (size and size[0] and size[1]) else None
    return _size_cache[abspath]


def is_power_of_two(v):
    return v > 0 and (v & (v - 1)) == 0


def snap_to_power_of_two(v, tolerance=0.15):
    """Nearest power of two when it is within *tolerance*, otherwise the next
    one up.

    Snapping down is only worth a little lost detail when the source was
    already almost the right size; anything further away is rounded up so the
    conversion never throws pixels away to hit an arbitrary target.
    """
    if v <= 1:
        return 1
    lo = 1 << (int(v).bit_length() - 1)
    hi = lo if lo == v else lo << 1
    for candidate in (lo, hi):
        if abs(v - candidate) / float(v) <= tolerance:
            return candidate
    return hi


def _source_size(s):
    """Size the conversion will start from. Channel composition scales every
    source up to the widest one, so that is what decides it."""
    sizes = [image_size(p) for p in (s.src_a, s.src_b) if p]
    sizes = [x for x in sizes if x]
    if not sizes:
        return None
    return max(sizes, key=lambda wh: wh[0])


def output_size(s):
    """Size the resulting DDS will have."""
    if s.resize_enabled:
        return (s.out_width, s.out_height)
    return _source_size(s)


def _on_resize_toggle(self, context):
    """Pre-fill the fields the first time the box is ticked, so the numbers
    offered are the recommended ones rather than a stale 1024."""
    if not self.resize_enabled:
        return
    src = _source_size(self)
    if src:
        self.out_width = snap_to_power_of_two(src[0])
        self.out_height = snap_to_power_of_two(src[1])


# ── Channel composition (generic 2-source version of mdf_tex_processor_base's
# _compose_channels — that one is keyed by PBR type name, this one by 'A'/'B') ─

def _compose_channels(channel_map, path_a, path_b, out_dir, name_hint, encode_octahedral=False):
    """channel_map: {'R': (src_key, ch_idx, invert), ...}
    src_key: 'A' | 'B' | 'CONST0' | 'CONST1'.

    encode_octahedral: after composing, run the G/A channels through
    core.re_normal_pack.encode_normal_ga -- R and B pass through untouched
    (roughness and AO/cavity respectively for NRRO/NRRC). Always applied when
    True, with no attempt to detect an already-encoded source: the transform
    is a smooth reparameterization of the same 2D disk with no structural
    signature to detect, and a source that's already packed is rare enough
    (it could only come from unpacking an existing NRRO/NRRC texture) that
    guessing wrong is a worse default than always encoding.
    """
    import numpy as np

    sources = {}
    if path_a and os.path.isfile(path_a):
        sources['A'] = path_a
    if path_b and os.path.isfile(path_b):
        sources['B'] = path_b
    if not sources:
        return None

    raw_imgs = {}
    ref_w = ref_h = 0
    for key, path in sources.items():
        tmp_name = f"__tex_convert_tmp_{key}"
        if tmp_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[tmp_name])
        img = bpy.data.images.load(path, check_existing=False)
        img.name = tmp_name
        img.colorspace_settings.name = 'Non-Color'
        iw, ih = img.size
        if iw > ref_w:
            ref_w, ref_h = iw, ih
        raw_imgs[key] = img

    if ref_w == 0:
        ref_w = ref_h = 1024

    loaded = {}
    for key, img in raw_imgs.items():
        iw, ih = img.size
        if iw != ref_w or ih != ref_h:
            img.scale(ref_w, ref_h)
        loaded[key] = image_to_array(img)
        bpy.data.images.remove(img)

    result = np.zeros((ref_h, ref_w, 4), dtype=np.float32)
    for out_ch, (src_key, ch_idx, invert) in channel_map.items():
        oi = _CH[out_ch]
        if src_key == 'CONST0':
            result[:, :, oi] = 0.0
            continue
        if src_key == 'CONST1':
            result[:, :, oi] = 1.0
            continue
        arr = loaded.get(src_key)
        if arr is None:
            result[:, :, oi] = 0.0
            continue
        data = arr[:, :, ch_idx].copy()
        if invert:
            data = 1.0 - data
        result[:, :, oi] = data

    if encode_octahedral:
        from .re_normal_pack import encode_normal_ga
        g = result[:, :, _CH['G']]
        a = result[:, :, _CH['A']]
        result[:, :, _CH['G']], result[:, :, _CH['A']] = encode_normal_ga(g, a)

    out_path = os.path.join(out_dir, f"{name_hint}_composed.tga")
    return write_tga_rgba8(out_path, result)


# ── Detail normal map overlay (SINGLE mode only) ────────────────────────────
# UDN / partial-derivative blend: only the X/Y (tangent/bitangent) components
# are summed, Z is re-derived from the unit-length constraint rather than
# blended — this is the standard cheap technique for laying a high-frequency
# detail normal map over a base normal map without renormalizing a full
# vector sum, and it only needs the two channels the caller asked for.

def _tile_sample_bilinear(arr, out_w, out_h, tiling_x, tiling_y):
    """Wrap-sample `arr` (h, w, c) into an (out_h, out_w, c) array, repeating
    it `tiling_x`/`tiling_y` times across the output — i.e. UV tiling."""
    import numpy as np

    dh, dw = arr.shape[0], arr.shape[1]
    xs = np.mod((np.arange(out_w) + 0.5) / out_w * tiling_x, 1.0) * dw - 0.5
    ys = np.mod((np.arange(out_h) + 0.5) / out_h * tiling_y, 1.0) * dh - 0.5

    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    fx = (xs - x0)[None, :, None]
    fy = (ys - y0)[:, None, None]
    x0m, x1m = np.mod(x0, dw), np.mod(x0 + 1, dw)
    y0m, y1m = np.mod(y0, dh), np.mod(y0 + 1, dh)

    top = arr[y0m][:, x0m] * (1.0 - fx) + arr[y0m][:, x1m] * fx
    bot = arr[y1m][:, x0m] * (1.0 - fx) + arr[y1m][:, x1m] * fx
    return top * (1.0 - fy) + bot * fy


def _blend_detail_normal(base_path, detail_path, tiling_x, tiling_y, out_dir, name_hint):
    """Overlay a tiled detail normal map onto a base normal map, blending
    only X/Y and re-deriving Z. Returns the output PNG path, or None on
    failure (e.g. unreadable detail image)."""
    import numpy as np

    def _load_arr(path, tag):
        tmp_name = f"__tex_convert_detail_{tag}"
        if tmp_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[tmp_name])
        img = bpy.data.images.load(path, check_existing=False)
        img.name = tmp_name
        img.colorspace_settings.name = 'Non-Color'
        arr = image_to_array(img)
        bpy.data.images.remove(img)
        return arr

    base_arr = _load_arr(base_path, "base")
    detail_arr = _load_arr(detail_path, "detail")
    h, w = base_arr.shape[0], base_arr.shape[1]

    detail_tiled = _tile_sample_bilinear(detail_arr, w, h, tiling_x, tiling_y)

    base_xy = base_arr[:, :, :2] * 2.0 - 1.0
    detail_xy = detail_tiled[:, :, :2] * 2.0 - 1.0

    xy = np.clip(base_xy + detail_xy, -1.0, 1.0)
    z = np.sqrt(np.clip(1.0 - np.sum(xy * xy, axis=-1), 0.0, 1.0))

    result = np.empty((h, w, 4), dtype=np.float32)
    result[:, :, 0:2] = xy * 0.5 + 0.5
    result[:, :, 2] = z * 0.5 + 0.5
    result[:, :, 3] = base_arr[:, :, 3]

    out_path = os.path.join(out_dir, f"{name_hint}.tga")
    return write_tga_rgba8(out_path, result)


# ── Color adjust (COLOR preset only) ────────────────────────────────────────
# Sliders and ranges follow Photoshop's own units so values carry over directly
# from a Photoshop workflow: Exposure in stops (Image > Adjustments > Exposure,
# -20..20), Saturation/Vibrance in Photoshop's -100..100 (Image > Adjustments
# > Vibrance). These are pixel-value approximations of PS's algorithms, not a
# colorimetric match -- good enough for texture editing, not photo grading.

def _luminance(rgb):
    import numpy as np
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return np.sum(rgb * weights, axis=-1, keepdims=True)




def _apply_color_grade_file(path, mode, out_dir, name_hint):
    """Run core.color_grade over *path* and stage the result as a TGA.

    Separate from _apply_color_adjustments on purpose: that one is a manual
    per-image tweak in Photoshop's units, this is the fixed three-way mode the
    generator and the texture processor also expose, so the same pick produces
    the same pixels wherever it is set.  Note the two 'exposure' notions differ --
    the slider multiplies the stored values, color_grade multiplies in linear
    light -- which is exactly why this does not just preset the sliders.
    """
    from . import color_grade
    if mode == 'NONE':
        return path
    tmp_name = "__tex_convert_grade"
    if tmp_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[tmp_name])
    img = bpy.data.images.load(path, check_existing=False)
    img.name = tmp_name
    img.colorspace_settings.name = 'Non-Color'
    arr = image_to_array(img)          # Blender 行序，和 write_tga_rgba8 一致，不用翻
    bpy.data.images.remove(img)
    out = color_grade.grade(arr, mode)
    return write_tga_rgba8(os.path.join(out_dir, f"{name_hint}.tga"), out)


def _apply_color_adjust(rgb, exposure, saturation, vibrance):
    """rgb: (h, w, 3) float32 array of the image's raw stored channel values.
    Order is exposure -> vibrance -> saturation, matching how the three stack
    in Photoshop's own Vibrance dialog (Saturation is the coarser, later knob)."""
    import numpy as np

    if exposure:
        rgb = rgb * (2.0 ** exposure)
    if vibrance:
        amt = vibrance / 100.0
        max_c = rgb.max(axis=-1, keepdims=True)
        avg_c = rgb.mean(axis=-1, keepdims=True)
        current_sat = max_c - avg_c
        scale = amt * (1.0 - current_sat)
        gray = _luminance(rgb)
        rgb = gray + (rgb - gray) * (1.0 + scale)
    if saturation:
        factor = 1.0 + saturation / 100.0
        gray = _luminance(rgb)
        rgb = gray + (rgb - gray) * factor
    return np.clip(rgb, 0.0, 1.0)


def _apply_color_adjustments(path, exposure, saturation, vibrance, out_dir, name_hint):
    """Load *path*, run _apply_color_adjust over its RGB (alpha untouched),
    and save the result as a new staging TGA in out_dir. Mirrors the load/save
    pattern _blend_detail_normal uses above."""
    tmp_name = "__tex_convert_coloradj"
    if tmp_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[tmp_name])
    img = bpy.data.images.load(path, check_existing=False)
    img.name = tmp_name
    img.colorspace_settings.name = 'Non-Color'
    arr = image_to_array(img)
    bpy.data.images.remove(img)

    arr[:, :, :3] = _apply_color_adjust(arr[:, :, :3], exposure, saturation, vibrance)

    out_path = os.path.join(out_dir, f"{name_hint}.tga")
    return write_tga_rgba8(out_path, arr)


def _import_mhwtex_convert():
    """Locate MHW Model Editor's convertDDSFileToTex — MHWI's .tex container is
    written by that external addon, not by core/tex_file.py (RE Engine only)."""
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


# ── PropertyGroup (single shared Scene singleton) ──────────────────────────────

def get_channel_mode_items(self=None, context=None):
    return [
        ('SINGLE', T("core.tex_convert_base.mode_single"), T("core.tex_convert_base.mode_single_desc")),
        ('RGB_A', T("core.tex_convert_base.mode_rgb_a"), T("core.tex_convert_base.mode_rgb_a_desc")),
        ('RGBA', T("core.tex_convert_base.mode_rgba"), T("core.tex_convert_base.mode_rgba_desc")),
    ]


class TexConvertSettings(bpy.types.PropertyGroup):
    channel_mode: bpy.props.EnumProperty(
        name="Channel Source",
        items=get_channel_mode_items,
    )
    src_a: bpy.props.StringProperty(name="Source Image", subtype='FILE_PATH', update=_on_src_a_update)
    src_a_invert: bpy.props.BoolProperty(name="Invert", default=False)
    src_b: bpy.props.StringProperty(name="Alpha Source", subtype='FILE_PATH')
    src_b_invert: bpy.props.BoolProperty(name="Invert", default=False)
    # RGB_A mode only, and only while no Alpha Source image is picked: lets the
    # user opt into a black-filled alpha instead of the default white/opaque
    # fill (matching PBR_DEFAULTS['alpha'] in mdf_tex_processor_base.py).
    alpha_fill_black: bpy.props.BoolProperty(name="Fill Alpha with Black", default=False)

    # SINGLE mode only: overlay a tiled detail normal map onto the source
    # image (blends only the X/Y components, Z is re-derived to keep the
    # result a unit normal — the standard UDN/partial-derivative technique).
    detail_enabled: bpy.props.BoolProperty(name="Detail Normal Map", default=False)
    detail_path: bpy.props.StringProperty(name="Detail Map", subtype='FILE_PATH')
    detail_tiling_x: bpy.props.FloatProperty(name="Tiling X", default=1.0, min=0.01)
    detail_tiling_y: bpy.props.FloatProperty(name="Tiling Y", default=1.0, min=0.01)

    # In RGBA mode each output channel only picks a "source image/constant +
    # source channel"; invert follows the corresponding source image's
    # (A/B) src_a_invert/src_b_invert above, not set per output channel — so
    # future adjustments hang off the source image rather than being
    # duplicated per channel.
    ch_r_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_g_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_b_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_a_source: bpy.props.EnumProperty(name="", items=get_src_items)
    ch_r_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='R')
    ch_g_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='G')
    ch_b_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='B')
    ch_a_channel: bpy.props.EnumProperty(name="", items=_CH_ITEMS, default='A')

    # 与生成器/贴图处理器同一套三档（core/color_grade.py）。和下面那组手动滑块是
    # 两回事：这一档是整套素材的**口径**转换（源游戏 vs 本作），滑块是单张微调。
    # 顺序也因此固定为「先档位、后滑块」。
    color_grade: bpy.props.EnumProperty(
        name="Colour Grade",
        description="Tone adjustment applied to the colour data before encoding",
        items=lambda self, ctx: color_grade_items(),
        default=DEFAULT_MODE_INDEX,
    )

    # COLOR preset only. Ranges/defaults match Photoshop's own sliders (see
    # _apply_color_adjust) so values carry over directly from a PS workflow.
    color_adjust_enabled: bpy.props.BoolProperty(name="Color Adjust", default=False)
    adjust_exposure: bpy.props.FloatProperty(name="Exposure", default=0.0, min=-20.0, max=20.0,
                                             soft_min=-3.0, soft_max=3.0)
    adjust_saturation: bpy.props.FloatProperty(name="Saturation", default=0.0, min=-100.0, max=100.0)
    adjust_vibrance: bpy.props.FloatProperty(name="Vibrance", default=0.0, min=-100.0, max=100.0)

    preset: bpy.props.EnumProperty(name="Preset", items=get_preset_items,
                                   update=_on_preset_update)
    format: bpy.props.EnumProperty(name="Target Format", items=get_format_items,
                                   update=_on_format_or_mips_update)
    format_guess_ok: bpy.props.BoolProperty(default=True)

    generate_mipmaps: bpy.props.BoolProperty(name="Generate Mipmaps", default=True,
                                             update=_on_format_or_mips_update)
    mipmap_strategy: bpy.props.EnumProperty(
        name="Mipmap Strategy",
        items=lambda self, ctx: [
            ('FAST', T("core.mip_strategy.fast"), T("core.mip_strategy.fast_desc")),
            ('QUALITY', T("core.mip_strategy.quality"), T("core.mip_strategy.quality_desc")),
        ],
        default=0,  # 'FAST' -- dynamic items need an int index default
    )
    output_path: bpy.props.StringProperty(name="Output Path", subtype='FILE_PATH')
    target: bpy.props.EnumProperty(name="Target Format", items=get_target_items, default=0)
    resize_enabled: bpy.props.BoolProperty(
        name="Resize Output", default=False, update=_on_resize_toggle,
        description="Override the output resolution instead of keeping the source's")
    out_width: bpy.props.IntProperty(name="Width", default=1024, min=1, max=16384)
    out_height: bpy.props.IntProperty(name="Height", default=1024, min=1, max=16384)


# ── Operators ────────────────────────────────────────────────────────────────

class MT_OT_TexConvertGuessFormat(bpy.types.Operator):
    bl_idname  = "mt.tex_convert_guess_format"
    bl_label   = "Re-guess Format"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.guess_format_desc")

    def execute(self, context):
        settings = context.scene.tex_convert_tool
        if not settings.src_a:
            self.report({'WARNING'}, T("core.tex_convert_base.select_src_image_first"))
            return {'CANCELLED'}
        guessed = _apply_guess(settings, settings.src_a)
        if guessed:
            self.report({'INFO'}, T("core.tex_convert_base.guessed_format").format(fmt=guessed))
        else:
            self.report({'WARNING'}, T("core.tex_convert_base.guess_failed"))
        return {'FINISHED'}


class MT_OT_TexConvertSnapSize(bpy.types.Operator):
    """Fill the width/height fields with the recommended power-of-two size"""
    bl_idname = "mt.tex_convert_snap_size"
    bl_label = "Recommended Size"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.snap_size_desc")

    def execute(self, context):
        s = context.scene.tex_convert_tool
        src = _source_size(s)
        if not src:
            self.report({'ERROR'}, T("core.tex_convert_base.select_src_image_first"))
            return {'CANCELLED'}
        s.out_width = snap_to_power_of_two(src[0])
        s.out_height = snap_to_power_of_two(src[1])
        return {'FINISHED'}


class MT_OT_TexConvertDialog(bpy.types.Operator):
    """Convert a single image directly to the target game's .tex texture."""
    bl_idname  = "mt.tex_convert_dialog"
    bl_label   = "Texture Conversion"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.dialog_desc")

    def invoke(self, context, event):
        # A scene saved before `preset` existed carries only format/mipmaps, so
        # derive the preset from them rather than opening on a label that
        # contradicts the values underneath it.
        s = context.scene.tex_convert_tool
        combo = (s.format, s.generate_mipmaps)
        s.preset = next((k for k, v in _PRESET_SETTINGS.items() if v == combo), 'CUSTOM')
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        s = context.scene.tex_convert_tool

        layout.label(text=T('core.tex_convert_base.dialog_title'))

        # Everything that describes the *output file* stays together at the
        # top; the channel plumbing that produces its pixels comes after.
        layout.prop(s, "target", text=T("core.tex_convert_base.target_name"))
        layout.prop(s, "preset", text=T("core.tex_convert_base.preset_name"))
        fmt_row = layout.row(align=True)
        fmt_row.prop(s, "format", text=T("core.tex_convert_base.format_name"))
        fmt_row.operator("mt.tex_convert_guess_format", text="", icon='FILE_REFRESH')
        if s.src_a and not s.format_guess_ok:
            layout.label(text=T("core.tex_convert_base.guess_fallback_warning"), icon='ERROR')
        mip_row = layout.row(align=True)
        mip_row.prop(s, "generate_mipmaps", text=T("core.tex_convert_base.generate_mipmaps_name"))
        if s.generate_mipmaps and s.format in _QUALITY_MIP_FORMATS:
            mip_row.prop(s, "mipmap_strategy", text="")

        layout.separator()

        layout.prop(s, "channel_mode", expand=True)
        layout.separator()

        # Image selection
        if s.channel_mode == 'SINGLE':
            layout.prop(s, "src_a", text=T("core.tex_convert_base.src_a_name"))
        elif s.channel_mode == 'RGB_A':
            layout.prop(s, "src_a", text=T("core.tex_convert_base.rgb_source_label"))
            layout.prop(s, "src_b", text=T("core.tex_convert_base.src_b_name"))
            if not s.src_b:
                layout.prop(s, "alpha_fill_black", text=T("core.tex_convert_base.alpha_fill_black_name"))
        else:  # RGBA
            layout.prop(s, "src_a", text=T("core.tex_convert_base.src_image_a"))
            layout.prop(s, "src_b", text=T("core.tex_convert_base.src_image_b"))

        # Adjust — hangs off the source image, not the output channel; future
        # brightness/saturation etc. adjustments go here too.
        if s.src_a or (s.src_b and s.channel_mode != 'SINGLE'):
            layout.separator()
            adj_box = layout.box()
            adj_box.label(text=T("core.tex_convert_base.adjust_header"))
            if s.channel_mode == 'RGB_A':
                # src_a is always the RGB source and src_b always the Alpha
                # source in this mode, so the labels can say so directly.
                if s.src_a:
                    adj_box.prop(s, "src_a_invert", text=T("core.tex_convert_base.invert_rgb_name"))
                if s.src_b:
                    adj_box.prop(s, "src_b_invert", text=T("core.tex_convert_base.invert_alpha_name"))
            elif s.channel_mode == 'RGBA':
                # A single image can feed any mix of destination channels
                # here, so invert is a single flag for the whole image again
                # (not split by RGB vs Alpha, unlike RGB_A above).
                if s.src_a:
                    adj_box.prop(s, "src_a_invert", text=T("core.tex_convert_base.invert_a_label"))
                if s.src_b:
                    adj_box.prop(s, "src_b_invert", text=T("core.tex_convert_base.invert_b_label"))
            else:  # SINGLE
                adj_box.prop(s, "src_a_invert", text=T("core.tex_convert_base.invert_name"))
                # Detail overlay is a normal-map technique (UDN blend), so it
                # only makes sense for NONCOLOR/NRRO -- CUSTOM stays fully open
                # since the user picked it precisely to bypass preset gating.
                if s.preset in ('NONCOLOR', 'NRRO', 'CUSTOM'):
                    adj_box.separator()
                    adj_box.prop(s, "detail_enabled", text=T("core.tex_convert_base.detail_enabled_name"))
                    if s.detail_enabled:
                        adj_box.prop(s, "detail_path", text=T("core.tex_convert_base.detail_map_name"))
                        tile_row = adj_box.row(align=True)
                        tile_row.prop(s, "detail_tiling_x", text=T("core.tex_convert_base.detail_tiling_x_name"))
                        tile_row.prop(s, "detail_tiling_y", text=T("core.tex_convert_base.detail_tiling_y_name"))

            # Exposure/Saturation/Vibrance only make sense on real color data,
            # not normal/mask/packed textures, so this is gated on COLOR --
            # CUSTOM stays fully open for the same reason as detail overlay above.
            if s.preset in ('COLOR', 'CUSTOM'):
                adj_box.separator()
                grade_row = adj_box.row(align=True)
                grade_row.label(text=T("core.color_grade.label"))
                grade_row.prop(s, "color_grade", text="")
                adj_box.prop(s, "color_adjust_enabled", text=T("core.tex_convert_base.color_adjust_enabled_name"))
                if s.color_adjust_enabled:
                    col = adj_box.column(align=True)
                    col.prop(s, "adjust_exposure", text=T("core.tex_convert_base.adjust_exposure_name"))
                    col.prop(s, "adjust_saturation", text=T("core.tex_convert_base.adjust_saturation_name"))
                    col.prop(s, "adjust_vibrance", text=T("core.tex_convert_base.adjust_vibrance_name"))

        # RGBA channel mapping: only pick source image/constant + source channel
        if s.channel_mode == 'RGBA':
            layout.separator()
            for ch in ('r', 'g', 'b', 'a'):
                row = layout.row(align=True)
                row.label(text=ch.upper())
                row.prop(s, f"ch_{ch}_source", text="")
                row.prop(s, f"ch_{ch}_channel", text="")

        layout.separator()
        layout.prop(s, "output_path", text=T("core.tex_convert_base.output_path_name"))
        layout.label(text=T("core.tex_convert_base.output_empty_hint"), icon='INFO')

        # Output size last: it is a consequence of everything above, and the
        # non-power-of-two warning is the thing to leave on screen.
        layout.separator()
        size = output_size(s)
        if size:
            w, h = size
            ok = is_power_of_two(w) and is_power_of_two(h)
            row = layout.row()
            row.alert = not ok
            row.label(text=T("core.tex_convert_base.output_size_label").format(w=w, h=h),
                      icon='TEXTURE' if ok else 'ERROR')
            if not ok:
                warn = layout.row()
                warn.alert = True
                warn.label(text=T("core.tex_convert_base.npot_warning"))
        else:
            layout.label(text=T("core.tex_convert_base.output_size_unknown"), icon='INFO')

        layout.prop(s, "resize_enabled", text=T("core.tex_convert_base.resize_name"))
        if s.resize_enabled:
            size_row = layout.row(align=True)
            size_row.prop(s, "out_width", text=T("core.tex_convert_base.width_name"))
            size_row.prop(s, "out_height", text=T("core.tex_convert_base.height_name"))
            size_row.operator("mt.tex_convert_snap_size", text="", icon='FILE_REFRESH')

    def execute(self, context):
        s = context.scene.tex_convert_tool

        src_a = bpy.path.abspath(s.src_a) if s.src_a else ""
        if not src_a or not os.path.isfile(src_a):
            self.report({'ERROR'}, T("core.tex_convert_base.select_src_image_first"))
            return {'CANCELLED'}

        src_b = bpy.path.abspath(s.src_b) if s.src_b else ""

        src_stem = os.path.splitext(os.path.basename(src_a))[0]
        if s.target == 'DDS':
            ext = '.dds'
        elif s.target == 'MHWI':
            ext = '.tex'
        else:
            ext = f'.tex.{_GAME_TEX_VERSION[s.target]}'
        default_filename = src_stem + ext

        if s.output_path:
            out_path = bpy.path.abspath(s.output_path)
            # No ".tex" in the given name -> treat the whole thing as a
            # target folder and name the file after the source image,
            # rather than requiring the filename to be typed out in full.
            if ext.split('.')[1] not in os.path.basename(out_path).lower():
                out_path = os.path.join(out_path, default_filename)
        else:
            out_path = os.path.join(os.path.dirname(src_a), default_filename)

        temp_dir = tempfile.mkdtemp(prefix="tex_convert_")
        encode_octahedral = _preset_needs_octahedral_encode(s.preset)

        try:
            if s.channel_mode == 'SINGLE':
                working = src_a
                if s.preset in ('NONCOLOR', 'NRRO', 'CUSTOM') and s.detail_enabled and s.detail_path:
                    detail_path = bpy.path.abspath(s.detail_path)
                    if os.path.isfile(detail_path):
                        working = _blend_detail_normal(
                            working, detail_path, s.detail_tiling_x, s.detail_tiling_y,
                            temp_dir, "tex_convert_detail")
                        if not working:
                            self.report({'ERROR'}, T("core.tex_convert_base.detail_blend_failed"))
                            return {'CANCELLED'}
                # The encode step needs to run through _compose_channels even
                # when nothing else does -- an un-inverted passthrough would
                # otherwise just reuse `working` as-is (see the else branch).
                if s.src_a_invert or encode_octahedral:
                    channel_map = {c: ('A', i, s.src_a_invert) for c, i in _CH.items()}
                    png_path = _compose_channels(channel_map, working, "", temp_dir, "tex_convert",
                                                 encode_octahedral=encode_octahedral)
                else:
                    png_path = working
            elif s.channel_mode == 'RGB_A':
                if src_b and os.path.isfile(src_b):
                    alpha_entry = ('B', 0, s.src_b_invert)
                else:
                    # No alpha source picked: default to white/opaque (matches
                    # PBR_DEFAULTS['alpha'] in mdf_tex_processor_base.py) unless
                    # the user opted into a black fill via alpha_fill_black.
                    alpha_entry = ('CONST0', 0, False) if s.alpha_fill_black else ('CONST1', 0, False)
                channel_map = {
                    'R': ('A', 0, s.src_a_invert), 'G': ('A', 1, s.src_a_invert),
                    'B': ('A', 2, s.src_a_invert), 'A': alpha_entry,
                }
                png_path = _compose_channels(channel_map, src_a, src_b, temp_dir, "tex_convert",
                                             encode_octahedral=encode_octahedral)
            else:  # RGBA
                channel_map = {}
                for ch in ('R', 'G', 'B', 'A'):
                    key = ch.lower()
                    src_key = getattr(s, f"ch_{key}_source")
                    invert = (s.src_a_invert if src_key == 'A'
                              else s.src_b_invert if src_key == 'B'
                              else False)
                    channel_map[ch] = (src_key, _CH[getattr(s, f"ch_{key}_channel")], invert)
                png_path = _compose_channels(channel_map, src_a, src_b, temp_dir, "tex_convert",
                                             encode_octahedral=encode_octahedral)

            if not png_path:
                self.report({'ERROR'}, T("core.tex_convert_base.channel_compose_failed"))
                return {'CANCELLED'}

            if s.preset in ('COLOR', 'CUSTOM') and s.color_grade != 'NONE':
                png_path = _apply_color_grade_file(
                    png_path, s.color_grade, temp_dir, "tex_convert_grade")

            if (s.preset in ('COLOR', 'CUSTOM') and s.color_adjust_enabled
                    and (s.adjust_exposure or s.adjust_saturation or s.adjust_vibrance)):
                png_path = _apply_color_adjustments(
                    png_path, s.adjust_exposure, s.adjust_saturation, s.adjust_vibrance,
                    temp_dir, "tex_convert_coloradj")

            from . import texconv_native
            resize = (s.out_width, s.out_height) if s.resize_enabled else None
            dds_path = None
            if (s.generate_mipmaps and s.mipmap_strategy == 'QUALITY'
                    and s.format in _QUALITY_MIP_FORMATS):
                try:
                    dds_path = texconv_native.convert_to_dds_area_mips(
                        png_path, s.format, temp_dir, size=resize)
                except ValueError:
                    size = output_size(s) or (0, 0)
                    self.report({'WARNING'}, T("core.mip_strategy.pot_fallback").format(
                        name=os.path.basename(out_path), w=size[0], h=size[1]))
            if dds_path is None:
                dds_path = texconv_native.convert_to_dds(
                    png_path, s.format, temp_dir, generate_mips=s.generate_mipmaps,
                    size=resize)

            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            if s.target == 'DDS':
                # The pipeline already produced exactly this; the game targets
                # only differ by the container written around it
                shutil.copy2(dds_path, out_path)
            elif s.target == 'MHWI':
                fn = _import_mhwtex_convert()
                if fn is None:
                    self.report({'ERROR'}, T("core.tex_convert_base.mhwtex_convert_unavailable"))
                    return {'CANCELLED'}
                fn([dds_path], out_path)
            else:
                from . import tex_file
                tex_file.write_tex_from_dds(dds_path, _GAME_TEX_VERSION[s.target], out_path)

            self.report({'INFO'}, T("core.tex_convert_base.generated").format(name=os.path.basename(out_path)))
            return {'FINISHED'}

        except Exception as err:
            self.report({'ERROR'}, T("core.tex_convert_base.convert_failed").format(err=err))
            return {'CANCELLED'}
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ── Drag & drop: batch convert dropped images to DDS ─────────────────────────
# Blender shows a chooser when several FileHandlers claim the same extension,
# so this appears alongside the other addons' entries rather than replacing
# them.  Unlike RE Mesh Editor's dialog this targets plain DDS only, and an
# unrecognised filename falls back to BC7_UNORM_SRGB rather than linear:
# a colour map wrongly tagged linear washes out visibly, while a mask wrongly
# tagged sRGB is the quieter mistake to make.
_DROP_FALLBACK_FORMAT = 'BC7_UNORM_SRGB'

_DROP_EXTENSIONS = ".png;.tga;.jpg;.jpeg;.bmp;.tif;.tiff;.dds"


class TexDropItem(bpy.types.PropertyGroup):
    filepath: bpy.props.StringProperty()
    format: bpy.props.EnumProperty(name="", items=get_format_items)


class MT_OT_TexDropToDDS(bpy.types.Operator):
    """Convert the dropped images to DDS"""
    bl_idname = "mt.tex_drop_to_dds"
    bl_label = "Convert to DDS"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement,
                                        options={'SKIP_SAVE', 'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'})

    generate_mipmaps: bpy.props.BoolProperty(
        name="Generate Mipmaps", default=True,
        description="Generate a full mipmap chain")
    mipmap_strategy: bpy.props.EnumProperty(
        name="Mipmap Strategy",
        items=lambda self, ctx: [
            ('FAST', T("core.mip_strategy.fast"), T("core.mip_strategy.fast_desc")),
            ('QUALITY', T("core.mip_strategy.quality"), T("core.mip_strategy.quality_desc")),
        ],
        default=0,  # 'FAST' -- dynamic items need an int index default
    )

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.drop_desc")

    def _paths(self):
        if self.files and self.directory:
            return [os.path.join(self.directory, f.name) for f in self.files if f.name]
        return [self.filepath] if self.filepath else []

    def invoke(self, context, event):
        items = context.scene.tex_drop_items
        items.clear()
        for path in self._paths():
            entry = items.add()
            entry.filepath = path
            entry.format = guess_dxgi_format(path) or _DROP_FALLBACK_FORMAT
        if not items:
            self.report({'ERROR'}, T("core.tex_convert_base.drop_no_files"))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        items = context.scene.tex_drop_items
        layout.label(text=T("core.tex_convert_base.drop_count").format(n=len(items)))
        box = layout.box()
        for entry in items:
            row = box.row(align=True)
            row.label(text=os.path.basename(entry.filepath))
            row.prop(entry, "format", text="")
        mip_row = layout.row(align=True)
        mip_row.prop(self, "generate_mipmaps", text=T("core.tex_convert_base.generate_mipmaps_name"))
        if self.generate_mipmaps and any(e.format in _QUALITY_MIP_FORMATS for e in items):
            mip_row.prop(self, "mipmap_strategy", text="")

    def execute(self, context):
        from . import texconv_native

        items = list(context.scene.tex_drop_items)
        done, failed = 0, []
        for entry in items:
            src = entry.filepath
            out_path = os.path.splitext(src)[0] + ".dds"
            temp_dir = tempfile.mkdtemp(prefix="tex_drop_")
            try:
                dds_path = None
                if (self.generate_mipmaps and self.mipmap_strategy == 'QUALITY'
                        and entry.format in _QUALITY_MIP_FORMATS):
                    try:
                        dds_path = texconv_native.convert_to_dds_area_mips(src, entry.format, temp_dir)
                    except ValueError:
                        dds_path = None  # not power-of-two -- fall back to Fast below
                if dds_path is None:
                    dds_path = texconv_native.convert_to_dds(
                        src, entry.format, temp_dir, generate_mips=self.generate_mipmaps)
                shutil.copy2(dds_path, out_path)
                done += 1
            except Exception as err:
                failed.append("%s (%s)" % (os.path.basename(src), err))
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        context.scene.tex_drop_items.clear()
        if failed:
            self.report({'WARNING'}, T("core.tex_convert_base.drop_partial").format(
                n=done, failed="; ".join(failed)))
        else:
            self.report({'INFO'}, T("core.tex_convert_base.drop_done").format(n=done))
        return {'FINISHED'}


class MT_FH_TexDropToDDS(bpy.types.FileHandler):
    bl_idname = "MT_FH_tex_drop_to_dds"
    bl_label = "Convert to DDS"
    bl_import_operator = "mt.tex_drop_to_dds"
    bl_file_extensions = _DROP_EXTENSIONS

    @classmethod
    def poll_drop(cls, context):
        return context.area and context.area.type in {'VIEW_3D', 'IMAGE_EDITOR', 'OUTLINER'}


# ── Drag & drop: batch decode dropped DDS to PNG ────────────────────────────
# A second FileHandler claiming .dds alongside MT_FH_TexDropToDDS above — Blender
# shows both as options in the drop chooser instead of picking one. No per-file
# format choice is needed here (decoding always targets plain R8G8B8A8), so this
# skips tex_drop_items and just lists the file names for confirmation.

class MT_OT_TexDropToPNG(bpy.types.Operator):
    """Decode the dropped DDS to PNG (stored bytes only, no gamma conversion)"""
    bl_idname = "mt.tex_drop_to_png"
    bl_label = "Convert to PNG"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement,
                                        options={'SKIP_SAVE', 'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        return T("core.tex_convert_base.drop_png_desc")

    def _paths(self):
        if self.files and self.directory:
            return [os.path.join(self.directory, f.name) for f in self.files if f.name]
        return [self.filepath] if self.filepath else []

    def invoke(self, context, event):
        if not self._paths():
            self.report({'ERROR'}, T("core.tex_convert_base.drop_no_files"))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        paths = self._paths()
        layout.label(text=T("core.tex_convert_base.drop_count").format(n=len(paths)))
        box = layout.box()
        for path in paths:
            box.label(text=os.path.basename(path))

    def execute(self, context):
        from . import texconv_native

        done, failed = 0, []
        for src in self._paths():
            out_path = os.path.splitext(src)[0] + ".png"
            temp_dir = tempfile.mkdtemp(prefix="tex_drop_png_")
            try:
                png_path = texconv_native.convert_to_png(src, temp_dir)
                shutil.copy2(png_path, out_path)
                done += 1
            except Exception as err:
                failed.append("%s (%s)" % (os.path.basename(src), err))
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        if failed:
            self.report({'WARNING'}, T("core.tex_convert_base.drop_png_partial").format(
                n=done, failed="; ".join(failed)))
        else:
            self.report({'INFO'}, T("core.tex_convert_base.drop_png_done").format(n=done))
        return {'FINISHED'}


class MT_FH_TexDropToPNG(bpy.types.FileHandler):
    bl_idname = "MT_FH_tex_drop_to_png"
    bl_label = "Convert to PNG"
    bl_import_operator = "mt.tex_drop_to_png"
    bl_file_extensions = ".dds"

    @classmethod
    def poll_drop(cls, context):
        return context.area and context.area.type in {'VIEW_3D', 'IMAGE_EDITOR', 'OUTLINER'}


# ── Registration ───────────────────────────────────────────────────────────────

classes = [TexConvertSettings, TexDropItem, MT_OT_TexConvertGuessFormat,
           MT_OT_TexConvertSnapSize,
           MT_OT_TexConvertDialog, MT_OT_TexDropToDDS, MT_FH_TexDropToDDS,
           MT_OT_TexDropToPNG, MT_FH_TexDropToPNG]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tex_convert_tool = bpy.props.PointerProperty(type=TexConvertSettings)
    bpy.types.Scene.tex_drop_items = bpy.props.CollectionProperty(type=TexDropItem)


def unregister():
    del bpy.types.Scene.tex_drop_items
    del bpy.types.Scene.tex_convert_tool
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
