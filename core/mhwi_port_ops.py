"""MHWI -> MHWS rebuild, execution layer.

Crossing engines is a rebuild, not a conversion, and the shape of the rebuild is the
opposite of what the RE-to-RE port does.  ``mesh_port`` converts the source rig in
place: rename its bones, merge what the target lacks, *build* what the target needs.
Building bones by rule is the weak part -- placement comes from a table of anchors
rather than from the target game, and it showed: 89 helper bones inserted, up to
250 mm from where MHWilds actually puts them, six of them parentless because the
insert order is alphabetical rather than hierarchical.

So the skeleton is not converted here, it is **replaced**.  The output rig is
MHWilds' own reference skeleton -- correct names, hierarchy, helper set and
orientations by construction -- snapped onto the MHWI model's joint positions so it
takes the *model's* proportions.  Nothing is placed by rule and nothing can come out
parentless (user's design, 2026-08-15).

The order matters, and the first two steps are the only ones that touch the mesh::

    1. translate    rig + meshes up by SOLE_OFFSET_Z, so the sole planes meet
    2. thumbs       swing MHWI's thumbs onto MHWilds' splay, mesh follows
    3. reference    import MHWilds' reference model, merge its facial bones, T-pose
                    it, discard its body mesh
    4. snap         move the *reference's* bones onto the MHWI rig's joints,
                    position only -- the mesh is not touched
    5. assemble     a .mesh collection holding the snapped rig and the meshes,
                    rebound to it
    6. vertex groups renamed MHWI -> MHWilds
    7. physics      graft the model's own cloth/hair bones onto the new rig
    8. optimise     the two MHWilds skeleton passes

Steps 1 and 2 move the mesh and so go through ``core/pose_bake.py``; step 4 moves the
skeleton to the mesh instead, which is why it can be a plain rest edit and why the
2.6 cm the old direction lost at the ankle simply does not arise -- MHWilds' ankle is
2.6 cm lower than MHWI's above the sole, and here it is the ankle that moves.

Nearly every step is an existing operator; see ``docs/mhwi_mhws_port_notes.md``.
"""

import math

import bpy
from mathutils import Matrix, Vector

from . import bone_utils, mhwi_port, pose_bake, ref_model, ref_model_ops
from .bone_mapper import build_cross_game_map
from .i18n import T

SRC_PRESET = "mhwi_world.json"

#: Kept as the default target so every existing call site and preset reference
#: still means MHWilds; the per-target rows live in mhwi_port.PORT_TARGETS.
DST_PRESET = "mhws.json"
DST_GAME = "MHWS"


# ── detection ───────────────────────────────────────────────────────────────────

def looks_like_mhwi(arm_obj):
    """True when a rig came out of MHW Model Editor.

    Checked on the *majority*, not on any one bone: a user who has renamed a few
    bones by hand should still be recognised, while an RE Engine rig that happens to
    carry one imported MHWI bone should not.
    """
    names = [b.name for b in arm_obj.data.bones]
    if not names:
        return False
    hits = sum(1 for n in names if mhwi_port.bone_id(n) is not None)
    return hits * 2 > len(names)


def is_mod3_collection(col):
    """MHW Model Editor tags and names its collections ``.mod3``, not ``.mesh``."""
    return col.get("~TYPE") == "MHW_MOD3_COLLECTION" or col.name.endswith(".mod3")


def bound_meshes(arm_obj):
    """Everything that travels with the rig, which is not the same set as everything
    it deforms -- see ``pose_bake.attached_meshes``.

    The port carries this set; ``pose_bake.bake_pose_to_rest`` deforms the narrower
    one on its own.  Getting that backwards in either direction is a real bug: the
    wide set for baking moves vertices nothing in the viewport moves, and the narrow
    set for carrying drops meshes out of the output entirely.
    """
    return pose_bake.attached_meshes(arm_obj)


def _activate(context, obj, *, selected=()):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for o in selected:
        o.hide_set(False)
        o.select_set(True)
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


# ── 1. translate ────────────────────────────────────────────────────────────────

def translate_rig(arm_obj, dz):
    """Lift the armature and everything it deforms by *dz* in world Z.

    Applied to object transforms rather than to bone and vertex data: it is a rigid
    move of the whole assembly, so there is nothing to bake.  Meshes parented to the
    armature come along on their own; ones merely bound by modifier do not.
    """
    arm_obj.location.z += dz
    for obj in bound_meshes(arm_obj):
        if obj.parent is not arm_obj:
            obj.location.z += dz
    bpy.context.view_layer.update()


# ── 2. thumbs ───────────────────────────────────────────────────────────────────

def _pose_world_rotate(arm_obj, bone_name, axis, degrees):
    """Rotate a pose bone **about its own head** -- orientation only, no translation."""
    pb = arm_obj.pose.bones.get(bone_name)
    if pb is None:
        return False
    head = (arm_obj.matrix_world @ pb.bone.matrix_local).translation
    R = Matrix.Rotation(math.radians(degrees), 4, Vector(axis).normalized())
    world = Matrix.Translation(head) @ R @ Matrix.Translation(-head)
    pb.matrix = arm_obj.matrix_world.inverted() @ world @ arm_obj.matrix_world @ pb.matrix
    bpy.context.view_layer.update()
    return True


def rotate_thumbs(arm_obj, context=None):
    """Swing MHWI's thumbs onto MHWilds' splay, mesh included.

    MHWI's thumb phalanges run along the hand axis exactly like its other fingers
    (``Thumb2 -> Thumb3`` measures ``(1, 0, 0)``); MHWilds' are splayed.  Every other
    finger matches to 0.00 degrees, so this is the single place the two hands
    disagree, and it is why step 4 cannot be left to sort the thumb out on its own:
    the snap moves MHWilds' thumb bone onto whatever MHWI's thumb is doing, so
    without this the ported thumb would point along the hand and MHWilds' thumb
    animation -- authored against the splay, and deliberately exempt from T-pose
    zeroing for that reason -- would drive it wrong.

    Two rotations rather than one (user's decision, 2026-08-15): rotating only at the
    first joint would swing the whole thumb rigidly and keep MHWI's internal shape,
    while these two land each phalanx near its MHWilds direction.  Exact coincidence
    is not the goal and is not checked -- the snap in step 4 sets final positions.

    Rotation only, never translation: each bone turns about its own head, so a joint
    never leaves the place the model put it.
    """
    posed = 0
    for side in ("L", "R"):
        for bone_name, axis, degrees in mhwi_port.THUMB_ROTATIONS[side]:
            if _pose_world_rotate(arm_obj, bone_name, axis, degrees):
                posed += 1
    if posed:
        pose_bake.bake_pose_to_rest(arm_obj, context)
    return posed


# ── 3. the reference rig ────────────────────────────────────────────────────────

def import_reference_rig(context, game=DST_GAME):
    """MHWilds' reference skeleton, facial bones merged and T-posed, mesh discarded.

    This is the state the "Import Reference Model" button produces with its first two
    options on, and it is the output rig -- so it is imported through the same code
    path rather than through ``ref_skeleton.import_reference_armature``, which keeps
    only the armature and would therefore have no vertex groups for the facial merge
    to act on.  The body mesh is dropped once the merges are done.

    Auxiliary bones are deliberately *not* merged: they are MHWilds' own helper
    system and the ported rig is supposed to have them.
    """
    ident = ref_model.MODELS.get(game, ())
    if not ident:
        return None
    # First entry: MHWilds ships only a female body, and where a game ships both
    # (MHRS) the choice does not survive anyway -- snap_reference_to_model moves
    # every mapped bone onto the MHWI joints, so the reference's own proportions
    # are overwritten and only its bone *set* matters, which is identical.
    arm = ref_model_ops.import_model(game, ident[0][0])
    if arm is None:
        return None
    # Both passes are no-ops for an OPTIONLESS game by definition -- that set means
    # "no facial rig, and authored in T-pose already" -- so they are skipped rather
    # than run for their own sake. ree_to_tpose in particular has nothing to derive
    # against for a game with no correction data.
    if game not in ref_model.OPTIONLESS_GAMES:
        ref_model_ops.apply_merges(arm, game, True, False)
        _activate(context, arm)
        bpy.ops.modder.ree_to_tpose()

    for obj in list(bound_meshes(arm)):
        bpy.data.objects.remove(obj, do_unlink=True)
    return arm


def duplicate_reference(master):
    """A working copy of an already-imported reference rig.

    Exists for the batch path, where the import above is the single most expensive
    step and every part of an armour set wants the same rig.  It cannot be shared:
    ``snap_reference_to_model`` and ``optimize`` both rewrite the rest pose in place,
    so the master has to stay untouched and each part gets its own copy.

    The data-block is copied too -- a plain ``obj.copy()`` would leave both objects
    pointing at one armature, and the first snap would move the master with it.
    """
    arm = master.copy()
    arm.data = master.data.copy()
    bpy.context.scene.collection.objects.link(arm)
    return arm


# ── 4. snap the reference onto the model ────────────────────────────────────────

def snap_reference_to_model(context, model_arm, ref_arm, dst_preset=DST_PRESET):
    """Move *ref_arm*'s bones onto *model_arm*'s joints, position only.

    ``modder.universal_snap`` reads the two rigs through the bone presets, so it
    matches MHWI's ``MhBone_NNN`` against MHWilds' names by standard slot -- a plain
    name match would find nothing.  Its convention is that the **active** armature is
    the one that moves, which is the reference; the model rig is only read.

    Position only: taking direction and roll from MHWI would throw away the very
    thing the reference is here to supply, since MHWI stores no bone orientation at
    all (all 86 of its bones share one rest frame).
    """
    settings = context.scene.mhw_suite_settings
    saved = (settings.import_preset_enum, settings.target_preset_enum,
             settings.align_mode_override)
    try:
        settings.import_preset_enum = SRC_PRESET
        settings.target_preset_enum = dst_preset
        settings.align_mode_override = 'POS_ONLY'
        _activate(context, ref_arm, selected=(model_arm,))
        bpy.ops.modder.universal_snap()
    finally:
        (settings.import_preset_enum, settings.target_preset_enum,
         settings.align_mode_override) = saved


# ── 5. assemble the output collection ───────────────────────────────────────────

def assemble_collection(src_col, ref_arm, meshes, game=DST_GAME):
    """A ``.mesh`` collection holding the new rig and the meshes, rebound to it.

    Tagged ``RE_MESH_COLLECTION`` because the output is a MHWilds model: every
    downstream check -- the RE exporter, the MDF tools, the pre-export check -- looks
    for that tag or the ``.mesh`` suffix, and a collection still carrying MHWI's
    ``MHW_MOD3_COLLECTION`` reads as the wrong engine to all of them.

    The colour is part of that: RE Mesh Editor stamps ``COLOR_01`` on every mesh
    collection it makes (``blender_re_mesh.py:694``, ``re_mesh_operators.py:158``), so
    a port without it is the one red-less collection in an outliner full of red ones
    -- it reads as "not really a mesh collection" even though every check passes.
    """
    stem = src_col.name
    for suffix in (".mod3", ".mesh"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    col = bpy.data.collections.new(f"{stem}_{game}.mesh")
    col["~TYPE"] = "RE_MESH_COLLECTION"
    col.color_tag = "COLOR_01"

    parents = [c for c in bpy.data.collections if src_col.name in c.children]
    for parent in (parents or [bpy.context.scene.collection]):
        parent.children.link(col)

    for obj in [ref_arm] + list(meshes):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)

    for mesh in meshes:
        # Re-parenting must not move the mesh.  Step 1's lift lives in the *object*
        # transform of the rig the meshes were parented to, so they inherit it --
        # hand them to a different armature without preserving world space and the
        # 1.05 m silently comes back off, leaving the body at MHWI's height while the
        # skeleton stands at MHWilds'.  Setting matrix_parent_inverse is not enough:
        # it cancels the new parent, not the old one.
        world = mesh.matrix_world.copy()
        mesh.parent = ref_arm
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        mesh.matrix_world = world
        # Binds rather than merely retargets: a mesh that arrived with an empty-target
        # modifier, or with none at all, is one the port has just rescued from being
        # dropped -- leaving it unbound would put it in the output looking correct and
        # deforming with nothing.
        pose_bake.rebind(mesh, ref_arm)
    return col


# ── 6. vertex groups ────────────────────────────────────────────────────────────

def rename_vertex_groups(context, meshes, dst_preset=DST_PRESET):
    """Rename the meshes' vertex groups from MHWI names to MHWilds names.

    ``modder.direct_convert`` is the same button a user would press ("Rename Vertex
    Groups [X+Y]"), driven by the same two presets as the snap, so the groups end up
    named for exactly the bones the snap moved.  Physics groups are not in either
    preset and are left alone, which is what step 7 relies on.
    """
    settings = context.scene.mhw_suite_settings
    saved = (settings.import_preset_enum, settings.target_preset_enum)
    try:
        settings.import_preset_enum = SRC_PRESET
        settings.target_preset_enum = dst_preset
        if not meshes:
            return
        _activate(context, meshes[0], selected=meshes[1:])
        bpy.ops.modder.direct_convert()
    finally:
        settings.import_preset_enum, settings.target_preset_enum = saved

    # A group named for an MHWI base bone that the preset never mapped survives the
    # rename -- ``MhBone_000``, the origin, is the one this hits.  It names no bone on
    # the new rig, so it can only confuse the exporter's bone/group matching.
    # Physics groups are left alone: they are the ones step 7 grafts bones for.
    for mesh in meshes:
        for vg in list(mesh.vertex_groups):
            if mhwi_port.is_base_bone(vg.name):
                mesh.vertex_groups.remove(vg)


# ── 7. physics bones ────────────────────────────────────────────────────────────

def _physics_order(arm_obj):
    """Physics bone names, parents before children."""
    out = []

    def walk(bone):
        if mhwi_port.is_physics_bone(bone.name):
            out.append(bone.name)
        for c in bone.children:
            walk(c)

    for root in [b for b in arm_obj.data.bones if b.parent is None]:
        walk(root)
    return out


def _graft_parent(eb, parents, name, name_map, overrides):
    """``(edit bone to hang *name* from, the MHWI bone it came from)``, or ``(None, None)``.

    Walks up rather than looking only at the direct parent.  A physics bone whose
    parent is a base bone the presets do not map used to be dropped and reported as an
    orphan -- and since its own children then had no parent either, the whole chain
    below it went with it.  MHWI's 064/067 skirt attach bones are exactly that case and
    are not exotic: they carry the skirt.

    Three ways an ancestor can be usable, in the order they are tried per ancestor:

    * an **override** -- a base bone with no counterpart whose right destination is
      known anyway (``mhwi_port.physics_parent_overrides``, already resolved for the
      target game by the caller).  First, because it beats what the walk would
      otherwise find: 064's own ancestry leads to the hip, which follows none of the
      leg's motion, where the override says thigh.
    * a **physics bone already grafted** -- it keeps its MHWI name, so it is looked up
      as-is.  Checked against *eb* rather than assumed, because an ancestor that was
      itself orphaned is not there and the walk has to carry on past it.
    * a **mapped base bone** -- the same mapping the snap used.

    Anything found must actually exist on the target rig; a name the presets produce
    for a bone MHWilds does not have is no better than no name.
    """
    for ancestor, is_physics in mhwi_port.physics_parent_chain(parents, name):
        override = overrides.get(ancestor)
        if override and override in eb:
            return eb[override], ancestor
        if is_physics:
            if ancestor in eb:
                return eb[ancestor], ancestor
            continue
        mapped = name_map.get(ancestor)
        if mapped and mapped in eb:
            return eb[mapped], ancestor
    return None, None


def transplant_physics(model_arm, ref_arm, name_map, target_game="MHWS"):
    """Copy the model's own cloth and hair bones onto the new rig.

    Safe to take world coordinates verbatim: step 4 has already moved the reference's
    joints onto the model's, so the two rigs coincide wherever they share a bone, and
    a physics bone's position relative to the body is the same in either.  That is
    also what "transplant as-is, relative to the parent" reduces to once the parent
    is in the right place.

    Which bones these are is decided by id window, not by name or by weights: MHWI
    restricts physics to ``mhwi_port.PHYSICS_ID_RANGES``, and a bone outside them has
    no physical effect in the game at all.  Their names are kept, because the chain
    file being rebuilt alongside will refer to them by the same name.

    Returns ``(made, orphans, rehomed)``.  An orphan is a physics bone with no usable
    ancestor at all, still reported rather than guessed at.  ``rehomed`` is
    ``[(bone, its MHWI parent, where it actually landed)]`` -- the chains that attached
    further up because their own parent has no MHWilds counterpart, which is a fact
    about the result the user should see rather than a silent success.
    """
    names = _physics_order(model_arm)
    if not names:
        return 0, [], []

    parents = {b.name: (b.parent.name if b.parent else None)
               for b in model_arm.data.bones}
    src_bones = model_arm.data.bones
    to_ref = ref_arm.matrix_world.inverted() @ model_arm.matrix_world

    _activate(bpy.context, ref_arm)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ref_arm.data.edit_bones
    made, orphans, rehomed = 0, [], []
    overrides = mhwi_port.physics_parent_overrides(target_game)
    try:
        for name in names:
            if name in eb:
                continue
            src = src_bones[name]
            parent, via = _graft_parent(eb, parents, name, name_map, overrides)
            if parent is None:
                orphans.append(name)
                continue
            direct = src.parent.name if src.parent else None
            if direct is not None and via != direct:
                rehomed.append((name, direct, parent.name))
            new = eb.new(name)
            new.head = to_ref @ src.head_local
            new.tail = to_ref @ src.tail_local
            new.align_roll((to_ref @ src.matrix_local).to_3x3() @ Vector((0.0, 0.0, 1.0)))
            new.parent = parent
            new.use_connect = False
            made += 1
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return made, orphans, rehomed


# ── 8. optimise ─────────────────────────────────────────────────────────────────

def optimize(context, arm_obj, meshes, ops=()):
    """The target's own skeleton passes, run as the user would run them by hand.

    Empty for MHRS, and that is not an omission: these are MHWilds' helper-system
    passes and MHRS has no helper system for them to act on."""
    for idname in ops:
        _activate(context, arm_obj, selected=meshes)
        category, _, name = idname.partition(".")
        getattr(getattr(bpy.ops, category), name)()


# ── the port itself ─────────────────────────────────────────────────────────────

def run_port(context, src_col, target_game, *, reference=None):
    """Rebuild one MHWI collection as *target_game*.  The whole port, minus the UI.

    Split out of the operator so the batch path can drive it directly: an operator's
    ``execute`` can only be re-entered through ``bpy.ops``, which re-runs the poll,
    re-reads the enum properties, and gives nothing back but a status set.

    *reference* is an already-imported reference rig to copy instead of importing a
    fresh one -- see ``duplicate_reference``.  It must be for *target_game*; nothing
    here can tell, and a MHWilds master handed to an MHRS port would produce a rig
    with the wrong bone set and no error anywhere.

    Returns a dict.  ``{"error": <T key>}`` when the inputs are not a portable model;
    otherwise the collection, the rig, and the four things worth saying out loud.
    """
    arms = [o for o in src_col.objects if o.type == 'ARMATURE'] if src_col else []
    if len(arms) != 1:
        return {"error": "core.mhwi_port_ops.pick_collection"}
    if not looks_like_mhwi(arms[0]):
        return {"error": "core.mhwi_port_ops.not_mhwi"}

    cfg = mhwi_port.port_target(target_game)
    cross = build_cross_game_map(SRC_PRESET, cfg["preset"])
    if cross is None:
        return {"error": "core.mhwi_port_ops.preset_load_failed"}

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Work on a copy: steps 1 and 2 rewrite mesh data, and the source model must
    # survive them intact.
    work_arm = bone_utils.duplicate_armature_with_meshes(
        arms[0], arms[0].name + "_port_tmp")
    work_meshes = bound_meshes(work_arm)

    # Bind the copies *before* anything moves, not at assembly time.  A mesh that
    # arrived with an empty modifier target is deformed by nothing, so the thumb
    # bake in step 2 would skip it -- and it would then be bound, at the end, to a
    # rig whose rest pose already carries the rotated thumb, leaving its own thumb
    # geometry where MHWI had it.  Binding here puts every mesh through every step.
    #
    # Only the copy is touched; the user's own model keeps whatever binding state
    # it had.  Harmless for the meshes that were already bound -- rebind retargets
    # in place rather than stacking a second modifier.
    for mesh in work_meshes:
        pose_bake.rebind(mesh, work_arm)

    if cfg["sole_offset"]:
        translate_rig(work_arm, cfg["sole_offset"])
    thumbs = rotate_thumbs(work_arm, context) if cfg["rotate_thumbs"] else 0

    ref_arm = (duplicate_reference(reference) if reference is not None
               else import_reference_rig(context, target_game))
    if ref_arm is None:
        # The mesh copies have to go too.  ``duplicate_armature_with_meshes``
        # links them into the *source's* collections, so leaving them behind
        # puts a second, unbound body in the user's own .mod3 collection --
        # which then reads as a two-mesh model on the next run.
        for obj in work_meshes:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.objects.remove(work_arm, do_unlink=True)
        return {"error": "core.mhwi_port_ops.need_reference"}

    snap_reference_to_model(context, work_arm, ref_arm, cfg["preset"])
    out_col = assemble_collection(src_col, ref_arm, work_meshes, target_game)
    rename_vertex_groups(context, work_meshes, cfg["preset"])
    grafted, orphans, rehomed = transplant_physics(
        work_arm, ref_arm, dict(cross.mapping), target_game)

    bpy.data.objects.remove(work_arm, do_unlink=True)
    optimize(context, ref_arm, work_meshes, cfg["optimize_ops"])

    return {
        "error": None,
        "collection": out_col,
        "armature": ref_arm,
        "meshes": work_meshes,
        "thumbs": thumbs,
        "grafted": grafted,
        "orphans": orphans,
        "rehomed": rehomed,
        "unknown": mhwi_port.partition([b.name for b in arms[0].data.bones])["unknown"],
    }


# ── operator ────────────────────────────────────────────────────────────────────

#: Same persistent-list rule as _collection_items below: Blender's C side keeps the
#: pointers, so the callback must not return a list it just built.
_target_item_cache = []

_TARGET_LABELS = {
    "MHWS": ("core.mhwi_port_ops.target_mhws", "core.mhwi_port_ops.target_mhws_desc"),
    "MHRS": ("core.mhwi_port_ops.target_mhrs", "core.mhwi_port_ops.target_mhrs_desc"),
}


def _target_game_items(self=None, context=None):
    _target_item_cache.clear()
    for game in mhwi_port.PORT_TARGET_ORDER:
        label, desc = _TARGET_LABELS[game]
        _target_item_cache.append((game, T(label), T(desc)))
    return _target_item_cache


_collection_item_cache = []


def _collection_items(self, context):
    """EnumProperty items must outlive the call: Blender's C side keeps the pointers."""
    _collection_item_cache.clear()
    _collection_item_cache.extend(
        (c.name, c.name, "") for c in bpy.data.collections if is_mod3_collection(c))
    if not _collection_item_cache:
        _collection_item_cache.append(
            ("NONE", T("core.mhwi_port_ops.no_mod3_collection"), ""))
    return _collection_item_cache


class MHWI_OT_PortToMHWS(bpy.types.Operator):
    bl_idname = "mhwi.port_to_mhws"
    bl_label = "MHWI Model Port"
    #: No 'UNDO', for the same reason as the mesh port and the reference importer:
    #: this creates and deletes objects through ``bpy.data``, so a redo-panel re-run
    #: would build a second model rather than revise the first.
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.mhwi_port_ops.desc")

    source_collection: bpy.props.EnumProperty(
        name="Source", items=_collection_items)
    target_game: bpy.props.EnumProperty(
        name="Target", items=_target_game_items, default=0)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=430)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection",
                    text=T("core.mhwi_port_ops.source_collection"))
        layout.prop(self, "target_game", text=T("core.mhwi_port_ops.target_label"))
        box = layout.box()
        box.label(text=T("core.mhwi_port_ops.rebuild_note"), icon='INFO')

    def execute(self, context):
        result = run_port(context, bpy.data.collections.get(self.source_collection),
                          self.target_game)
        if result["error"]:
            self.report({'ERROR'}, T(result["error"]))
            return {'CANCELLED'}

        out_col, orphans = result["collection"], result["orphans"]
        rehomed, unknown = result["rehomed"], result["unknown"]
        parts = [T("core.mhwi_port_ops.stat").format(
            name=out_col.name, thumbs=result["thumbs"],
            bones=len(result["armature"].data.bones),
            grafted=result["grafted"], meshes=len(result["meshes"]))]
        if orphans:
            parts.append(T("core.mhwi_port_ops.physics_orphans").format(
                n=len(orphans), names=", ".join(orphans[:8])))
        if rehomed:
            # Worth saying out loud: these chains work, but they hang somewhere the
            # source did not put them, so they will follow a little more motion than
            # they used to.
            pairs = sorted({f"{src}->{dst}" for _b, src, dst in rehomed})
            parts.append(T("core.mhwi_port_ops.physics_rehomed").format(
                n=len(rehomed), pairs=", ".join(pairs[:4])))
        if unknown:
            parts.append(T("core.mhwi_port_ops.unknown_ids").format(
                n=len(unknown), names=", ".join(unknown[:8])))
        self.report({'WARNING'} if (orphans or unknown or rehomed) else {'INFO'},
                    "  ".join(parts))
        return {'FINISHED'}


classes = [MHWI_OT_PortToMHWS]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
