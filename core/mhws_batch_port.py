"""MHWS -> MHRS batch port, orchestration layer.

One MHWilds armour set in, one set of MHRS collections out, with the three
cross-game ports run back to back per part and nothing asked in between.  The
ports themselves are unchanged; this module decides *what* to run them on and in
what order.  Everything from binding the results onwards lives in
``core/mhrs_batch_target.py``, shared with the MHWI batch.

Three things differ from the MHWI flow, and all three come from the source side:

* **Armour is addressed, not walked.**  MHWilds ships its armour under
  ``Art/Model/Character/ch0N/<set>/<style>/``, and the shipped scheme already
  records the full path of every part -- so the scan checks the paths the scheme
  names rather than listing folders.  ``games/mhws/batch_import.scan_mhws_catalog``
  does the same thing for the import panel, from the same helpers.
* **A set has up to four variants.**  Measured over the shipped scheme (418
  variants, no exceptions): the **first** letter is the body -- ``m`` is always
  ``ch02``, ``f`` always ``ch03`` -- and the **second** is the armour's style,
  ``m`` being the ``...0`` suffix and ``f`` the ``...1``.  MHRS has one body per
  gender and no style axis, so exactly one variant can be ported per run and the
  user picks it; see ``default_variant`` for what is pre-selected.
* **No wrapper collections.**  RE Mesh Editor links its results flat and names
  them ``<variant armour id><part>.mesh`` and so on, so a part's collections are
  found by name rather than by walking a group.

Textures are not the bottleneck they are for MHWI: MHWS and MHRS pack every slot
identically, so ``mdf_port_tex.repack_slot`` rewrites the container without
touching a pixel.  Hence no "skip textures" option here -- there is nothing
expensive to skip.
"""

import os

import bpy

from . import chain_convert
from . import mhrs_batch_target as target
# The MHRS end of the port, shared with core/mhwi_batch_port.py.
from .mhrs_batch_target import (          # noqa: F401  (re-exported)
    EXTRA_FILES, export, resolve_chain_sources,
)

SOURCE_GAME = "MHWS"
TARGET_GAME = "MHRS"

#: MHWS numbers its parts, MHRS names them.  Both games have exactly these five
#: and nothing else, so this is a total mapping rather than a lookup that can miss.
PART_MAP = {"1": "arm", "2": "body", "3": "helm", "4": "leg", "5": "wst"}

#: Body first, and not for tidiness: it is the part every other part may fall back
#: to for physics, and the one preferred as the shadow-mesh alignment rig.  Running
#: it first means both are already available by the time anything asks.  Same
#: reasoning, same resulting order, as ``mhwi_batch_port.PART_ORDER``.
PART_ORDER = ("2", "3", "1", "5", "4")

#: The source file types this flow can use.  ``gpuc`` has no importer at all and
#: ``clsp`` is MHWilds' separate collider container -- MHRS' chain v1 carries its
#: colliders inside the ``.chain``, and ``core/chain_convert.py`` already knows to
#: read a ``.clsp`` sitting beside its chain rather than as a file of its own.
FILE_TYPES = ("mesh", "mdf2", "chain2", "clsp")

#: Reasons a part is not ported.  Codes rather than sentences, the same split
#: ``core/pre_export_check.py`` and the MHWI batch use.
SKIP_NO_MESH = 'no_mesh'
SKIP_NO_MDF2 = 'no_mdf2'

#: Which MHRS reference skeleton a run aligns against.  The batch already knows the
#: target gender, and these are the two files ``assets/reference_skeletons/mhrs/``
#: ships, so nothing has to be asked.
REFERENCE_BY_GENDER = {"f": "f_shadow.fbx", "m": "m_shadow.fbx"}


def skip_reason(has_mesh, has_mdf2):
    """Why a part cannot be ported, or ``None``.

    Both are required for the same reasons the MHWI flow requires its two: a model
    with no materials fails MHRS' own load, and materials with no model have
    nothing to attach to.  One rule, asked twice -- once by the scan off file names
    to show the user what will happen, once after the import off the collections to
    decide what actually does.
    """
    if not has_mesh:
        return SKIP_NO_MESH
    if not has_mdf2:
        return SKIP_NO_MDF2
    return None


# ── variants ────────────────────────────────────────────────────────────────────

def variant_gender(variant):
    """The MHRS gender a MHWS variant's *body* is.

    The first letter, which is the measured fact: across the shipped scheme every
    ``m*`` variant is a ``ch02`` model and every ``f*`` is ``ch03``, 209 each with
    no exceptions.  The second letter is the armour's style and has no MHRS
    counterpart -- MHRS has one appearance per gender.
    """
    return (variant or "  ")[0]


def variants_for(entry, gender):
    """*entry*'s variants whose body is *gender*, matching style first.

    ``ff`` before ``fm`` for a female run: the second letter is the style, so
    ``ff`` is the female-styled armour on the female body, which is what "this
    set, for her" normally means.  The other one is still offered, because 35 of
    the 122 shipped sets have only the ``...0`` style and would otherwise have no
    female entry at all.
    """
    have = entry.get("variants", {})
    return [v for v in (gender + gender, gender + _other(gender)) if v in have]


def _other(gender):
    return "m" if gender == "f" else "f"


def default_variant(entry, gender):
    """What the dialog pre-selects, or ``None`` when the set has no such body."""
    found = variants_for(entry, gender)
    return found[0] if found else None


# ── source discovery ────────────────────────────────────────────────────────────

def scan(natives_root, scheme_filename):
    """MHWS armour sets present under *natives_root*.

    Returns ``[{'armor_id', 'name', 'variants': {variant: {'armor_id',
    'parts': {part_id: {filetype: path}}}}}]`` -- only variants and parts whose
    files are actually on disk, so a set that appears here can be ported.

    Deliberately built from ``games/mhws/batch_export``'s own path helpers rather
    than a second copy of the naming rule: ``_make_filepath`` is what the export
    side writes to and what the import panel reads from, and a third spelling of it
    would drift from both.
    """
    from ..games.mhws.batch_export import (
        MHWS_PARTS, _canonical_order_file_types, _load_scheme, _make_filepath,
        _resolve_part_file_types,
    )

    scheme = _load_scheme(scheme_filename)
    if not scheme:
        return []

    out = []
    for armor_set in scheme.get("armor_sets", []):
        parts_mask = armor_set.get("parts_mask", 0b11111)
        variants = {}
        for variant, variant_data in armor_set.get("variants", {}).items():
            variant_armor_id = variant_data["armor_id"]
            base_path = variant_data["base_path"]
            parts = {}
            for part_id, _name in MHWS_PARTS:
                if not (parts_mask & (1 << (int(part_id) - 1))):
                    continue
                fts = [ft for ft in _resolve_part_file_types(armor_set, part_id)
                       if ft in FILE_TYPES]
                files = {}
                for filetype in _canonical_order_file_types(fts):
                    path = _make_filepath(natives_root, base_path, part_id,
                                          variant_armor_id, filetype)
                    if os.path.isfile(path):
                        files[filetype] = path
                if files:
                    parts[part_id] = files
            if parts:
                variants[variant] = {"armor_id": variant_armor_id, "parts": parts}
        if variants:
            out.append({"armor_id": armor_set["id"],
                        "name": armor_set.get("name", armor_set["id"]),
                        "variants": variants})
    return out


def plan_parts(entry, variant):
    """What the run will do to each part, before anything is imported.

    ``[{'part', 'mhrs_part', 'files', 'skip'}]`` in ``PART_ORDER``.  Parts that
    cannot be ported are returned rather than dropped, so the dialog can show that
    they were found and passed over -- which it cannot do for something it never
    hears about.
    """
    parts = entry.get("variants", {}).get(variant, {}).get("parts", {})
    out = []
    for part_id in PART_ORDER:
        files = parts.get(part_id)
        if not files:
            continue
        out.append({
            "part": part_id,
            "mhrs_part": PART_MAP[part_id],
            "files": files,
            "skip": skip_reason("mesh" in files, "mdf2" in files),
        })
    return out


def import_set(context, entry, variant):
    """Import one variant through ``mhws.batch_import``.  ``(ok, created names)``.

    Drives that operator rather than the RE Mesh/Chain importers directly: it
    already pairs a ``.mesh`` with its ``.mdf2`` into one call (the only way the
    material names come out right), orders the mesh before the chain2/clsp that
    have to bind to its armature, and falls back to a standalone MDF import.

    It reads its file list off the scene, so the list is written first.  That does
    replace whatever the MHWS import panel was showing, which is a visible side
    effect and an intended one: what it shows afterwards is what this just
    imported.

    The *created* names are what tell a fresh collection from one an earlier run
    left behind -- RE Mesh Editor names deterministically, so a second import of
    the same set produces ``....001`` and first-found would be the older one.
    """
    scene = context.scene
    items, groups = scene.mhws_import_items, scene.mhws_import_groups
    items.clear()
    groups.clear()

    variant_data = entry["variants"][variant]
    g = groups.add()
    g.group_key = entry["armor_id"]

    for part_id, files in variant_data["parts"].items():
        for filetype, path in files.items():
            item = items.add()
            item.filepath = path
            item.armor_id = entry["armor_id"]
            item.variant = variant
            item.variant_armor_id = variant_data["armor_id"]
            item.part = part_id
            item.filetype = filetype
            item.enabled = True

    before = set(bpy.data.collections.keys())
    ok = bpy.ops.mhws.batch_import('EXEC_DEFAULT') == {'FINISHED'}
    return ok, set(bpy.data.collections.keys()) - before


def discover(entry, variant, parts, created=None):
    """Attach the imported collections to the planned parts.

    Found by name, because RE Mesh Editor builds them from the file name and links
    them flat -- ``<variant armour id><part>.<ext>`` -- rather than nesting them
    under a wrapper the way MHW Model Editor does.  *created* prefers this run's
    collections over a previous run's, for the same reason the MHWI flow tracks it.
    """
    stem = entry["variants"][variant]["armor_id"]
    out = []
    for part in parts:
        found = dict(part, mesh=None, mdf2=None, chain2=None, clsp=None)
        for filetype in FILE_TYPES:
            if filetype not in part["files"]:
                continue
            found[filetype] = _pick(f"{stem}{part['part']}.{filetype}", created)
        # The plan was made off file names; the import is what decides.  A file
        # that was on disk but failed to import must skip the part rather than
        # reach the ports as a None.
        found["skip"] = part["skip"] or skip_reason(found["mesh"] is not None,
                                                    found["mdf2"] is not None)
        out.append(found)
    return out


def _pick(name, created=None):
    """The collection called *name*, preferring one this run just made."""
    if created:
        for candidate in sorted(created):
            if candidate == name or candidate.startswith(name + "."):
                return bpy.data.collections.get(candidate)
    return bpy.data.collections.get(name)


def is_mhws_collection(col):
    """One of the collection kinds a MHWS import produces.

    Tagged rather than named: the ports' own results are ``RE_*`` collections too,
    and the only thing separating a source ``.mesh`` from a ported one is the
    ``_MHRS`` in the name.  So this asks the name, and the caller only ever hands
    it the collections the import actually created.
    """
    return col is not None and not chain_convert.chain_stem(col.name).endswith(
        f"_{TARGET_GAME}")


# ── the port itself ─────────────────────────────────────────────────────────────

def run(context, parts, *, gender, dest_base_path="", dst_root=None, progress=None):
    """Port every portable part in *parts*.  Returns a list of per-part results.

    *parts* is what ``discover`` returns.  *progress*, when given, is called as
    ``progress(index, total, part_code)`` before each part.

    A result carries ``mesh``/``mdf2``/``chain`` collections (any may be ``None``),
    the output armature, and ``skip``/``error``.  A part that fails does not stop
    the batch: the parts of an armour set are independent and a half-ported set is
    more useful than none.
    """
    results = []
    for i, part in enumerate(parts):
        if part["skip"]:
            results.append(dict(part, part=part["mhrs_part"], mesh=None, mdf2=None,
                                chain=None, armature=None, error=None))
            continue
        if progress is not None:
            progress(i, len(parts), part["mhrs_part"])
        results.append(_run_part(context, part, gender=gender,
                                 dest_base_path=dest_base_path, dst_root=dst_root))
    return results


def _run_part(context, part, *, gender, dest_base_path, dst_root):
    """Model, then materials, then physics, for one part.

    The order is forced rather than chosen: the chain port needs the *ported* mesh
    collection to re-attach its colliders to, so the mesh has to exist first.

    Every step is driven through ``bpy.ops`` because the three cross-game ports
    expose no programmatic entry point.  Measured (2026-08-17, Blender 5.1), that
    is safe in the ways it needed to be checked:

    * A value the dynamic ``EnumProperty`` cannot resolve raises **TypeError** at
      the call, naming the value and the list -- it does not silently fall back to
      a default.
    * ``reference_skeleton``'s item list is derived from ``target_game``, and it is
      rebuilt against the ``target_game`` passed in the **same** call: MHWilds' own
      reference is rejected under an MHRS target.  Keyword order does not matter.
    * A failed ``poll()`` and a reported error both surface as **RuntimeError**
      rather than a returned status, so neither can be mistaken for success.

    The by-name lookup afterwards is what covers the remaining case: an operator
    that returns without raising has still not promised to have made anything.
    """
    out = dict(part, part=part["mhrs_part"], mesh=None, mdf2=None, chain=None,
               armature=None, error=None)

    src_mesh = part["mesh"]
    want = _ported_name(src_mesh.name, ".mesh")
    try:
        bpy.ops.modder.port_mesh_cross_game(
            'EXEC_DEFAULT', source_game=SOURCE_GAME, target_game=TARGET_GAME,
            source_collection=src_mesh.name,
            reference_skeleton=REFERENCE_BY_GENDER.get(gender, "NONE"),
            skeleton_only=False, replace_original=False)
    except (RuntimeError, TypeError) as err:
        out["error"] = "core.mhws_batch_port.mesh_failed"
        print(f"[MHWS->MHRS] {src_mesh.name}: mesh port raised {err}")
        return out

    out["mesh"] = bpy.data.collections.get(want)
    if out["mesh"] is None:
        out["error"] = "core.mhws_batch_port.mesh_failed"
        return out
    out["armature"] = next((o for o in out["mesh"].objects if o.type == 'ARMATURE'),
                           None)

    src_mdf = part["mdf2"]
    want_mdf = _ported_name(src_mdf.name, ".mdf2")
    try:
        bpy.ops.modder.port_mdf_material_cross_game(
            'EXEC_DEFAULT', source_game=SOURCE_GAME, target_game=TARGET_GAME,
            source_collection=src_mdf.name, convert_textures=True,
            dest_base_path=(dest_base_path or "").strip())
    except (RuntimeError, TypeError) as err:
        out["error"] = "core.mhws_batch_port.mdf_failed"
        print(f"[MHWS->MHRS] {src_mdf.name}: material port raised {err}")
    else:
        out["mdf2"] = bpy.data.collections.get(want_mdf)
        if out["mdf2"] is None:
            out["error"] = "core.mhws_batch_port.mdf_failed"

    src_chain = part.get("chain2")
    if src_chain is not None:
        want_chain = chain_convert.ported_chain_collection_name(
            src_chain.name, TARGET_GAME)
        try:
            bpy.ops.modder.convert_chain_cross_game(
                'EXEC_DEFAULT', source_game=SOURCE_GAME, target_game=TARGET_GAME,
                source_collection=src_chain.name,
                target_mesh_collection=out["mesh"].name, replace_original=False)
        except (RuntimeError, TypeError) as err:
            out["error"] = out["error"] or "core.mhws_batch_port.chain_failed"
            print(f"[MHWS->MHRS] {src_chain.name}: chain port raised {err}")
        else:
            out["chain"] = bpy.data.collections.get(want_chain)
            if out["chain"] is None:
                out["error"] = out["error"] or "core.mhws_batch_port.chain_failed"
    return out


def _ported_name(source_name, ext):
    """``<stem>_MHRS<ext>`` -- what the mesh and material ports name their output.

    Both build it the same way (``mesh_port_ops.duplicate_mesh_collection`` and
    ``mdf_port_ops._new_port_collection``), and the chain port has its own helper
    because its extension changes with the target.  Restated here rather than
    imported because those two are private to their operators' modules.
    """
    stem = source_name[:-len(ext)] if source_name.endswith(ext) else source_name
    return f"{stem}_{TARGET_GAME}{ext}"


def discard_source(results):
    """Delete the imported MHWS side, leaving the ported results in place.

    Takes the collections rather than a wrapper to walk down from, because this
    importer makes no wrappers -- see the module docstring.  The careful half of
    the deletion is shared with the MHWI flow.
    """
    roots = []
    for r in results:
        for key in FILE_TYPES:
            col = r.get(key)
            if col is not None and col.name in bpy.data.collections:
                roots.append(col)
    return target.discard_collections(roots)
