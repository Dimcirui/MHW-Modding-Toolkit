"""MHWI -> MHRS batch port, orchestration layer.

One MHWI armour set in, one set of MHRS collections out, with the three ports run
back to back per part and nothing asked of the user in between.  The ports
themselves are unchanged -- this module only decides *what* to run them on, in what
order, and what to reuse between parts.

Three things are shared across the whole batch rather than rebuilt per part, and
they are the whole reason this is not just a ``for`` loop over the three operators:

* **the reference rig** -- imported once and copied per part.  It is the single
  most expensive step of the model port and every part wants the same rig.
* **the texture decode cache** -- keyed on the source ``.tex`` path, so the
  ``Body_BML`` that four materials across three parts all bind is decoded once
  instead of four times.
* **one temp directory** -- because the cache above names PNGs inside it, so a
  per-part directory would invalidate the cache it is supposed to feed.

**A part needs both a .mod3 and a .mrl3.**  Either one alone is skipped: a model
with no materials fails MHRS' own load (the material/mesh mismatch the pre-export
check reports), and materials with no model have nothing to attach to.

**A part does not need a .ctc.**  MHWI authors routinely put the cloth physics on
the body alone and let the other parts inherit it -- MHWI resolves a chain against
the body skeleton, which is authoritative, so a skirt authored on the body drives
the same-named bones everywhere.  That inheritance is handled on the MHRS side; see
``core/mhrs_batch_target.py``, which owns everything from binding the results
onwards and is shared with the MHWS batch.
"""

import re
import shutil
import tempfile

import bpy

from . import ctc_port_ops, mhwi_port_ops, mrl3_port_ops
from . import mhrs_batch_target as target
# The MHRS end of the port -- bind, export, clear up -- does not depend on where the
# set came from, so it lives in one module the MHWS batch shares.  Re-exported here
# rather than reached for through ``target``: this module is the batch's public face
# and its callers already say ``batch.export(...)``.
from .mhrs_batch_target import (          # noqa: F401  (re-exported)
    EXTRA_FILES, discard_armature, export, resolve_chain_sources,
)

#: MHWI's part codes.  Identical to MHRS' own ``MHRS_PARTS`` codes, which is why
#: nothing here translates between them.
PART_CODES = ("body", "helm", "arm", "wst", "leg")

#: Body first, and not for tidiness: it is the part every other part may fall back
#: to for physics, and the one preferred as the shadow-mesh alignment rig.  Running
#: it first means both are already available by the time anything asks.
PART_ORDER = PART_CODES

#: ``f_body029_0101`` -> gender ``f``, part ``body``, id ``029_0101``.  MHW Model
#: Editor names the collection after the file, so this is the file name's shape.
_PART_NAME = re.compile(
    r'^(?P<gender>[fm])_(?P<part>%s)(?P<id>.*)$' % "|".join(PART_CODES))

#: Reasons a part is not ported.  Codes rather than sentences: this layer has no
#: opinion about wording, the same split ``core/pre_export_check.py`` uses.
SKIP_NO_MOD3 = 'no_mod3'
SKIP_NO_MRL3 = 'no_mrl3'


#: Where MHWI keeps armour, and the gender each folder means.  Weapons are not
#: scanned: they have no counterpart in MHRS' five armour parts, so a weapon found
#: here would have nowhere to export to.
EQUIP_DIRS = (("f", "f_equip"), ("m", "m_equip"))

#: The three file types a part can have.  Order matters to the importer -- a ``.ctc``
#: read before its ``.mod3`` has no bones to bind to -- but not here.
FILE_TYPES = ("mod3", "mrl3", "ctc")


def skip_reason(has_mod3, has_mrl3):
    """Why a part cannot be ported, or ``None``.

    The one place the rule lives, because it is asked twice about the same part:
    once by the scan, off file names, to show the user what will happen, and once
    by ``discover``, off the imported collections, to decide what actually does.
    Two spellings of it would eventually disagree, and the disagreement would look
    like the port silently ignoring a part the dialog promised.
    """
    if not has_mod3:
        return SKIP_NO_MOD3
    if not has_mrl3:
        return SKIP_NO_MRL3
    return None


def scan(source_root):
    """MHWI armour sets under *source_root*, newest-first by nothing -- sorted by name.

    Returns ``[{'group', 'gender', 'parts': {part: {filetype: path}}}]``.  Reads
    ``<root>/nativePC/pl/{f,m}_equip/<group>/<part>/mod/``, which is the layout MHWI
    mods ship in and the same one ``games/mhwi/batch_import.py`` scans.

    A group is a folder, not a guess: whatever ``f_equip`` contains is one armour
    set, so nothing here has to interpret ``pl029_0101``.
    """
    import os

    out = []
    pl_dir = os.path.join(source_root, "nativePC", "pl")
    if not os.path.isdir(pl_dir):
        return out

    for gender, equip_folder in EQUIP_DIRS:
        equip_dir = os.path.join(pl_dir, equip_folder)
        if not os.path.isdir(equip_dir):
            continue
        for group in sorted(os.listdir(equip_dir)):
            parts = {}
            for part in PART_ORDER:
                mod_dir = os.path.join(equip_dir, group, part, "mod")
                if not os.path.isdir(mod_dir):
                    continue
                files = {}
                for fname in sorted(os.listdir(mod_dir)):
                    ext = os.path.splitext(fname)[1].lower().lstrip(".")
                    if ext in FILE_TYPES and ext not in files:
                        files[ext] = os.path.join(mod_dir, fname)
                if files:
                    parts[part] = files
            if parts:
                out.append({"group": group, "gender": gender, "parts": parts})
    return out


def parse_part_name(name):
    """``(gender, part, id)`` for a MHWI collection name, or ``(None, None, None)``.

    The trailing suffix is stripped first, so ``f_body029_0101.mod3`` and the
    wrapper collection ``f_body029_0101`` both parse the same way.
    """
    stem = name.rsplit(".", 1)[0] if "." in name else name
    m = _PART_NAME.match(stem)
    if not m:
        return None, None, None
    return m.group('gender'), m.group('part'), m.group('id')


def discover(group_col, created=None):
    """The parts under a MHWI group collection, in ``PART_ORDER``.

    *created* is the set of collection names this run's import just made.  Given it,
    a fresh collection displaces a stale one for the same slot; without it, first
    found wins.  It matters because the importer **reuses** a group collection of the
    same name rather than making a second one (``games/mhwi/batch_import.
    _get_or_create_collection``), and a group name is a vanilla armour slot code like
    ``pl119_0000`` -- so two different mods replacing the same slot land in one
    collection, the second one's parts named ``.001``.  First-found would then be the
    *previous* port's model, ported again under the new armour id, silently.

    Each entry is ``{'part', 'gender', 'mod3', 'mrl3', 'ctc', 'skip'}``, with the
    three collections or ``None`` and *skip* set to a ``SKIP_*`` code when the part
    cannot be ported.  Parts that cannot be ported are still returned rather than
    dropped -- the UI is supposed to show that they were found and passed over,
    which it cannot do for something it never hears about.

    Walks recursively: the batch importer nests ``<part>/<part>.mod3`` and the
    manual route may not, so depth is not something to depend on.
    """
    found = {}

    def classify(col):
        if mhwi_port_ops.is_mod3_collection(col):
            return "mod3"
        if mrl3_port_ops.is_mrl3_collection(col):
            return "mrl3"
        if is_ctc_collection(col):
            return "ctc"
        return None

    def walk(col):
        gender, part, _id = parse_part_name(col.name)
        slot = classify(col) if part else None
        if slot is not None:
            entry = found.setdefault(part, {"part": part, "gender": gender,
                                            "mod3": None, "mrl3": None, "ctc": None})
            # First one wins, *except* that something this import created displaces
            # something it did not -- see the docstring.  Within a single import the
            # two rules agree: everything is new, so first still wins.
            fresh = created is not None and col.name in created
            stale = (entry[slot] is not None and created is not None
                     and entry[slot].name not in created)
            if entry[slot] is None or (fresh and stale):
                entry[slot] = col
        for child in col.children:
            walk(child)

    walk(group_col)

    parts = []
    for part in PART_ORDER:
        entry = found.get(part)
        if entry is None:
            continue
        entry["skip"] = skip_reason(entry["mod3"] is not None,
                                    entry["mrl3"] is not None)
        parts.append(entry)
    return parts


def import_group(context, entry):
    """Import one scanned armour set, and return its group collection.

    Drives ``mhwi.batch_import`` rather than calling the MHW Model Editor importers
    directly.  That operator already pairs a ``.mod3`` with its ``.mrl3`` into a
    single joint import -- which is the only way the material names come out right --
    orders ``mod3`` before ``ctc``, and nests the results under a group collection.
    Reimplementing that here would be a second copy of all three.

    It reads its file list off the scene, so the list is written first.  That does
    replace whatever the MHWI import panel was showing, which is a visible side
    effect and an intended one: what it shows afterwards is what this just imported.

    Returns ``(group collection or None, set of collection names created)``.  The
    second half is what tells ``discover`` which parts are this run's -- the group
    collection alone cannot, because the importer reuses one of the same name.
    """
    scene = context.scene
    items, groups = scene.mhwi_import_items, scene.mhwi_import_groups
    items.clear()
    groups.clear()

    g = groups.add()
    g.group_key = entry["group"]
    g.kind = "armor"
    for part, files in entry["parts"].items():
        for filetype, path in files.items():
            item = items.add()
            item.filepath = path
            item.group_key = entry["group"]
            item.gender = entry["gender"]
            item.part = part
            item.filetype = filetype
            item.enabled = True
            item.kind = "armor"

    before = set(bpy.data.collections.keys())
    if bpy.ops.mhwi.batch_import('EXEC_DEFAULT') != {'FINISHED'}:
        return None, set()
    created = set(bpy.data.collections.keys()) - before
    return bpy.data.collections.get(entry["group"]), created


def is_ctc_collection(col):
    """MHW Model Editor's physics collection.

    The ``.ccl`` colliders live *inside* the ``.ctc`` collection as a child, so
    only the outer one is a part's physics source -- matching on ``.ccl`` as well
    would find the same physics twice.
    """
    return col.get("~TYPE") == "MHW_CTC_COLLECTION" or col.name.endswith(".ctc")


def run(context, parts, *, target_game="MHRS", dest_base_path="",
        src_root=None, dst_root=None, progress=None, skip_textures=False):
    """Port every portable part in *parts*.  Returns a list of per-part results.

    *parts* is what ``discover`` returns.  *progress*, when given, is called as
    ``progress(index, total, part_code)`` before each part -- the batch has no
    report to build up, so this is the only thing that says where it got to.

    *skip_textures* produces the mdf2 with its texture paths filled but writes no
    ``.tex``.  For replacing a set's mesh/mdf2/ctc over textures an earlier run
    already put on disk: the texture pass is the batch's dominant cost, and nothing
    else in the flow depends on its output.

    A result carries the three output collections (``mesh``, ``mdf2``, ``chain``,
    any of which may be ``None``), the output armature, and ``skip``/``error`` when
    the part did not make it.  A part that fails does not stop the batch: the other
    parts of an armour set are independent and a half-ported set is more useful
    than none.
    """
    results = []
    temp_dir = tempfile.mkdtemp(prefix="mhwi_batch_")
    tex_cache = mrl3_port_ops.new_tex_cache()
    reference = None
    try:
        portable = [p for p in parts if not p["skip"]]
        # Imported lazily, so a batch whose parts are all skipped never pays for it
        # and never leaves a stray rig behind.
        if portable:
            reference = mhwi_port_ops.import_reference_rig(context, target_game)
            if reference is None:
                return [dict(p, error="core.mhwi_port_ops.need_reference")
                        for p in parts]

        for i, part in enumerate(parts):
            if part["skip"]:
                results.append(dict(part, mesh=None, mdf2=None, chain=None,
                                    armature=None, error=None))
                continue
            if progress is not None:
                progress(i, len(parts), part["part"])
            results.append(_run_part(
                context, part, target_game=target_game,
                dest_base_path=dest_base_path, src_root=src_root,
                dst_root=dst_root, temp_dir=temp_dir, tex_cache=tex_cache,
                reference=reference, skip_textures=skip_textures))
    finally:
        discard_armature(reference)
        shutil.rmtree(temp_dir, ignore_errors=True)
    return results


def is_mhwi_collection(col):
    """One of the three collection kinds a MHWI import produces."""
    return (mhwi_port_ops.is_mod3_collection(col)
            or mrl3_port_ops.is_mrl3_collection(col)
            or is_ctc_collection(col))


def discard_source(group_col):
    """Delete the imported MHWI side, leaving the ported results in place.

    The walk is shared; naming the three MHWI collection kinds is the only part of
    it that is about MHWI, so that is all this passes in.
    """
    return target.discard_source(group_col, is_mhwi_collection)


def _run_part(context, part, *, target_game, dest_base_path, src_root, dst_root,
              temp_dir, tex_cache, reference, skip_textures=False):
    """Model, then materials, then physics, for one part.

    The order is forced rather than chosen: the material port needs the ``.mod3``
    collection to know which materials are actually used, and the physics port
    needs the rig the model port builds.
    """
    out = dict(part, mesh=None, mdf2=None, chain=None, armature=None, error=None)

    model = mhwi_port_ops.run_port(context, part["mod3"], target_game,
                                   reference=reference)
    if model["error"]:
        out["error"] = model["error"]
        return out
    out["mesh"] = model["collection"]
    out["armature"] = model["armature"]

    material = mrl3_port_ops.run_port(
        context, part["mrl3"], target_game,
        dest_base_path=dest_base_path, params_mode='BASIC',
        convert_textures=not skip_textures, cull_unused=True,
        mod3_col=part["mod3"], paths_only=skip_textures,
        src_root=src_root, dst_root=dst_root, temp_dir=temp_dir,
        tex_cache=tex_cache)
    if material["error"]:
        # Not fatal for the part: the model is a real result, and a set that
        # exports its meshes with stock materials is further along than one that
        # exports nothing.  The caller sees the code and can say so.
        out["error"] = material["error"]
    else:
        out["mdf2"] = material["collection"]

    if part["ctc"] is not None:
        physics = ctc_port_ops.run_port(context, part["ctc"], out["armature"],
                                        target_game, 'BASIC')
        if physics["error"]:
            out["error"] = out["error"] or physics["error"]
        else:
            out["chain"] = physics["collection"]
    return out
