"""Apply modifiers to a mesh that has shape keys.

Blender refuses to apply a modifier while shape keys exist, and the usual
workaround is to duplicate the object once per key, bake each duplicate down to
that key, apply the modifiers, and pull the results back with
``bpy.ops.object.join_shapes``.  That works but costs N+1 object copies and
N+1 modifier-stack applications through the operator layer.

The depsgraph already offers what those duplicates are for: with
``show_only_shape_key`` the mesh evaluates *at* the active key's shape, so
reading ``obj.evaluated_get(dg)`` once per key gives exactly the same
per-key result with no duplication and no operator calls.  Measured on a
13700-vertex mesh with 48 keys: 0.48s -> 0.12s for an armature modifier, and
46.5s -> 3.8s once a Subsurf is in the stack.

Correctness was checked against the semantics people actually expect — bake
the key into the mesh first, *then* apply the modifier — using an independent
code path (``shape_key_clear`` + ``modifier_apply``).  Every one of the 48 keys
came back bit-identical, including with non-affine modifiers (Smooth, Cast) in
the stack.  That is not a coincidence: both routes feed the modifier the same
input mesh.

The one thing that cannot be preserved is intermediate slider values.  A shape
key stores a linear offset, so dialling the result to 0.5 interpolates between
two modifier outputs instead of running the modifier on a half-mixed shape.
For affine deformers (plain linear-blend-skinning armatures) these are equal;
for Smooth/Cast/Shrinkwrap they are not.  That is a property of shape keys, not
of this implementation — every cross-shape-key approach shares it.
"""

import numpy as np

#: Modifier types whose output topology depends on vertex positions, so each
#: shape key would produce a different vertex count or ordering.  Decimate is
#: the nasty one: the counts often match by luck, `join_shapes` accepts them,
#: and the keys come out silently scrambled.
TOPOLOGY_UNSTABLE = {
    'DECIMATE', 'WELD', 'REMESH', 'BOOLEAN', 'MASK', 'SKIN', 'BUILD', 'EXPLODE',
}


def shape_key_mix(obj):
    """The mesh's vertex positions with only the shape keys applied.

    Deliberately not the evaluated mesh: custom split normals live in the
    *undeformed* mesh, so the armature's pose must stay out of it — otherwise a
    posed character's normals get treated as if the pose were part of the shape.

    Relative keys are ``basis + sum(value * (key - relative_key))``, each term
    optionally masked by the key's own vertex group.  Returns None for absolute
    keys (``use_relative`` off), which have no closed form here.
    """
    me = obj.data
    sk = me.shape_keys
    n = len(me.vertices)
    if sk is None:
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        return co.reshape(-1, 3).astype(np.float64)
    if not sk.use_relative:
        return None

    def block_co(kb):
        a = np.empty(n * 3, np.float32)
        kb.data.foreach_get("co", a)
        return a.reshape(-1, 3).astype(np.float64)

    ref = sk.reference_key
    # The accumulator has to be a separate array from the cached basis: sharing
    # one object means ``out += delta`` also rewrites the basis, and from the
    # second key on the deltas are measured against the running total instead —
    # the whole sum collapses to roughly its last term.  A single key hides this.
    cache = {ref.name: block_co(ref)}
    out = cache[ref.name].copy()
    for kb in sk.key_blocks:
        if kb == ref or kb.mute or kb.value == 0.0:
            continue
        rel = kb.relative_key or ref
        if rel.name not in cache:
            cache[rel.name] = block_co(rel)
        delta = (block_co(kb) - cache[rel.name]) * kb.value
        if kb.vertex_group:
            w = _vgroup_weights(obj, kb.vertex_group)
            if w is not None:
                delta *= w[:, None]
        out += delta
    return out


def _vgroup_weights(obj, name):
    vg = obj.vertex_groups.get(name)
    if vg is None:
        return None
    idx = vg.index
    w = np.zeros(len(obj.data.vertices))
    for i, v in enumerate(obj.data.vertices):
        for g in v.groups:
            if g.group == idx:
                w[i] = g.weight
                break
    return w


def target_modifiers(obj):
    """Modifiers that will be applied — the viewport-enabled ones, matching
    what the user sees."""
    return [m for m in obj.modifiers if m.show_viewport]


def check(obj):
    """Pre-flight. Returns (ok, message_key, format_kwargs).

    Two gates: a static scan for modifier types that cannot survive the round
    trip, then an actual evaluation of the first and last key to catch anything
    the list misses.
    """
    me = obj.data
    if not me.shape_keys or len(me.shape_keys.key_blocks) < 2:
        return False, "core.shapekey_utils.err_no_shape_keys", {}

    mods = target_modifiers(obj)
    if not mods:
        return False, "core.shapekey_utils.err_no_modifiers", {}

    risky = [m.name for m in mods
             if m.type in TOPOLOGY_UNSTABLE
             or (m.type == 'MIRROR' and getattr(m, 'use_mirror_merge', False))]
    if risky:
        return False, "core.shapekey_utils.err_unstable_modifier", {"names": "、".join(risky)}

    # Envelope weights are a function of the vertex's rest position, which
    # differs per key, so the deformation stops being affine in the shape
    if any(m.type == 'ARMATURE' and getattr(m, 'use_bone_envelopes', False) for m in mods):
        return False, "core.shapekey_utils.err_bone_envelopes", {}

    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    kbs = me.shape_keys.key_blocks
    prev_only, prev_idx = obj.show_only_shape_key, obj.active_shape_key_index
    obj.show_only_shape_key = True
    counts = []
    for i in (0, len(kbs) - 1):
        obj.active_shape_key_index = i
        dg.update()
        counts.append(len(obj.evaluated_get(dg).data.vertices))
    obj.show_only_shape_key, obj.active_shape_key_index = prev_only, prev_idx
    if counts[0] != counts[1]:
        return False, "core.shapekey_utils.err_vertex_count", {"a": counts[0], "b": counts[1]}
    return True, None, {}


def apply_modifiers_keep_shape_keys(obj):
    """Apply the viewport-enabled modifiers, rebuilding the shape keys on top of
    the result.  Returns (modifier count, key count, vertex count).

    Call :func:`check` first.  The object keeps its identity — only ``obj.data``
    is swapped — so drivers, constraints and parenting survive.
    """
    import bpy

    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.data
    kbs = me.shape_keys.key_blocks
    meta = [(kb.name, kb.value, kb.mute, kb.slider_min, kb.slider_max,
             kb.vertex_group, kb.relative_key.name if kb.relative_key else None)
            for kb in kbs]
    mod_names = [m.name for m in target_modifiers(obj)]

    prev_only, prev_idx = obj.show_only_shape_key, obj.active_shape_key_index
    obj.show_only_shape_key = True
    coords = []
    for i in range(len(kbs)):
        obj.active_shape_key_index = i
        dg.update()
        ev_me = obj.evaluated_get(dg).data
        buf = np.empty(len(ev_me.vertices) * 3, np.float32)
        ev_me.vertices.foreach_get("co", buf)
        coords.append(buf)

    obj.active_shape_key_index = 0
    dg.update()
    new_me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.show_only_shape_key, obj.active_shape_key_index = prev_only, prev_idx

    nv = len(new_me.vertices)
    if any(len(c) // 3 != nv for c in coords):
        bpy.data.meshes.remove(new_me)
        raise RuntimeError("vertex count changed between shape keys")

    old_me = obj.data
    new_me.name = old_me.name
    obj.data = new_me
    for name in mod_names:
        mod = obj.modifiers.get(name)
        if mod:
            obj.modifiers.remove(mod)

    for i, (name, value, mute, lo, hi, vgroup, _rel) in enumerate(meta):
        kb = obj.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set("co", coords[i])
        kb.value, kb.mute = value, mute
        kb.slider_min, kb.slider_max = lo, hi
        if vgroup:
            kb.vertex_group = vgroup
    # relative_key can only be wired once every block exists
    blocks = obj.data.shape_keys.key_blocks
    for name, _v, _m, _lo, _hi, _vg, rel in meta:
        if rel and rel in blocks:
            blocks[name].relative_key = blocks[rel]

    if old_me.users == 0:
        bpy.data.meshes.remove(old_me)
    obj.data.update()
    return len(mod_names), len(meta), nv
