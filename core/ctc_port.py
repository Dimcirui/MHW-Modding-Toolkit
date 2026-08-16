"""MHWI ctc/ccl -> MHWilds chain2/clsp, planning layer: the tables a rebuild needs.

This is the third cross-game port in the family, and it is a **rebuild** for the same
reason ``core/mrl3_port.py`` is: the two containers do not have the same shape.  ctc
has two levels (chain -> node); chain2 has three (settings -> group -> node), and the
collision shapes live in a separate ``.clsp`` entirely.  Aligning containers would
produce a half-legal file, so the pipeline reads the *bindings and parameters* out of
ctc/ccl and drives RE-Chain-Editor's own builders to make a fresh chain2 + clsp.

**The mapping in here is the user's, from experience with both games -- it is not
derived from the reference assets and must not be "corrected" against them.**  The
scene the work was validated in has both games' files hand-tuned per game, so a
parameter diff against it measures the author's tuning, not this table.  See
``docs/mhwi_physics_port_plan.md`` §10, which this module is the executable form of.

Two consequences of that worth stating up front, because both look like bugs:

* Most of ctc's chain parameters are **deliberately dropped**.  Only five carry a
  value across.  ``LimitForce`` / ``springLimitRate`` and ``ReflectCoef`` /
  ``coefOfElasticity`` in particular are name-similar pairs that are *not* verified
  to mean the same thing, so pairing them would be a guess dressed up as a mapping.
* Every dropped field is reported rather than silently ignored, because a chain that
  relied on one comes out subtly wrong and -- per the MHWmodfixer findings recorded
  in the plan doc -- broken chain physics surfaces **only at game boot**.  Nothing in
  the export path, the file, or the scene will say a word.

Free of ``bpy``: pure tables and pure functions, so the whole translation is checkable
offline in ``tests/test_ctc_port.py``.
"""

# ── units ───────────────────────────────────────────────────────────────────────

#: ctc node radii are in **centimetres** and have to be scaled here.
#:
#: This is the one place the 100x actually bites, and the reason it is a single
#: constant rather than a blanket rule is that MHW Model Editor already converted
#: *some* fields on import (``ctc_properties.getCTCChain`` divides ``Gravity`` and
#: ``LimitForce`` by 100) and left others alone.  Dividing everything again would
#: silently shrink gravity to -0.098.
#:
#: Nodes are also the only case that has to touch a property group at all.  The
#: **collision shapes do not**: both addons' importers write metres into
#: ``obj.location`` / ``obj.scale`` (ccl_properties.py:42,63 and
#: re_chain_propertyGroups.py:172,242), so a collider ports by copying those two and
#: letting ``syncCollisionOffsets()`` back-fill the property group.  Read
#: ``mhw_ccl_collision.ColRadius`` instead and it is 100x out.
NODE_RADIUS_SCALE = 0.01

#: Gravity crosses untouched -- not 1/100, and not axis-swapped either.  Measured:
#: the ctc scene value is ``(0, -9.8, 0)`` and ``chainSettings.gravity``'s own default
#: is ``(0, -9.8, 0)``, component for component.
GRAVITY_SCALE = 1.0

#: ``AngleLimitRadius`` is already radians on both sides (0.2618 = 15 degrees,
#: measured).  Named so nobody "fixes" it into a degree conversion.
ANGLE_SCALE = 1.0


# ── flag bit layouts ────────────────────────────────────────────────────────────

#: ``ctc.CollisionAttrFlag``, from MHW Model Editor's own ctypes bitfield
#: (``file_ctc.py::CollisionAttrFlag_bits``).  Bit 0 is a "none" sentinel, not a
#: switch.
CTC_COLLISION_BITS = {
    "CollisionFlags_None": 1,
    "CollisionSelfEnable": 2,
    "CollisionModelEnable": 4,
    "CollisionVGroundEnable": 8,
}

#: ``ctc.ChainAttrFlag`` (``file_ctc.py::ChaAttrFlag_bits``).
CTC_CHAIN_BITS = {
    "AngleLimitEnable": 1,
    "AngleLimitRestitutionEnable": 2,
    "EndRotConstraintEnable": 4,
    "TransAnimationEnable": 8,
    "AngleFreeEnable": 16,
    "StretchBothEnable": 32,
    "PartBlendEnable": 64,
}

#: ctc's own defaults (``file_ctc.py::Chain.__init__``), so a caller can tell an
#: authored value from an untouched one when reporting.
CTC_COLLISION_DEFAULT = 4    # CollisionModelEnable
CTC_CHAIN_DEFAULT = 39       # AngleLimit + Restitution + EndRotConstraint + StretchBoth

#: chain2's group attribute vocabulary (``re_chain_operators.chain2GroupAttrFlags``).
#:
#: The **same** vocabulary is used by two different fields -- ``group.attrFlags`` and
#: ``settings.groupDefaultAttr`` -- which is why ``translate_flags`` returns one mask
#: pair for "group attr" and both fields get it.  Note this is the *chain2* table:
#: ``chainGroupAttrFlags`` (the ``.chain`` one) differs at 4, 65536 and 131072, so
#: reading the wrong one lands ScaleAnimation on ExtraNode.
CHAIN2_GROUP_ATTR = {
    "RootRotation": 1,
    "AngleLimit": 2,
    "ScaleAnimation": 4,
    "CollisionDefault": 8,
    "CollisionSelf": 16,
    "CollisionModel": 32,
    "CollisionVGround": 64,
    "CollisionCollider": 128,
    "CollisionGroup": 256,
    "EnablePartBlend": 512,
    "WindDefault": 1024,
    "TransAnimation": 2048,
    "AngleLimitRestitution": 4096,
    "StretchBoth": 8192,
    "EndRotConstraint": 16384,
    "EnableEnvWind": 32768,
    "CollisionCharacter": 65536,
    "ExtraNode": 131072,
    "UseBitFlag": 262144,
    "StretchBothAutoScale": 524288,
}

#: chain2's settings attribute vocabulary
#: (``re_chain_operators.chainSettingsAttrFlags``).
CHAIN2_SETTINGS_ATTR = {
    "Default": 1,
    "VirtualGroundRoot": 2,
    "VirtualGroundTarget": 4,
    "IgnoreSameGroupCollision": 8,
    "UseReduceDistanceCurve": 16,
}

#: Where each ctc flag bit goes: ``[(domain, chain2 bit name), ...]``.
#:
#: ``'group'`` means both ``group.attrFlags`` and ``settings.groupDefaultAttr``
#: (user's decision): writing only the settings side would let ``attrFlags``'s
#: default of 99331 -- which already carries ``AngleLimit`` -- flatten the per-chain
#: difference the whole translation exists to preserve.
#:
#: ``CollisionVGroundEnable`` is the one bit that fans out to two domains: MHWilds
#: needs the group to opt into virtual-ground collision *and* the settings to declare
#: itself a virtual-ground root.
FLAG_ROUTES = {
    "CollisionSelfEnable":         (("group", "CollisionSelf"),),
    "CollisionModelEnable":        (("group", "CollisionModel"),),
    "CollisionVGroundEnable":      (("group", "CollisionVGround"),
                                    ("settings", "VirtualGroundRoot")),
    "AngleLimitEnable":            (("group", "AngleLimit"),),
    "AngleLimitRestitutionEnable": (("group", "AngleLimitRestitution"),),
    "EndRotConstraintEnable":      (("group", "EndRotConstraint"),),
    "TransAnimationEnable":        (("group", "TransAnimation"),),
    "StretchBothEnable":           (("group", "StretchBoth"),),
}

#: ctc flag bits with no destination, and why.  ``CollisionFlags_None`` is a sentinel
#: rather than a switch; ``AngleFree`` and ``PartBlend`` are dropped by the user's
#: decision -- chain2 does have an ``EnablePartBlend``, so this is a choice, not a gap.
DISCARDED_FLAGS = ("CollisionFlags_None", "AngleFreeEnable", "PartBlendEnable")

#: The one ctc flag whose chain2 namesake was confirmed to *behave* the same
#: (user, measured in game, 2026-08-16).
#:
#: The rest of ``FLAG_ROUTES`` pairs names that match letter for letter and still do
#: different things -- which is why the routing is a tier rather than a fact.  Under
#: ``'BASIC'`` only this flag is routed and the others are left exactly as the target
#: preset has them: **neither set nor cleared**, because "MHWI said off" is not
#: evidence about a flag that means something else in MHWilds.  Under ``'ALL'`` the
#: full table applies, which reproduces the source faithfully at the cost of trusting
#: those name matches.
#:
#: Same shape as ``mrl3_port.param_pairs``'s two tiers, and for the same reason: the
#: conservative tier carries only what is known to mean the same thing.
BASIC_FLAGS = frozenset({"AngleLimitEnable"})

FLAG_MODES = ("BASIC", "ALL")


def decode_bits(table, value):
    """``{bit name: bool}`` for every entry of *table* against an int *value*."""
    return {name: bool(value & mask) for name, mask in table.items()}


def translate_flags(collision_value, chain_value, mode="ALL"):
    """Route ctc's two bitfields onto chain2's two, as set/clear mask pairs.

    Returns ``{'group_on', 'group_off', 'settings_on', 'settings_off', 'dropped',
    'deferred'}``.

    Both mask directions are produced deliberately.  A ctc bit that is *off* has to
    **clear** its chain2 counterpart, not merely fail to set it: the defaults these
    are applied over already carry ``AngleLimit`` and friends, so an OR-only
    translation would turn every chain's angle limit on regardless of what MHWI said.

    *mode* selects the tier -- see ``BASIC_FLAGS``.  Under ``'BASIC'`` a non-basic
    flag lands in **neither** mask, which is the whole point: leaving the target
    preset's own value alone is different from copying MHWI's, and only the former is
    honest about a flag whose two namesakes behave differently.

    ``dropped`` lists discarded bits that were actually *set* -- an unset discarded
    bit changes nothing by being dropped.  ``deferred`` lists flags a narrower *mode*
    declined to route, whatever their value, since under BASIC the source's value is
    not being consulted at all.
    """
    src = dict(decode_bits(CTC_COLLISION_BITS, collision_value))
    src.update(decode_bits(CTC_CHAIN_BITS, chain_value))
    routed = FLAG_ROUTES if mode == "ALL" else {
        f: r for f, r in FLAG_ROUTES.items() if f in BASIC_FLAGS}

    masks = {"group_on": 0, "group_off": 0, "settings_on": 0, "settings_off": 0}
    tables = {"group": CHAIN2_GROUP_ATTR, "settings": CHAIN2_SETTINGS_ATTR}
    for flag, routes in routed.items():
        on = src.get(flag, False)
        for domain, target in routes:
            key = f"{domain}_{'on' if on else 'off'}"
            masks[key] |= tables[domain][target]

    masks["dropped"] = tuple(f for f in DISCARDED_FLAGS if src.get(f))
    masks["deferred"] = tuple(f for f in FLAG_ROUTES if f not in routed)
    return masks


def apply_flags(base, on_mask, off_mask):
    """*base* with *on_mask* set and *off_mask* cleared, in that order.

    Order matters only if a bit appeared in both, which ``translate_flags`` cannot
    produce -- a ctc bit is either on or off, never both.  Clearing last is still the
    safer convention: it keeps "this chain says off" authoritative over any default.
    """
    return (int(base) | int(on_mask)) & ~int(off_mask)


# ── chain parameters ────────────────────────────────────────────────────────────

#: ``(ctc field, chain2 settings field, factor)``.  Five, out of ctc's thirteen.
#:
#: ``WindRate``'s halving is the only non-unit factor and is the user's calibration,
#: not a unit conversion: MHWI's single wind rate reads about twice as strong as
#: MHWilds' ``windEffectCoef`` for the same visible motion.  MHWilds' *environmental*
#: wind is a separate coefficient and is left at the prefab default rather than fed
#: from the same source.
CHAIN_TO_SETTINGS = (
    ("Gravity",        "gravity",                GRAVITY_SCALE),
    ("Damping",        "damping",                1.0),
    ("TransForceCoef", "reduceSelfDistanceRate", 1.0),
    ("SpringCoef",     "springForce",            1.0),
    ("WindRate",       "windEffectCoef",         0.5),
)

#: ctc chain fields with no destination.  Reported, never guessed at -- see the module
#: docstring on why the name-similar pairs are not pairs.
DISCARDED_CHAIN_FIELDS = (
    "ColAttribute", "ColGroup", "ColType", "LimitForce", "FrictionCoef",
    "ReflectCoef", "WindLimit", "unknAttrFlag1", "unknAttrFlag2",
)

#: The ctc field holding a vector rather than a scalar, so a caller knows which of
#: CHAIN_TO_SETTINGS needs component-wise handling without inspecting the value.
VECTOR_CHAIN_FIELDS = frozenset({"Gravity"})


# ── node parameters ─────────────────────────────────────────────────────────────

#: ctc ``AngleMode`` -> chain2 ``angleMode``, **as the string identifiers Blender's
#: EnumProperty actually stores**.
#:
#: The one that matters is 3.  Both enums have a value 3 and they are different
#: things: ctc's is *Oval*, chain2's is *LimitConeBox*, and chain2 puts Oval at 4.
#: An ``int()`` round-trip therefore compiles, exports, loads, and gives the node the
#: wrong shape of angle limit.
ANGLE_MODE_MAP = {
    "0": "0",   # Free            -> AngleMode_Free
    "1": "1",   # Cone            -> AngleMode_LimitCone
    "2": "2",   # Hinge           -> AngleMode_LimitHinge
    "3": "4",   # Oval            -> AngleMode_LimitOval   (NOT LimitConeBox)
}

#: ctc ``CollisionShape`` -> chain2 ``collisionShape``.  Same numbering for all three
#: values ctc has; chain2's 3 (StretchCapsule) has no ctc source.
COLLISION_SHAPE_MAP = {"0": "0", "1": "1", "2": "2"}

#: ``(ctc field, chain2 node field, factor)``.
#:
#: ``Mass -> gravityCoef`` is the user's mapping and is a **behavioural** equivalence,
#: not a physical one: MHWI gives a node a mass, MHWilds gives it a per-node multiplier
#: on the chain's gravity, and the two are not the same quantity.  What they share is
#: the visible effect -- a node with twice the number falls harder than its neighbours
#: -- which is what a port has to preserve.  Carried 1:1 because both are dimensionless
#: multipliers that default to 1.0 on their own side.
NODE_TO_CHAIN2 = (
    ("BoneColRadius",    "collisionRadius", NODE_RADIUS_SCALE),
    ("AngleLimitRadius", "angleLimitRad",   ANGLE_SCALE),
    ("Mass",             "gravityCoef",     1.0),
)

#: ctc node fields with no destination.  ``ElasticCoef`` is a genuine model difference
#: -- an RE chain node has no per-node elasticity, that lives on the settings as a
#: whole -- and ``WidthRate`` only ever meant anything for ctc's Oval mode, whose
#: chain2 counterpart parameterises its oval differently.
#:
#: Dropping ``WidthRate`` is therefore also the reason an Oval node cannot port
#: *faithfully* even though ANGLE_MODE_MAP has a destination for it: the mode arrives,
#: its width does not.  Worth a line in the report when a source actually uses Oval.
DISCARDED_NODE_FIELDS = (
    "WidthRate", "ElasticCoef", "unknByte1", "unknByte2", "unknEnum",
)


#: Angle modes whose behaviour depends on the frame's **roll about its own X axis**,
#: not just on where X points.
#:
#: A cone is rotationally symmetric about X, so for Free and Cone any roll gives the
#: same physics and the frame only has to point the right way.  Hinge confines
#: rotation to one plane and Oval makes the cone asymmetric -- for those two the roll
#: *is* the parameter, and a frame that merely points correctly is wrong.
#:
#: Stated in ctc's own numbering, because this is a question you ask of the source.
#: Measured on the reference asset: all 221 nodes are mode 1, so nothing there
#: exercises this -- which is exactly why it is written down rather than discovered
#: later by an asset that does.
ROLL_SENSITIVE_ANGLE_MODES = frozenset({"2", "3"})   # ctc Hinge, ctc Oval


def needs_roll(angle_mode):
    """True when this ctc angle mode cares about the frame's roll about X."""
    return str(angle_mode) in ROLL_SENSITIVE_ANGLE_MODES


def translate_angle_mode(value):
    """chain2 ``angleMode`` for a ctc ``AngleMode``, or None if unrecognised.

    None rather than a fallback: ctc's enum has exactly four values, so anything else
    means the source is not what this expects, and quietly substituting Free would
    remove a limit the author set.
    """
    return ANGLE_MODE_MAP.get(str(value))


def translate_collision_shape(value):
    """chain2 ``collisionShape`` for a ctc ``CollisionShape``, or None."""
    return COLLISION_SHAPE_MAP.get(str(value))


# ── angle limit frames ──────────────────────────────────────────────────────────

#: Both games store a node's angle-limit direction as a **frame object parented to the
#: node**, and in both the stored value is a rotation *relative to the node*, with the
#: frame's position and scale supplied by constraints rather than authored.  Only the
#: spelling differs: ctc keeps a matrix (``NodeMatrix``, written to
#: ``frame.matrix_local``) and chain2 a quaternion (``angleLimitDirectionX/Y/Z/W``,
#: written to ``frame.rotation_quaternion``).
#:
#: Both also agree on which axis means "along the chain": the frame's **local X**.
#: RE-Chain-Editor's own ``chain_from_bone`` builds its frame by rotating X onto the
#: direction of the next node (``re_chain_operators.py:149-176``), and the reference
#: ctc's frames sit on that same direction to 0.00 degrees across all 124 of its
#: non-terminal nodes.
#:
#: **That 0.00 is a property of that asset, not of the format** (user, 2026-08-16):
#: pointing at the next node is the *default*, and authors hand-adjust away from it.
#: Measured on the reference MHWilds chain2, which does contain hand-tuning: 45 of its
#: 224 non-terminal frames deviate, up to 66.6 degrees, and every one of them is a
#: skirt bone -- exactly where an author turns the limit outward so a panel swings
#: away from the leg instead of collapsing onto it.
#:
#: So the direction has to be *carried*, not recomputed.  A recomputed port of a
#: hand-tuned chain does not look broken, which is the problem: every cone points
#: plausibly along its chain, just not where the author put it.
FRAME_FORWARD_AXIS = "X"

#: Terminal nodes carry a meaningless frame, by both tools' own account.  MHW Model
#: Editor hides their cone by default and says so outright ("the last node is
#: typically unused and has a dummy rotation value"); measured, 42 of the reference
#: body's 42 chain-terminal frames are identity while **no** mid-chain frame is.
#: So a terminal frame that fails to match is not a defect worth reporting.
TERMINAL_FRAME_IS_DUMMY = True


#: The maths that turns the measurement above into a value lives in
#: ``core/bone_correction.relocalise_frame`` -- that module is what re-expressing a
#: rotation from one bone's frame in another's belongs to, it is equally bpy-free, and
#: the RE-to-RE chain port needs the identical operation for the identical reason.
#: Not imported here: this module's whole point is that it has no imports at all.


# ── defaults for a freshly built chain2 ─────────────────────────────────────────

#: What a new chain header starts as (user's reference panel, 2026-08-16).  Enum
#: fields are the identifier strings Blender stores, not the display names: the panel
#: reads "CalculateMode_Quality" but the property holds ``"3"``.
HEADER_DEFAULTS = {
    "errFlags": "0",                 # ErrFlags_None
    "masterSize": 0,
    "rotationOrder": "0",            # RotationOrder_XYZ
    "defaultSettingIdx": 0,
    "calculateMode": "3",            # CalculateMode_Quality
    "chainAttrFlags": "4",           # ChainAttrFlags_UNKN4
    "parameterFlag": "0",            # ChainParamFlags_None
    "calculateStepTime": 2.0,
    "modelCollisionSearch": 1,
    "highFPSCalculateMode": "2",     # HighFpsCalculateMode_VariableStepTime
    "wilds_unkn1": 1,
    "wilds_unkn2": 1,
}
HEADER_DEFAULTS.update({f"collisionFilterHit{i}": "0" for i in range(8)})

#: What a new chain group starts as, before ``translate_flags`` is layered on.
#:
#: ``attrFlags = 99331`` decodes as ``RootRotation | AngleLimit | WindDefault |
#: EnableEnvWind | CollisionCharacter``.  ``AngleLimit`` being present here is exactly
#: why the translation has to clear as well as set.
#:
#: ``clspFlags0 = -1`` is all-bits-on, i.e. "collide with every clsp slot".  Those
#: slots are a fixed 20-entry vocabulary keyed by bone pair
#: (``re_chain_operators.chain2GroupClspFlags``), so -1 is the safe default and needs
#: no translation from MHWI, which has no equivalent concept.
GROUP_DEFAULTS = {
    "rotationOrder": "0",              # RotationOrder_XYZ
    "attrFlags": 99331,
    "dampingNoise0": 0.0,
    "dampingNoise1": 0.0,
    "endRotConstMax": 12.57,
    "angleLimitDirectionMode": "0",    # AngleLimitDirectionMode_BasePose
    "interpCount": 0,
    "nodeInterpolationMode": "3",      # NodeInterpolationMode_FastSpline
    "colliderQualityLevel": 0,
    "clspFlags0": -1,
    "clspFlags1": 0,
    "autoBlendCheckNodeNo": 0,
    "tagCount": 0,
    "tag0": 0, "tag1": 0, "tag2": 0, "tag3": 0,
    "hierarchyHash0": 0, "hierarchyHash1": 0,
    "hierarchyHash2": 0, "hierarchyHash3": 0,
}

#: What a new ChainSettings starts as, before §10.1's five values and
#: ``translate_flags`` are layered on.
#:
#: ``id`` is deliberately absent: RE-Chain-Editor assigns it at export.
#: ``colliderFilterInfoPath`` is deliberately absent too -- it is a path into
#: MHWilds' own files and ``chain_convert.COLLIDER_FILTER_BY_GAME`` is already the
#: single place that knows it.  A second copy here is a second thing to keep right.
SETTINGS_DEFAULTS = {
    "settingsAttrFlags": 1,             # Default
    "gravity": (0.0, -9.8, 0.0),
    "damping": 0.20,
    "minDamping": 0.20,
    "dampingPow": 1.0,
    "secondDamping": 0.05,
    "secondMinDamping": 0.05,
    "secondDampingSpeed": 0.0,
    "secondDampingPow": 1.0,
    "collideMaxVelocity": 0.0,
    "springCalcType": "0",              # ChainSpringCalcType_Position
    "springForce": 0.01,
    "springLimitRate": 0.0,
    "springMaxVelocity": 0.0,
    "reduceSelfDistanceRate": 0.30,
    "secondReduceDistanceRate": 0.50,
    "secondReduceDistanceSpeed": 0.0,
    "friction": 0.0,
    "shockAbsorptionRate": 0.20,
    "coefOfElasticity": 0.0,
    "coefOfExternalForces": 0.0,
    "stretchInteractionRatio": 0.50,
    "angleLimitInteractionRatio": 0.50,
    "motionForce": 0.0,
    "motionForceCalcType": "0",         # MotionForceCalcType_MotionForce
    "groupDefaultAttr": 65536,          # CollisionCharacter
    "windDelayType": "1",               # WindDelayType_Auto
    "windEffectCoef": 0.0,
    "envWindEffectCoef": 0.20,
    "windDelaySpeed": 0.0,
    "velocityLimit": 0.0,
    "hardness": 0.0,
    "chainType": "0",                   # ChainType_Chain
}

#: Settings fields the port computes rather than inherits from SETTINGS_DEFAULTS.
#: Kept as a name so the two lists cannot drift apart silently.
SETTINGS_TRANSLATED = tuple(dst for _src, dst, _f in CHAIN_TO_SETTINGS) + (
    "settingsAttrFlags", "groupDefaultAttr")


def build_settings(chain_values, collision_flags, chain_flags, flag_mode="ALL"):
    """The full ChainSettings field dict for one ctc chain.

    *chain_values* maps ctc field names to their scene values (already metric -- see
    NODE_RADIUS_SCALE's note on which fields MHW Model Editor converts on import).

    Returns ``(fields, report)``.  ``report`` carries ``dropped_flags`` and
    ``dropped_fields``, the latter listing only fields the source actually set away
    from ctc's own default, since dropping an untouched field changes nothing.
    """
    fields = dict(SETTINGS_DEFAULTS)

    for src, dst, factor in CHAIN_TO_SETTINGS:
        if src not in chain_values:
            continue
        value = chain_values[src]
        if src in VECTOR_CHAIN_FIELDS:
            fields[dst] = tuple(v * factor for v in value)
        else:
            fields[dst] = value * factor

    masks = translate_flags(collision_flags, chain_flags, flag_mode)
    fields["groupDefaultAttr"] = apply_flags(
        fields["groupDefaultAttr"], masks["group_on"], masks["group_off"])
    fields["settingsAttrFlags"] = apply_flags(
        fields["settingsAttrFlags"], masks["settings_on"], masks["settings_off"])

    report = {
        "dropped_flags": masks["dropped"],
        "deferred_flags": masks["deferred"],
        "dropped_fields": tuple(f for f in DISCARDED_CHAIN_FIELDS
                                if f in chain_values),
    }
    return fields, report


def build_group(collision_flags, chain_flags, flag_mode="ALL"):
    """The full ChainGroup field dict for one ctc chain.

    Only ``attrFlags`` differs from GROUP_DEFAULTS, and it takes the *same* group mask
    that went into the settings' ``groupDefaultAttr`` -- that is the "write both sides"
    decision.  Everything else about a group (interpolation, clsp mask, tags) has no
    MHWI source.
    """
    fields = dict(GROUP_DEFAULTS)
    masks = translate_flags(collision_flags, chain_flags, flag_mode)
    fields["attrFlags"] = apply_flags(
        fields["attrFlags"], masks["group_on"], masks["group_off"])
    return fields


def build_node(node_values):
    """``(fields, unmapped)`` for one ctc node.

    ``unmapped`` names the enum values that had no translation, which is a real error
    rather than a rounding issue -- see ``translate_angle_mode`` on why None is not
    replaced with a default.
    """
    fields, unmapped = {}, []

    if "AngleMode" in node_values:
        mode = translate_angle_mode(node_values["AngleMode"])
        if mode is None:
            unmapped.append(("AngleMode", node_values["AngleMode"]))
        else:
            fields["angleMode"] = mode

    if "CollisionShape" in node_values:
        shape = translate_collision_shape(node_values["CollisionShape"])
        if shape is None:
            unmapped.append(("CollisionShape", node_values["CollisionShape"]))
        else:
            fields["collisionShape"] = shape

    for src, dst, factor in NODE_TO_CHAIN2:
        if src in node_values:
            fields[dst] = node_values[src] * factor

    return fields, unmapped


# ── settings clustering ─────────────────────────────────────────────────────────

#: Decimal places a float is rounded to before it becomes part of a clustering key.
#: Without this, ``WindRate * 0.5`` splits two chains that were authored identically,
#: because the products differ in the last bit.  Six places is far finer than any of
#: these parameters is authored to and far coarser than float noise.
CLUSTER_PRECISION = 6


def settings_key(fields):
    """A hashable key identifying one ChainSettings by *what it will contain*.

    Keyed on the built settings rather than on the ctc source, deliberately.  Eight of
    ctc's thirteen chain fields are dropped, so a source-side key would refuse to merge
    two chains that differ only in, say, ``ReflectCoef`` -- and emit two byte-identical
    ChainSettings.  Keying the output also means adding a row to CHAIN_TO_SETTINGS
    automatically makes the clustering finer, with nothing else to update.

    Only the fields a port can actually vary take part; the rest are constant by
    construction and would just pad the key.
    """
    parts = []
    for name in SETTINGS_TRANSLATED:
        value = fields.get(name)
        if isinstance(value, (tuple, list)):
            parts.append(tuple(round(float(v), CLUSTER_PRECISION) for v in value))
        elif isinstance(value, float):
            parts.append(round(value, CLUSTER_PRECISION))
        else:
            parts.append(value)
    return tuple(parts)


def cluster_settings(per_chain_fields):
    """Group chains that need identical settings.

    *per_chain_fields* is ``[(chain id, settings field dict), ...]``.  Returns
    ``[(settings field dict, [chain id, ...]), ...]`` in first-seen order, so the
    output is stable across runs and diffable.

    This only removes duplicates -- **no value is ever averaged, rounded into a
    neighbour, or otherwise reconciled** (user's decision).  Two chains share a
    ChainSettings exactly when every field that reaches it already agrees.
    """
    order, groups = [], {}
    for chain_id, fields in per_chain_fields:
        key = settings_key(fields)
        if key not in groups:
            order.append(key)
            groups[key] = (fields, [])
        groups[key][1].append(chain_id)
    return [groups[k] for k in order]


# ── collision shapes ────────────────────────────────────────────────────────────

#: clsp shape ids (``re_chain_propertyGroups`` ``chainCollisionShape``), for the two
#: this port emits.  clsp *does* support a real sphere -- the choice below is an
#: authoring preference, not a format limit.
CLSP_SHAPE_SPHERE = "1"
CLSP_SHAPE_CAPSULE = "2"

#: What a ported collider starts as.  The counterpart of ``GROUP_DEFAULTS``'
#: ``clspFlags0 = -1``, and needed for the same reason: that one says the group
#: collides with every clsp tag group, while this one says which groups the
#: collider *belongs to*.  RE Chain Editor defaults it to 0 -- no bits, so no tag
#: group -- and the two together mean "collide with everything" meeting "I am in
#: nothing", which collides with nothing at all.  -1 is all-bits-on, the same safe
#: default, and needs no translation from MHWI, which has no equivalent concept.
#:
#: B stays 0 (user, 2026-08-16).
#:
#: Only ``.clsp`` reads these, so they are inert on the MHRS route, whose v1
#: ``.chain`` carries its collisions inline -- written anyway rather than switched
#: on the target game, because a field the format ignores costs nothing and a
#: per-game branch here would be a second thing to keep true.
COLLIDER_DEFAULTS = {
    "clspBitFlag0": -1,
    "clspBitFlag1": 0,
}


def sphere_as_capsule(bone, offset, radius):
    """A ccl sphere expressed as clsp's degenerate, same-bone capsule.

    **This is a presentation choice, not a necessity** (user's decision, 2026-08-16).
    clsp has a native sphere (``RE_CHAIN_COLLISION_SINGLE``, shape 1) and the port
    could emit one; capsules are used so the output matches the all-capsule shape of
    a hand-authored MHWilds clsp.

    Worth being explicit about what this is *not*: the reference MHWilds asset has six
    same-bone capsules against MHWI's one sphere, and those six have different start
    and end offsets -- they are ordinary capsules that happen to span one bone, not
    spheres in disguise.  So this function is how *we* choose to spell a sphere; it is
    not a decoding of what the reference author did.

    *offset* and *radius* come from the sphere object's ``location`` and ``scale[0]``,
    already in metres.  Both ends take the same bone, the same offset and the same
    radius, which is what makes the capsule degenerate to a sphere geometrically.
    """
    return {
        "shape": CLSP_SHAPE_CAPSULE,
        "begin_bone": bone,
        "end_bone": bone,
        "begin_offset": tuple(offset),
        "end_offset": tuple(offset),
        "begin_radius": radius,
        "end_radius": radius,
    }


def capsule(begin_bone, end_bone, begin_offset, end_offset, radius):
    """A ccl capsule as a clsp capsule.

    Near-isomorphic: the only structural difference is that ccl stores one radius for
    the whole capsule while clsp stores one per end, so the single value is written to
    both.  A genuinely tapered capsule is a separate clsp shape (5) that ccl cannot
    express, so this never produces one.
    """
    return {
        "shape": CLSP_SHAPE_CAPSULE,
        "begin_bone": begin_bone,
        "end_bone": end_bone,
        "begin_offset": tuple(begin_offset),
        "end_offset": tuple(end_offset),
        "begin_radius": radius,
        "end_radius": radius,
    }
