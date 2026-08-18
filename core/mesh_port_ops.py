"""RE Mesh port, execution layer: carry out a plan on a real rig, plus the operator.

The planning half is ``core/mesh_port.py``; everything here needs Blender.  Three
decisions shape this file:

**It always works on a copy, and copies the meshes with the armature.**  Two separate
reasons, both load-bearing: editing a rig in place drops the bindings of any RE Chain
data already attached to it, and merging bones has to move *vertex groups*, which live
on the meshes -- copy the armature alone and the weights have nowhere to go.  (The
chain port is the opposite: it edits in place, because duplicating a chain collection
would leave its links pointing at the original's groups by object name.)

**Bone orientation is changed by posing and applying, not by writing edit_bones.**
``core/pose_ops.py`` already solved this shape of problem: pose the bones, then
``_apply_and_rebind()`` bakes the pose into the rest skeleton and re-binds the meshes,
so skinning follows the change instead of tearing.  Writing rest matrices directly
would leave every mesh bound to the old rest.

**The axis correction C is derived from the two rigs at run time, never from a baked
table of constants.**  Bone *positions* differ per character by 130-160 mm between
body types while orientations do not, so anything position-shaped must be measured on
the actual asset.  C itself is gated by ``core.bone_correction``: bones whose derived C
is not a signed permutation fall back to the validated table or are reported -- never
silently replaced by identity, which would leave that bone in the source game's
convention with nothing to show for it until an animation twists it in-game.
"""

import bpy
from mathutils import Matrix, Vector

from . import bone_utils, pose_bake, ref_model
from .bone_correction import (DEFAULT_TOLERANCE_DEG, derive_bone_correction,
                              expand_corrections, invert_correction_table,
                              same_convention_set)
from .bone_mapper import BoneMapManager, auto_detect_preset, build_cross_game_map
from .i18n import T
from .mesh_port import PLUMBING_BONES, build_port_plan, origin_shift
from .ref_skeleton import get_reference_skeleton_items, import_reference_armature
from .weight_utils import merge_weights_and_delete_bones
from .port_consent import gate

#: Games sharing one axis convention: a port between any two of them needs no C.
#: RE9 is the only registered member of the other family.
#:
#: These are ``game_code`` values, matched against a preset's own
#: ``preset_info.game_code`` -- so they must be spelled the way the presets spell
#: them.  MH Rise used to appear here as ``MHR``/``MHWR`` while the rest of the
#: addon said ``MHRS``, which is not a cosmetic split: build_cross_game_map keys
#: CrossGameBoneMap off the preset while this set and mesh_port._INSERT_RULES key
#: off the other spelling, so a mismatch yields a silently *empty* mapping rather
#: than an error.  One spelling, everywhere.
FAMILY_A = frozenset({"MHWS", "RE4", "SF6", "DMC5", "MHRS"})

#: Ported rigs are offered for the games with a reference skeleton to derive against.
#: MHRS joined once it had one (assets/reference_skeletons/mhrs/) and a native bone
#: table; it is the first member whose rig origin is not on the ground, which is what
#: RIG_ORIGIN and origin_shift() exist for.
PORTABLE_GAMES = ("MHWS", "RE4", "RE9", "MHRS")

#: Reference skeletons live under assets/reference_skeletons/<lowercased game_code>/.
_REF_DIRS = {"MHWS": "mhws", "RE4": "re4", "RE9": "re9", "MHRS": "mhrs"}

_TEMP_PREFIX = "__port_tmp__"


def mhws_insert_rules():
    """MHWilds helper placement, borrowed rather than restated.

    ``MHWS_OT_OptimizeAuxBones`` already carries the tables for all 39 ``_HJ_`` /
    ``Palm`` helpers, including the twist bones that sit at a limb's midpoint.  A
    second copy here would drift from it silently, so it is imported -- lazily,
    because ``core`` is otherwise below ``games`` and only this one borrow crosses.
    """
    try:
        from ..games.mhws.operators import _HJ_MOVE_DIRECT, _HJ_MOVE_MIDPOINT
    except Exception:
        return {}
    rules = {hj: ("colocate", base) for hj, base in _HJ_MOVE_DIRECT.items()}
    rules.update({hj: ("midpoint", tuple(pair))
                  for hj, pair in _HJ_MOVE_MIDPOINT.items()})
    return rules


def _preset_by_game():
    """``{game_code: filename}`` for the shipped bone presets."""
    import json
    import os
    out = {}
    mgr = BoneMapManager()
    root = os.path.dirname(mgr.get_preset_path("x.json"))
    if not os.path.isdir(root):
        return out
    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(root, fname), "r", encoding="utf-8") as f:
                info = json.load(f).get("preset_info", {})
        except Exception:
            continue
        code = info.get("game_code")
        if code and code not in out:
            out[code] = fname
    return out


def _preset_main_names(fname):
    mgr = BoneMapManager()
    if not mgr.load_preset(fname):
        return set()
    return {n for entry in mgr.mapping_data.values() for n in entry.get("main", ())}


def duplicate_mesh_collection(col, arm_obj, suffix):
    """Copy a whole .mesh collection, and return the copy's armature.

    A ported model is a *second model*, so it belongs in its own collection sitting
    next to the original -- that is how the importers deliver them and how the
    exporters expect to find them.  Dropping the copies into the original's
    collection instead leaves two rigs and two bodies in the one place that is
    supposed to hold exactly one of each, which the port itself then refuses to read.

    Named ``<original>_<GAME>.mesh`` so it still reads as a mesh collection, and
    linked under the same parents as the original.
    """
    stem = col.name[:-5] if col.name.endswith(".mesh") else col.name
    new_col = bpy.data.collections.new(f"{stem}_{suffix}.mesh")
    if col.get("~TYPE") is not None:
        new_col["~TYPE"] = col["~TYPE"]
    new_col.color_tag = col.color_tag

    parents = [c for c in bpy.data.collections if col.name in c.children]
    if not parents:
        parents = [bpy.context.scene.collection]
    for parent in parents:
        parent.children.link(new_col)

    new_arm = bone_utils.duplicate_armature_with_meshes(
        arm_obj, f"{arm_obj.name}_{suffix}")
    # attached_meshes, not find_armature(): a mesh parented to the rig whose Armature
    # modifier has an empty target is deformed by nothing, so find_armature() does not
    # see it -- and it would be copied by the line above but never linked into the new
    # collection, i.e. dropped from the port with no warning.
    copies = [new_arm] + pose_bake.attached_meshes(new_arm)
    for obj in copies:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        new_col.objects.link(obj)
    return new_arm


def _fallback_table(source_game, target_game, cross):
    """The per-bone C to fall back on when the derivation rejects a bone.

    ``core.pose_ops``'s tables describe **RE9's** deviation from the family-A
    convention -- a property of RE9, not of which end of the port it is on.  Looking
    them up by target game alone therefore only worked in one direction: porting *out*
    of RE9 found nothing and left the derivation to fend for itself, which is how
    ``R_Arm_Clavicle`` came out 179.8 degrees off and the thumbs 89-106 -- the very
    numbers ``_build_re9_c_supplement`` was written to eliminate.

    So: use the target's table when there is one, otherwise invert the source's.  The
    supplement carries the bones that must not be in the T-pose zeroing list --
    clavicles and thumbs, because zeroing a thumb changes where it actually points --
    and a cross-game port needs their C all the same.
    """
    from .pose_ops import _REE_BONE_CORRECTION, _REE_C_SUPPLEMENT

    forward = {**(_REE_BONE_CORRECTION.get(target_game) or {}),
               **(_REE_C_SUPPLEMENT.get(target_game) or {})}
    if forward:
        return forward
    backward = {**(_REE_BONE_CORRECTION.get(source_game) or {}),
                **(_REE_C_SUPPLEMENT.get(source_game) or {})}
    return invert_correction_table(backward, dict(cross.mapping))


def _armature_only_copy(arm_obj):
    """A linked-into-the-scene copy of just the armature, for measuring on.

    Deliberately without the meshes: this copy gets T-posed, and T-posing rebinds
    whatever meshes it carries.  Nothing here may touch the user's mesh.
    """
    probe = arm_obj.copy()
    probe.data = arm_obj.data.copy()
    probe.name = arm_obj.name + "_probe"
    bpy.context.scene.collection.objects.link(probe)
    return probe


def _tpose(context, arm_obj):
    """Run the rest-level T-pose conversion on one rig.

    Both rigs have to go through it, not just the reference: C is
    ``R_src^-1 . R_dst``, so any pose difference between them is absorbed into C 1:1.
    Zeroing both to the same physical pose is what makes M0 cancel and leaves the
    pure convention difference (measured on the RE4R/RE9 pair: 11 bones derived
    before, 39 after).
    """
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.hide_set(False)
    arm_obj.select_set(True)
    context.view_layer.objects.active = arm_obj
    bpy.ops.modder.ree_to_tpose()


# ── plan execution ──────────────────────────────────────────────────────────────

def _rename_bones(arm_obj, pairs):
    """Rename through a temporary prefix so a rename never collides with a name that
    has not been vacated yet -- Blender would answer a collision by silently appending
    ``.001``, and the export would then hash a name no rig has.

    Vertex groups follow: Blender's bone rename renames the matching groups on every
    mesh bound to the armature, which is why this does not touch them by hand.
    """
    bones = arm_obj.data.bones
    staged = []
    for src, dst in pairs:
        b = bones.get(src)
        if b is None:
            continue
        b.name = _TEMP_PREFIX + dst
        staged.append(dst)
    for dst in staged:
        b = bones.get(_TEMP_PREFIX + dst)
        if b is not None:
            b.name = dst
    return len(staged)


def _insert_bones(arm_obj, inserts, ref_arm):
    """Create the target game's missing base bones, placed by the plan's rules.

    Direction and roll are copied from the reference model's own bone; only the head
    position comes from the rules, since that is the part that has to follow *this*
    character's proportions rather than the reference character's.
    """
    if not inserts:
        return 0
    ref_bones = ref_arm.data.bones if ref_arm is not None else {}
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_obj.data.edit_bones
    made = 0
    try:
        for name, rule, anchor in inserts:
            if name in eb:
                continue
            ref = ref_bones.get(name) if ref_bones else None
            if rule == "colocate":
                a = eb.get(anchor)
                if a is None:
                    continue
                head = a.head.copy()
                parent = eb.get(ref.parent.name) if (ref and ref.parent) else a
            elif rule == "midpoint":
                a, b = (eb.get(n) for n in anchor)
                if a is None or b is None:
                    continue
                head = (a.head + b.head) / 2.0
                parent = eb.get(ref.parent.name) if (ref and ref.parent) else a
            else:                                   # ref_offset
                if ref is None or ref.parent is None:
                    continue
                parent = eb.get(ref.parent.name)
                if parent is None:
                    continue
                head = parent.head + (ref.head_local - ref.parent.head_local)

            new = eb.new(name)
            new.head = head
            if ref is not None:
                vec = ref.tail_local - ref.head_local
                new.tail = head + vec
                new.align_roll(ref.matrix_local.to_3x3() @ Vector((0.0, 0.0, 1.0)))
            else:
                new.tail = head + Vector((0.0, 0.0, 0.01))
            new.parent = parent if parent is not None else None
            new.use_connect = False

            # A base bone inserted mid-chain has to take over its children, or it
            # ends up a dangling sibling: measured on a real MHWS -> RE4 run, the
            # inserted Neck_0 sat under Spine_2 next to Neck_1 instead of between
            # them, so RE4's Neck_0 animation channel would have driven nothing.
            # Which bones are its children is read from the reference rig, and only
            # bones currently parented to the *same* parent are moved -- so this
            # re-links the chain without re-shaping anything else.
            #
            # Compared by name, not by identity: Blender hands out a fresh Python
            # wrapper on each RNA access, so ``child.parent is parent`` is False even
            # for the same bone, which silently skipped every re-parent (that is how
            # the dangling Neck_0 survived the first attempt at this fix).
            if ref is not None and parent is not None:
                for child_ref in ref.children:
                    child = eb.get(child_ref.name)
                    if (child is not None and child.name != name
                            and child.parent is not None
                            and child.parent.name == parent.name):
                        child.parent = new
            made += 1

        # Second pass, for the parent that did not exist yet.  ``inserts`` is in
        # alphabetical order, not hierarchy order, so an inserted bone whose parent
        # is *also* being inserted can be created first and come out parentless --
        # measured on MHWI -> MHWS, where L_Biceps_HJ_00 (position 2) needs
        # L_UpperArmTwist_HJ_01 (position 47).  Left alone it becomes a second root,
        # and a bone with no parent inherits no motion at all.
        #
        # Only bones that are still parentless are touched, so nothing the first pass
        # decided is overridden.
        for name, _rule, _anchor in inserts:
            new = eb.get(name)
            ref = ref_bones.get(name) if ref_bones else None
            if new is None or new.parent is not None or ref is None or ref.parent is None:
                continue
            new.parent = eb.get(ref.parent.name)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return made


def sync_child_orientation(arm_obj, base_names):
    """Give every non-base bone its parent's direction and roll, recursively.

    RE9 is the reason this exists: its bones are **not** all oriented the same way --
    each region has its own default orientation, and every bone in that region, base
    or auxiliary or physics, has to share it.  That is what
    ``re9.sync_child_orientation`` is for, and a port has to do the same thing: once
    the base bones are re-expressed in the target convention, their non-base children
    are left pointing the source game's way, and so is everything below them.

    Deciding per bone whether it "rides" on its parent was the wrong model and is
    gone.  The source rig has already been put in its correct pose by ree_to_tpose --
    every bone, base, auxiliary and physics alike, is where it belongs -- so the only
    thing a port changes is the base bones, and everything hanging off them simply
    follows.  Hair and cloth included: in RE9 they must match their region too.

    Heads never move; only direction and roll change, and edit bones are absolute, so
    this is again a rest-only edit that leaves the mesh untouched.
    """
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    synced = 0
    try:
        def walk(bone):
            nonlocal synced
            parent = bone.parent
            if parent is not None and bone.name not in base_names:
                direction = (parent.tail - parent.head).normalized()
                bone.tail = bone.head + direction * bone.length
                bone.roll = parent.roll
                synced += 1
            for child in bone.children:
                walk(child)

        for root in [b for b in arm_obj.data.edit_bones if b.parent is None]:
            walk(root)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return synced


def apply_corrections(arm_obj, correction_set):
    """Re-express corrected bones' rest orientation in the target's convention.

    **Written on edit bones, and the mesh is never touched.**  That is not an
    optimisation, it is the only correct way: armature deformation is relative to the
    rest pose, so editing rest bones with the pose left at identity moves no vertex at
    all.  The previous version posed the rig and baked the pose in through
    ``_apply_and_rebind()``, which both deformed the mesh and ran
    ``object.convert(target='MESH')`` on it -- applying its modifiers and wrecking the
    model.  A cross-game port must change the skeleton and nothing else: the mesh is
    already correct, only the bone layout differs.

    Joint positions are held fixed (each bone keeps its head); what changes is the
    bone's axes, which is what a convention relabel *is* -- so bones do re-point, and
    that is why a ported rig matches the target game's own rig visually.

    Edit bones are stored in absolute armature space, so re-orienting a parent does
    not drag its children: every bone is written independently and bones with no
    correction simply stay as they are.
    """
    targets = {}
    for b in arm_obj.data.bones:
        c = correction_set.get(b.name) if correction_set is not None else None
        if c is None or c.is_identity:
            continue
        targets[b.name] = b.matrix_local.to_3x3() @ Matrix([list(r) for r in c.matrix])

    if not targets:
        return 0

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    changed = 0
    try:
        for name, rot in targets.items():
            eb = arm_obj.data.edit_bones.get(name)
            if eb is None:
                continue
            m = rot.to_4x4()
            m.translation = eb.head
            eb.matrix = m          # keeps the head and the bone length, rewrites axes
            changed += 1
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return changed


def execute_port(arm_obj, plan, ref_arm=None, correction_set=None, base_names=None):
    """Run *plan* on *arm_obj* (already a copy).  Returns a counts dict."""
    counts = {"merged": 0, "renamed": 0, "inserted": 0, "corrected": 0, "synced": 0}

    if plan.merges:
        # (keep, delete) is the order merge_weights_and_delete_bones expects; it also
        # resolves chains of merges onto the final survivor.
        merge_weights_and_delete_bones(arm_obj, [(into, src) for src, into in plan.merges])
        counts["merged"] = len(plan.merges)

    # Corrections go on **before** the renames: a CorrectionSet is keyed by source
    # bone name, and once a bone is called L_Leg_Upper there is nothing left to match
    # L_Thigh against.  Measured before this was fixed: 72 corrections derived, 1
    # applied -- the one bone (Hip) whose name is the same in both games.
    if correction_set is not None:
        counts["corrected"] = apply_corrections(arm_obj, correction_set)

    counts["renamed"] = _rename_bones(arm_obj, plan.renames)
    # Insertion comes last because its rules are written in target-game names, and
    # the bones it copies orientation from are already in the target convention.
    counts["inserted"] = _insert_bones(arm_obj, plan.inserts, ref_arm)

    # Last, and only when the convention actually changed: the non-base bones follow
    # the base bones they hang off.  Runs after the renames so *base_names* -- which
    # is in target-game naming -- matches what the bones are called by now.
    if correction_set is not None and base_names:
        counts["synced"] = sync_child_orientation(arm_obj, base_names)
    return counts


# ── operator ────────────────────────────────────────────────────────────────────

_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _target_game_items(self, context):
    presets = _preset_by_game()
    items = [(c, c, "", i) for i, c in enumerate(
        c for c in PORTABLE_GAMES if c != self.source_game and c in presets)]
    if not items:
        items = [("NONE", "-", "", 0)]
    return _cached("target_game", items)


def is_mesh_collection(col):
    """A collection holding an imported RE mesh.

    Same test the MDF tools use (``core/mdf_generator_base.py``): the importers tag
    the collection with ``~TYPE``, and the naming convention is the fallback for
    collections made by hand.
    """
    return col.get("~TYPE") == "RE_MESH_COLLECTION" or col.name.endswith(".mesh")


def mesh_collections():
    return [c for c in bpy.data.collections if is_mesh_collection(c)]


def _translate_rig(arm_obj, dz):
    """Move the *body* by *dz* in world Z, leaving the file origin where it is.

    Object transform for the body, because it is a rigid move of the whole
    assembly and there is nothing to bake -- and it does reach the file:
    RE Mesh Editor's exporter runs ``exportArmatureData.transform(
    armatureObj.matrix_world)`` before writing, so the object's location is baked
    into the exported bone data.  Meshes parented to the armature come along on
    their own; ones merely bound by modifier do not, so they move explicitly.
    ``pose_bake.attached_meshes`` is what "travels with the rig" means everywhere
    else in this file.

    **The plumbing root is then put back.**  It is not anatomy, it is the origin
    the file is expressed around, and both conventions keep it at zero -- what
    differs is where the *body* sits relative to it.  Carried down with everything
    else, it would land a metre below the model and change every child's
    parent-relative offset by that metre, so animation driving the root would swing
    the body about a point under its feet.  This is what the MHWI pipeline already
    does, by a different route: ``root`` is in PLUMBING_BONES and no preset maps
    it, so ``snap_reference_to_model`` leaves it at the reference rig's origin
    while ``translate_rig`` lifts only the model onto it.
    """
    arm_obj.location.z += dz
    for obj in pose_bake.attached_meshes(arm_obj):
        if obj.parent is not arm_obj:
            obj.location.z += dz
    bpy.context.view_layer.update()

    prev_mode = arm_obj.mode
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        for eb in arm_obj.data.edit_bones:
            if eb.name not in PLUMBING_BONES:
                continue
            # Children that are *connected* would follow the parent's tail, which
            # would undo the move for that branch. Nothing in these rigs connects
            # to the root (MHWilds' root sits 1.02 below its own Hip), but a rig
            # that did would fail silently, so it is broken rather than trusted.
            for child in eb.children:
                child.use_connect = False
            eb.head.z -= dz
            eb.tail.z -= dz
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
        if prev_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=prev_mode)
    bpy.context.view_layer.update()


def collection_armatures(col):
    return [o for o in col.all_objects if o.type == 'ARMATURE']


def _collection_items(self, context):
    items = [(c.name, f"{c.name}  ({len(collection_armatures(c))})", "",
              'OUTLINER_COLLECTION', i) for i, c in enumerate(mesh_collections())]
    if not items:
        items = [("NONE", T("core.mesh_port_ops.no_mesh_collection"), "", 'ERROR', 0)]
    return _cached("collection", items)


def _reference_items(self, context):
    game = _REF_DIRS.get(self.target_game, "")
    return _cached("reference", list(get_reference_skeleton_items(game)))


@gate
class MODDER_OT_PortMeshCrossGame(bpy.types.Operator):
    bl_idname = "modder.port_mesh_cross_game"
    bl_label = "Port Mesh to Another Game"
    #: No 'UNDO', which would put this in the redo panel where adjusting a property
    #: re-runs the operator.  The port is not idempotent -- a second run would port
    #: the copy it just made -- and it writes through bpy.data, so the undo stack
    #: cannot take the result back either.  It must run exactly once per click.
    bl_options = {'REGISTER'}

    source_game: bpy.props.StringProperty(options={'HIDDEN'})
    #: A name, not an EnumProperty.  A dynamic enum's stored value is an index into a
    #: list rebuilt on every access, and this operator grows the object list mid-run by
    #: importing the reference skeleton -- so the safe thing is a value that cannot be
    #: re-resolved at all.  ``prop_search`` gives the same picker in the dialog.
    source_armature: bpy.props.StringProperty(name="Source Armature")
    #: The normal way in: a .mesh collection holds exactly one rig and all the meshes
    #: bound to it, which is the unit a port actually operates on.  Picking the
    #: armature by hand means remembering which meshes belong to it.
    source_collection: bpy.props.EnumProperty(
        name="Mesh Collection", items=_collection_items)
    skeleton_only: bpy.props.BoolProperty(
        name="Skeleton Only", default=False,
        description="Convert an armature on its own, without its meshes")
    target_game: bpy.props.EnumProperty(name="Target Game", items=_target_game_items)
    reference_skeleton: bpy.props.EnumProperty(
        name="Reference Skeleton", items=_reference_items)
    replace_original: bpy.props.BoolProperty(
        name="Replace the Original", default=False,
        description="Convert the original in place instead of converting a copy")

    @classmethod
    def description(cls, context, properties):
        return T("core.mesh_port_ops.desc")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in bpy.data.objects)

    def invoke(self, context, event):
        self._lines = []
        self._blocked = True
        self._prefill(context)
        return context.window_manager.invoke_props_dialog(self, width=480)

    def _prefill(self, context):
        """Fill in what the selection already says, so the usual case needs no picking.

        Whatever is active decides: an object inside a .mesh collection names that
        collection, and an active armature names itself for the skeleton-only path.
        """
        obj = context.active_object
        if obj is None:
            return
        for col in obj.users_collection:
            if is_mesh_collection(col):
                try:
                    self.source_collection = col.name
                except (TypeError, ValueError):
                    pass
                break
        if obj.type == 'ARMATURE':
            self.source_armature = obj.name

    def check(self, context):
        self._preflight(context)
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "skeleton_only", text=T("core.mesh_port_ops.skeleton_only"))
        if self.skeleton_only:
            layout.prop_search(self, "source_armature", bpy.data, "objects",
                               text=T("core.mesh_port_ops.source_armature"))
        else:
            layout.prop(self, "source_collection",
                        text=T("core.mesh_port_ops.source_collection"))
        layout.prop(self, "target_game", text=T("core.mesh_port_ops.target_game"))
        layout.prop(self, "reference_skeleton",
                    text=T("core.mesh_port_ops.reference_skeleton"))
        layout.prop(self, "replace_original",
                    text=T("core.port.replace_original"))
        if not getattr(self, "_lines", None):
            self._preflight(context)
        box = layout.box()
        for icon, text in self._lines:
            box.label(text=text, icon=icon)

    # ── preflight ──────────────────────────────────────────────────────────────

    def _plan_for(self, arm, ref_arm):
        presets = _preset_by_game()
        src, dst = presets.get(self.source_game), presets.get(self.target_game)
        if not src or not dst:
            return None, None
        cross = build_cross_game_map(src, dst)
        if cross is None:
            return None, None
        extra = mhws_insert_rules() if self.target_game == "MHWS" else None
        plan = build_port_plan(
            [b.name for b in arm.data.bones], cross,
            src_main_names=_preset_main_names(src),
            dst_bones=({b.name for b in ref_arm.data.bones}
                       if ref_arm is not None else None),
            extra_rules=extra,
            src_parents={b.name: (b.parent.name if b.parent else None)
                         for b in arm.data.bones},
            src_native_bones=ref_model.load_base_bones(self.source_game))
        return plan, cross

    def _source_armature(self):
        """``(armature, error_line)`` for whichever way the source was chosen.

        A .mesh collection is expected to hold exactly one rig.  Two means the
        collection is not what it claims -- several models merged into one, most
        likely -- and porting would silently pick one of them, so it is refused.
        """
        if self.skeleton_only:
            arm = bpy.data.objects.get(self.source_armature)
            if arm is None or arm.type != 'ARMATURE':
                return None, ('INFO', T("core.mesh_port_ops.pick_target"))
            return arm, None

        col = bpy.data.collections.get(self.source_collection)
        if col is None:
            return None, ('INFO', T("core.mesh_port_ops.pick_collection"))
        arms = collection_armatures(col)
        if not arms:
            return None, ('ERROR', T("core.mesh_port_ops.collection_no_armature"))
        if len(arms) > 1:
            return None, ('ERROR', T("core.mesh_port_ops.collection_many_armatures")
                          .format(n=len(arms), names=", ".join(a.name for a in arms[:3])))
        return arms[0], None

    def _preflight(self, context):
        self._lines = []
        self._blocked = True
        arm, err = self._source_armature()
        if err is not None:
            self._lines = [err]
            return

        detected = auto_detect_preset(arm, False)
        if detected:
            mgr = BoneMapManager()
            code = mgr.preset_info.get("game_code") if mgr.load_preset(detected) else None
            if code and self.source_game and code != self.source_game:
                self._lines = [('ERROR', T("core.mesh_port_ops.wrong_source_game").format(
                    found=code, expected=self.source_game))]
                return

        plan, _cross = self._plan_for(arm, None)
        if plan is None:
            self._lines = [('ERROR', T("core.mesh_port_ops.pick_target"))]
            return

        self._lines.append(('INFO', T("core.mesh_port_ops.stat_plan").format(
            renamed=len(plan.renames), merged=len(plan.merges),
            inserted=len(plan.inserts), kept=len(plan.passthrough))))
        if plan.clashes:
            names = ", ".join(f"{s}->{d}" for s, d in plan.clashes[:3])
            self._lines.append(('ERROR', T("core.mesh_port_ops.name_clash").format(
                n=len(plan.clashes), names=names)))
        if plan.uninsertable:
            self._lines.append(('ERROR', T("core.mesh_port_ops.unplaceable").format(
                n=len(plan.uninsertable),
                names=", ".join(plan.uninsertable[:4]))))
        if self.target_game not in FAMILY_A or self.source_game not in FAMILY_A:
            self._lines.append(('INFO', T("core.mesh_port_ops.needs_correction")))
        if plan.ok:
            self._lines.append(('CHECKMARK', T("core.mesh_port_ops.all_resolved")))
        self._blocked = not plan.ok

    # ── execute ────────────────────────────────────────────────────────────────

    def execute(self, context):
        arm, err = self._source_armature()
        if err is not None:
            self.report({'ERROR'}, err[1])
            return {'CANCELLED'}

        # Everything below either writes through bpy.data directly (new
        # collections, duplicated armatures/meshes, the probe's removal) or
        # calls sub-operators -- mode_set, modder.ree_to_tpose -- that push
        # their own undo step regardless of this operator's bl_options.  Left
        # on, a Ctrl+Z after the port lands on one of those mid-run steps: a
        # half-renamed, half-corrected rig that was never a valid standalone
        # scene state, and restoring it is what crashes Blender.  Suppressing
        # global undo for the run makes a later Ctrl+Z skip over the whole
        # port instead, matching the "runs once, not undoable" contract this
        # operator already declares by leaving 'UNDO' out of bl_options.
        prefs = context.preferences.edit
        undo_was_on = prefs.use_global_undo
        prefs.use_global_undo = False
        try:
            return self._execute_port(context, arm)
        finally:
            prefs.use_global_undo = undo_was_on

    def _execute_port(self, context, arm):
        # Copy unless told otherwise. The meshes come too: merging supernumerary
        # bones moves vertex groups, which live on the mesh, so an armature-only
        # copy would have nothing to transfer the weights on.
        if not self.replace_original:
            if self.skeleton_only:
                arm = _armature_only_copy(arm)
                arm.name = f"{arm.name.replace('_probe', '')}_{self.target_game}"
                arm.data.name = arm.name
            else:
                col = bpy.data.collections.get(self.source_collection)
                if col is not None:
                    arm = duplicate_mesh_collection(col, arm, self.target_game)
                else:
                    arm = bone_utils.duplicate_armature_with_meshes(
                        arm, f"{arm.name}_{self.target_game}")

        # Into the target's rig frame before anything measures against the
        # reference, which is imported in that frame.  Nothing downstream actually
        # depends on the order -- the insert rules are origin-agnostic (colocate and
        # midpoint anchor on the *model's* own bones, ref_offset takes the
        # reference's parent-relative offset) and the correction derivation only
        # reads rotations -- but "already in the target frame" is the assumption a
        # later reader will make, so make it true as early as possible.
        dz = origin_shift(self.source_game, self.target_game)
        if dz:
            _translate_rig(arm, dz)

        ref_arm = None
        if self.reference_skeleton and self.reference_skeleton != "NONE":
            ref_arm = import_reference_armature(_REF_DIRS.get(self.target_game, ""),
                                                self.reference_skeleton)
        try:
            plan, cross = self._plan_for(arm, ref_arm)
            if plan is None:
                self.report({'ERROR'}, T("core.mesh_port_ops.pick_target"))
                return {'CANCELLED'}
            if not plan.ok:
                self.report({'ERROR'}, T("core.mesh_port_ops.blocked").format(
                    detail="; ".join(plan.uninsertable)))
                return {'CANCELLED'}

            cross_convention = (self.source_game in FAMILY_A) != (
                self.target_game in FAMILY_A)
            correction_set = None
            if cross_convention:
                if ref_arm is None:
                    self.report({'ERROR'}, T("core.mesh_port_ops.need_reference"))
                    return {'CANCELLED'}
                # C is measured on throwaway copies, never on the user's rig.  The
                # derivation needs both rigs in the same physical pose, and the only
                # way to arrange that is to T-pose them -- but T-posing re-poses the
                # mesh, and a port must leave the mesh alone.  C is a local axis
                # relabel and therefore pose-independent, so measuring it on a T-posed
                # probe and applying it to the rig as it stands is exact.
                probe = _armature_only_copy(arm)
                _tpose(context, probe)
                _tpose(context, ref_arm)
                correction_set = derive_bone_correction(
                    probe, ref_arm, cross,
                    table=_fallback_table(self.source_game, self.target_game, cross),
                    tolerance_deg=DEFAULT_TOLERANCE_DEG,
                    src_game=self.source_game, dst_game=self.target_game)
                # Helpers and torso bones have no trustworthy C of their own; give
                # them their nearest corrected ancestor's, checked per bone.  Without
                # this the rig comes out half-converted: MHWilds' _HJ_ helpers keep
                # pointing the old way while the base bones they ride on re-point.
                expand_corrections(
                    correction_set,
                    {b.name: (b.parent.name if b.parent else None)
                     for b in probe.data.bones},
                    {b.name: b.matrix_local.to_3x3() for b in probe.data.bones},
                    {b.name: b.matrix_local.to_3x3() for b in ref_arm.data.bones},
                    cross)
                bpy.data.objects.remove(probe, do_unlink=True)
                if correction_set.pose_mismatch_suspected:
                    # Over half the bones failed the signed-permutation gate, which
                    # means the two rigs are not in the same physical pose -- the
                    # derivation's precondition.  Running modder.ree_to_tpose on both
                    # fixes it (measured: 11 derived before, 39 after).
                    self.report({'ERROR'}, T("core.mesh_port_ops.pose_mismatch").format(
                        rejected=len(correction_set.rejected)))
                    return {'CANCELLED'}

            base_names = set(cross.mapping.values()) | {n for n, _r, _a in plan.inserts}
            counts = execute_port(arm, plan, ref_arm, correction_set, base_names)
        finally:
            if ref_arm is not None:
                bpy.data.objects.remove(ref_arm, do_unlink=True)

        msg = T("core.mesh_port_ops.done").format(
            game=self.target_game, name=arm.name, **counts)
        if correction_set is not None and correction_set.rejected:
            msg += " " + T("core.mesh_port_ops.rejected").format(
                n=len(correction_set.rejected),
                names=", ".join(b for b, _t, _d in correction_set.rejected[:4]))
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


classes = [MODDER_OT_PortMeshCrossGame]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
