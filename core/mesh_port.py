"""RE Mesh port, planning layer: what has to happen to a rig to make it another
game's rig.

Named after the mesh rather than the skeleton on purpose: across RE Engine games the
mesh itself needs nothing -- same naming system, same data -- so "porting a mesh"
*is* porting its rig.  ``core/chain_convert.py`` is the physics half and depends on
this one: a chain can only be ported onto a rig that has already been ported, and
**both must consume the same rename map** (``core.bone_mapper.build_cross_game_map``).
Two copies of that mapping drifting apart puts a collider on the wrong bone, and per
memory ``reference_mhwmodfixer`` broken chain physics fails *at boot only* -- nothing
static catches it.

Four things happen to a source bone, and the split is not symmetric:

* **rename** -- the mapping gives a target name nothing else claims.
* **merge** -- several source bones map to one target bone (MHWilds' ``_HJ_`` helpers
  collapsing onto their base, ``L_Knee`` onto ``L_Shin``).  They must be *merged*, not
  kept and not dropped: keeping an extra joint between two base bones breaks animation
  (channels are resolved by name hash, so an unreferenced link in the middle drives
  the tip to the wrong place), while dropping one throws away vertex weights.  Only
  leaf bones -- hair, cloth -- can multiply freely, because nothing animates them.
* **pass through** -- no mapping at all *and* not part of the source game's own
  skeleton.  This is the correct outcome for per-asset hair/cloth/prop bones: they
  travel with the model, so their names, and therefore their hashes, already match in
  the target game.

  Rig furniture is the opposite case and used to be lumped in here, wrongly.  A bone
  like ``L_Elbow_HJ_00`` belongs to *MHWilds' skeleton*, not to the model: the target
  game has no such bone, nothing will ever animate it, and keeping it just inflates
  the rig -- while the helpers that happen to be registered in the preset were being
  merged, so half the same family survived and half did not, for no reason a user
  could see.  A source bone that is in the source game's **native** skeleton but has
  no mapping now merges into its nearest mapped ancestor, weights included.
* **insert** -- the reverse direction's problem: the target game has a base bone the
  source rig lacks.  Same animation argument in reverse, so it has to be synthesised.

Insertion is deliberately limited to the curated table below rather than "every bone
the reference rig has".  The bundled reference models are whole characters, so their
bone lists include that character's own hair and cloth; inserting those into someone
else's model would be nonsense.  Anything a target rig wants that is not in the table
is *reported*, never guessed -- the same rule ``chain_convert`` follows for unmapped
collider attach points.

Placement rules come from measurement, not intuition:

* ``Palm`` sits **at** ``Hand``, not at the midpoint between ``Hand`` and the finger
  roots it parents.  Measured against the real bone on four rigs (mm off): RE9 Leon
  33.6 vs 36.4, RE9 Grace 25.4 vs 31.7, MHWS 12.0 vs 47.0, RE4 Leon 27.9 vs 27.5.
  Co-locating on ``Hand`` wins or ties everywhere, and it is what the existing MHWS
  rule ``{s}_Palm -> {s}_Hand`` already does.
* End and attachment bones (``ToesEnd``, ``Wep``, ``Prop``, ``GroundAngle``,
  ``Null_Offset``) carry no joint semantics, so they are placed at the reference
  model's own parent-relative offset, unscaled.
* Never walk up the parent chain looking for somewhere to hang a bone.  That was
  proposed and the data refused it: ``L_Knee``'s parent ``L_Thigh`` is 400 mm away at
  the hip, and "distance to parent" does not separate helpers from real joints either
  (of MHWilds' 137 ``_HJ_`` bones, 118 sit >5 mm from their parent).

This module is free of ``bpy`` so the plan can be unit-tested offline; geometry and
weight transfer live in ``core/mesh_port_ops.py``.
"""

from .mhwi_port import SOLE_OFFSET_Z

#: Where a game puts its rig origin *anatomically*.  Measured on the reference
#: bodies (2026-08-16): MHWilds' ``root`` and MHRS's ``Root`` are both at
#: ``(0,0,0)``, but MHWilds' ``Hip`` is 1.02 above its root while MHRS's
#: ``Waist_00`` is *at* it -- so MHWilds measures from the ground and MHRS
#: measures from the pelvis.  MHWI does the same as MHRS, which is why
#: ``mhwi_port`` has had to lift its models all along.
#:
#: RE4 and RE9 are ``GROUND`` by deduction rather than measurement: the existing
#: MHWS <-> RE4 <-> RE9 ports translate nothing at all and are known good, which
#: they could not be if any of the three disagreed by a metre.
#:
#: An unregistered game defaults to ``GROUND`` -- every RE Engine game measured so
#: far is, and MHRS is the exception, so that is the way to be wrong least often.
RIG_ORIGIN = {
    "MHWS": "GROUND", "RE4": "GROUND", "RE9": "GROUND",
    "SF6": "GROUND", "DMC5": "GROUND",
    "MHRS": "PELVIS",
}
DEFAULT_RIG_ORIGIN = "GROUND"


def origin_shift(source_game, target_game):
    """World-Z the model must move by to land in *target_game*'s rig frame.

    ``0.0`` between two games of the same convention, so every port that works
    today keeps translating nothing.

    One constant in both directions rather than a per-model measurement (user's
    decision), which makes the shift exactly reversible: a round trip through the
    other convention returns the model to where it started, and no port can
    quietly resize a character by disagreeing with its own inverse.

    The constant is ``mhwi_port``'s, imported rather than restated -- it is the
    same rig frame and the docstring there carries the measurement, including why
    neither hip-to-hip (1.02, sinks the model 2.7 cm) nor mesh-sole-to-mesh-sole
    (1.0518, and a sole moves 8 mm from the T-pose conversion alone) is the
    number.  Its cost is that a character of non-standard height lands slightly
    off; the rejected alternatives were not more accurate, only less stable.
    """
    src = RIG_ORIGIN.get(source_game, DEFAULT_RIG_ORIGIN)
    dst = RIG_ORIGIN.get(target_game, DEFAULT_RIG_ORIGIN)
    if src == dst:
        return 0.0
    # Leaving a pelvis-origin frame, the sole sits at -SOLE_OFFSET_Z and has to
    # come up to 0; entering one, the reverse.
    return SOLE_OFFSET_Z if dst == "GROUND" else -SOLE_OFFSET_Z


#: Placement rules for a bone the target game has and the source rig lacks.
#:
#: ``("colocate", anchor)``   -- head goes exactly where *anchor*'s head is, so the
#:                               bone inherits the target model's own proportions.
#: ``("midpoint", (a, b))``   -- head goes midway between two joints; this is what
#:                               MHWilds' twist helpers need, and the rules for those
#:                               come in through *extra_rules* from the existing
#:                               ``MHWS_OT_OptimizeAuxBones`` tables.
#: ``("ref_offset", None)``   -- head goes at the offset from its parent that the
#:                               bundled reference model has, unscaled.
#: ``("fraction", (a, b, t))`` -- head goes *t* of the way from joint *a* to joint *b*,
#:                               so it scales with the model.  RE9's twist helpers sit
#:                               on exact thirds of the bone they ride (measured on two
#:                               native rigs: t = 0, 1/3, 2/3, 1, perpendicular offset
#:                               0.0 mm on all sixteen).
#: ``("drop", (a, b))``       -- head takes X/Y from joint *a* and Z from joint *b*:
#:                               straight down from *a* to *b*'s height.  For a joint
#:                               that sits under another one at ground level, this is
#:                               the only rule that scales with the model -- colocate
#:                               puts it at the wrong height and ref_offset hands it
#:                               the reference character's leg length.
#:
#: ``{s}`` expands to ``L`` and ``R``.  Keys are target-game bone names.
_INSERT_RULES = {
    "RE9": {
        # RE9 splits the ankle into two joints, and the extra one does *not* ride on
        # the ankle -- measured on three native RE9 rigs (the two bundled references
        # plus a hand-made one), it sits directly below it at the toe joint's height:
        # X/Y within 0.5 mm of the ankle, Z within 1.3 mm of the toes.  Colocating it
        # with the ankle put it ~70 mm too high, which pivots the whole forefoot.
        "{s}_Leg_Foot": ("drop", ("{s}_Leg_Ankle", "{s}_Leg_Toes")),
        "{s}_Hand_Palm": ("colocate", "{s}_Arm_Hand"),
        # RE9's four-segment twist chains.  The ones RE4 also has are *renamed* into
        # place by bone_mapper's _HELPER_NAME_MAP, weights and all; these rules only
        # build what is genuinely missing, which for RE4 is Twist_0 everywhere plus
        # Twist_2/_3 on the legs.  Fractions measured, not guessed -- see the module
        # docstring on "fraction".
        "{s}_Arm_Upper_Twist_0": ("fraction", ("{s}_Arm_Upper", "{s}_Arm_Lower", 0.0)),
        "{s}_Arm_Upper_Twist_1": ("fraction", ("{s}_Arm_Upper", "{s}_Arm_Lower", 1 / 3)),
        "{s}_Arm_Upper_Twist_2": ("fraction", ("{s}_Arm_Upper", "{s}_Arm_Lower", 2 / 3)),
        "{s}_Arm_Upper_Twist_3": ("fraction", ("{s}_Arm_Upper", "{s}_Arm_Lower", 1.0)),
        "{s}_Arm_Lower_Twist_0": ("fraction", ("{s}_Arm_Lower", "{s}_Arm_Hand", 0.0)),
        "{s}_Arm_Lower_Twist_1": ("fraction", ("{s}_Arm_Lower", "{s}_Arm_Hand", 1 / 3)),
        "{s}_Arm_Lower_Twist_2": ("fraction", ("{s}_Arm_Lower", "{s}_Arm_Hand", 2 / 3)),
        "{s}_Arm_Lower_Twist_3": ("fraction", ("{s}_Arm_Lower", "{s}_Arm_Hand", 1.0)),
        "{s}_Leg_Upper_Twist_0": ("fraction", ("{s}_Leg_Upper", "{s}_Leg_Lower", 0.0)),
        "{s}_Leg_Upper_Twist_1": ("fraction", ("{s}_Leg_Upper", "{s}_Leg_Lower", 1 / 3)),
        "{s}_Leg_Upper_Twist_2": ("fraction", ("{s}_Leg_Upper", "{s}_Leg_Lower", 2 / 3)),
        "{s}_Leg_Upper_Twist_3": ("fraction", ("{s}_Leg_Upper", "{s}_Leg_Lower", 1.0)),
        "{s}_Leg_Lower_Twist_0": ("fraction", ("{s}_Leg_Lower", "{s}_Leg_Ankle", 0.0)),
        "{s}_Leg_Lower_Twist_1": ("fraction", ("{s}_Leg_Lower", "{s}_Leg_Ankle", 1 / 3)),
        "{s}_Leg_Lower_Twist_2": ("fraction", ("{s}_Leg_Lower", "{s}_Leg_Ankle", 2 / 3)),
        "{s}_Leg_Lower_Twist_3": ("fraction", ("{s}_Leg_Lower", "{s}_Leg_Ankle", 1.0)),
        "Spine_0": ("colocate", "Hip"),
        "Neck_0": ("colocate", "Neck_1"),
        "{s}_Leg_ToesEnd": ("ref_offset", None),
        "{s}_Wep": ("ref_offset", None),
        "GroundAngle": ("ref_offset", None),
        "R_Prop_Hip_A": ("ref_offset", None),
        "C_Prop_Spine_A": ("ref_offset", None),
        "C_Prop_Spine_B": ("ref_offset", None),
        "C_Prop_Spine_C": ("ref_offset", None),
        "C_Prop_Hip_A": ("ref_offset", None),
        "C_Prop_Hip_B": ("ref_offset", None),
    },
    "RE4": {
        "{s}_Palm": ("colocate", "{s}_Hand"),
        "Spine_0": ("colocate", "Hip"),
        "Neck_0": ("colocate", "Neck_1"),
        "{s}_ToeEnd": ("ref_offset", None),
        "{s}_Wep": ("ref_offset", None),
        "Null_Offset": ("ref_offset", None),
    },
    # MHWilds' helper system is large but already solved: MHWS_OT_OptimizeAuxBones
    # holds the placement tables, and mesh_port_ops feeds them in through
    # *extra_rules* rather than restating 39 bones here.
    "MHWS": {
        "{s}_Knee": ("colocate", "{s}_Shin"),
        "COG": ("colocate", "Hip"),
        "{s}_Palm": ("colocate", "{s}_Hand"),
        "{s}_Instep": ("ref_offset", None),
    },
    # MHRS's whole rig is 79 bones and the preset maps 51 of them, so this table
    # only has to cover the other 28 -- one of which, ``Root``, is plumbing and
    # never inserted.  Measured on f_shadow (2026-08-16), distance from each bone
    # to the nearest *mapped* joint; everything below is 0-2 mm from its anchor,
    # so co-location is not a simplification here, it is what the rig does.
    #
    # ``_W`` helpers and ``_T`` twists are MHRS's equivalent of MHWilds' ``_HJ_``
    # family. Unlike MHWilds there is no separate table to borrow, but they need
    # none: each sits on a joint rather than between two, so none of them is a
    # midpoint case.  Note the anchor is the joint the bone rides on, which is
    # *not* always its parent -- ``L_Arm_00_W`` hangs off ``L_Arm_00`` but sits
    # 137.5 mm away, on ``L_Arm_01``.
    "MHRS": {
        "Cog": ("colocate", "Waist_00"),
        "Neck_00_S": ("colocate", "Neck_00"),
        "{s}_Arm_00_W": ("colocate", "{s}_Arm_01"),
        "{s}_Arm_01_T": ("colocate", "{s}_Arm_01"),
        "{s}_Arm_01_W": ("colocate", "{s}_Arm_02"),
        "{s}_Leg_00_W": ("colocate", "{s}_Leg_00"),
        "{s}_Leg_01_W": ("colocate", "{s}_Leg_01"),
        "{s}_Leg_02_T": ("colocate", "{s}_Leg_02"),
        "{s}_Weapon_00": ("colocate", "{s}_Arm_03"),
        # The palm, and the reason this pair cannot use {s}: the left hand's is
        # L_Finger_09 while the right hand's is called R_Grip_00, because on that
        # side it doubles as the weapon grip.  Both parent the ring and pinky
        # roots, both sit 21.3 mm off the hand -- the same relationship MHWS and
        # RE4 express as {s}_Palm -> {s}_Hand.
        "L_Finger_09": ("colocate", "L_Arm_03"),
        "R_Grip_00": ("colocate", "R_Arm_03"),
        # Not on any joint: 74.1 mm past the forearm, between it and the hand.
        "{s}_Arm_02_T": ("ref_offset", None),
        # Rig furniture with no anatomical anchor. The IK targets are the reason
        # this is not simply "everything unmapped colocates": L_Hand_IK hangs off
        # Spine_01 but sits 154.3 mm away and 10 mm from its opposite number, i.e.
        # nowhere near a joint of its own.
        "{s}_Foot_IK": ("ref_offset", None),
        "{s}_Hand_IK": ("ref_offset", None),
        "Face_Parts": ("ref_offset", None),
        "LookAt": ("ref_offset", None),
        "PL_Cam": ("ref_offset", None),
    },
}

#: The bone every rig has as scene plumbing rather than anatomy: the origin the
#: file is expressed around.  No preset registers it, so it is not renamed by the
#: mapping and never inserted as a missing target bone.
#:
#: It is **not** the same name in every game, which is the trap this pair exists to
#: close.  MHWS, RE4 and RE9 all spell it ``root``; MHRS spells it ``Root``.  RE
#: Engine binds bones by name *hash*, so those are two different bones -- a ported
#: rig that kept ``root`` in an MHRS file has no origin bone at all, and every
#: reference bone parented to ``Root`` (Face_Parts, LookAt, PL_Cam, the foot IK
#: targets) then has no parent to be inserted under.  Caught by the first real
#: MHWS -> MHRS run, which produced 79 bones of which 6 were the wrong 6.
PLUMBING_ROOT_BY_GAME = {"MHWS": "root", "RE4": "root", "RE9": "root",
                         "SF6": "root", "DMC5": "root", "MHRS": "Root"}
DEFAULT_PLUMBING_ROOT = "root"

#: Every spelling, for "is this bone plumbing?" tests that do not know a game.
PLUMBING_BONES = frozenset(PLUMBING_ROOT_BY_GAME.values())


def plumbing_root(game_code):
    """What *game_code* calls its origin bone."""
    return PLUMBING_ROOT_BY_GAME.get(game_code, DEFAULT_PLUMBING_ROOT)


def insert_rules_for(game_code, extra_rules=None):
    """``{bone_name: (rule, anchor_or_None)}`` for *game_code*, ``{s}`` expanded."""
    out = {}
    for template, (rule, anchor) in (_INSERT_RULES.get(game_code) or {}).items():
        if "{s}" in template:
            for side in ("L", "R"):
                # An anchor is one bone name or a pair of them (midpoint / drop);
                # both sides of a pair need the same expansion.
                if isinstance(anchor, (tuple, list)):
                    sided = tuple(a.format(s=side) if isinstance(a, str) else a
                                  for a in anchor)
                else:
                    sided = anchor.format(s=side) if anchor else None
                out[template.format(s=side)] = (rule, sided)
        else:
            out[template] = (rule, anchor)
    if extra_rules:
        out.update(extra_rules)
    return out


class PortPlan:
    """What a port would do to one rig.

    renames      : [(src, dst)] -- bone keeps its identity under a new name
    merges       : [(src, into)] -- src disappears, its weights move to *into*
    passthrough  : [src] -- no mapping, kept verbatim (hair/cloth/props/plumbing)
    inserts      : [(name, rule, anchor)] -- target base bone the source rig lacks
    uninsertable : [name] -- target wants it, no rule covers it.  **Reported, never
                   guessed**: a base bone placed by intuition is a skinning bug that
                   only shows up in motion.
    collisions   : {dst: [src, ...]} -- the many-to-one groups behind *merges*,
                   kept for reporting.
    clashes      : [(src, into)] -- a pass-through bone whose name is also produced by
                   a rename, so it is merged into the bone taking that name.  These
                   are in *merges* too; the separate list exists to report them,
                   because they are the one merge the mapping did not ask for.

                   The case is real and symmetric.  Every one of these games runs
                   ``Hip -> Spine_0 -> Spine_1 -> Spine_2 -> Neck_0 -> Neck_1 ->
                   Head``, measured on three shipped rigs along the Hip->Neck_0 axis:

                       t         Spine_0  Spine_1  Spine_2  Neck_0  Neck_1
                       MHWS        0.002    0.273    0.548   0.638   0.810
                       RE4         0.000    0.333    0.666   0.494   0.739
                       RE9         0.000    0.342    0.683   0.501   0.745

                   Same names, same order, same parents.  What differs is which
                   member each *preset* assigns to the ``spine_01`` / ``neck``
                   standard slot -- mhws.json says ``Spine_0`` and ``Neck_0``,
                   re4.json says ``Spine_1`` and ``Neck_1``.  The preset table is the
                   authority here by decision, so the port shifts the chain by one
                   and the source's own top neck bone is left without a slot.
                   Merging it into its neighbour keeps its weights and keeps the
                   target's joint count right; keeping it would leave two bones
                   fighting for one name, which Blender resolves by appending
                   ``.001`` and the game resolves by hashing a name no rig has.
    """

    def __init__(self, src_game, dst_game):
        self.src_game = src_game
        self.dst_game = dst_game
        self.renames = []
        self.merges = []
        self.passthrough = []
        self.inserts = []
        self.uninsertable = []
        self.collisions = {}
        self.clashes = []

    @property
    def ok(self):
        return not self.uninsertable

    def summary(self):
        parts = [f"{self.src_game}->{self.dst_game}",
                 f"{len(self.renames)} renamed",
                 f"{len(self.merges)} merged",
                 f"{len(self.inserts)} inserted",
                 f"{len(self.passthrough)} kept"]
        if self.uninsertable:
            parts.append(f"{len(self.uninsertable)} UNPLACEABLE")
        if self.clashes:
            parts.append(f"{len(self.clashes)} name clash merged")
        return ", ".join(parts)


def by_dst_sources(by_dst):
    """Every source bone that has a mapping, from the grouped-by-destination dict."""
    return {name for names in by_dst.values() for name in names}


def _pick_primary(dst_name, src_names, src_main_names):
    """Which of several source bones mapping to *dst_name* survives as that bone.

    Preference order, most specific first: the bone already called *dst_name* (the
    two games share the name in the same slot), then the source preset's ``main``
    bone for its slot (the anatomical joint, e.g. ``L_Thigh`` when helpers collapse
    with it), then alphabetical so the result is at least deterministic.
    """
    if dst_name in src_names:
        return dst_name
    for name in sorted(src_names):
        if name in src_main_names:
            return name
    return sorted(src_names)[0]


def build_port_plan(src_bones, cross_map, dst_game=None, src_main_names=(),
                    dst_bones=None, extra_rules=None, src_parents=None,
                    src_native_bones=None):
    """Plan the rig half of a cross-game mesh port.

    *src_bones*      : the source rig's bone names.
    *cross_map*      : ``CrossGameBoneMap`` from ``build_cross_game_map`` -- the same
                       object the chain port consumes, not a second copy.
    *dst_bones*      : the target reference rig's bone names, when one is available.
                       Without it, insertions can still be planned from the rule table
                       but nothing can be checked against a real target rig.
    *src_main_names* : the source preset's ``main`` bones, used to break merge ties.
    *extra_rules*    : extra ``{name: (rule, anchor)}`` entries, e.g. MHWilds' helper
                       placement tables.
    *src_parents* / *src_native_bones* : together these separate the source game's own
                       rig furniture from the model's own bones -- see "pass through"
                       in the module docstring.  Without them every unmapped bone is
                       kept, which leaves the target rig carrying helpers it has no
                       use for.
    """
    plan = PortPlan(getattr(cross_map, "src_game", None),
                    dst_game or getattr(cross_map, "dst_game", None))
    src_bones = list(src_bones)
    src_main_names = set(src_main_names)

    # 0. the plumbing root, which no preset maps and which is therefore invisible to
    #    cross_map.  It still has to be *renamed* when the two games spell it
    #    differently (MHRS capitalises it), because bones bind by name hash.
    src_root = plumbing_root(plan.src_game)
    dst_root = plumbing_root(plan.dst_game)
    root_rename = (src_root != dst_root and src_root in src_bones
                   and dst_root not in src_bones)

    # 1. group by destination, so many-to-one shows up before anything is decided
    by_dst = {}
    for name in src_bones:
        if root_rename and name == src_root:
            plan.renames.append((name, dst_root))
            continue
        if name in PLUMBING_BONES:
            plan.passthrough.append(name)
            continue
        dst = cross_map.get(name)
        if dst is None:
            plan.passthrough.append(name)
            continue
        by_dst.setdefault(dst, []).append(name)

    # Unmapped bones that belong to the source game's *skeleton* are furniture, not
    # model data: merge them into the nearest mapped ancestor.  Done before the
    # per-destination pass so they join the normal merge machinery.
    if src_parents and src_native_bones:
        mapped = set(by_dst_sources(by_dst))
        for name in list(plan.passthrough):
            if name not in src_native_bones:
                continue
            ancestor = src_parents.get(name)
            while ancestor is not None and ancestor not in mapped:
                ancestor = src_parents.get(ancestor)
            if ancestor is None:
                continue
            plan.passthrough.remove(name)
            plan.merges.append((name, ancestor))

    produced = set()
    for dst, srcs in sorted(by_dst.items()):
        primary = _pick_primary(dst, srcs, src_main_names)
        produced.add(dst)
        if primary != dst:
            plan.renames.append((primary, dst))
        for name in sorted(srcs):
            if name != primary:
                plan.merges.append((name, dst))
        if len(srcs) > 1:
            plan.collisions[dst] = sorted(srcs)

    # 2. what the target game has that the port has not produced.  Only bones the
    #    rule table covers are candidates -- see the module docstring on why the
    #    reference rig's full bone list is not the right set.
    rules = insert_rules_for(plan.dst_game, extra_rules)
    kept = set(plan.passthrough)
    for name, (rule, anchor) in sorted(rules.items()):
        if name in produced or name in kept:
            continue
        if dst_bones is not None and name not in dst_bones:
            continue        # this particular target rig does not have it either
        plan.inserts.append((name, rule, anchor))

    # 3. an insertion is only placeable if its anchor will actually be there.  A
    #    co-located bone whose anchor is missing has nowhere to go, and the fallback
    #    everyone reaches for -- walk up to the nearest mappable ancestor -- was
    #    refuted by measurement, so it becomes a report instead.
    available = produced | set(plan.passthrough) | {n for n, _r, _a in plan.inserts}
    placeable = []
    for name, rule, anchor in plan.inserts:
        needed = () if anchor is None else (
            tuple(a for a in anchor if isinstance(a, str))
            if isinstance(anchor, (tuple, list)) else (anchor,))
        if any(a not in available for a in needed):
            plan.uninsertable.append(name)
        else:
            placeable.append((name, rule, anchor))
    plan.inserts = placeable

    # 4. a bone kept verbatim must not land on a name the port is also producing --
    #    Blender would silently suffix it and the game would hash a name no rig has.
    #    It merges into whatever takes the name, weights and all.
    #    The survivor is named by *its own* source name, because merges run before
    #    renames: at that point the bone taking over the name is still called
    #    whatever it was called in the source game.
    inserted = {n for n, _r, _a in plan.inserts}
    taken_by = {dst: src for src, dst in plan.renames}
    for name in list(plan.passthrough):
        if name not in produced and name not in inserted:
            continue
        into = taken_by.get(name)
        if into is None:                # the name survives under itself; no clash
            continue
        plan.passthrough.remove(name)
        plan.clashes.append((name, into))
        plan.merges.append((name, into))

    # 5. anything the target rig has, the port did not produce, and no rule places.
    #    Custom bones of the reference character are excluded by only counting bones
    #    the preset knows about -- those are the base skeleton.
    if dst_bones is not None:
        placed = produced | kept | inserted | PLUMBING_BONES
        known_targets = {cross_map.get(n) for n in getattr(cross_map, "mapping", {})}
        plan.uninsertable.extend(
            n for n in dst_bones if n in known_targets and n not in placed)
    plan.uninsertable = sorted(set(plan.uninsertable))

    return plan
