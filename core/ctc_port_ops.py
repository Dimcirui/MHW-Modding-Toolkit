"""MHWI ctc/ccl -> MHWilds chain2, execution layer.

``core/ctc_port.py`` decides *what* a value becomes; this decides *where it goes*.
The shape of the job follows the plan doc's §3: nothing is converted at file level.
The ctc collection is read for its bindings and parameters, and RE-Chain-Editor's own
operators build a fresh chain2 -- so every object comes out with the geometry nodes,
materials, hooks, cone helpers and constraints that addon expects, none of which is
worth reimplementing.

**One output collection, not two.**  Colliders land in a ``Chain Collisions - ...``
child of the chain2 collection, parented to its header, and the ``.clsp`` is exported
from there.  A standalone .clsp collection is what *import* produces, not something to
build: RE-Chain-Editor's own ``clspErrorCheck`` rejects a header-less collection
outright.  ``core/chain_convert.duplicate_chain_collection`` reached the same
conclusion the hard way and its docstring records it.

Three things here are not obvious from the code they call:

* **Frame rotations go through world space.**  See ``bone_correction.relocalise_frame``.  The
  two node rotations that formula needs are read from **pose bones**, not from the node
  objects -- measured, a node's world rotation matches its bound bone's to 1.2e-7, and
  going via the bone means the maths does not depend on a constraint having been
  evaluated.  That matters because the build runs with ``alignChains`` patched out.
* **The source is read once, up front.**  A single ``view_layer.update()`` then every
  matrix is captured, before anything is created.  Reading source matrices lazily
  during the build would interleave with the very depsgraph churn the patch avoids.
* **Neither builder lets us choose bone order.**  ``chain_from_bone`` and
  ``collision_from_bone`` both read ``bpy.context.selected_pose_bones``, which is in
  *armature* order, not selection order.  So both results are verified and fixed up
  afterwards rather than trusted -- a capsule with its ends swapped is a legal file
  that behaves wrong, which is the failure mode this whole port has to avoid.
"""

import bpy
from mathutils import Matrix

from . import chain_convert, ctc_port, mhwi_port, re_chain_utils
from .bone_correction import relocalise_frame
from .bone_mapper import build_cross_game_map
from .i18n import T
from .port_consent import gate

SRC_PRESET = "mhwi_world.json"

#: Default target; the per-target rows are mhwi_port.PORT_TARGETS, shared with the
#: mesh port so the two cannot offer different destinations.
DST_PRESET = "mhws.json"
DST_GAME = "MHWS"


def _retarget_group_attrs(fields, game):
    """Re-encode the group attribute mask for a ``.chain`` target.

    ctc_port builds everything in chain2's vocabulary, because MHWilds was the only
    destination.  MHRS reads ``.chain`` v48, where three of those bits mean
    something else -- ExtraNode, ScaleAnimation and CollisionCharacter are a
    three-cycle between the two formats -- so the mask has to be re-encoded rather
    than carried.  Identity for a chain2 target, so MHWilds is untouched.
    """
    if chain_convert.is_chain2(game):
        return fields, []
    dropped = []
    for key in ("attrFlags", "groupDefaultAttr"):
        if key not in fields:
            continue
        fields[key], gone = chain_convert.translate_group_attr(
            fields[key], True, False)
        dropped.extend(gone)
    return fields, dropped

#: MHW Model Editor's object tags.  Note the key is ``~TYPE`` on the MHWI side and
#: plain ``TYPE`` on the RE side -- the two addons chose differently and mixing them
#: up finds nothing rather than erroring.
CTC_COLLECTION = "MHW_CTC_COLLECTION"
CTC_CHAIN = "MHW_CTC_CHAIN"
CTC_NODE = "MHW_CTC_NODE"
CTC_NODE_FRAME = "MHW_CTC_NODE_FRAME"
CCL_SPHERE = "MHW_CCL_SPHERE"
CCL_CAPSULE = "MHW_CCL_CAPSULE"
CCL_CAPSULE_START = "MHW_CCL_CAPSULE_START"
CCL_CAPSULE_END = "MHW_CCL_CAPSULE_END"
CTC_HEADER = "MHW_CTC_HEADER"

#: RE-Chain-Editor's, for the objects this creates.
RE_GROUP = "RE_CHAIN_CHAINGROUP"
RE_NODE = "RE_CHAIN_NODE"
RE_NODE_FRAME = "RE_CHAIN_NODE_FRAME"
RE_CAPSULE_ROOT = "RE_CHAIN_COLLISION_CAPSULE_ROOT"
RE_CAPSULE_START = "RE_CHAIN_COLLISION_CAPSULE_START"
RE_CAPSULE_END = "RE_CHAIN_COLLISION_CAPSULE_END"

BONE_CONSTRAINT = chain_convert.BONE_CONSTRAINT

#: The ctc chain fields worth carrying into a report, i.e. everything
#: ``ctc_port`` might map or name as dropped.  Read off the property group by name so
#: a field added upstream shows up as "dropped" rather than vanishing.
_CHAIN_FIELDS = tuple(s for s, _d, _f in ctc_port.CHAIN_TO_SETTINGS) + \
    ctc_port.DISCARDED_CHAIN_FIELDS
_NODE_FIELDS = tuple(s for s, _d, _f in ctc_port.NODE_TO_CHAIN2) + \
    ("AngleMode", "CollisionShape")


# ── scene helpers ───────────────────────────────────────────────────────────────

def is_ctc_collection(col):
    """True for a ctc file's **root** collection, the only thing worth porting.

    Not the same test as ``mhwi_port_ops.is_mod3_collection``, and copying that one
    verbatim is the mistake: a ``.mod3`` collection has no ``.mod3``-suffixed
    children, but a ctc one does.  MHW Model Editor names the sub-collection holding
    the chains ``Chain Entries - <file>.ctc``, so a plain ``endswith(".ctc")`` offers
    it as a source too -- and it has neither a header nor the ccl shapes, so picking
    it silently ports half a file.

    The ``~TYPE`` tag is the real marker (and what colours the collection in the
    outliner).  The name is only a fallback for a collection that has lost its tag,
    and even then it must own a header, which is exactly what a ``Chain Entries``
    child does not.
    """
    if col.get("~TYPE") == CTC_COLLECTION:
        return True
    return col.name.endswith(".ctc") and any(
        o.get("~TYPE") == CTC_HEADER for o in col.all_objects)


def _mhwi_typed(objs, tag):
    return [o for o in objs if o.get("~TYPE") == tag]


def _mhwi_child(obj, tag):
    return next((c for c in obj.children if c.get("~TYPE") == tag), None)


def _re_child(obj, tag):
    return next((c for c in obj.children if c.get("TYPE") == tag), None)


def _bound_bone(obj):
    con = obj.constraints.get(BONE_CONSTRAINT) if obj is not None else None
    return (getattr(con, "subtarget", "") or None) if con is not None else None


def _rot3(matrix):
    """A mathutils matrix's rotation as a row-major nested tuple.

    Scale is divided out rather than assumed absent: a ctc node inherits its scale
    from the chain object through a COPY_SCALE constraint, so a user who scaled the
    chain for visibility would otherwise feed a scaled basis into the frame maths.
    """
    m = matrix.to_3x3()
    m.normalize()
    return tuple(tuple(m[r][c] for c in range(3)) for r in range(3))


def _bone_rot(arm_obj, bone_name):
    """A bound bone's world rotation, or None.

    The pose matrix, not the rest matrix: that is what COPY_ROTATION actually copies,
    so this equals the node object's own world rotation without needing the constraint
    evaluated (measured: 1.2e-7 max component difference over 40 nodes).
    """
    pb = arm_obj.pose.bones.get(bone_name) if arm_obj is not None else None
    if pb is None:
        return None
    return _rot3(arm_obj.matrix_world @ pb.matrix)


def _activate(context, obj):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def _select_bones(arm_obj, names):
    """Select exactly *names* in pose mode, active = the first.

    Blender 4.x keeps selection on the Bone, 5.x moved it to the PoseBone; both are
    written, matching what ``re_chain_utils._make_one_chain`` already does.
    """
    bpy.ops.pose.select_all(action='DESELECT')
    for name in names:
        pb = arm_obj.pose.bones.get(name)
        if pb is None:
            continue
        if hasattr(pb, "select"):
            pb.select = True
        else:
            pb.bone.select = True
    first = arm_obj.pose.bones.get(names[0]) if names else None
    if first is not None:
        arm_obj.data.bones.active = first.bone


# ── reading the ctc side ────────────────────────────────────────────────────────

def _node_run(chain_obj):
    """A ctc chain's nodes, head first.

    ctc parents node to node, so the run is found by descent rather than by sorting
    names -- the names are bone names and sort into the wrong order the moment a
    chain crosses a hundred boundary (``MhBone_299`` before ``MhBone_300``).
    """
    out = []
    cur = _mhwi_child(chain_obj, CTC_NODE)
    while cur is not None:
        out.append(cur)
        cur = _mhwi_child(cur, CTC_NODE)
    return out


def read_chains(context, col):
    """Every ctc chain in *col*, as plain data with matrices already captured.

    One ``view_layer.update()`` first, then everything is read -- see the module
    docstring.  Sorted by object name so two runs on the same file produce the same
    output order, which is what makes a port diffable.
    """
    context.view_layer.update()
    chains = []
    for chain_obj in sorted(_mhwi_typed(col.all_objects, CTC_CHAIN),
                            key=lambda o: o.name):
        pg = chain_obj.mhw_ctc_chain
        nodes = []
        for node_obj in _node_run(chain_obj):
            npg = node_obj.mhw_ctc_node
            frame = _mhwi_child(node_obj, CTC_NODE_FRAME)
            nodes.append({
                "bone": _bound_bone(node_obj),
                "values": {f: getattr(npg, f) for f in _NODE_FIELDS
                           if hasattr(npg, f)},
                "frame_world_rot": _rot3(frame.matrix_world) if frame else None,
            })
        chains.append({
            "name": chain_obj.name,
            "values": {f: getattr(pg, f) for f in _CHAIN_FIELDS if hasattr(pg, f)},
            "collision_flags": pg.CollisionAttrFlagValue,
            "chain_flags": pg.ChainAttrFlagValue,
            "nodes": nodes,
        })
    return chains


def read_colliders(col):
    """Every ccl shape in *col*, in metres.

    Offsets and radii come from ``location`` / ``scale`` rather than from
    ``mhw_ccl_collision`` -- the property group is still in centimetres, the object
    transform is not.  See ``ctc_port.NODE_RADIUS_SCALE``.

    A sphere is emitted through ``ctc_port.sphere_as_capsule`` here rather than left
    as a sphere, which is the user's choice of spelling, not a format constraint.
    """
    out = []
    for obj in sorted(_mhwi_typed(col.all_objects, CCL_SPHERE), key=lambda o: o.name):
        bone = _bound_bone(obj)
        shape = ctc_port.sphere_as_capsule(bone, tuple(obj.location), obj.scale[0])
        shape["name"] = obj.name
        shape["from_sphere"] = True
        out.append(shape)

    for obj in sorted(_mhwi_typed(col.all_objects, CCL_CAPSULE), key=lambda o: o.name):
        begin = _mhwi_child(obj, CCL_CAPSULE_START)
        end = _mhwi_child(obj, CCL_CAPSULE_END)
        if begin is None or end is None:
            continue
        # The radius lives on the START child; ccl has no per-end radius at all.
        shape = ctc_port.capsule(_bound_bone(begin), _bound_bone(end),
                                 tuple(begin.location), tuple(end.location),
                                 begin.scale[0])
        shape["name"] = obj.name
        shape["from_sphere"] = False
        out.append(shape)
    return out


# ── bone identity ───────────────────────────────────────────────────────────────

def resolve_bone(name, cross_map):
    """``(target bone name or None, 'base' | 'physics' | 'unknown')``.

    Physics bones keep their name: the model port carries them across unrenamed
    (``mhwi_port_ops.transplant_physics``), precisely so the chain file rebuilt beside
    it can still name them.  Base bones go through the *same* cross-game map the model
    port used -- see the plan doc's §0.1 on why a second, independently built map is
    the one mistake here that no check catches.

    An unknown id is tried against the map anyway before giving up; it is reported
    either way, since it means the source has a bone outside MHWI's own id scheme.
    """
    kind = mhwi_port.classify(name or "")
    if kind == "physics":
        return name, kind
    return cross_map.get(name), kind


def resolve_chains(chains, cross_map, target_bones):
    """Fill in each node's ``target_bone``; return the bindings that failed.

    Returns ``[(chain name, source bone, reason)]`` where reason is ``'unmapped'``
    (no cross-game entry) or ``'missing'`` (named a bone the target rig lacks).
    Both are fatal for the chain they belong to: a node bound to a bone that does not
    exist is dropped by RE-Chain-Editor on import and by the game at load.

    Both also leave ``target_bone`` as **None**, so that one check downstream covers
    them.  The distinction matters for the report but not for buildability, and
    keeping ``'missing'`` truthy is a trap: a physics bone always resolves to its own
    name, so a rig that simply does not have it -- the normal case when a ctc from one
    body part is pointed at a rig ported from another, since MHWI's ids are per-part
    -- would sail past a None check and reach ``chain_from_bone`` with nothing
    selectable, which it answers with a console error rather than a return value.
    """
    bad = []
    for chain in chains:
        for node in chain["nodes"]:
            target, _kind = resolve_bone(node["bone"], cross_map)
            if target is None:
                bad.append((chain["name"], node["bone"], "unmapped"))
            elif target not in target_bones:
                bad.append((chain["name"], node["bone"], "missing"))
                target = None
            node["target_bone"] = target
    return bad


def resolve_colliders(colliders, cross_map, target_bones):
    """As ``resolve_chains``, for the two bones of every collision shape.

    Same rule: an unusable end is None, so ``build`` skips the shape rather than
    handing ``collision_from_bone`` a selection it cannot make.
    """
    bad = []
    for shape in colliders:
        for end in ("begin", "end"):
            src = shape[f"{end}_bone"]
            target, _kind = resolve_bone(src, cross_map)
            if target is None:
                bad.append((shape["name"], src, "unmapped"))
            elif target not in target_bones:
                bad.append((shape["name"], src, "missing"))
                target = None
            shape[f"{end}_target"] = target
    return bad


# ── building the chain2 side ────────────────────────────────────────────────────

def _new_of_type(col, before_names, tag):
    return next((o for o in col.all_objects
                 if o.name not in before_names and o.get("TYPE") == tag), None)


def _group_nodes(group_obj):
    """A built chain group's node objects, head first (parented in a run, as ctc's)."""
    out = []
    cur = _re_child(group_obj, RE_NODE)
    while cur is not None:
        out.append(cur)
        cur = _re_child(cur, RE_NODE)
    return out


def _write_pg(pg, fields):
    """Set what can be set, collect what cannot.  Never raises on one bad field."""
    missed = []
    for key, value in fields.items():
        try:
            setattr(pg, key, value)
        except (AttributeError, TypeError, ValueError):
            missed.append(key)
    return missed


def _apply_group(group_obj, chain, report, flag_mode, game=DST_GAME):
    """Write the group defaults and the routed flags onto one built chain group.

    Easy to leave out, and it fails quietly when you do: ``chain_from_bone`` gives
    every group RE-Chain-Editor's own ``Chain2GroupData`` defaults, which are close
    enough to the intended ones (measured 99339 against 99331) that the result looks
    authored rather than untouched.  What is actually missing is the whole
    ctc-to-chain2 flag routing on the group side -- and per the user's decision the
    group and the settings must carry the *same* routed bits, or the group's own
    default flattens the per-chain difference the settings just recorded.
    """
    fields, dropped = _retarget_group_attrs(
        ctc_port.build_group(chain["collision_flags"], chain["chain_flags"],
                             flag_mode),
        game)
    report["dropped_flags"].update(dropped)
    missed = _write_pg(group_obj.re_chain_chaingroup, fields)
    report["unwritable_group_fields"].update(missed)


def _apply_nodes(arm_obj, group_obj, chain, report):
    """Write the translated node parameters and angle-limit frames onto one group.

    The node order is **verified, not assumed**: ``chain_from_bone`` builds its run
    from ``selected_pose_bones``, which Blender returns in armature order.  For a
    chain grafted by ``transplant_physics`` that happens to be parent-before-child and
    therefore right, but "happens to be" is not a property to bind a silent failure to.
    """
    built = _group_nodes(group_obj)
    if len(built) != len(chain["nodes"]):
        report["node_count_mismatch"].append(
            (chain["name"], len(chain["nodes"]), len(built)))
        return

    for node_obj, spec in zip(built, chain["nodes"]):
        if _bound_bone(node_obj) != spec["target_bone"]:
            report["node_order_mismatch"].append(
                (chain["name"], spec["target_bone"], _bound_bone(node_obj)))
            continue

        fields, unmapped = ctc_port.build_node(spec["values"])
        for field, value in unmapped:
            report["unmapped_enums"].append((chain["name"], field, value))
        missed = _write_pg(node_obj.re_chain_chainnode, fields)
        report["unwritable_node_fields"].update(missed)

        _apply_frame(arm_obj, node_obj, spec, report)


def _apply_frame(arm_obj, node_obj, spec, report):
    """Carry one node's angle-limit direction across.

    ``frame_local_new = node_dst_rot^-1 @ frame_world_src`` -- the whole reason this
    is not left to ``chain_from_bone`` is that the builder reproduces the *default*
    direction only, and authors adjust away from it (measured on a hand-tuned MHWilds
    chain: 45 of 224 frames deviate, up to 66.6 degrees).
    """
    frame = _re_child(node_obj, RE_NODE_FRAME)
    src_rot = spec.get("frame_world_rot")
    if frame is None or src_rot is None:
        return
    dst_rot = _bone_rot(arm_obj, spec["target_bone"])
    if dst_rot is None:
        return
    local = relocalise_frame(dst_rot, src_rot)
    saved = frame.rotation_mode
    frame.rotation_mode = 'QUATERNION'
    frame.rotation_quaternion = Matrix(local).to_quaternion()
    frame.rotation_mode = saved
    report["frames_set"] += 1


def _build_collider(context, arm_obj, col, shape, report):
    """One ccl shape as a chain2 collision capsule.

    Always a capsule, including for a sphere: ``collision_from_bone`` with a single
    bone selected and shape CAPSULE produces ``startBone == endBone``, which is
    exactly the degenerate capsule the user chose as a sphere's spelling.

    The two endpoint bindings are **rewritten afterwards**.  The operator takes its
    ends from ``selected_pose_bones[0]`` and ``[1]``, and that list is in armature
    order -- so for a capsule whose two bones happen to be ordered the other way round
    on the rig, begin and end come out swapped.  A swapped capsule is geometrically
    identical only when both offsets and radii match, which is exactly the case that
    does not need fixing; every other case is silently wrong.
    """
    begin, end = shape["begin_target"], shape["end_target"]
    names = [begin] if begin == end else [begin, end]
    before = {o.name for o in col.all_objects}

    context.scene.re_chain_toolpanel.collisionShape = 'CAPSULE'
    _select_bones(arm_obj, names)
    if bpy.ops.re_chain.collision_from_bone() != {'FINISHED'}:
        report["collider_failed"].append(shape["name"])
        return None

    root = _new_of_type(col, before, RE_CAPSULE_ROOT)
    if root is None:
        report["collider_failed"].append(shape["name"])
        return None

    start_obj = _re_child(root, RE_CAPSULE_START)
    end_obj = _re_child(root, RE_CAPSULE_END)
    for obj, bone in ((start_obj, begin), (end_obj, end)):
        con = obj.constraints.get(BONE_CONSTRAINT) if obj is not None else None
        if con is not None:
            con.target = arm_obj
            con.subtarget = bone

    pg = root.re_chain_chaincollision
    # Order matters: the shape enum drives which of the radius setters touches which
    # child, so it goes first.  Offsets and radii are written through the property
    # group rather than onto the children, because its update callbacks are what move
    # them -- setting child.location directly leaves the group disagreeing with the
    # scene, and export reads the group.
    missed = _write_pg(pg, {
        "chainCollisionShape": shape["shape"],
        "radius": shape["begin_radius"],
        "endRadius": shape["end_radius"],
        "collisionOffset": shape["begin_offset"],
        "endCollisionOffset": shape["end_offset"],
        **ctc_port.COLLIDER_DEFAULTS,
    })
    report["unwritable_collider_fields"].update(missed)

    # The operator names a capsule after whatever bones it picked; rename so the
    # outliner shows the binding this actually has.
    stem = root.name.split(" - ")[0]
    root.name = f"{stem} - {begin} > {end}"
    return root


def _new_report():
    return {
        "settings": 0, "groups": 0, "nodes": 0, "colliders": 0, "frames_set": 0,
        "chains_failed": [], "collider_failed": [],
        "node_count_mismatch": [], "node_order_mismatch": [],
        "unmapped_enums": [], "dropped_flags": set(), "dropped_fields": set(),
        "deferred_flags": set(),
        "unwritable_node_fields": set(), "unwritable_collider_fields": set(),
        "unwritable_settings_fields": set(), "unwritable_group_fields": set(),
    }


def build(context, arm_obj, chains, colliders, stem, flag_mode="ALL",
          game=DST_GAME):
    """Create one chain2 collection holding *chains* and *colliders*.

    Returns ``(collection, report)``, or ``(None, report)`` if the collection could
    not be made.  Settings are clustered first so the whole build is one pass per
    cluster: create the settings object, then every chain that shares it -- which is
    also what makes ``chain_from_bone`` parent each group to the right settings,
    since ``create_chain_settings`` leaves the new object in
    ``toolpanel.chainSetting``.
    """
    report = _new_report()
    toolpanel = getattr(context.scene, "re_chain_toolpanel", None)
    if toolpanel is None:
        return None, report

    config = re_chain_utils.REChainConfig(
        chain_format=chain_convert.CHAIN_EXT_BY_GAME[game],
        chain_file_type="chain2" if chain_convert.is_chain2(game) else "chain",
        auto_create_collection=True,
        collection_name=stem,
        tuning=ctc_port.HEADER_DEFAULTS,
    )
    col, _header, error = re_chain_utils._auto_create_chain_collection(config)
    if error or col is None:
        return None, report

    # Per chain, translate first: the settings fields are the clustering key, so they
    # have to exist before anything is created.
    per_chain = []
    for chain in chains:
        fields, chain_report = ctc_port.build_settings(
            chain["values"], chain["collision_flags"], chain["chain_flags"],
            flag_mode)
        # The one field the port must not carry a second copy of.
        fields["colliderFilterInfoPath"] = \
            chain_convert.COLLIDER_FILTER_BY_GAME.get(game, "")
        fields, attr_dropped = _retarget_group_attrs(fields, game)
        report["dropped_flags"].update(attr_dropped)
        report["dropped_flags"].update(chain_report["dropped_flags"])
        report["deferred_flags"].update(chain_report["deferred_flags"])
        report["dropped_fields"].update(chain_report["dropped_fields"])
        per_chain.append((chain["name"], fields))
    clusters = ctc_port.cluster_settings(per_chain)
    by_name = {c["name"]: c for c in chains}

    saved = (toolpanel.chainCollection, toolpanel.chainFileType,
             getattr(toolpanel, "experimentalPoseModeOptions", False),
             toolpanel.collisionShape)
    toolpanel.chainCollection = col
    toolpanel.chainFileType = "chain2" if chain_convert.is_chain2(game) else "chain"

    _activate(context, arm_obj)
    bpy.ops.object.mode_set(mode='POSE')

    # alignChains() is O(chains x nodes^2) with a depsgraph update inside the inner
    # loop and RE-Chain-Editor calls it after *every* chain and collider.  See
    # memory note project_chain_import_perf_trap: the same shape once made a chain
    # import take 78 minutes.  Patched out for the build, restored and run once.
    patches = re_chain_utils._patch_chain_cleanup(disable=True)
    try:
        for fields, chain_names in clusters:
            before = {o.name for o in col.all_objects}
            if bpy.ops.re_chain.create_chain_settings() != {'FINISHED'}:
                report["chains_failed"].extend(chain_names)
                continue
            settings_obj = re_chain_utils._find_new_settings(col, before)
            if settings_obj is not None:
                report["unwritable_settings_fields"].update(
                    re_chain_utils._apply_params_to_cs(settings_obj, fields))
                report["settings"] += 1

            for name in chain_names:
                chain = by_name[name]
                path = [n["target_bone"] for n in chain["nodes"]]
                if not all(path):
                    report["chains_failed"].append(name)
                    continue
                before_objs = {o.name for o in col.all_objects}
                if not re_chain_utils._make_one_chain(arm_obj, toolpanel, path):
                    report["chains_failed"].append(name)
                    continue
                group = _new_of_type(col, before_objs, RE_GROUP)
                if group is None:
                    report["chains_failed"].append(name)
                    continue
                report["groups"] += 1
                report["nodes"] += len(chain["nodes"])
                _apply_group(group, chain, report, flag_mode, game)
                _apply_nodes(arm_obj, group, chain, report)

        for shape in colliders:
            if not (shape["begin_target"] and shape["end_target"]):
                report["collider_failed"].append(shape["name"])
                continue
            if _build_collider(context, arm_obj, col, shape, report) is not None:
                report["colliders"] += 1
    finally:
        re_chain_utils._patch_chain_cleanup(disable=False)
        if patches:
            _mod, align, color = patches[0]
            align()
            color(arm_obj)
        (toolpanel.chainCollection, toolpanel.chainFileType,
         toolpanel.experimentalPoseModeOptions, toolpanel.collisionShape) = saved
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

    return col, report


# ── operator ────────────────────────────────────────────────────────────────────

_ctc_items_cache = []
_arm_items_cache = []


def _ctc_items(self, context):
    """EnumProperty items must outlive the call: Blender's C side keeps the pointers."""
    _ctc_items_cache.clear()
    _ctc_items_cache.extend(
        (c.name, c.name, "") for c in bpy.data.collections if is_ctc_collection(c))
    if not _ctc_items_cache:
        _ctc_items_cache.append(("NONE", T("core.ctc_port_ops.no_ctc_collection"), ""))
    return _ctc_items_cache


def _armature_items(self, context):
    _arm_items_cache.clear()
    _arm_items_cache.extend(
        (o.name, o.name, "") for o in bpy.data.objects if o.type == 'ARMATURE')
    if not _arm_items_cache:
        _arm_items_cache.append(("NONE", T("core.ctc_port_ops.no_armature"), ""))
    return _arm_items_cache


#: Persistent backing, same rule as the two caches above: Blender keeps the string
#: pointers, so the callback must not hand back a list it just built.
_target_item_cache = []

_TARGET_LABELS = {
    "MHWS": ("core.ctc_port_ops.target_mhws", "core.ctc_port_ops.target_mhws_desc"),
    "MHRS": ("core.ctc_port_ops.target_mhrs", "core.ctc_port_ops.target_mhrs_desc"),
}


def _target_game_items(self=None, context=None):
    _target_item_cache.clear()
    for game in mhwi_port.PORT_TARGET_ORDER:
        label, desc = _TARGET_LABELS[game]
        _target_item_cache.append((game, T(label), T(desc)))
    return _target_item_cache


#: Game codes this dialog has to name in a sentence, including the one that is only
#: ever a *source* -- detect_armature_game can return MHWI, and "MHWI" untranslated
#: in the middle of a Chinese sentence is the thing the i18n table exists to avoid.
_GAME_LABEL_KEYS = {
    "MHWS": "core.ctc_port_ops.target_mhws",
    "MHRS": "core.ctc_port_ops.target_mhrs",
    "MHWI": "core.ctc_port_ops.game_mhwi",
}


def _game_label(game_code):
    key = _GAME_LABEL_KEYS.get(game_code)
    return T(key) if key else (game_code or "?")


#: ``{(name, bone count): game_code or None}``.
#:
#: Needed because the caller is ``draw()``, which Blender re-runs on every redraw of
#: the dialog -- including while the mouse simply moves over it -- and one detection
#: loads *every* shipped preset and tests all 47 standard slots against the rig.
#: Uncached that is tens of preset loads per frame.
#:
#: Keyed on the bone count as well as the name so an armature edited between two
#: openings of the dialog is re-tested rather than answered from a stale entry; a
#: rename alone also misses, which is the cheap direction to be wrong in.
_detect_cache = {}


def detect_armature_game(arm_obj):
    """Which game's rig *arm_obj* looks like, by bone names, or ``None``.

    The same >= 95% standard-slot coverage test the bone tools already use to
    auto-pick a preset -- asking the armature instead of telling the user what to
    pick.  ``None`` means no preset claimed it, which for this dialog is the
    ordinary case of a hand-built or partial rig, not an error.

    Returns a ``game_code``, so an MHWI rig comes back as ``"MHWI"`` and can be
    called out specifically: picking the *source* rig here is the mistake the old
    static hint existed to prevent, and it is exactly the one this can detect.
    """
    if arm_obj is None or arm_obj.type != 'ARMATURE':
        return None
    key = (arm_obj.name, len(arm_obj.data.bones))
    if key in _detect_cache:
        return _detect_cache[key]

    from .bone_mapper import BoneMapManager, auto_detect_preset
    game = None
    try:
        preset = auto_detect_preset(arm_obj, False)
        if preset:
            mgr = BoneMapManager()
            if mgr.load_preset(preset):
                game = mgr.preset_info.get("game_code")
    except Exception:
        game = None
    _detect_cache[key] = game
    return game


def run_port(context, col, arm, target_game, migrate_flags='BASIC'):
    """Rebuild one MHWI ``.ctc`` collection against *arm*.  The port, minus the UI.

    Split out of the operator for the batch path, which needs to hand in the rig the
    model port just built rather than pick one from an enum.  Returns a dict;
    ``{"error": <T key>}`` when the inputs cannot be ported.
    """
    if col is None or arm is None or arm.type != 'ARMATURE':
        return {"error": "core.ctc_port_ops.pick_inputs"}
    if getattr(context.scene, "re_chain_toolpanel", None) is None:
        return {"error": "core.ctc_port_ops.need_chain_editor"}

    cross = build_cross_game_map(
        SRC_PRESET, mhwi_port.port_target(target_game)["preset"])
    if cross is None:
        return {"error": "core.ctc_port_ops.preset_load_failed"}

    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    chains = read_chains(context, col)
    colliders = read_colliders(col)
    if not chains and not colliders:
        return {"error": "core.ctc_port_ops.nothing_to_port"}

    target_bones = set(arm.data.bones.keys())
    bad = (resolve_chains(chains, cross, target_bones)
           + resolve_colliders(colliders, cross, target_bones))

    stem = chain_convert.chain_stem(col.name)
    if stem.endswith(".ctc"):
        stem = stem[:-4]
    out, report = build(context, arm, chains, colliders,
                        f"{stem}_{target_game}", migrate_flags, target_game)
    if out is None:
        return {"error": "core.ctc_port_ops.build_failed"}
    return {"error": None, "collection": out, "report": report, "bad": bad}


@gate
class MHWI_OT_PortPhysicsToMHWS(bpy.types.Operator):
    bl_idname = "mhwi.port_physics_to_mhws"
    bl_label = "MHWI Physics Port"
    #: No 'UNDO', for the same reason as the model port: this creates objects through
    #: operators and bpy.data, so a redo-panel re-run would build a second chain2
    #: rather than revise the first.
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("core.ctc_port_ops.desc")

    source_collection: bpy.props.EnumProperty(name="Source", items=_ctc_items)
    target_armature: bpy.props.EnumProperty(name="Armature", items=_armature_items)
    target_game: bpy.props.EnumProperty(
        name="Target", items=_target_game_items, default=0)
    migrate_flags: bpy.props.EnumProperty(
        name="Flags",
        items=lambda self, ctx: [
            ('BASIC', T("core.ctc_port_ops.flags_basic"),
             T("core.ctc_port_ops.flags_basic_desc")),
            ('ALL', T("core.ctc_port_ops.flags_all"),
             T("core.ctc_port_ops.flags_all_desc"))],
        default=0)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=430)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection",
                    text=T("core.ctc_port_ops.source_collection"))
        layout.prop(self, "target_armature",
                    text=T("core.ctc_port_ops.target_armature"))
        layout.prop(self, "target_game", text=T("core.ctc_port_ops.target_label"))
        layout.prop(self, "migrate_flags",
                    text=T("core.ctc_port_ops.migrate_flags"))

        # What the armature actually is, rather than a note about what to pick.
        # The old hint named MHWilds, which stopped being true once the port grew
        # a target -- and it could only ever describe the mistake, never catch it.
        box = layout.box()
        arm = bpy.data.objects.get(self.target_armature)
        detected = detect_armature_game(arm)
        if detected is None:
            box.label(text=T("core.ctc_port_ops.detect_unknown"), icon='QUESTION')
        elif detected == "MHWI":
            # The one specific mistake worth naming: this is the rig the .ctc came
            # off, so its bones are the *source* names and nothing would remap.
            box.label(text=T("core.ctc_port_ops.detect_is_source"), icon='ERROR')
        elif detected == self.target_game:
            box.label(text=T("core.ctc_port_ops.detect_ok").format(
                game=_game_label(detected)), icon='CHECKMARK')
        else:
            box.label(text=T("core.ctc_port_ops.detect_mismatch").format(
                found=_game_label(detected), chosen=_game_label(self.target_game)),
                icon='ERROR')

    def execute(self, context):
        result = run_port(context, bpy.data.collections.get(self.source_collection),
                          bpy.data.objects.get(self.target_armature),
                          self.target_game, self.migrate_flags)
        if result["error"]:
            self.report({'ERROR'}, T(result["error"]))
            return {'CANCELLED'}
        return self._report(result["collection"], result["report"], result["bad"])

    def _report(self, out, report, bad):
        parts = [T("core.ctc_port_ops.stat").format(
            name=out.name, settings=report["settings"], groups=report["groups"],
            nodes=report["nodes"], colliders=report["colliders"],
            frames=report["frames_set"])]
        warn = False

        if bad:
            warn = True
            names = ", ".join(sorted({b for _o, b, _r in bad})[:6])
            parts.append(T("core.ctc_port_ops.unresolved_bones").format(
                n=len(bad), names=names))
        for key, msg in (("chains_failed", "core.ctc_port_ops.chains_failed"),
                         ("collider_failed", "core.ctc_port_ops.colliders_failed")):
            if report[key]:
                warn = True
                parts.append(T(msg).format(n=len(report[key])))
        if report["node_order_mismatch"] or report["node_count_mismatch"]:
            warn = True
            parts.append(T("core.ctc_port_ops.node_mismatch").format(
                n=len(report["node_order_mismatch"])
                + len(report["node_count_mismatch"])))
        if report["unmapped_enums"]:
            warn = True
            parts.append(T("core.ctc_port_ops.unmapped_enums").format(
                n=len(report["unmapped_enums"])))
        if report["dropped_fields"] or report["dropped_flags"]:
            names = ", ".join(sorted(report["dropped_fields"]
                                     | report["dropped_flags"])[:8])
            parts.append(T("core.ctc_port_ops.dropped").format(names=names))
        if report["deferred_flags"]:
            parts.append(T("core.ctc_port_ops.deferred_flags").format(
                n=len(report["deferred_flags"])))

        self.report({'WARNING'} if warn else {'INFO'}, "  ".join(parts))
        return {'FINISHED'}


classes = [MHWI_OT_PortPhysicsToMHWS]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
