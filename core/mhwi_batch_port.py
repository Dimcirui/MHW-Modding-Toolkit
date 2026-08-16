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
the same-named bones everywhere.  To keep that, a part with no ``.ctc`` of its own
is given **the body's ported chain**, not a copy of it: the same collection is
simply exported again under that part's file name, which is byte-for-byte what
"the body's physics, on this part too" means and cannot lose a node to a bone the
part's own rig happens not to carry.  ``resolve_chain_sources`` decides this; the
export layer acts on it.
"""

import re
import shutil
import tempfile

import bpy

from . import ctc_port_ops, mhwi_port_ops, mrl3_port_ops

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


def resolve_chain_sources(results):
    """``{part: the part whose ported chain it should export}``.

    A part with its own chain maps to itself.  A part with none maps to ``body``
    when the body has one -- see the module docstring for why that is the same
    chain rather than a copy of it -- and is absent from the mapping when there is
    nothing to inherit either.
    """
    body = next((r for r in results
                 if r["part"] == "body" and r.get("chain") is not None), None)
    out = {}
    for r in results:
        if r.get("skip"):
            continue
        if r.get("chain") is not None:
            out[r["part"]] = r["part"]
        elif body is not None:
            out[r["part"]] = "body"
    return out


#: What the batch forces on MHRS' export panel, and what the user is not shown.
#: Every one of these is a decision the batch has already made for them: blank
#: files because a part the MHWI set does not have still needs *a* file, cleanup
#: because a MHWI mesh has never been through RE Mesh' checks, and a body-proportion
#: scheme because a MHWI rig is not MHRS-proportioned and nothing else in this flow
#: would carry that across.
#:
#: ``LUA`` rather than ``SHADOW`` for that last one: a batch port is a whole armour
#: set aimed at one armour id, and the global skeleton would make *that* set's
#: proportions the proportions of every outfit in the game -- so porting two sets
#: would leave the second one's body on the first one's armour.  LuaBoneSystem keys
#: the same offsets on the armour id, which is what a per-set port means.  The cost
#: is a REFramework script on the player's side, and it is the batch's call to pay
#: it; the export panel still offers all three.
_FORCED_EXPORT_SETTINGS = {
    "mhrs_use_blank_export": True,
    "mhrs_cleanup_before_export": True,
    "mhrs_skeleton_mode": {'LUA'},
}


def _shadow_armature(results):
    """The rig the shadow mesh aligns to: the body's, or any ported part's.

    Body first because it is the one part whose rig covers the whole skeleton;
    a boot-only set still has to align to *something*, which is the fallback.
    """
    for want_body in (True, False):
        for r in results:
            if r.get("armature") is None:
                continue
            if want_body == (r["part"] == "body"):
                return r["armature"]
    return None


def export(context, results, *, armor_id, gender, natives_root):
    """Bind the ported collections to MHRS' own batch export and run it.

    Deliberately drives ``mhrs.batch_export`` rather than writing the files here.
    That operator already knows the things this flow must not get wrong -- the
    per-part file types, that ``user.2`` exists only on the helmet, the armour's
    ``parts_mask``, the blank-file fallback, the shadow mesh -- and a second
    implementation would have to be kept in step with all of it.

    Returns ``{'error': <T key>}`` or
    ``{'error': None, 'bound': n, 'copied': [...], 'extra': [...]}``.
    """
    from ..games.mhrs import batch_export as mhrs_export

    scheme = mhrs_export._load_scheme(context.scene.mhw_suite_settings.mhrs_armor_scheme)
    if not scheme:
        return {"error": "mhrs.batch_export.load_scheme_failed"}
    if not any(a["id"] == armor_id for a in scheme.get("armor_sets", [])):
        return {"error": "mhrs.batch_export.armor_not_found_in_scheme"}

    scene = context.scene
    settings = scene.mhw_suite_settings
    inherited = resolve_chain_sources(results)

    # Every slot is written, including the empty ones.  A binding is a scene
    # property that outlives the run that made it, so a part this set does not
    # have would otherwise export whatever the *previous* set left bound to the
    # same armour id -- silently, and with a collection that looks plausible.
    by_part = {r["part"]: r for r in results}
    bound = 0
    for part_id, _name in mhrs_export.MHRS_PARTS:
        r = by_part.get(part_id)
        for filetype, key in (("mesh", "mesh"), ("mdf2", "mdf2"), ("chain", "chain")):
            col = None
            if r is not None and not r.get("skip") and r.get(key) is not None:
                # A part inheriting the body's chain is left unbound on purpose:
                # it gets the body's *file*, copied after the export, rather than
                # a second export of the same collection.
                if not (filetype == "chain" and inherited.get(part_id) != part_id):
                    col = r[key].name
            mhrs_export.set_binding(scene, armor_id, gender, part_id, filetype,
                                    col or "")
            bound += int(bool(col))

    saved_root = scene.get("mhrs_natives_root", "")
    saved = {k: getattr(settings, k) for k in _FORCED_EXPORT_SETTINGS}
    saved["mhrs_selected_armor"] = settings.mhrs_selected_armor
    saved["mhrs_gender"] = settings.mhrs_gender
    saved["mhrs_shadow_armature"] = settings.mhrs_shadow_armature
    try:
        scene["mhrs_natives_root"] = natives_root
        for k, v in _FORCED_EXPORT_SETTINGS.items():
            setattr(settings, k, v)
        settings.mhrs_selected_armor = armor_id
        settings.mhrs_gender = gender
        settings.mhrs_shadow_armature = _shadow_armature(results)
        bpy.ops.mhrs.batch_export('EXEC_DEFAULT')
    finally:
        scene["mhrs_natives_root"] = saved_root
        for k, v in saved.items():
            setattr(settings, k, v)

    copied = _copy_inherited_chains(natives_root, gender, armor_id, inherited)
    extra = _copy_extra_files(natives_root, gender, armor_id)
    return {"error": None, "bound": bound, "copied": copied, "extra": extra}


#: Files a particular armour slot needs that the port cannot produce, keyed on
#: ``(gender, armour id)`` and written verbatim at the end of the export.
#:
#: A ``.pfb`` is a prefab: it is what names the mesh, mdf2, chain and sound bank
#: that make up one equipment part, and nothing in this addon builds one -- the
#: port writes the four files a prefab points *at*, not the prefab.  For most slots
#: that is fine, because the vanilla prefab already points at the right names and a
#: replacement mod keeps those names.  Where it is not fine, the working prefab has
#: to be shipped and dropped in, which is what this table is for.
#:
#: 279 (公会十字 / Guild Cross) female legs is the one such slot so far.  The file
#: shipped here names ``f_leg279``'s mesh, mdf2, **chain** and ``.wcc``; it is a
#: known-good prefab supplied by the user (2026-08-16), not something derived.
#:
#: Female only, and not because the male set was overlooked: the prefab's contents
#: name ``f_leg279`` throughout, so it is the female part's prefab and copying it
#: under ``m/`` would point the male legs at the female files.
#:
#: Paths are relative to ``assets/`` and to the mod root respectively.
EXTRA_FILES = {
    ("f", "279"): (
        ("mhrs/prefab/f_leg279.pfb.17",
         "natives/STM/player/prefab/mod/f/pl279/f_leg279.pfb.17"),
    ),
}


def _copy_extra_files(natives_root, gender, armor_id):
    """Drop in whatever ``EXTRA_FILES`` lists for this slot.  Returns the paths written.

    Silent by design (user, 2026-08-16): from the user's side this is part of what
    "port the set" means, not a step they chose, so a report line would be noise
    about something they cannot act on.  A missing shipped asset is skipped rather
    than raised, for the same reason the blank-file copy is: the armour itself
    exported fine, and failing the whole run over an extra file would be worse than
    the file's absence.
    """
    import os

    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    written = []
    for asset_rel, dest_rel in EXTRA_FILES.get((gender, armor_id), ()):
        src = os.path.join(addon_dir, "assets", *asset_rel.split("/"))
        if not os.path.isfile(src):
            print(f"[MHWI->MHRS] extra file missing from the addon: {asset_rel}")
            continue
        dst = os.path.join(natives_root, *dest_rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        written.append(dst)
    return written


def _copy_inherited_chains(natives_root, gender, armor_id, inherited):
    """Give every inheriting part a copy of the file its donor just exported.

    A plain file copy rather than a second export: the two are meant to be the
    same physics, and copying is both the cheaper way to say that and the only
    one that cannot drift -- an export runs through RE Chain Editor again and has
    no obligation to produce the same bytes twice.
    """
    import os

    from ..games.mhrs import batch_export as mhrs_export

    copied = []
    for part_id, donor in inherited.items():
        if donor == part_id:
            continue
        src = mhrs_export._make_filepath(natives_root, gender, armor_id, donor, "chain")
        dst = mhrs_export._make_filepath(natives_root, gender, armor_id, part_id, "chain")
        if not os.path.isfile(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(part_id)
    return copied


def run(context, parts, *, target_game="MHRS", dest_base_path="",
        src_root=None, dst_root=None, progress=None):
    """Port every portable part in *parts*.  Returns a list of per-part results.

    *parts* is what ``discover`` returns.  *progress*, when given, is called as
    ``progress(index, total, part_code)`` before each part -- the batch has no
    report to build up, so this is the only thing that says where it got to.

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
                reference=reference))
    finally:
        _discard_armature(reference)
        shutil.rmtree(temp_dir, ignore_errors=True)
    return results


def discard_source(group_col):
    """Delete the imported MHWI side outright, data-blocks and all.

    **Not the whole group collection.**  The ports nest their results *inside* the
    part they came from, so a real ported set looks like

        pl082_0000 / f_body082_0000 / f_body082_0000.mod3        <- source
                                      f_body082_0000.mrl3        <- source
                                      f_body082_0000.ctc         <- source
                                      f_body082_0000_MHRS.mesh   <- the result
                                      f_body082_0000_MHRS.mdf2   <- the result

    and deleting the tree would take the deliverable with it.  So this deletes the
    three MHWI collection kinds and whatever hangs off them, then drops the wrappers
    that end up holding nothing -- leaving the results where they were.

    Safe to delete those because the ports never work in place:
    ``mhwi_port_ops.run_port`` duplicates the rig and its meshes before touching
    anything, and the material and physics ports build fresh collections from a
    prefab.

    Worth doing rather than leaving to the user, for three reasons, in order of how
    much they cost:

    * The importer reuses a group collection of the same name, and a group name is a
      vanilla armour slot code, so a leftover set is what makes a later port of a
      *different* mod for the same slot ambiguous.  ``discover``'s *created* set
      already resolves that ambiguity; clearing the scene means it does not arise.
    * A MHWI set is heavy, and it has served its purpose the moment the port is done.
    * Unlinking alone would not do it: an object dropped from every collection still
      sits in ``bpy.data`` at zero users until the file is saved and reloaded, as does
      its mesh.  So the data-blocks go too.

    Only data-blocks left with **no users** are removed, which is what keeps this from
    reaching into the port's output: anything the new materials genuinely share -- an
    image, say -- still has a user and stays.

    Returns ``{'objects': n, 'collections': n, 'data': n}``.
    """
    if group_col is None or group_col.name not in bpy.data.collections:
        return {"objects": 0, "collections": 0, "data": 0}

    # Find the MHWI collections, and stop there: a .ctc owns its "Chain Entries" and
    # "Collision Entries" children, which go with it, and nothing below a MHWI
    # collection is ever a result.
    roots = []

    def find(col):
        if is_mhwi_collection(col):
            roots.append(col)
            return
        for child in list(col.children):
            find(child)

    find(group_col)

    cols, objs = [], []

    def walk(col):
        for child in col.children:
            walk(child)
        cols.append(col)
        objs.extend(col.objects)

    for root in roots:
        walk(root)

    # Names, not references.  Removing the objects can free the data-block outright,
    # and a Python reference to a freed one raises ReferenceError on *any* attribute
    # -- including the ``users`` this needs to read to decide.  A name survives.
    orphans = [(_DATA_COLLECTIONS.get(type(o.data).__name__), o.data.name)
               for o in objs if o.data is not None]

    n_obj = 0
    for obj in {o.name: o for o in objs}.values():
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
            n_obj += 1

    n_col = 0
    for col in cols:
        if col.name in bpy.data.collections:
            bpy.data.collections.remove(col)
            n_col += 1

    n_data = 0
    for coll_name, data_name in orphans:
        coll = getattr(bpy.data, coll_name, None) if coll_name else None
        data = coll.get(data_name) if coll is not None else None
        if data is not None and data.users == 0:
            coll.remove(data)
            n_data += 1

    n_col += _prune_empty(group_col)
    return {"objects": n_obj, "collections": n_col, "data": n_data}


def is_mhwi_collection(col):
    """One of the three collection kinds a MHWI import produces."""
    return (mhwi_port_ops.is_mod3_collection(col)
            or mrl3_port_ops.is_mrl3_collection(col)
            or is_ctc_collection(col))


def _prune_empty(col):
    """Drop wrappers under *col* -- and *col* -- once they hold nothing.

    The per-part wrapper of a part that was skipped, or that produced no result, has
    nothing left in it after the source goes; the group wrapper likewise when every
    part was skipped.  Depth-first, so a wrapper is judged after its children are.

    A ``~TYPE`` is what makes something *not* a wrapper.  The batch importer's
    per-part and per-group collections are plain; everything meaningful -- MHWI's
    three kinds and the ports' ``RE_*`` results -- is tagged.  Judging on emptiness
    alone would take a result with it: an ``RE_MDF_COLLECTION`` whose materials have
    not been built yet holds no objects and no children, and looks exactly like a
    spent wrapper.
    """
    removed = 0
    for child in list(col.children):
        removed += _prune_empty(child)
    if (col.name in bpy.data.collections and not col.get("~TYPE")
            and not col.children and not col.objects):
        bpy.data.collections.remove(col)
        removed += 1
    return removed


#: ``obj.data``'s type name -> the ``bpy.data`` collection it lives in.  Only the
#: kinds a MHWI import can produce; anything else is left alone rather than guessed.
_DATA_COLLECTIONS = {
    "Mesh": "meshes",
    "Armature": "armatures",
}


def _discard_armature(obj):
    """Remove an armature object *and* its data-block.

    ``objects.remove`` drops only the object; the ``bpy.data.armatures`` entry
    survives at zero users until the file is saved and reloaded.  Harmless once,
    but this is the master reference and ``duplicate_reference`` gave it a data
    block of its own precisely so the copies could not share it -- so leaving it
    behind leaks one armature per batch, on top of the mesh data ``import_reference_rig``
    already leaves when it discards the reference body.
    """
    if obj is None or obj.name not in bpy.data.objects:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.armatures.remove(data)


def _run_part(context, part, *, target_game, dest_base_path, src_root, dst_root,
              temp_dir, tex_cache, reference):
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
        convert_textures=True, cull_unused=True, mod3_col=part["mod3"],
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
