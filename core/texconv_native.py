"""Native PNG/TGA/etc. -> DDS conversion via a bundled texconv DLL (Windows only).

Uses matyalatte's Texconv-Custom-DLL (MIT, wraps Microsoft's MIT-licensed
DirectXTex) bundled directly in assets/bin/texconv/ — no external Blender
addon dependency. Flag logic (-sepalpha, -x2bias) ported from
NSA-Cloud/AsteriskAmpersand's RE-Mesh-Editor texconv.py wrapper (MIT).
"""

import ctypes
import os
import shutil
import struct
import tempfile
import zlib

from . import dxgi_format as dxgi

_DLL = None

# PNG colour-space chunks that make WIC report the image as sRGB-encoded, which
# in turn makes DirectXTex gamma-convert the pixels on load.  See
# _sanitize_png_color_metadata.
_PNG_COLOR_CHUNKS = (b'sRGB', b'cHRM', b'iCCP', b'gAMA')
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
#: gAMA is stored as gamma * 100000, so this is gamma 1.0 -- "these bytes are
#: already in their final encoding".  Written explicitly rather than left absent
#: because it is exactly what texconv's own PNG writer emits, and that output is
#: known to round-trip through this function unchanged.
_GAMA_UNITY = struct.pack('>I', 100000)


def _png_chunks(raw):
    """Yield ``(type, payload)`` for each chunk in a PNG byte string."""
    i = len(_PNG_SIGNATURE)
    while i + 8 <= len(raw):
        length, ctype = struct.unpack('>I4s', raw[i:i + 8])
        yield ctype, raw[i + 8:i + 8 + length]
        i += 12 + length  # length + type + payload + CRC


def _png_chunk(ctype, payload):
    return (struct.pack('>I', len(payload)) + ctype + payload
            + struct.pack('>I', zlib.crc32(ctype + payload) & 0xFFFFFFFF))


def _sanitize_png_color_metadata(filepath, work_dir):
    """A copy of *filepath* with its colour-space chunks replaced by gamma 1.0.

    Blender's PNG writer always tags its output ``sRGB`` + ``gAMA`` 1/2.2 +
    ``cHRM``, no matter what the image datablock's colorspace is set to -- so a
    ``Non-Color`` composed slot map still comes out of ``Image.save()`` claiming
    to be sRGB-encoded.  texconv reads PNGs through WIC, which honours that
    claim, and DirectXTex then *linearises* the pixels on load: every composed
    map came out darkened by a full sRGB->linear curve, colour and packed data
    alike.

    That silently contradicted this module's whole contract (sRGB is a tag, the
    bytes pass through untouched), and it was invisible in the composed PNG --
    the file on disk had the right bytes all along, only the metadata lied.

    Returns the original path unchanged for anything that is not a PNG, and for
    a PNG that carries no such chunks.
    """
    if not filepath.lower().endswith('.png'):
        return filepath
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
    except OSError:
        return filepath
    if not raw.startswith(_PNG_SIGNATURE):
        return filepath
    if not any(ctype in _PNG_COLOR_CHUNKS for ctype, _ in _png_chunks(raw)):
        return filepath

    out = [_PNG_SIGNATURE]
    gama_written = False
    for ctype, payload in _png_chunks(raw):
        if ctype in _PNG_COLOR_CHUNKS:
            continue
        if ctype == b'IDAT' and not gama_written:
            # Ancillary chunks must precede IDAT; this is the last legal spot.
            out.append(_png_chunk(b'gAMA', _GAMA_UNITY))
            gama_written = True
        out.append(_png_chunk(ctype, payload))

    # Same basename: texconv names its output after the input stem, and callers
    # (slot_resolver.write_slot_tex) then look for that exact name.
    dst_dir = tempfile.mkdtemp(prefix='png_srgb_', dir=work_dir or None)
    dst = os.path.join(dst_dir, os.path.basename(filepath))
    with open(dst, 'wb') as f:
        f.write(b''.join(out))
    return dst


def _bin_dir():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, "assets", "bin", "texconv")


def _ensure_com_initialized():
    """texconv reads images via WIC, which requires COM to be initialized on the
    calling thread. Safe to call repeatedly (COM reference-counts init calls);
    we never pair it with CoUninitialize since the host process (Blender) outlives us."""
    COINIT_APARTMENTTHREADED = 0x2
    ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)


def _load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL
    dll_path = os.path.join(_bin_dir(), "texconv.dll")
    if not os.path.isfile(dll_path):
        raise RuntimeError(f"texconv library not found: {dll_path}")
    _DLL = ctypes.cdll.LoadLibrary(dll_path)
    return _DLL


def unload_dll():
    global _DLL
    if _DLL is None:
        return
    ctypes.windll.kernel32.FreeLibrary(_DLL._handle)
    _DLL = None


def _is_signed(fmt_name):
    return 'SNORM' in fmt_name or 'SF16' in fmt_name


def _run_texconv(dll, file, args, out_dir, verbose=False, allow_slow_codec=False):
    args = list(args)
    if out_dir:
        args += ['-o', out_dir]
        if out_dir not in ('.', '') and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
    args += ['-y', '--', os.path.normpath(file)]

    args_p = (ctypes.c_wchar_p * len(args))(*[ctypes.c_wchar_p(a) for a in args])
    err_buf = ctypes.create_unicode_buffer(512)
    result = dll.texconv(len(args), args_p, verbose, False, allow_slow_codec, err_buf, 512)
    if result != 0:
        raise RuntimeError(err_buf.value)


def convert_to_dds(filepath, dxgi_format_name, out_dir, generate_mips=True,
                    image_filter="CUBIC", verbose=False, allow_slow_codec=False,
                    size=None):
    """Convert an image (PNG/TGA/DDS/etc, whatever texconv itself supports) to a
    DX10-header DDS using the given DXGI format name (e.g. "BC7_UNORM_SRGB").

    sRGB-ness is a *tag only*: the "SRGB" in dxgi_format_name goes into the DDS
    header (and on to the .tex header) to tell the GPU how to decode, but the
    pixel bytes are never gamma-converted — a source PNG is already sRGB-encoded,
    so an extra decode/encode pass would only lose precision or, if it doesn't
    round-trip exactly, darken the result. This deliberately does NOT pass
    texconv's -srgb (TEX_FILTER_SRGB_IN|OUT), matching how kagenocookie's
    REE-Content-Editor converts textures (DirectXTex called with plain
    TexCompressFlags.Default and the sRGB-ness carried only by the format enum).

    Callers must still pass the format matching the texture's *role*, since that
    tag is what the shader honours (see core/mdf_tex_processor_base.py's
    SRGB_SLOT_TYPES for how that's decided per slot).

    ``image_filter`` defaults to CUBIC rather than texconv's own LINEAR default,
    again to match REE-Content-Editor (TexFilterFlags.Cubic|SeparateAlpha) — its
    mips hold detail noticeably better at the lower levels.

    ``size`` is an optional (width, height) to resize to; the game engines
    want powers of two and non-conforming sizes can crash them.

    Returns the path to the resulting .dds file.
    """
    if not dxgi.is_valid_format_name(dxgi_format_name):
        raise ValueError(f"Not a known DXGI format: {dxgi_format_name}")

    _ensure_com_initialized()
    dll = _load_dll()

    # Must happen before texconv sees the file: a PNG claiming to be sRGB gets
    # gamma-decoded on load, which is precisely what this function promises not
    # to do.  Applies to every source, not just Blender's own -- a PNG exported
    # from Photoshop carries the same tags.
    filepath = _sanitize_png_color_metadata(filepath, out_dir)

    args = ['-f', dxgi_format_name, '-sepalpha']  # -sepalpha: without it, alpha gets mangled by mip generation
    if not generate_mips:
        args += ['-m', '1']
    if image_filter:
        args += ['-if', image_filter]
    if size:
        # texconv resizes before compressing, so the block encoder sees the
        # final resolution rather than a downscale of an already-lossy image
        args += ['-w', str(int(size[0])), '-h', str(int(size[1]))]
    if _is_signed(dxgi_format_name):
        args += ['-x2bias']

    _run_texconv(dll, filepath, args, out_dir, verbose=verbose, allow_slow_codec=allow_slow_codec)

    base_name = os.path.splitext(os.path.basename(filepath))[0] + '.dds'
    return os.path.join(out_dir or '.', base_name)


#: TGA header: id_length, colour_map_type, image_type(2=uncompressed true-colour),
#: colour map spec (5B, unused), x/y origin, width, height, depth, descriptor.
#: Mirrors core/tga_file.py's own _HEADER_STRUCT_FMT -- kept separate rather than
#: imported since that module writes only, this reads only, and the two staying
#: in sync is trivially checked by inspection (both are the documented TGA spec).
_TGA_HEADER = struct.Struct('<BBB5s2H2HBB')


def _read_tga_rgba8(filepath):
    """Read an uncompressed 32bpp true-colour TGA into an (h, w, 4) uint8 array,
    channel order RGBA, row 0 = top of the image regardless of how the file
    stored it (the descriptor's bit 5 says which; flipped to a single canonical
    order here so callers never have to think about it again)."""
    import numpy as np

    with open(filepath, 'rb') as f:
        raw = f.read()
    id_length, _cmap_type, img_type, _cmap_spec, _x0, _y0, w, h, bpp, descriptor = \
        _TGA_HEADER.unpack_from(raw, 0)
    if img_type != 2 or bpp != 32:
        raise ValueError(f"Unsupported TGA layout (type={img_type}, bpp={bpp}): {filepath}")

    start = _TGA_HEADER.size + id_length
    body = raw[start:start + w * h * 4]
    arr = np.frombuffer(body, dtype=np.uint8).reshape(h, w, 4)
    if not (descriptor & 0x20):  # bit 5 clear = stored bottom-up
        arr = arr[::-1]
    return arr[:, :, [2, 1, 0, 3]]  # BGRA on disk -> RGBA


def convert_to_raw_rgba(filepath, out_dir, verbose=False, allow_slow_codec=False):
    """Decompress any texconv-readable image (DDS in any DXGI format, or
    PNG/TGA/JPG/etc.) straight to an (h, w, 4) uint8 RGBA numpy array.

    Same never-gamma-convert contract as convert_to_png (see its docstring),
    just handed back as pixels instead of a file -- for callers that want to
    do further numpy processing (e.g. convert_to_dds_area_mips below) without
    depending on PIL, which Blender's bundled Python does not ship.  Routes
    through TGA rather than PNG for exactly that reason: this addon already
    carries a trivial TGA reader/writer (core/tga_file.py) for the same "no
    image library available" constraint, whereas decoding PNG's DEFLATE stream
    from scratch would mean reimplementing part of zlib's inflate.
    """
    _ensure_com_initialized()
    dll = _load_dll()

    args = ['-f', 'R8G8B8A8_UNORM', '-ft', 'TGA']

    # Into a private subdirectory, not out_dir.  texconv names its output after
    # the input stem, so a .tga source that already lives in out_dir would have
    # the output land on top of it -- and then the cleanup below would delete the
    # caller's own file.  That is not hypothetical: composed slots and generated
    # solid colours are both .tga written into the very temp dir that gets passed
    # here as out_dir, and the symptom is a FileNotFoundError (80070002) on the
    # *next* use of a source that had silently vanished.
    work = tempfile.mkdtemp(prefix='raw_rgba_', dir=out_dir or None)
    _run_texconv(dll, filepath, args, work, verbose=verbose, allow_slow_codec=allow_slow_codec)

    tga_path = os.path.join(work, os.path.splitext(os.path.basename(filepath))[0] + '.tga')
    try:
        return _read_tga_rgba8(tga_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _is_pot(v):
    return v > 0 and (v & (v - 1)) == 0


def convert_to_dds_area_mips(filepath, dxgi_format_name, out_dir, size=None,
                              verbose=False, allow_slow_codec=False):
    """Like convert_to_dds(generate_mips=True), but builds every mip level by
    box-averaging directly from the full-resolution source, rather than
    recursively re-filtering the previous level with texconv's own CUBIC (or
    any other interpolation-style) filter.

    Why this exists: CUBIC (and similarly LINEAR/POINT) are *interpolation*
    filters -- good for resizing smooth content, but their support is narrower
    than the pixel footprint they are decimating, so repeated 2x downsampling
    under-suppresses spatial frequencies near each level's Nyquist limit. For a
    texture with fine, repeating, high-contrast detail (a woven/quilted fabric
    baked into a normal map, say) that shows up as aliasing that barely decays
    down the mip chain -- measured on one such texture, curvature-energy stayed
    at ~1.4-2.0 from 256px all the way to 16px. A true box average -- the mean
    over the *entire* source footprint each output texel covers -- is the
    textbook-correct decimation filter and does not have this problem (same
    texture, same metric: 0.05 at 256px down to 0.001 at 16px). Because box
    averaging is linear and associative, computing it directly from the source
    at each level's exact resolution gives the identical result a from-scratch
    box filter at that footprint would -- it just avoids compounding whatever
    rounding/quantization the intermediate BC7 recompression of each previous
    level would otherwise introduce.

    Only useful for content with fine repeating/high-contrast detail -- for
    smooth textures this and the recursive CUBIC path look the same, and this
    is slower (one texconv encode per mip level instead of one call total).

    Requires power-of-two width and height (after `size`, if given) so every
    level's box filter divides evenly; raises ValueError otherwise; callers
    should fall back to convert_to_dds(generate_mips=True) in that case, same
    as they already do for non-power-of-two textures elsewhere in this addon.

    Returns the path to the resulting .dds file.
    """
    import numpy as np
    from . import dds_file

    if not dxgi.is_valid_format_name(dxgi_format_name):
        raise ValueError(f"Not a known DXGI format: {dxgi_format_name}")

    rgba = convert_to_raw_rgba(filepath, out_dir, verbose=verbose, allow_slow_codec=allow_slow_codec)
    h, w = rgba.shape[:2]

    if size:
        tw, th = int(size[0]), int(size[1])
        if (tw, th) != (w, h):
            if tw <= 0 or th <= 0 or w % tw or h % th:
                raise ValueError(
                    f"convert_to_dds_area_mips needs size {size} to evenly divide "
                    f"the source resolution {w}x{h}")
            bw, bh = w // tw, h // th
            rgba = rgba.reshape(th, bh, tw, bw, 4).mean(axis=(1, 3))
            w, h = tw, th

    if not (_is_pot(w) and _is_pot(h)):
        raise ValueError(f"convert_to_dds_area_mips needs power-of-two dimensions, got {w}x{h}")

    from .tga_file import write_tga_rgba8

    stem = os.path.splitext(os.path.basename(filepath))[0]
    level = rgba.astype(np.float32) / 255.0  # (h, w, 4) in 0..1, row 0 = top
    cw, ch = w, h
    mips = []
    out_fmt = None

    while True:
        tmp_tga = os.path.join(out_dir, f"__area_mip_{stem}_{cw}x{ch}.tga")
        # write_tga_rgba8 expects row 0 = bottom (Blender's own convention,
        # see its docstring); our arrays are row 0 = top throughout, so flip
        # only at this final handoff.
        write_tga_rgba8(tmp_tga, level[::-1])
        level_dds = None
        try:
            level_dds = convert_to_dds(tmp_tga, dxgi_format_name, out_dir, generate_mips=False,
                                       verbose=verbose, allow_slow_codec=allow_slow_codec)
            d = dds_file.read_dds(level_dds)
            mips.append(d.mips[0])
            out_fmt = d.dxgi_format
        finally:
            if os.path.isfile(tmp_tga):
                os.remove(tmp_tga)
            if level_dds and os.path.isfile(level_dds):
                os.remove(level_dds)

        if cw == 1 and ch == 1:
            break
        nw, nh = max(1, cw // 2), max(1, ch // 2)
        bw, bh = cw // nw, ch // nh
        level = level[:nh * bh, :nw * bw].reshape(nh, bh, nw, bw, 4).mean(axis=(1, 3))
        cw, ch = nw, nh

    out_dds = dds_file.DDSFile()
    out_dds.width, out_dds.height = w, h
    out_dds.dxgi_format = out_fmt
    out_dds.mips = mips
    out_path = os.path.join(out_dir, stem + '.dds')
    dds_file.write_dds(out_dds, out_path)
    return out_path


def convert_to_png(filepath, out_dir, verbose=False, allow_slow_codec=False):
    """Decompress a DDS (any DXGI format, including BC7_UNORM_SRGB) to a plain
    8-bit PNG, always mip 0.

    Mirrors convert_to_dds's own rule in reverse: never gamma-convert, just hand
    back the stored bytes. No -srgb/-srgbi/-srgbo regardless of whether the
    source is tagged _SRGB — an editor (Photoshop, GIMP, ...) that instead
    re-decodes on its own DDS import and re-encodes on PNG export is exactly
    what silently doubles the gamma curve on a round trip through an external
    tool. Keeping this byte-for-byte means feeding the PNG back into
    core/mdf_tex_processor_base.py's PBR compose and re-converting reproduces
    the original DDS exactly.

    Returns the path to the resulting .png file.
    """
    _ensure_com_initialized()
    dll = _load_dll()

    args = ['-f', 'R8G8B8A8_UNORM', '-ft', 'PNG']
    _run_texconv(dll, filepath, args, out_dir, verbose=verbose, allow_slow_codec=allow_slow_codec)

    base_name = os.path.splitext(os.path.basename(filepath))[0] + '.png'
    return os.path.join(out_dir or '.', base_name)
