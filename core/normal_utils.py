"""Custom split normal tools for face meshes.

Why a cylinder
--------------
Reverse-engineering the shipped face meshes (MHWS `face`, MHWI `f_face002`)
shows the custom split normals are not the mesh's own smooth normals and not a
transfer from a modelled proxy head.  Over the frontal region they are, to
within one degree, the horizontal radial direction from the vertical axis
through the object's local origin — a mathematically exact cylinder.  Nose,
lips and eye sockets vanish from the shading entirely, which is the point: a
cylindrical field gives a purely left-right light falloff with no nose shadow,
and it stays stable when the head tilts.

Outside that region (ears, back of the skull, the neck cap) the mesh keeps its
own angle-weighted smooth normals bit-exact, and the mask is a hard per-face
selection with no feathering.  The front/side transition is not painted: it
falls out of averaging the two fields at the shared boundary vertices, weighted
by corner angle, which makes it exactly one vertex wide.  Reproducing a shipped
head this way lands at 0.57 degrees p90 across the skin.

The mask cannot be derived — an angle threshold, the vertex colour layers and a
frontal-cone isoline were all measured against the shipped meshes and all fail
(the isoline scores well per-loop but cuts across edge loops, so the boundary
comes out visibly jagged).  It has to be a face selection.

Resetting
---------
The game will not take a mesh with welded seams, so a body ships cut into many
pieces: split vertices, sharp edges and separate objects along every seam.
`reset_normals` shades that back as if it were one uncut surface — it gathers
the selected objects into world space, groups every corner by *position*, and
gives each group the angle-weighted average of the face normals meeting there.
No shading groups, no sharp-edge splits, no per-vertex fans: the split is
ignored at calculation time and left completely intact in the mesh, because the
answer is written as custom split normals, which override sharp edges for
shading without removing them.

The one thing to know is that averaging across a position is unconditional by
design, so two coincident surfaces facing opposite ways (eyelash cards) cancel
out.  Those positions are detected rather than silently emitted as noise, and
`angle_limit` below 180 is the escape hatch.
"""

import numpy as np


# ── mesh readback ──────────────────────────────────────────────────────────

def mesh_arrays(me):
    """(vertex coords, loop→vertex, poly loop_start, poly loop_total)."""
    nv, nl, npo = len(me.vertices), len(me.loops), len(me.polygons)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    lv = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(npo, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npo, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return co.reshape(-1, 3).astype(np.float64), lv, ls, lt


def corner_normals(me):
    a = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", a)
    return a.reshape(-1, 3).astype(np.float64)


def corner_angles(co, lv, ls, lt):
    """Per-loop corner angle — the weight Blender and the DCCs use for vertex
    normals.  Everything here weights by angle, never by area: the shipped
    meshes' untouched regions match angle-weighted normals to a median of
    0.00 degrees, and area-weighted to 2.48."""
    nl = len(lv)
    lface = np.repeat(np.arange(len(ls)), lt)
    start = ls[lface]
    total = lt[lface]
    k = np.arange(nl) - start
    nxt = start + (k + 1) % total
    prv = start + (k - 1) % total
    here = co[lv]
    a = co[lv[prv]] - here
    b = co[lv[nxt]] - here
    la = np.linalg.norm(a, axis=1, keepdims=True)
    lb = np.linalg.norm(b, axis=1, keepdims=True)
    ok = (la[:, 0] > 1e-12) & (lb[:, 0] > 1e-12)
    a = a / np.maximum(la, 1e-12)
    b = b / np.maximum(lb, 1e-12)
    ang = np.arccos(np.clip((a * b).sum(1), -1.0, 1.0))
    ang[~ok] = 0.0
    return ang


# ── vector helpers ─────────────────────────────────────────────────────────

def normalize(v, eps=1e-12):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), eps)


def slerp(a, b, w):
    """Great-circle interpolation; w=0 gives a, w=1 gives b.  Falls back to a
    straight pick when the two are collinear (including antipodal, where the
    arc is undefined)."""
    dot = np.clip((a * b).sum(1), -1.0, 1.0)
    om = np.arccos(dot)
    s = np.sin(om)
    degen = s < 1e-6
    om = om[:, None]
    w = w[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (np.sin((1.0 - w) * om) * a + np.sin(w * om) * b) / np.maximum(s[:, None], 1e-9)
    out = np.where(degen[:, None], np.where(w > 0.5, b, a), out)
    return normalize(out)


# ── treating a cut-up mesh as one surface ──────────────────────────────────

def face_normals(co, lv, ls, lt):
    """Unit polygon normal per face, by Newell's method.

    Computed from the geometry rather than read back from ``me.polygons`` so the
    caller can hand in world-space coordinates for several objects at once.  The
    sum of ``p_i x p_{i+1}`` around the loop is twice the polygon's area vector,
    which is well behaved on n-gons and on slivers where a single cross product
    would be noise.
    """
    nl = len(lv)
    lface = np.repeat(np.arange(len(ls)), lt)
    start = ls[lface]
    total = lt[lface]
    k = np.arange(nl) - start
    nxt = start + (k + 1) % total
    n = np.zeros((len(ls), 3))
    np.add.at(n, lface, np.cross(co[lv], co[lv[nxt]]))
    return normalize(n)


# self plus half of the 26 neighbours, so every neighbouring pair of cells is
# visited exactly once
_HALF_NEIGHBOURS = (
    (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
    (1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, 1, -1),
    (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1),
)


def position_clusters(co, distance):
    """Group vertices by position: two vertices land in the same cluster when
    they are within ``distance`` of each other.  Returns (cluster id per vertex,
    cluster count).

    A plain rounded grid key is not enough — two points a hair apart can still
    straddle a cell boundary and never meet — so this walks the 3x3x3
    neighbourhood and tests the real distance, the way YAVNE's merge does.  The
    exact duplicates that a game mesh's cuts produce are collapsed first, which
    is what keeps the Python part small on a 50k-vertex mesh.
    """
    n = len(co)
    if n == 0:
        return np.zeros(0, np.int64), 0

    uniq, inv = np.unique(co, axis=0, return_inverse=True)
    inv = inv.reshape(-1).astype(np.int64)
    if distance <= 0.0:
        return inv, len(uniq)

    m = len(uniq)
    parent = list(range(m))

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    cells = {}
    for i, key in enumerate(map(tuple, np.floor(uniq / distance).astype(np.int64).tolist())):
        cells.setdefault(key, []).append(i)

    d2 = distance * distance
    for key, members in cells.items():
        for off in _HALF_NEIGHBOURS:
            if off == (0, 0, 0):
                for a in range(len(members)):
                    for b in range(a + 1, len(members)):
                        i, j = members[a], members[b]
                        if ((uniq[i] - uniq[j]) ** 2).sum() <= d2:
                            union(i, j)
                continue
            other = cells.get((key[0] + off[0], key[1] + off[1], key[2] + off[2]))
            if not other:
                continue
            for i in members:
                for j in other:
                    if ((uniq[i] - uniq[j]) ** 2).sum() <= d2:
                        union(i, j)

    roots = np.array([find(i) for i in range(m)], np.int64)
    _, cid = np.unique(roots, return_inverse=True)
    return cid.reshape(-1).astype(np.int64)[inv], int(cid.max()) + 1


def integral_normals(co, lv, ls, lt, distance=1e-5, angle_limit=180.0,
                     face_flip=None):
    """Corner normals computed as if every coincident vertex were a single one.

    This is the whole point of the reset: the game will not accept a welded
    mesh, so a body is shipped cut into many pieces with sharp edges and split
    vertices along every seam.  Shading it as one surface means ignoring that
    structure at *calculation* time — no shading groups, no sharp-edge splits,
    no per-vertex fans — while leaving it untouched in the mesh.  Every corner
    at a shared position gets the same normal, the angle-weighted average of the
    face normals meeting there, which is exactly what an unsplit mesh would have
    had.

    ``angle_limit`` (degrees) is an escape hatch, off at 180: below it, corners
    whose faces disagree by more than the limit are averaged separately, so
    back-to-back cards such as eyelashes are not cancelled out.

    ``face_flip`` is a per-face +-1 sign applied to the geometric face normals,
    which is how a negatively scaled object is brought into agreement with the
    rest of the selection before anything is averaged.

    Returns (corner normals, positions merged, degenerate positions).
    """
    ang = corner_angles(co, lv, ls, lt)
    fn = face_normals(co, lv, ls, lt)
    if face_flip is not None:
        fn = fn * np.asarray(face_flip, np.float64)[:, None]
    lface = np.repeat(np.arange(len(ls)), lt)
    lfn = fn[lface]
    cid, ncl = position_clusters(co, distance)
    lc = cid[lv]

    acc = np.zeros((ncl, 3))
    np.add.at(acc, lc, ang[:, None] * lfn)

    if angle_limit < 180.0:
        acc = _split_opposed(acc, lc, ang, lfn, angle_limit)
        ncl = len(acc)

    # A cluster that cancels out has no meaningful average — two coincident
    # surfaces pointing opposite ways.  Those corners keep their own face
    # normal rather than being handed a normalized rounding error.
    weight = np.zeros(ncl)
    np.add.at(weight, lc, ang)
    length = np.linalg.norm(acc, axis=1)
    degenerate = length < np.maximum(weight, 1e-30) * 1e-6

    out = normalize(acc)[lc]
    dead = degenerate[lc]
    out[dead] = lfn[dead]

    sizes = np.bincount(cid, minlength=ncl)
    return out, int((sizes > 1).sum()), int(degenerate.sum())


def _split_opposed(acc, lc, ang, lfn, angle_limit):
    """Re-accumulate the clusters whose faces disagree by more than
    ``angle_limit``, splitting each into direction groups.  ``lc`` is modified
    in place to point at the new cluster ids."""
    cos_lim = np.cos(np.radians(angle_limit))
    mean = normalize(acc)
    bad = np.unique(lc[(lfn * mean[lc]).sum(1) < cos_lim])
    if not len(bad):
        return acc

    order = np.argsort(lc, kind="stable")
    starts = np.searchsorted(lc[order], bad, side="left")
    ends = np.searchsorted(lc[order], bad, side="right")
    extra = []
    for c, s, e in zip(bad, starts, ends):
        idx = order[s:e]
        # Seed by descending corner angle so the grouping does not depend on
        # loop order
        rest = list(idx[np.argsort(-ang[idx], kind="stable")])
        first = True
        while rest:
            seed = rest[0]
            grp = [i for i in rest if float(lfn[i] @ lfn[seed]) >= cos_lim]
            rest = [i for i in rest if i not in set(grp)]
            vec = (lfn[grp] * ang[grp][:, None]).sum(0)
            if first:
                acc[c] = vec
                first = False
            else:
                lc[grp] = len(acc) + len(extra)
                extra.append(vec)
    return np.concatenate([acc, np.array(extra).reshape(-1, 3)]) if extra else acc


# ── public operations ──────────────────────────────────────────────────────

def reset_normals(objects, distance=1e-5, angle_limit=180.0, shade_smooth=True):
    """Reshade the given mesh objects as if they were one uncut surface.

    The objects are gathered into world space and treated as a single mesh, so a
    body split into a dozen pieces — the shape the game requires — shades across
    the cuts, including cuts that fall between two separate objects.  Nothing
    about the split is touched: vertices stay split, sharp edges stay marked,
    materials stay where they are.  The result is written as custom split
    normals, which override the sharp edges for shading while leaving them in
    place for export.

    ``shade_smooth`` sets ``use_smooth`` on the faces.  A flat-shaded face
    ignores custom normals outright, so without it the result is invisible on
    exactly the faces that most need it; it is a shading flag only and does not
    merge or move anything.

    Returns (objects done, positions merged, degenerate positions).
    """
    parts = []
    co_all, lv_all, ls_all, lt_all, flip_all = [], [], [], [], []
    voff = loff = 0
    for obj in objects:
        me = obj.data
        if not me.polygons:
            continue
        co, lv, ls, lt = mesh_arrays(me)
        m = np.array(obj.matrix_world.to_3x3())
        origin = np.array(obj.matrix_world.translation)
        # A negatively scaled object draws with its normals flipped, so its
        # geometry-derived face normals have to be flipped to agree with the
        # rest of the selection before anything is averaged
        mirrored = np.linalg.det(m) < 0.0
        co_all.append(co @ m.T + origin)
        lv_all.append(lv.astype(np.int64) + voff)
        ls_all.append(ls.astype(np.int64) + loff)
        lt_all.append(lt.astype(np.int64))
        flip_all.append(np.full(len(ls), -1.0 if mirrored else 1.0))
        parts.append((me, m, loff, loff + len(lv), mirrored))
        voff += len(co)
        loff += len(lv)

    if not parts:
        return 0, 0, 0

    out, merged, degenerate = integral_normals(
        np.concatenate(co_all), np.concatenate(lv_all),
        np.concatenate(ls_all), np.concatenate(lt_all),
        distance, angle_limit, face_flip=np.concatenate(flip_all))

    for me, m, s, e, mirrored in parts:
        # world -> local for a normal is the transpose of the linear part
        local = normalize(out[s:e] @ m)
        if mirrored:
            local = -local
        if shade_smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        clear_intent(me)
        me.normals_split_custom_set(local.tolist())
        me.update()

    return len(parts), merged, degenerate


def apply_cylindrical(me, axis=2, center=None, face_mask=None,
                      smooth_boundary=True, strength=1.0):
    """Replace the masked faces' custom split normals with a cylindrical field.

    ``axis`` is the cylinder's direction in mesh-local space: either an index
    (0/1/2) or a 3-vector, which is what the caller passes once it has mapped
    the user's world axis through the object's rotation.  A vector is needed
    because game meshes are often imported rotated — assuming local Z is
    vertical collapses the field to a near-constant direction on a Y-up mesh.

    ``center`` is a point on the axis in mesh-local space (defaults to the
    origin).  ``face_mask`` is a bool array over polygons; ``None`` means every
    face.  Unmasked faces keep whatever normals they already have.

    There is no proxy geometry and no radius: the target is the normalized
    horizontal offset from the axis, so the result is scale-invariant — the
    same mesh scaled by any factor yields identical normals.

    Returns (masked face count, boundary vertex count).
    """
    co, lv, ls, lt = mesh_arrays(me)
    npo = len(me.polygons)
    if face_mask is None:
        face_mask = np.ones(npo, bool)

    ang = corner_angles(co, lv, ls, lt)
    base = corner_normals(me)

    if center is None:
        center = np.zeros(3)
    if np.isscalar(axis):
        u = np.zeros(3)
        u[int(axis)] = 1.0
    else:
        u = normalize(np.asarray(axis, np.float64).reshape(3))
    d = co - np.asarray(center, np.float64)
    # Strip the along-axis component; for a basis vector this is d[:, axis] = 0
    d -= np.outer(d @ u, u)
    radius = np.linalg.norm(d, axis=1)
    # Relative epsilon so the on-axis test survives any model scale
    extent = float(np.linalg.norm(co.max(0) - co.min(0))) if len(co) else 0.0
    on_axis = radius < max(1e-12, extent * 1e-6)
    target = d / np.maximum(radius[:, None], 1e-12)

    # Per-vertex weight: the share of the surrounding corner angle that belongs
    # to masked faces.  Boundary vertices land between 0 and 1 on their own,
    # which is where the one-vertex-wide transition comes from.
    lface = np.repeat(np.arange(npo), lt)
    num = np.zeros(len(co))
    den = np.zeros(len(co))
    np.add.at(num, lv, ang * face_mask[lface])
    np.add.at(den, lv, ang)
    w = np.divide(num, den, out=np.zeros(len(co)), where=den > 1e-12)

    if not smooth_boundary:
        w = (w > 0.5).astype(np.float64)
    w[on_axis] = 0.0
    w *= strength

    clear_intent(me)
    me.normals_split_custom_set(slerp(base, target[lv], w[lv]).tolist())
    me.update()

    n_boundary = int(((w > 0.02) & (w < 0.98)).sum())
    return int(face_mask.sum()), n_boundary


# ── keeping custom normals through a shape key ─────────────────────────────

# Why a re-encode and not a re-bake
# ---------------------------------
# Blender stores a custom split normal as ``INT16_2D``: not the direction, but
# the direction *encoded in that corner's normal space*, and that space is
# derived from the surrounding geometry.  Move a vertex with a shape key and the
# stored bytes do not change, but the basis they decode against does — so the
# direction the viewport shades with, and the one an exporter reads off the
# evaluated mesh, drifts away from what was authored.
#
# Measured on a shipped face (7013 verts, 14 non-zero keys, 6.7mm of travel):
# the base mesh's decode and the shape-keyed decode differ by a mean of only
# 1.58 degrees, but 1565 corners exceed 5 degrees, 230 exceed 20, and the worst
# reaches 165 — a flip.  On unmoved vertices it is 0.009 degrees, so it is
# entirely deformation-driven.  Those few hundred corners are the blotches that
# show up around the eyes and mouth after the keys are dialled in.
#
# The fix is to write the wanted directions onto a throwaway mesh whose geometry
# *is* the deformed geometry, let Blender encode them against that basis, and
# copy the raw INT16_2D back.  Residual after the round trip: mean 0.005
# degrees, max 0.73, nothing above 5.  Note this deliberately makes the
# undeformed base mesh decode to something else — which costs nothing, because
# the mesh is always shown and exported with its keys applied, and the game's
# blend shapes carry position deltas only, so one normal set is all there is.
#
# The target field is kept in an attribute rather than re-read each run, so
# running twice is idempotent: the second run must not treat the already
# re-encoded result as the new intent, or the error compounds.

INTENT_ATTR = "mhw_normal_intent"


def clear_intent(me):
    """Forget the stored target field.

    Anything that rewrites the custom normals invalidates it — the stored
    directions describe what the *base* mesh used to decode to, which a re-bake
    replaces outright.
    """
    attr = me.attributes.get(INTENT_ATTR)
    if attr is not None:
        me.attributes.remove(attr)


def _intent_field(me, data=None):
    """Read (data=None) or write the stored target field."""
    attr = me.attributes.get(INTENT_ATTR)
    if data is None:
        if attr is None:
            return None
        a = np.empty(len(me.loops) * 3, np.float32)
        attr.data.foreach_get("vector", a)
        return normalize(a.reshape(-1, 3).astype(np.float64))
    _vector_attr(me, INTENT_ATTR, data)
    return data


def decode_at(me, co):
    """The directions ``me``'s stored normals mean when decoded against the
    geometry ``co`` instead of the mesh's own.

    The decode basis is derived from the surrounding geometry, so the same
    stored bytes answer differently on different geometry — which is the whole
    problem this module exists for, and also the lever: handing it the geometry
    the normals were authored against recovers what they were authored to be.
    """
    import bpy

    dec = me.copy()
    try:
        dec.vertices.foreach_set("co", np.asarray(co, np.float32).ravel())
        dec.update()
        return normalize(corner_normals(dec))
    finally:
        bpy.data.meshes.remove(dec)


def reencode_for_shape(me, deformed_co, reset_intent=False, base_co=None):
    """Re-encode the custom split normals against ``deformed_co``.

    ``deformed_co`` is the mesh's vertex positions under the deformation the
    normals have to survive — for a shape key, the mixed positions.  Nothing
    about the mesh's geometry, keys or topology is touched; only the stored
    encoding changes.

    ``base_co`` is the geometry to *read* the authored directions off, in this
    mesh's own local space.  ``None`` means the mesh's own base geometry, which
    is what its stored normals already decode against.  Passing a reference
    mesh's base instead recovers the directions as they were authored, for when
    this mesh's own base has been edited out from under them — the stored bytes
    did not change, but what they decode to did.  It has no effect once a target
    field is stored: that field *is* the answer ``base_co`` would be used to
    work out, so only a fresh capture consults it.

    Returns (corners written, whether the target field was captured now,
    per-corner residual in degrees between the deformed decode and the target).
    """
    import bpy  # only needed for the throwaway mesh; the rest of this file is numpy

    def authored():
        return corner_normals(me) if base_co is None else decode_at(me, base_co)

    if me.attributes.get("custom_normal") is None:
        # Nothing authored to preserve yet — pin down what the mesh shades with
        # now, so there is a target to re-encode at all
        me.normals_split_custom_set(authored().tolist())
        me.update()

    target = None if reset_intent else _intent_field(me)
    fresh = target is None
    if fresh:
        target = normalize(authored())
        _intent_field(me, target)

    enc = me.copy()
    try:
        enc.vertices.foreach_set("co", np.asarray(deformed_co, np.float32).ravel())
        enc.update()
        enc.normals_split_custom_set(target.tolist())
        raw = np.empty(len(enc.loops) * 2, np.int16)
        enc.attributes["custom_normal"].data.foreach_get("value", raw)
        # enc's own decode is the deformed decode, so the round-trip error can be
        # measured here without going through the depsgraph
        resid = np.degrees(np.arccos(np.clip(
            (normalize(corner_normals(enc)) * target).sum(1), -1.0, 1.0)))
    finally:
        bpy.data.meshes.remove(enc)

    me.attributes["custom_normal"].data.foreach_set("value", raw)
    me.update()
    return len(target), fresh, resid

# ── baking an object transform without losing the normals ──────────

#: Where the normals wait out the bake.  Removed again on the way out.
CARRY_ATTR = "mtk_normal_carry"


def stash_normals(me, matrix):
    """Park the split normals in world space so an object-transform bake cannot
    damage them.  Returns False if there is nothing authored to protect.

    Why this needs doing at all: a custom normal is stored relative to a basis
    derived from the surrounding geometry, so baking a negative-determinant
    matrix -- any mirror -- flips that basis and the same stored bytes decode to
    a different direction.  Measured on one face mesh with only the matrix's
    sign changing, determinant +1 came out 0 degrees off and determinant -1 left
    76% of corners more than 90 degrees off.

    Why a plain corner attribute rather than a captured array: the bake also
    reverses every polygon's winding, so corner *index* i afterwards is a
    different corner than index i before.  Blender moves its own corner
    attributes along with the corners (measured: the permutation it applies is
    exactly the one a ``(polygon, vertex)`` key reconstructs, 0 of 34350
    corners differing), so riding along in an attribute gets the bookkeeping
    for free.  Reconstructing the permutation by hand instead invites writing
    the values back by index, which scrambles the normals inside each face and
    -- because reading back the same indices just written always agrees --
    reports success while doing it.

    The stored intent field (see ``reencode_for_shape``) is object-space too,
    so it is converted in place and rides along the same way.
    """
    if me.attributes.get("custom_normal") is None:
        return False
    # Normals transform by the inverse transpose, so as rows: n @ inv(M3)
    inv = np.array(matrix.to_3x3().inverted_safe(), np.float64)
    _vector_attr(me, CARRY_ATTR, normalize(corner_normals(me) @ inv))
    intent = _intent_field(me)
    if intent is not None:
        _intent_field(me, normalize(intent @ inv))
    return True


def unstash_normals(me, matrix):
    """Write the parked normals back into a mesh whose transform has just been
    baked, and drop the parking attribute.

    Returns the per-corner residual in degrees between what was parked and what
    the mesh decodes to now.  That is the INT16 re-encode error only, read back
    through the mesh; the corner matching is Blender's own, not something this
    measures.  Returns None if nothing was parked.
    """
    attr = me.attributes.get(CARRY_ATTR)
    if attr is None:
        return None
    a = np.empty(len(me.loops) * 3, np.float32)
    attr.data.foreach_get("vector", a)
    world = a.reshape(-1, 3).astype(np.float64)
    me.attributes.remove(me.attributes[CARRY_ATTR])

    # World back into the new object space: inverse of the inverse transpose
    m3 = np.array(matrix.to_3x3(), np.float64)
    out = normalize(world @ m3)
    me.normals_split_custom_set(out.tolist())
    intent = _intent_field(me)
    if intent is not None:
        _intent_field(me, normalize(intent @ m3))
    me.update()
    return np.degrees(np.arccos(np.clip(
        (normalize(corner_normals(me)) * out).sum(1), -1.0, 1.0)))


def _vector_attr(me, name, data):
    attr = me.attributes.get(name)
    if attr is not None and (attr.domain != 'CORNER'
                             or attr.data_type != 'FLOAT_VECTOR'):
        me.attributes.remove(attr)
        attr = None
    if attr is None:
        attr = me.attributes.new(name, 'FLOAT_VECTOR', 'CORNER')
    attr.data.foreach_set("vector", data.astype(np.float32).ravel())
    return attr

# ── matching corners between two meshes by position ──────────────────

def corner_anchors(me, matrix, co):
    """One distinct world point per corner: the corner's vertex nudged toward
    its face centre.

    Corner *index* is not a correspondence between two meshes — two exports of
    the same head can carry the same counts in a different vertex and face
    order (measured on one character's four expression meshes: 17046 of 35886
    corners disagreed, and not by a winding flip either).  Position is the only
    thing that does correspond.  The vertex position alone is not enough,
    because a split fan puts several corners on one vertex; offsetting toward
    the face centre separates them while staying a position, so it survives any
    reordering.
    """
    m = np.array(matrix.to_3x3(), np.float64)
    world = np.asarray(co, np.float64) @ m.T + np.array(matrix.translation, np.float64)
    lv, ls, lt = _topology(me)
    pid = np.repeat(np.arange(len(ls)), lt)
    cent = np.zeros((len(ls), 3))
    np.add.at(cent, pid, world[lv])
    cent /= lt[:, None]
    v = world[lv]
    return v + 0.3 * (cent[pid] - v)


def match_corners(src_anchors, dst_anchors):
    """``(source index, distance)`` per destination corner, nearest first.

    The caller decides what distance is too far; nothing is rejected here.
    """
    from mathutils import Vector
    from mathutils.kdtree import KDTree

    tree = KDTree(len(src_anchors))
    for i, p in enumerate(src_anchors):
        tree.insert(Vector(p), i)
    tree.balance()
    idx = np.empty(len(dst_anchors), np.int64)
    dist = np.empty(len(dst_anchors), np.float64)
    for i, p in enumerate(dst_anchors):
        _co, j, d = tree.find(Vector(p))
        idx[i], dist[i] = j, d
    return idx, dist


def _topology(me):
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return lv, ls, lt
