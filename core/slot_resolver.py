"""Shared slot resolution: turning one source image into one game .tex.

The processor (existing MDF → replace textures) and the generators (Blender
material → new MDF from preset) start from different places and should keep
separate entry points — "I have the original MDF" and "I am building from
scratch" are genuinely different starting points, and merging them would just
push the difference into UI branches.

What must *not* be duplicated is the tail: given a source image file and a
destination, write the game's .tex.  That block had drifted into seven near
copies:

  - the processor handled .tex passthrough and .dds direct conversion; the
    generators did not, so a .dds source was needlessly decoded and
    re-compressed through texconv
  - MHWI's tex writer takes (dds_paths, out), the RE games' takes
    (dds_paths, version, out)

Callers pass ``dds_to_tex`` already bound to their tex version, which is what
lets one function serve both signatures.
"""

import os
import shutil


def resolve_dds_format(slot_type, srgb_slots):
    """DXGI format name for a slot's texture data.

    One decision bit — colour or not — exactly as kagenocookie/REE-Content-Editor
    does it (its Color Texture / Non-Color Texture presets are BC7_UNORM_SRGB and
    BC7_UNORM, and none of its per-slot packing presets ever picks BC5). BC7 also
    suits MHWI's MRL3 normals: the shader ignores B there, so the safer four-
    channel format costs nothing over a two-channel BC5.
    """
    return 'BC7_UNORM_SRGB' if slot_type in srgb_slots else 'BC7_UNORM'


def grade_source_file(src_img, temp_dir, dds_fmt, grade_mode):
    """Colour-grade *src_img* to a new TGA, or None when nothing needs doing.

    Runs on the decoded float buffer rather than on the finished 8-bit texture:
    grading an already-quantised image throws away shadow detail it cannot get
    back (measured: a median-66 fabric albedo collapses to median 14, with the
    darks squeezed into a dozen levels).  Here the quantisation happens once, on
    the way out.

    Skipped for .tex sources -- those are already in a game container, and
    decoding one needs the per-game decoder this module deliberately does not
    depend on.  They are handled by the passthrough branch above.
    """
    from . import color_grade
    if grade_mode == 'NONE' or not color_grade.is_color_format(dds_fmt):
        return None

    from . import texconv_native, tga_file
    import numpy as np

    arr = texconv_native.convert_to_raw_rgba(src_img, temp_dir).astype(np.float32) / 255.0
    out = color_grade.grade(arr, grade_mode)
    # 新的 stem：避免和未处理的同名源在 temp_dir 里互相覆盖（texconv 按 stem 命名输出）
    stem = os.path.splitext(os.path.basename(src_img))[0] + '_' + grade_mode.lower()
    path = os.path.join(temp_dir, stem + '.tga')
    # convert_to_raw_rgba hands back row 0 = top; write_tga_rgba8 wants row 0 =
    # bottom (Blender's convention -- see its docstring).  Without this flip every
    # graded texture ships upside down, and only the graded ones, which is exactly
    # the kind of bug that gets blamed on the grading maths.
    tga_file.write_tga_rgba8(path, out[::-1])
    return path


def write_slot_tex(src_img, disk_path, temp_dir, *,
                   dds_fmt, generate_mipmaps, mip_quality='FAST',
                   image_to_dds, dds_to_tex, grade_mode='NONE'):
    """Convert one source image into a .tex at ``disk_path``.

    ``src_img``     source file: .tex, .dds, or anything texconv reads
    ``dds_to_tex``  callable (dds_path_list, out_path) -> None, already bound
                    to the caller's tex version
    ``image_to_dds`` callable ([(src, fmt)], out_dir, mipmaps, mip_quality) -> None
    ``mip_quality`` 'FAST' (texconv's own recursive CUBIC) or 'QUALITY'
                    (core.texconv_native.convert_to_dds_area_mips); ignored
                    when ``generate_mipmaps`` is False.
    ``grade_mode``  core.color_grade mode, applied to **colour slots only** and
                    only when not 'NONE'.  Which slots count is read off dds_fmt
                    (the _SRGB suffix), so it follows resolve_dds_format rather
                    than keeping a second list of colour slot types.

    Creates the destination directory.  Raises FileNotFoundError if texconv
    produced nothing, so a silent zero-byte texture cannot reach the game.
    """
    os.makedirs(os.path.dirname(disk_path), exist_ok=True)

    src_name  = os.path.basename(src_img)
    src_lower = src_img.lower()

    # Substring rather than extension match — preserved verbatim from the
    # processor, whose behaviour this function must not change.  It means a
    # source like "foo.texture.png" is copied raw instead of converted; see the
    # note in the commit that introduced this module.
    if '.tex' in src_name.lower():
        shutil.copy2(src_img, disk_path)
        return src_img

    if src_lower.endswith('.dds'):
        dds_to_tex([src_img], disk_path)
        return src_img

    # texconv names its output after the input, in out_dir.  Callers that pull
    # sources from outside temp_dir must stage them under a unique stem first
    # (see slot_sources.stage_source_file) or two slots sharing a basename will
    # collide here under different sRGB flags.
    graded = grade_source_file(src_img, temp_dir, dds_fmt, grade_mode)
    if graded is not None:
        src_img, src_name = graded, os.path.basename(graded)

    dds_path = os.path.join(temp_dir, os.path.splitext(src_name)[0] + '.dds')
    image_to_dds([(src_img, dds_fmt)], temp_dir, generate_mipmaps, mip_quality)
    if not os.path.isfile(dds_path):
        raise FileNotFoundError(f"texconv output not found: {dds_path}")
    dds_to_tex([dds_path], disk_path)
    return dds_path
