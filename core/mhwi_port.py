"""MHWI -> MHWS port, planning layer: the constants a rebuild needs.

This is a *rebuild*, not a conversion, and that is a deliberate split from
``core/mesh_port.py``.  The RE-to-RE port rests on one premise, stated in
``mesh_port_ops.apply_corrections``: "the mesh is already correct, only the bone
layout differs" -- so every step there is a rest-pose edit that provably moves no
vertex.  Crossing from MT Framework to RE Engine breaks that premise three ways:

* the two bodies are different proportions (thigh -9.1%, torso -7.8%, Hip->Thigh +42%),
* MHWI's thumb is axis-aligned like its other fingers and MHWilds' is not (29 degrees),
* the two games put their origin in different places (1.0468 m apart).

All three need the *mesh* to move with the skeleton, so this pipeline is
pose-then-bake throughout, via ``core/pose_bake.py``.

Everything here is measured, not assumed -- see ``docs/mhwi_mhws_port_notes.md`` for
the raw numbers and the reference rigs they came from.  Free of ``bpy`` so the
partitioning can be unit-tested offline.
"""

import re

#: Vertical offset from MHWI's origin to MHWilds', in metres.
#:
#: **Deliberately a constant, not derived from the loaded reference** (user's
#: decision, 2026-08-15).  The tempting derivation -- "translate so the source Hip
#: lands on the reference's Hip" -- keys off a landmark authors move: MHWilds' COG
#: and Hip get shifted by some riggers.  What neither game's authors move is the
#: **sole plane**, so that is what this aligns, and relative to each game's own
#: origin the sole plane is fixed.  Hence one number rather than a measurement.
#:
#: Measured on the reference bodies: MHWI's sole sits at z = -1.0468 with its origin
#: ``MhBone_000`` at z = 0; MHWilds' ground plane is its ``root`` at z = 0.
#:
#: Not to be confused with the Hip-to-Hip distance, which is 1.02 -- MHWI's hip rides
#: 2.7 cm higher above its own sole than MHWilds' does, so aligning hips would sink
#: the model 2.7 cm into the ground.  Nor with the mesh-sole-to-mesh-sole distance
#: (1.0518): a body mesh's lowest vertex is not stable, the same MHWilds body's sole
#: moves 8 mm just from the T-pose conversion straightening its 8-degree thigh splay.
SOLE_OFFSET_Z = 1.0468

#: Pose-space rotations that put MHWI's thumb where MHWilds' thumb is, applied at the
#: named bone about its own head, **in list order**: the second entry is the residual
#: left after the first has already swung the rest of the chain.
#:
#: MHWI's thumb phalanges run along the hand axis exactly like its other fingers
#: (``Thumb2 -> Thumb3`` is ``(1, 0, 0)``); MHWilds' are splayed.  Every other finger
#: matches to 0.00 degrees, so this is the one place the two hands genuinely differ.
#:
#: The left and right axes are mirror images in the axial-vector sense (x keeps its
#: sign, y and z flip) and the angles agree to three decimals -- that self-consistency
#: is why these are trusted as signal rather than fit noise.
THUMB_ROTATIONS = {
    "L": [("MhBone_031", (-0.1216, 0.2002, -0.9722), 29.025),
          ("MhBone_032", (0.4818, 0.8651, 0.1395), 13.182)],
    "R": [("MhBone_048", (-0.1216, -0.2002, 0.9722), 29.026),
          ("MhBone_049", (0.4818, -0.8651, -0.1395), 13.182)],
}

#: What differs per destination game.  MHWilds was the only target for a long time,
#: so what used to be four module constants is now one row each.
#:
#: MHRS's row is nearly empty, and that is the measurement rather than a stub:
#:
#: * ``sole_offset = 0`` -- MHWI and MHRS are the *same rest frame*.  16 landmarks
#:   over the two reference bodies, max deviation 0.0022 m, most exactly zero, and
#:   identical bounding boxes to four decimals.  Both measure from the pelvis while
#:   MHWilds measures from the ground, which is the whole of SOLE_OFFSET_Z.
#: * ``rotate_thumbs = False`` -- the thumb swing is a *MHWilds* fixup, not an MHWI
#:   quirk.  MHWI's thumb axis sits 24.19 deg from MHWilds' and **0.351 deg** from
#:   MHRS's, so applying it here would introduce the error it exists to remove.
#: * ``optimize_ops = ()`` -- ``mhws.optimize_skeleton`` and ``mhws.optimize_aux_bones``
#:   are MHWilds' own helper-system passes.  MHRS has no helper system to optimise
#:   and no such operators; there is nothing to substitute, not merely nothing wired.
#:
#: ``preset`` is the bone preset's *filename*.  MH Rise's is still ``mhwr.json`` for
#: compatibility with existing user presets even though its game_code is ``MHRS``.
PORT_TARGETS = {
    "MHWS": {
        "preset": "mhws.json",
        "sole_offset": None,            # filled from SOLE_OFFSET_Z below
        "rotate_thumbs": True,
        "optimize_ops": ("mhws.optimize_skeleton", "mhws.optimize_aux_bones"),
    },
    "MHRS": {
        "preset": "mhwr.json",
        "sole_offset": 0.0,
        "rotate_thumbs": False,
        "optimize_ops": (),
    },
}

#: Order the targets are offered in; MHWilds first because it is the validated one.
PORT_TARGET_ORDER = ("MHWS", "MHRS")


PORT_TARGETS["MHWS"]["sole_offset"] = SOLE_OFFSET_Z


def port_target(game_code):
    """The per-game row, or MHWilds' as the default."""
    return PORT_TARGETS.get(game_code) or PORT_TARGETS["MHWS"]


#: MHWI's origin bone, and what MHWilds calls the same thing.  Function id 000 is
#: "原点/Root" in the id table, and it is the parent of the pelvis -- so it is the one
#: leftover that gets renamed rather than dropped, because a rig with no root leaves
#: ``COG`` and ``Hip`` parentless too.
ORIGIN_BONE = "MhBone_000"
PLUMBING_ROOT = "root"

#: ``MhBone_%03d`` -- the only name MHW Model Editor ever gives a mod3 bone, because
#: mod3 has no bone *names*, only a ``boneFunction`` id in a global 0..511 namespace
#: (``mod3_parser.py``: ``"MhBone_" + str(remap[i]).zfill(3)``).
_NAME_RE = re.compile(r"^MhBone_(\d{3})$")

#: 255 is not a bone.  It is mod3's sentinel: ``boneParent == 255`` means "no parent",
#: and 255 in the 512-byte remap table means "no such bone".
SENTINEL_ID = 255

#: Function ids the base skeleton occupies, from the user's own id/name table
#: (``身体ID及对应部位.xlsx``, sheet ``身体骨骼ID``).  Ranges are inclusive.
#:
#: 000 origin; 001-021 spine/limbs; 030+047 weapon attach; 031-063 fingers;
#: 064-069 skirt attach; 070-077 shoulder/elbow/glute/knee helpers;
#: 080-085 twist helpers + foot attach; 100-104 scoutfly and slinger; 247-254 IK.
BASE_ID_RANGES = ((0, 21), (30, 63), (64, 69), (70, 77), (80, 85), (100, 104),
                  (247, 254))

#: Where per-asset physics bones are allowed to live.  **Closed by the game, not by
#: convention** (user, 2026-08-15): MHWI restricts physics to these ids, and a bone
#: placed outside them has no physical effect at all.  That is what makes a range test
#: sufficient here, where ``mesh_port`` has to fall back to reporting.
PHYSICS_ID_RANGES = ((150, 246), (256, 511))


#: Where a physics chain hanging off a *base* bone with no counterpart goes instead.
#: target game -> {MHWI bone name: target bone name} (user's decision, 2026-08-16).
#:
#: 064 and 067 are the left and right leg's skirt attach bones.  They are genuinely
#: half-followers: they rise when the leg lifts and ignore everything else it does, and
#: neither target has a bone that behaves that way, so the bone presets map neither --
#: which left every skirt chain hanging off them orphaned and dropped.
#:
#: The thigh is the deliberate approximation.  A chain moved there follows *all* of the
#: leg's motion rather than only the lift, which is wrong in the same direction the
#: source is right; the alternative the generic walk reaches is the hip, which follows
#: none of it.  Overshooting beats not moving at all for a skirt.
#:
#: Keyed per game because the destination is a *bone name*, and the two targets do not
#: share one: MHWilds' thigh is ``L_Thigh``, MHRS' is ``L_Leg_00`` (``mhwr.json``'s
#: ``thigh_L``).  A single MHWilds-named table silently did nothing under MHRS -- the
#: lookup in ``mhwi_port_ops._graft_parent`` requires the name to exist on the target
#: rig, so a wrong name is indistinguishable from no override.
#:
#: Only these two bones are listed because only these two have a known answer.  The
#: rest of the 064-069 skirt block falls through to ``physics_parent_chain``, which
#: finds the nearest ancestor that does map rather than guessing at a slot.
PHYSICS_PARENT_OVERRIDES = {
    "MHWS": {
        "MhBone_064": "L_Thigh",
        "MhBone_067": "R_Thigh",
    },
    "MHRS": {
        "MhBone_064": "L_Leg_00",
        "MhBone_067": "R_Leg_00",
    },
}


def physics_parent_overrides(game_code):
    """The per-game override table, or MHWilds' as the default."""
    return PHYSICS_PARENT_OVERRIDES.get(game_code) or PHYSICS_PARENT_OVERRIDES["MHWS"]


def physics_parent_chain(parent_names, start):
    """Ancestors of *start*, nearest first, as ``(mhwi name, is_physics)`` pairs.

    *parent_names* is ``{bone: parent_or_None}`` from the source rig.  Walking rather
    than looking only at the direct parent is what turns "this chain has nowhere to go"
    into "this chain attaches higher up": a physics bone whose parent is a base bone the
    presets do not map used to be reported as an orphan and dropped, taking every bone
    below it with it, because its own children then had no parent either.

    Cycle-guarded, since a malformed rig would otherwise hang the port rather than
    report it.
    """
    out, seen = [], set()
    node = parent_names.get(start)
    while node is not None and node not in seen:
        seen.add(node)
        out.append((node, is_physics_bone(node)))
        node = parent_names.get(node)
    return out


def bone_id(name):
    """The mod3 function id behind an ``MhBone_NNN`` name, or None if not one."""
    m = _NAME_RE.match(name or "")
    return int(m.group(1)) if m else None


def _in(ranges, i):
    return any(lo <= i <= hi for lo, hi in ranges)


def is_base_bone(name):
    """True for a bone belonging to MHWI's own skeleton (anatomy *and* furniture)."""
    i = bone_id(name)
    return i is not None and _in(BASE_ID_RANGES, i)


def is_physics_bone(name):
    """True for a per-asset physics bone -- cloth, hair, anything chain-driven."""
    i = bone_id(name)
    return i is not None and i != SENTINEL_ID and _in(PHYSICS_ID_RANGES, i)


def classify(name):
    """``'base'`` | ``'physics'`` | ``'unknown'`` for one bone name.

    ``'unknown'`` covers both non-``MhBone_`` names and the gaps in the id space
    (022-029, 078-079, 086-099, 105-149, and 255).  The gaps cannot hold physics --
    the game ignores bones there -- so an unknown is a genuine oddity worth surfacing
    rather than a category the port has to support.
    """
    i = bone_id(name)
    if i is None:
        return "unknown"
    if _in(BASE_ID_RANGES, i):
        return "base"
    if i != SENTINEL_ID and _in(PHYSICS_ID_RANGES, i):
        return "physics"
    return "unknown"


def partition(names):
    """``{'base': [...], 'physics': [...], 'unknown': [...]}``, each sorted.

    The three groups take different routes through the port: *base* bones are aligned
    onto the MHWilds reference, *physics* bones ride their parent's transform with
    their local offsets untouched, and *unknown* is reported.
    """
    out = {"base": [], "physics": [], "unknown": []}
    for n in names:
        out[classify(n)].append(n)
    for k in out:
        out[k].sort()
    return out
