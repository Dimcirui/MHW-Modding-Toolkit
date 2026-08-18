"""The MHRS end of a batch port: bind the results, export them, clear the source.

Shared by every batch flow that *lands* in MHRS -- ``core/mhwi_batch_port.py`` and
``core/mhws_batch_port.py`` -- because none of what follows depends on where the
set came from.  Everything here takes the same ``results`` shape: one dict per
MHRS part, carrying ``part`` and the ``mesh``/``mdf2``/``chain`` collections plus
``armature``, with ``skip`` set on the parts that produced nothing.

The one thing that *is* source-specific is which collections to delete afterwards,
and that is passed in as a predicate rather than guessed -- see ``discard_source``.

**A part does not need a chain of its own.**  Authors routinely put the cloth
physics on the body alone and let the other parts inherit it, and the source games
resolve a chain against the body skeleton, which is authoritative.  To keep that, a
part with no physics of its own is given **the body's ported chain**, not a copy of
it: the same collection is simply exported again under that part's file name, which
is byte-for-byte what "the body's physics, on this part too" means and cannot lose a
node to a bone the part's own rig happens not to carry.  ``resolve_chain_sources``
decides this; ``export`` acts on it.
"""

import os
import shutil

import bpy


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
#: files because a part the source set does not have still needs *a* file, cleanup
#: because a ported mesh has never been through RE Mesh' checks, and a body-proportion
#: scheme because a source rig is not MHRS-proportioned and nothing else in this flow
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
#: Keyed on the *destination* slot, so it applies to every batch flow that lands
#: there -- the file is a fact about MHRS' armour 279, not about where the set that
#: replaces it came from.
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
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    written = []
    for asset_rel, dest_rel in EXTRA_FILES.get((gender, armor_id), ()):
        src = os.path.join(addon_dir, "assets", *asset_rel.split("/"))
        if not os.path.isfile(src):
            print(f"[batch port -> MHRS] extra file missing from the addon: {asset_rel}")
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


# ── clearing the source side ────────────────────────────────────────────────────

def discard_source(group_col, is_source_collection):
    """Delete the imported source side outright, data-blocks and all.

    *is_source_collection* is the one source-specific thing here: a predicate
    saying which collections the importer produced.  Passed in rather than
    inferred, because "what a source import looks like" is exactly what differs
    between the flows -- MHWI's three MHW-Model-Editor kinds against MHWS'
    ``RE_*`` ones, which are the same tags the *results* carry.

    **Not the whole group collection.**  The ports nest their results *inside* the
    part they came from, so a real ported set looks like

        pl082_0000 / f_body082_0000 / f_body082_0000.mod3        <- source
                                      f_body082_0000.mrl3        <- source
                                      f_body082_0000.ctc         <- source
                                      f_body082_0000_MHRS.mesh   <- the result
                                      f_body082_0000_MHRS.mdf2   <- the result

    and deleting the tree would take the deliverable with it.  So this deletes the
    source collection kinds and whatever hangs off them, then drops the wrappers
    that end up holding nothing -- leaving the results where they were.

    Safe to delete those because the ports never work in place: they duplicate the
    rig and its meshes before touching anything, and build fresh collections from a
    prefab for materials and physics.

    Worth doing rather than leaving to the user, for three reasons, in order of how
    much they cost:

    * The importer reuses a group collection of the same name, and a group name is a
      vanilla armour slot code, so a leftover set is what makes a later port of a
      *different* mod for the same slot ambiguous.  ``discover``'s *created* set
      already resolves that ambiguity; clearing the scene means it does not arise.
    * A source set is heavy, and it has served its purpose the moment the port is done.
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

    # Find the source collections, and stop there: a physics collection owns its
    # "Chain Entries" and "Collision Entries" children, which go with it, and
    # nothing below a source collection is ever a result.
    roots = []

    def find(col):
        if is_source_collection(col):
            roots.append(col)
            return
        for child in list(col.children):
            find(child)

    find(group_col)
    return discard_collections(roots, prune_from=group_col)


def discard_collections(roots, prune_from=None):
    """Delete *roots* and everything under them, data-blocks included.

    Split out of ``discard_source`` because the MHWS importer produces no wrapper
    tree to walk down from -- RE Mesh Editor names its collections deterministically
    and links them flat, so that flow already *has* the roots and only needs the
    careful half.  Which is this: delete the objects before reading their
    data-blocks' user counts, and only remove a data-block that nobody else kept.

    *prune_from*, when given, is a wrapper tree to tidy afterwards.
    """
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

    if prune_from is not None:
        n_col += _prune_empty(prune_from)
    return {"objects": n_obj, "collections": n_col, "data": n_data}


def _prune_empty(col):
    """Drop wrappers under *col* -- and *col* -- once they hold nothing.

    The per-part wrapper of a part that was skipped, or that produced no result, has
    nothing left in it after the source goes; the group wrapper likewise when every
    part was skipped.  Depth-first, so a wrapper is judged after its children are.

    A ``~TYPE`` is what makes something *not* a wrapper.  The batch importers'
    per-part and per-group collections are plain; everything meaningful -- the source
    kinds and the ports' ``RE_*`` results -- is tagged.  Judging on emptiness alone
    would take a result with it: an ``RE_MDF_COLLECTION`` whose materials have not
    been built yet holds no objects and no children, and looks exactly like a spent
    wrapper.
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
#: kinds an armour import can produce; anything else is left alone rather than guessed.
_DATA_COLLECTIONS = {
    "Mesh": "meshes",
    "Armature": "armatures",
}


def discard_armature(obj):
    """Remove an armature object *and* its data-block.

    ``objects.remove`` drops only the object; the ``bpy.data.armatures`` entry
    survives at zero users until the file is saved and reloaded.  Harmless once,
    but this is used on the master reference rig, which was given a data block of
    its own precisely so the per-part copies could not share it -- so leaving it
    behind leaks one armature per batch.
    """
    if obj is None or obj.name not in bpy.data.objects:
        return
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.armatures.remove(data)
