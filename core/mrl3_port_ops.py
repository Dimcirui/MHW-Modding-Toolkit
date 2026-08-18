"""MRL3 -> MDF2 port, execution layer.

One MHWI ``.mrl3`` collection in, one MHWilds ``.mdf2`` collection out, with the
textures actually recoded rather than left pointing at MT Framework paths.

Three things are borrowed wholesale rather than rebuilt, because the RE-to-RE port
already does them and a second copy would drift:

* ``re_mdf_presets.readPresetJSON`` builds the destination material from the shipped
  ``basic`` prefab -- the same call ``core/mdf_port_ops.py`` makes,
* ``mdf_tex_processor_base._compose_channels`` packs PBR planes into a MHWilds slot,
* ``mdf_port_tex.write_ported_tex`` puts the result on disk under MHWilds' own naming
  and container conventions.

What is new here is the front half of the texture path.  The RE-to-RE port unpacks one
source slot at a time, because RE games' slots correspond one to one; MHWI's do not,
so a whole material's slots are decoded together and taken apart into PBR planes by
``core/mrl3_port_tex.py`` before any of them is repacked.  ``RMTMap`` alone feeds three
different MHWilds slots.

Source textures are read off disk, not out of Blender: MHWI's importer converts to a
preview format, and porting the preview would ship a re-encoded, sometimes rescaled
copy of the texture instead of the one the mod actually has.  MHWI's own on-disk
convention is ``<natives root>/nativePC/<mapList value>.tex`` -- no ``Art/`` prefix and
no version suffix, both of which the RE side has.
"""

import os
import tempfile

import bpy

from . import mdf_port_tex, mrl3_port, mrl3_port_tex
from .i18n import T
from .mdf_port_ops import import_read_preset_json
from .port_consent import gate

#: The game this port actually builds against.  It stays MHWilds even when the user
#: asks for MHRS, because MHWilds is the only game MHWI's material model has been
#: mapped onto: mrl3_port's 23 parameter destinations are all Base_Equip names.
DST_GAME = "MHWS"
SRC_NATIVES_KEY = "mhwi_natives_root"

#: Targets offered to the user.  MHRS is reached by handing the MHWilds result to
#: the ordinary MHWS -> MHRS material port, not by a second mrl3 table.
#:
#: Measured before choosing (2026-08-16).  Of the 23 mrl3 destinations that exist
#: in Base_Equip, 6 survive the second hop; of the 17 that do not, **15 have no
#: counterpart in MHRS at all** -- PL_Default is a single shader with no
#: RoughnessParam, no ColorParam, no SSS and no ColorLayer, so a direct table
#: could not carry them either.  A whole parallel pipeline would buy 8 of 23
#: instead of 6.
#:
#: Texture quality does not pay for the extra hop either: every one of the 15
#: MHWS slot types maps to an MHRS slot with an identical channel layout, so
#: ``mdf_port_tex.repack_slot`` takes its "container rewrite, pixels untouched"
#: path for all of them.  The one real decode/encode happens in this port, once.
TARGET_GAMES = ("MHWS", "MHRS")

#: Spelled out rather than built from TARGET_GAMES with an f-string: a key the
#: table check cannot read as a literal is a key it cannot verify exists.
_TARGET_ITEMS = (
    ("MHWS", "core.mrl3_port_ops.target_mhws", "core.mrl3_port_ops.target_mhws_desc"),
    ("MHRS", "core.mrl3_port_ops.target_mhrs", "core.mrl3_port_ops.target_mhrs_desc"),
)

#: Persistent backing for the dynamic enum below.  Blender's C side keeps the
#: pointers to these strings, so a list built fresh inside the callback is freed
#: the moment Python drops it -- the same trap core/ref_skeleton.py and
#: core/chain_convert_ops.py both document.  Cleared and refilled rather than
#: built once, so switching language still re-resolves the labels.
_target_item_cache = []


def _target_game_items(self=None, context=None):
    _target_item_cache.clear()
    _target_item_cache.extend((g, T(label), T(desc)) for g, label, desc in _TARGET_ITEMS)
    return _target_item_cache


#: Where the second hop's output should end up named, given this port's own output.
_RELAY_TARGET = "MHRS"

#: mrl3 stores a property's value in a field named after its type; so does MDF, with
#: a different set of names.  Neither exposes a generic "value".
#:
#: The vector keys carry brackets -- ``FLOAT[3]``, not ``FLOAT3`` -- because that is
#: how MHW Model Editor spells the enum, mirroring the type strings in its own
#: ``property_dict.json``.  Getting this wrong does not raise: the lookup misses, the
#: field is treated as absent, and the parameter is silently skipped.
_MRL3_VALUE_ATTR = {
    "FLOAT": "float_value", "INT": "int_value", "UINT": "uint_value",
    "BOOL": "bool_value", "FLOAT[2]": "float2_value", "FLOAT[3]": "float3_value",
    "FLOAT[4]": "float4_value", "COLOR": "color_value",
}
_MDF_VALUE_ATTR = {
    "FLOAT": "float_value", "BOOL": "bool_value", "COLOR": "color_value",
    "VEC4": "float_vector_value", "FLOAT4": "float_vector_value",
}


# ── source discovery ────────────────────────────────────────────────────────────

def is_mrl3_collection(col):
    return col.get("~TYPE") == "MHW_MRL3_COLLECTION" or col.name.endswith(".mrl3")


def mrl3_materials(col):
    return [o for o in col.objects
            if o.get("~TYPE") == "MHW_MRL3_MATERIAL"
            and getattr(o, "mhw_mrl3_material", None)]


def source_tex_path(natives_root, map_value):
    """``<natives root>/nativePC/<mapList value>.tex``.

    MHWI's binding is a bare backslash path with no extension and no ``nativePC``
    segment -- ``Dimcirui\\AiriSeraphim\\Body_BML`` -- so both are added back here.
    Unlike the RE side there is no version suffix on the filename.
    """
    rel = (map_value or "").replace("\\", "/").strip("/")
    if not rel:
        return ""
    return os.path.join(natives_root, "nativePC", *rel.split("/")) + ".tex"


def _is_null_tex(value):
    """MHWI's stand-in textures, which exist to fill a slot and mean "nothing here"."""
    return "null_" in (value or "").lower()


# ── MHWI texture decode ─────────────────────────────────────────────────────────

def _mhw_tex_module():
    """MHW Model Editor's ``modules.tex.tex_function``, or None.

    Found by scanning ``sys.modules`` the same way
    ``games/mhwi/mrl3_tex_processor._import_mhwtex_convert`` does: the addon is
    installed under a name we do not control, so it cannot simply be imported.
    """
    import sys
    for key, mod in sys.modules.items():
        if key.endswith(".modules.tex.tex_function"):
            return mod
    return None


def decode_mhwi_tex(tex_path, temp_dir):
    """A MHWI ``.tex`` -> a PNG path, via MHW Model Editor's own decoder.

    Two hops, because neither side speaks the other's container: MT Framework's tex
    is unwrapped to DDS by the editor that knows its header, and DDS is what texconv
    turns into something with addressable pixels.
    """
    mod = _mhw_tex_module()
    if mod is None:
        raise RuntimeError("MHW Model Editor's tex module is not loaded")
    tex_file_cls = getattr(mod, "MHWTexFile", None)
    to_dds = getattr(mod, "convertTexFileToDDS", None)
    if tex_file_cls is None or to_dds is None:
        raise RuntimeError("MHW Model Editor's tex decoder is missing")

    from . import texconv_native

    tex = tex_file_cls()
    tex.read(tex_path)
    stem = os.path.splitext(os.path.basename(tex_path))[0]
    dds_path = os.path.join(temp_dir, stem + "_mrl3_src.dds")
    # convertTexFileToDDS takes the *parsed* tex, not the path -- the commented-out
    # path-taking version above it in tex_function.py is not the live one.
    to_dds(tex.tex, dds_path)
    return texconv_native.convert_to_png(dds_path, temp_dir)


def _png_to_array(png_path):
    from .mdf_tex_processor_base import image_to_array

    name = "__mrl3_port_src"
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.load(png_path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = 'Non-Color'
    try:
        return image_to_array(img)
    finally:
        bpy.data.images.remove(img)


def new_tex_cache():
    """Backing store for the decode/compose caching below.

    Keyed on the source ``.tex`` **path**, not on the material -- which is the whole
    point.  One armour set's parts routinely bind the same texture from several
    materials, and decoding is three hops (MT tex -> DDS -> PNG -> array) of the most
    expensive work this port does.  A per-run dict rather than a module global, so a
    cache never outlives the temp directory the PNGs it names live in.
    """
    return {"png": {}, "arr": {}, "composed": {}}


def load_source_slots(mat_data, natives_root, temp_dir, cache=None, slots=None):
    """``({slot: array}, {slot: png path}, [missing], {slot: source path})``.

    The PNGs are kept alongside the arrays because the two slots that cross over
    unchanged -- masks, which have no PBR reading -- are written from the file rather
    than rebuilt from planes.

    The source paths come back too so the caller can tell whether two materials were
    built from the same pixels; nothing here uses them.

    *slots* narrows the work to the named slots.  The Nuki rule needs two of them
    read even in a run that writes no textures at all, and decoding is three hops per
    file -- so "decode everything and use two" is not an option there.
    """
    arrays, pngs, missing, sources = {}, {}, [], {}
    for item in mat_data.mapList_items:
        slot = item.name
        if slots is not None and slot not in slots:
            continue
        if not item.value or _is_null_tex(item.value):
            continue
        if slot not in mrl3_port_tex.DECODE_MAP and slot not in mrl3_port_tex.DIRECT_SLOTS:
            continue
        path = source_tex_path(natives_root, item.value)
        if not path or not os.path.isfile(path):
            missing.append(f"{slot}: {item.value}")
            continue
        try:
            png_cache = cache["png"] if cache is not None else None
            if png_cache is not None and path in png_cache:
                png = png_cache[path]
            else:
                png = decode_mhwi_tex(path, temp_dir)
                if png_cache is not None:
                    png_cache[path] = png
            pngs[slot] = png
            sources[slot] = path
            if slot in mrl3_port_tex.DECODE_MAP:
                arr_cache = cache["arr"] if cache is not None else None
                if arr_cache is not None and path in arr_cache:
                    arrays[slot] = arr_cache[path]
                else:
                    arrays[slot] = _png_to_array(png)
                    if arr_cache is not None:
                        arr_cache[path] = arrays[slot]
        except Exception as err:
            missing.append(f"{slot}: {err}")
    return arrays, pngs, missing, sources


# ── material rebuild ────────────────────────────────────────────────────────────

def apply_flags(src_data, dst_data):
    """Carry MHWI's surface/alpha coefficients over as MDF flags.

    ``alpha_test`` is only ever turned *on*.  The rule behind it is sufficient but not
    necessary -- see ``mrl3_port.decode_flags`` -- so forcing it off where MHWI calls
    a material opaque would override the prefab's own, better-informed default.
    """
    flags = mrl3_port.decode_flags(list(src_data.surfaceCoef), list(src_data.alphaCoef))
    dst_data.flags.BaseTwoSideEnable = flags["two_side"]
    if flags["alpha_test"]:
        dst_data.flags.BaseAlphaTestEnable = True
    return flags


def _mrl3_values(src_data):
    """``{ori_name: value}`` across every constant buffer the material carries."""
    out = {}
    for block in src_data.propertyBlock_items:
        for item in block.propertyList_items:
            attr = _MRL3_VALUE_ATTR.get(item.data_type)
            if attr is None:
                continue
            value = getattr(item, attr, None)
            if hasattr(value, "__len__") and not isinstance(value, str):
                value = list(value)
            out[item.ori_name] = value
    return out


def _set_mdf_prop(dst_data, prop_name, value, converter):
    """Write one MDF property, converting mrl3's type spelling into MDF's."""
    item = next((p for p in dst_data.propertyList_items
                 if p.prop_name == prop_name), None)
    if item is None:
        return False
    attr = _MDF_VALUE_ATTR.get(item.data_type)
    if attr is None:
        return False

    if converter == "scalar":
        setattr(item, attr, float(value))
    elif converter == "bool":
        setattr(item, attr, bool(value))
    elif converter in ("bool_as_float", "uint_as_float"):
        setattr(item, attr, float(value))
    elif converter in ("color4", "color3"):
        rgba = list(value)[:4]
        while len(rgba) < 4:
            rgba.append(1.0)
        target = getattr(item, attr)
        for i in range(min(len(target), 4)):
            target[i] = rgba[i]
    else:
        return False
    return True


def migrate_params(src_data, dst_data, mode):
    """Returns ``(migrated, skipped)``."""
    values = _mrl3_values(src_data)
    migrated = skipped = 0
    for src_name, dst_name, converter in mrl3_port.param_pairs(mode):
        if src_name not in values:
            skipped += 1
            continue
        if _set_mdf_prop(dst_data, dst_name, values[src_name], converter):
            migrated += 1
        else:
            skipped += 1

    if mode == "ALL" and mrl3_port.EMISSIVE_SOURCE in values:
        rgba, power = mrl3_port.split_emissive(values[mrl3_port.EMISSIVE_SOURCE])
        colour_ok = _set_mdf_prop(dst_data, "Emissive_Color", rgba, "color4")
        power_ok = _set_mdf_prop(dst_data, "Emissive_Power", power, "scalar")
        migrated += int(colour_ok) + int(power_ok)
        skipped += int(not colour_ok) + int(not power_ok)
    return migrated, skipped


# ── texture rebuild ─────────────────────────────────────────────────────────────

def port_textures(mat_data, dst_data, tex_name, arrays, pngs, dst_cfg,
                  dst_root, dst_base, temp_dir, cache=None, sources=None):
    """Fill the new material's bindings, writing each texture out.  ``(written, notes)``.

    With a *cache*, the composed PNG for a destination slot is reused whenever a
    later material decomposes from **the same set of source files**, which is the
    signature *sources* carries.  Deliberately the whole material's source set
    rather than just the planes one slot reads: it costs a few missed hits and buys
    the guarantee that a hit means identical pixels, which a per-plane key would
    have to prove separately for every slot in ``BASE_SLOT_CHANNEL_MAPS``.

    Only the compose is shared.  The write is not: the file name is built from
    *tex_name*, so each material still gets its own ``.tex`` on disk.
    """
    from .mdf_tex_processor_base import BASE_SLOT_CHANNEL_MAPS, _compose_channels

    planes, notes = mrl3_port_tex.decompose(arrays)
    written = 0
    signature = (tuple(sorted((sources or {}).values()))
                 if cache is not None and sources else None)

    for binding in dst_data.textureBindingList_items:
        slot = binding.textureType
        source = None

        direct_src = next((s for s, d in mrl3_port_tex.DIRECT_SLOTS.items()
                           if d == slot and s in pngs), None)
        if direct_src is not None:
            # A mask has no PBR reading to take apart, so it crosses as pixels.
            source = ("png", pngs[direct_src])
        elif planes and slot in BASE_SLOT_CHANNEL_MAPS:
            needed = {src[0] for src in BASE_SLOT_CHANNEL_MAPS[slot].values()
                      if isinstance(src, tuple)}
            # Only rebuild a slot the source actually has something for.  Without
            # this every slot in the prefab would be written, burying the four real
            # textures in twenty neutral ones.
            if not (needed & set(planes)):
                continue
            key = (slot, signature) if signature is not None else None
            if key is not None and key in cache["composed"]:
                composed = cache["composed"][key]
            else:
                composed = _compose_channels(
                    slot, {}, {}, temp_dir, tex_name,
                    channel_maps=BASE_SLOT_CHANNEL_MAPS, pbr_arrays=planes,
                    octahedral=True)
                if key is not None and composed is not None:
                    cache["composed"][key] = composed
            if composed is None:
                continue
            source = ("png", composed)

        if source is None:
            continue
        mdf_path, on_disk = mdf_port_tex.write_ported_tex(
            source, slot, dst_cfg, tex_name, dst_root, dst_base, temp_dir)
        binding.path = mdf_path
        written += int(on_disk)
    return written, notes


def source_slots_present(mat_data, natives_root=None):
    """The source slots that hold a real texture this port can read.

    The same three tests ``load_source_slots`` applies -- bound, not a null stand-in,
    a slot with a decode or direct rule -- minus the decode itself.  The file-exists
    test is only made when *natives_root* is known, since without a root there is
    nothing to look in and the binding is still the author's stated intent.
    """
    out = set()
    for item in mat_data.mapList_items:
        slot = item.name
        if not item.value or _is_null_tex(item.value):
            continue
        if slot not in mrl3_port_tex.DECODE_MAP and slot not in mrl3_port_tex.DIRECT_SLOTS:
            continue
        if natives_root:
            path = source_tex_path(natives_root, item.value)
            if not path or not os.path.isfile(path):
                continue
        out.add(slot)
    return out


def port_texture_paths(mat_data, dst_data, tex_name, dst_cfg, dst_base,
                       natives_root=None):
    """Fill the bindings ``port_textures`` would fill, writing no pixels.  ``filled``.

    This is the "skip textures" half of the batch: the point of that run is to swap
    in a new mesh/mdf2/ctc against textures that are *already on disk* from an
    earlier full run, so the paths have to come out identical to what the full path
    would have produced -- otherwise the mdf2 points at nothing.

    Which slots get a path is the one thing that has to be re-derived rather than
    copied, and it is derivable: ``port_textures`` decides per destination slot by
    asking whether any PBR plane it reads was produced, and which planes exist
    follows from *which source slots are bound* through ``DECODE_MAP`` alone -- the
    pixel values never enter that decision.  So the two selections agree by
    construction, and ``tests/test_mrl3_port_tex.py`` pins them together.

    One case it cannot reproduce: ``_compose_channels`` returning None for a slot it
    was asked to build, which skips the binding in the full path and cannot be known
    without composing.  That leaves a path pointing at a ``.tex`` the full run did not
    write -- reported by the pre-export check rather than silently.
    """
    from .mdf_tex_processor_base import BASE_SLOT_CHANNEL_MAPS, make_mdf_path

    have = source_slots_present(mat_data, natives_root)
    planes = {pbr for slot in have if slot in mrl3_port_tex.DECODE_MAP
              for pbr, _index in mrl3_port_tex.DECODE_MAP[slot].values()}

    filled = 0
    for binding in dst_data.textureBindingList_items:
        slot = binding.textureType
        direct = any(dst == slot and src in have
                     for src, dst in mrl3_port_tex.DIRECT_SLOTS.items())
        if not direct:
            if not planes or slot not in BASE_SLOT_CHANNEL_MAPS:
                continue
            needed = {src[0] for src in BASE_SLOT_CHANNEL_MAPS[slot].values()
                      if isinstance(src, tuple)}
            if not (needed & planes):
                continue
        binding.path = make_mdf_path(dst_base, tex_name, slot,
                                     dst_cfg['abbrev_map'], dst_cfg['use_art_prefix'])
        filled += 1
    return filled


# ── the MHRS dissolve rule ──────────────────────────────────────────────────────

def read_nuki_dissolve(src_data, arrays):
    """One material's ``Nuki_Dissolve``, or None when the rule does not apply.

    *arrays* is what ``load_source_slots`` decoded -- which may hold only the two
    slots the rule reads, or nothing at all when the source root is unset.  A slot
    that is absent from it is either a null stand-in (read from the binding instead,
    which is the only way to tell white from black) or unreadable, and an unreadable
    albedo means no rule: guessing opaque there would write a dissolve the material
    never asked for.
    """
    bindings = {item.name: item.value for item in src_data.mapList_items}

    albedo_kind = mrl3_port.null_tex_kind(bindings.get(mrl3_port.NUKI_ALBEDO_SLOT))
    if albedo_kind == "white":
        strength = 1.0
    elif albedo_kind is not None:
        strength = None          # a black stand-in is not the flat-white case
    else:
        strength = mrl3_port_tex.albedo_alpha_strength(
            arrays.get(mrl3_port.NUKI_ALBEDO_SLOT))

    emissive = bindings.get(mrl3_port.NUKI_EMISSIVE_SLOT)
    if mrl3_port.null_tex_kind(emissive) is not None or not emissive:
        emissive_flat = True
    else:
        emissive_flat = mrl3_port_tex.is_flat_emissive(
            arrays.get(mrl3_port.NUKI_EMISSIVE_SLOT))

    factor = _mrl3_values(src_data).get(mrl3_port.NUKI_FACTOR_FIELD)
    if factor is None or len(factor) < 4:
        return None
    return mrl3_port.nuki_dissolve(strength, emissive_flat, factor[3])


def apply_nuki_dissolve(col, values):
    """Write the collected values onto the finished MHRS materials.  ``written``.

    After the relay, not before: the property is MHRS', and the intermediate the
    relay reads is built on MHWilds' ``basic`` prefab, which has no such property to
    carry across.
    """
    written = 0
    for name, data in mrl3_port._materials_by_name(col).items():
        value = values.get(name)
        if value is None:
            continue
        if _set_mdf_prop(data, mrl3_port.NUKI_TARGET_PROP, value, "scalar"):
            written += 1
    return written


# ── operator ────────────────────────────────────────────────────────────────────

_collection_item_cache = []


def _collection_items(self, context):
    """EnumProperty items must outlive the call: Blender's C side keeps the pointers."""
    _collection_item_cache.clear()
    _collection_item_cache.extend(
        (c.name, c.name, "") for c in bpy.data.collections if is_mrl3_collection(c))
    if not _collection_item_cache:
        _collection_item_cache.append(
            ("NONE", T("core.mrl3_port_ops.no_mrl3_collection"), ""))
    return _collection_item_cache


_mod3_item_cache = []


def _mod3_items(self, context):
    """The ``.mod3`` collections a material set can be checked against."""
    from .mhwi_port_ops import is_mod3_collection

    _mod3_item_cache.clear()
    _mod3_item_cache.extend(
        (c.name, c.name, "") for c in bpy.data.collections if is_mod3_collection(c))
    if not _mod3_item_cache:
        _mod3_item_cache.append(
            ("NONE", T("core.mrl3_port_ops.no_mod3_collection"), ""))
    return _mod3_item_cache


def _new_mdf_collection(src_col):
    stem = src_col.name
    if stem.endswith(".mrl3"):
        stem = stem[:-5]
    col = bpy.data.collections.new(f"{stem}_{DST_GAME}.mdf2")
    col["~TYPE"] = "RE_MDF_COLLECTION"
    # The outliner colour is how a user tells a material collection from a mesh or
    # chain one at a glance, and every importer sets it -- RE and MHWI both give
    # material collections COLOR_05.  A collection that carries the right ~TYPE but
    # no colour reads as "something the addon made wrong".
    col.color_tag = 'COLOR_05'
    parents = [c for c in bpy.data.collections if src_col.name in c.children]
    for parent in (parents or [bpy.context.scene.collection]):
        parent.children.link(col)
    return col


def used_material_names(mod3_col):
    """Material names the meshes of a ``.mod3`` collection actually reference.

    Read off the mesh object names -- ``Group_x_Sub_y__<material>`` -- through
    ``pre_export_check.parse_mesh_name``, so the dedup suffix Blender adds
    (``__Body.001``) is stripped exactly the way the exporter's own check strips it
    and a ported material is not culled for a name only Blender invented.
    """
    from .pre_export_check import parse_mesh_name

    names = set()
    for obj in mod3_col.objects:
        if obj.type != 'MESH':
            continue
        mat, how = parse_mesh_name(obj.name)
        if mat:
            names.add(mat)
        elif obj.data.materials:
            names.add(obj.data.materials[0].name.split(".")[0])
    return names


def run_port(context, src_col, target_game, *, dest_base_path="",
             params_mode='BASIC', convert_textures=True, cull_unused=True,
             mod3_col=None, src_root=None, dst_root=None, temp_dir=None,
             tex_cache=None, paths_only=False):
    """Port one MHWI ``.mrl3`` collection to *target_game*.  The port, minus the UI.

    *paths_only* builds the materials in full but writes no texture files, filling
    the bindings with the paths a full run would have produced.  For re-porting a set
    whose textures are already on disk, where the decode/compose/encode pass is the
    whole cost of the run.  The MHRS dissolve rule still reads its two slots -- it has
    to stay right, so the mode is "skip the writes", not "skip the pixels".

    Split out of the operator for the batch path.  Two of the parameters exist only
    for it:

    * *src_root* / *dst_root* default to the scene's own natives roots when left
      ``None``, which is what the operator wants -- but the batch writes into a
      folder the user picked for that run, which is not a scene setting at all.
    * *temp_dir*, when given, is neither created nor removed here.  Decoding is the
      expensive half of this port and an armour set's parts share source textures,
      so the batch keeps one directory across every part and cleans it up itself.

    Returns a dict; ``{"error": <T key>}`` when the port cannot start.
    """
    materials = mrl3_materials(src_col) if src_col else []
    if not materials:
        return {"error": "core.mrl3_port_ops.no_targets"}

    # Culled before anything is built, not after: a material that will not
    # survive should not cost a texture decode, and the count in the report is
    # then "what was ported", not "what was ported minus what was thrown away".
    culled = []
    if cull_unused:
        if mod3_col is None:
            return {"error": "core.mrl3_port_ops.pick_mod3"}
        used = used_material_names(mod3_col)
        keep = []
        for obj in materials:
            name = obj.mhw_mrl3_material.materialName or obj.name
            (keep if name in used else culled).append(obj if name in used else name)
        materials = keep
        if not materials:
            return {"error": "core.mrl3_port_ops.all_culled"}

    # Textures go straight to the *final* target, even when the material is
    # built against MHWilds' prefab on the way to MHRS.  Writing them as
    # MHWilds and fixing them up afterwards would mean either a second
    # decode/encode or a pile of orphaned .tex in the wrong container; writing
    # them once here costs nothing extra, because the two games' channel_maps
    # and abbrev_map are identical and only tex_version (241106027 vs 28),
    # use_art_prefix and the natives root differ.
    dst_cfg = mdf_port_tex.get_game_tex_config(target_game)
    if dst_cfg is None:
        return {"error": "core.mdf_port_ops.missing_tex_config"}

    read_preset = import_read_preset_json()
    if read_preset is None:
        return {"error": "core.mdf_port_ops.cannot_load_preset_tool"}

    prefab = mrl3_port.prefab_path()
    if prefab is None:
        return {"error": "core.mrl3_port_ops.no_prefab"}

    if src_root is None:
        src_root = context.scene.get(SRC_NATIVES_KEY, "")
    if dst_root is None:
        dst_root = context.scene.get(dst_cfg["natives_root_key"], "")
    dst_base = mdf_port_tex.full_base_path(dst_cfg, (dest_base_path or "").strip())
    convert = convert_textures and bool(src_root) and not paths_only
    # MHRS only: MHWilds' basic prefab has no Nuki_Dissolve to write.
    want_nuki = target_game == _RELAY_TARGET

    owns_temp = temp_dir is None
    if owns_temp:
        temp_dir = tempfile.mkdtemp(prefix="mrl3_port_")
    new_col = _new_mdf_collection(src_col)
    built = failed = tex_written = tex_paths = 0
    params_ok = params_skip = 0
    missing, notes, unportable = [], [], set()
    nuki_values = {}

    try:
        for obj in materials:
            src_data = obj.mhw_mrl3_material
            name = src_data.materialName or obj.name
            new_obj = read_preset(prefab, new_col)
            if not new_obj:
                failed += 1
                continue
            dst_data = new_obj.re_mdf_material
            dst_data.materialName = name
            apply_flags(src_data, dst_data)
            ok, skip = migrate_params(src_data, dst_data, params_mode)
            params_ok += ok
            params_skip += skip

            arrays = {}
            if convert:
                arrays, pngs, gone, sources = load_source_slots(
                    src_data, src_root, temp_dir, tex_cache)
                missing.extend(f"{name}/{m}" for m in gone)
                unportable.update(mrl3_port_tex.unportable(arrays))
                written, size_notes = port_textures(
                    src_data, dst_data, name.removesuffix('_UseSC'),
                    arrays, pngs, dst_cfg, dst_root, dst_base, temp_dir,
                    tex_cache, sources)
                tex_written += written
                notes.extend(f"{name}/{n}" for n in size_notes)
            else:
                if want_nuki and src_root:
                    arrays, _p, gone, _s = load_source_slots(
                        src_data, src_root, temp_dir, tex_cache,
                        slots=mrl3_port.NUKI_SLOTS)
                    missing.extend(f"{name}/{m}" for m in gone)
                if paths_only:
                    tex_paths += port_texture_paths(
                        src_data, dst_data, name.removesuffix('_UseSC'),
                        dst_cfg, dst_base, src_root)
            if want_nuki:
                value = read_nuki_dissolve(src_data, arrays)
                if value is not None:
                    nuki_values[name] = value
            built += 1
    finally:
        if owns_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    result = {
        "error": None, "collection": new_col, "built": built, "failed": failed,
        "textures": tex_written, "tex_paths": tex_paths,
        "params_ok": params_ok, "params_skip": params_skip,
        "culled": culled, "missing": missing, "notes": notes,
        "unportable": unportable,
        "source_root_missing": convert_textures and not paths_only and not src_root,
        "relay": None, "nuki": 0,
    }
    if target_game == _RELAY_TARGET and built:
        result["relay"] = relay(context, new_col, dest_base_path=dest_base_path,
                                params_mode=params_mode)
        if result["relay"][0]:
            result["collection"] = bpy.data.collections.get(result["relay"][2])
            if result["collection"] is not None:
                result["nuki"] = apply_nuki_dissolve(result["collection"], nuki_values)
    return result


def relay(context, mhws_col, *, dest_base_path="", params_mode='BASIC'):
    """Hand the MHWilds result to the ordinary MHWS -> MHRS material port.

    The intermediate is removed on success, so the user is left with the one
    collection they asked for rather than two -- but only on success: if the
    second hop fails, the MHWilds materials are a real result and throwing
    them away would turn a partial port into no port at all.

    Textures are not converted again -- ``run_port`` has already written them in
    MHRS's own container and path convention, so there is nothing left to
    convert.  But the material port skips its whole binding loop when
    ``convert_textures`` is off, which would leave the new materials on
    PL_Default's stock paths, so the bindings are carried over here by slot
    type.  A plain name-keyed copy is enough: MHWilds and MHRS name all 15 slot
    types identically and pack them identically, which is the same measurement
    that makes the relay free in the first place.

    Returns ``(ok, note, result collection name or None)``.
    """
    stem = mhws_col.name
    for suffix in (f"_{DST_GAME}.mdf2", ".mdf2"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    try:
        r = bpy.ops.modder.port_mdf_material_cross_game(
            'EXEC_DEFAULT', source_game=DST_GAME, target_game=_RELAY_TARGET,
            source_collection=mhws_col.name, convert_textures=False,
            dest_base_path=(dest_base_path or "").strip(),
            migrate_params=params_mode,
            # Only what this port actually wrote.  The rest of the intermediate is
            # MHWilds' prefab defaults, and the migration would carry them over
            # MHRS' own -- see mrl3_port.written_props.
            migrate_only=",".join(sorted(mrl3_port.written_props(params_mode))))
    except (RuntimeError, TypeError) as e:
        return False, T("core.mrl3_port_ops.relay_failed").format(err=e), None
    if 'FINISHED' not in r:
        return False, T("core.mrl3_port_ops.relay_failed").format(
            err=", ".join(r)), None

    made = next((c for c in bpy.data.collections
                 if c.get("~TYPE") == "RE_MDF_COLLECTION"
                 and c.name.startswith(mhws_col.name.removesuffix(".mdf2"))
                 and c is not mhws_col), None)
    if made is None:
        return False, T("core.mrl3_port_ops.relay_no_result"), None
    made.name = f"{stem}_{_RELAY_TARGET}.mdf2"
    # Only the author's own textures move. The stock paths differ per game and
    # the destination prefab already carries the right ones -- see
    # carry_texture_bindings' docstring for what carrying them costs.
    from .mdf_material_convert_base import (_load_vanilla_art_paths,
                                            is_custom_tex_path)
    src_cfg = mdf_port_tex.get_game_tex_config(DST_GAME) or {}
    vanilla = _load_vanilla_art_paths(src_cfg.get("vanilla_asset_rel", ""))
    carried = mrl3_port.carry_texture_bindings(
        mhws_col, made, lambda p: is_custom_tex_path(p, vanilla))
    n = len([o for o in made.objects if o.get("~TYPE") == "RE_MDF_MATERIAL"])
    for obj in list(mhws_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(mhws_col)
    return True, T("core.mrl3_port_ops.relayed").format(
        name=made.name, n=n, tex=carried), made.name


@gate
class MHWI_OT_PortMrl3ToMdf2(bpy.types.Operator):
    bl_idname = "mhwi.port_mrl3_to_mdf2"
    bl_label = "MHWI Material Port"
    #: No 'UNDO': materials and .tex files are created outside the undo stack, so a
    #: redo-panel re-run would build a second set rather than revise the first.
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.mrl3_port_ops.desc")

    source_collection: bpy.props.EnumProperty(
        name="Source", items=_collection_items)
    #: One click for MHWI -> MHRS, two hops behind it.  See TARGET_GAMES for why
    #: relaying beats a second mrl3 table.
    target_game: bpy.props.EnumProperty(
        name="Target", items=_target_game_items, default=0)
    dest_base_path: bpy.props.StringProperty(name="Base Path", default="")
    migrate_params: bpy.props.EnumProperty(
        name="Params",
        items=lambda self, ctx: [
            ('BASIC', T("core.mrl3_port_ops.params_basic"),
             T("core.mrl3_port_ops.params_basic_desc")),
            ('ALL', T("core.mrl3_port_ops.params_all"),
             T("core.mrl3_port_ops.params_all_desc"))],
        default=0)
    convert_textures: bpy.props.BoolProperty(name="Convert Textures", default=True)
    #: Default on, because leaving it off is the option that breaks the game.  The
    #: two engines disagree about an unused material: MHWI ignores it, MHWilds
    #: refuses to load the model at all -- a mismatch its own pre-export check
    #: already reports, so a port that produces one has produced a broken mod.
    cull_unused: bpy.props.BoolProperty(name="Cull Unused", default=True)
    mod3_collection: bpy.props.EnumProperty(
        name="Mod3", items=lambda self, ctx: _mod3_items(self, ctx))

    def invoke(self, context, event):
        if not self.dest_base_path:
            settings = getattr(context.scene, "mdf_tex_processor", None)
            self.dest_base_path = getattr(settings, "texture_base_path", "") or ""
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection",
                    text=T("core.mrl3_port_ops.source_collection"))
        layout.prop(self, "target_game", text=T("core.mrl3_port_ops.target_label"))
        layout.prop(self, "dest_base_path",
                    text=T("core.mrl3_port_ops.dest_base_path"))
        # The field takes the part *between* the game's texture root and the file
        # name, which the label alone does not convey -- an example says it in fewer
        # words than a sentence would.
        layout.label(text=T("core.mrl3_port_ops.base_path_example"))
        layout.prop(self, "migrate_params",
                    text=T("core.mrl3_port_ops.migrate_params"))
        layout.prop(self, "convert_textures",
                    text=T("core.mrl3_port_ops.convert_textures"))
        layout.prop(self, "cull_unused",
                    text=T("core.mrl3_port_ops.cull_unused"))
        if self.cull_unused:
            box = layout.box()
            box.prop(self, "mod3_collection",
                     text=T("core.mrl3_port_ops.mod3_collection"))
            box.label(text=T("core.mrl3_port_ops.cull_note"), icon='INFO')
        if self.convert_textures:
            from .mdf_port_ops import _draw_mod_root_row
            box = layout.box()
            # A label per row, not one above both.  The two rows are a *source* and a
            # *destination*, and a single "choose the natives root the textures live
            # under" over the pair reads as though both are places to find textures --
            # which is what it looked like in use.
            box.label(text=T("core.mdf_port_ops.mod_root_hint"), icon='INFO')
            _draw_mod_root_row(box, context, "MHWI",
                               {"natives_root_key": SRC_NATIVES_KEY})
            dst_cfg = mdf_port_tex.get_game_tex_config(self.target_game)
            if dst_cfg:
                box.label(text=T("core.mrl3_port_ops.export_root_hint"), icon='EXPORT')
                _draw_mod_root_row(box, context, self.target_game, dst_cfg)

    def execute(self, context):
        result = run_port(
            context, bpy.data.collections.get(self.source_collection),
            self.target_game,
            dest_base_path=self.dest_base_path,
            params_mode=self.migrate_params,
            convert_textures=self.convert_textures,
            cull_unused=self.cull_unused,
            mod3_col=bpy.data.collections.get(self.mod3_collection))
        if result["error"]:
            self.report({'ERROR'}, T(result["error"]))
            return {'CANCELLED'}
        if result["source_root_missing"]:
            self.report({'WARNING'}, T("core.mrl3_port_ops.source_root_missing"))

        culled, missing = result["culled"], result["missing"]
        parts = [T("core.mrl3_port_ops.stat").format(
            name=result["collection"].name, built=result["built"],
            textures=result["textures"], migrated=result["params_ok"],
            skipped=result["params_skip"])]
        if culled:
            parts.append(T("core.mrl3_port_ops.culled").format(
                n=len(culled), names=", ".join(sorted(culled)[:8])))
        if result["failed"]:
            parts.append(T("core.mrl3_port_ops.failed").format(n=result["failed"]))
        if missing:
            parts.append(T("core.mrl3_port_ops.missing_tex").format(
                n=len(missing), names="; ".join(missing[:4])))
        if result["unportable"]:
            parts.append(T("core.mrl3_port_ops.unportable").format(
                names=", ".join(sorted(result["unportable"]))))
        if result["notes"]:
            parts.append(T("core.mrl3_port_ops.rescaled").format(
                n=len(result["notes"]), names="; ".join(result["notes"][:4])))
        self.report({'WARNING'} if (result["failed"] or missing) else {'INFO'},
                    "  ".join(parts))

        if result["relay"] is not None:
            ok, note, _name = result["relay"]
            self.report({'INFO'} if ok else {'WARNING'}, note)
        return {'FINISHED'}


classes = [MHWI_OT_PortMrl3ToMdf2]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
