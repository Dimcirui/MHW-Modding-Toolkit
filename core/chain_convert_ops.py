"""Operator for the cross-game chain port, one entry per REE game section.

The section supplies ``source_game``, so the direction is fixed by where the user
clicked and only the target has to be chosen.  That introduces one failure mode the
panel-less version did not have -- clicking it in the MHWS section while a RE4R chain
collection is selected -- so the source game is verified against the collection's own
armature and a mismatch is refused rather than silently converted the wrong way.

All the work lives in ``core.chain_convert`` and ``core.bone_mapper``; this file is
only the dialog.
"""

import json
import os

import bpy

from .bone_mapper import BoneMapManager, auto_detect_preset, build_cross_game_map
from .chain_convert import (apply_target_game_settings, duplicate_chain_collection,
                            export_operator_for, is_chain2, iter_collider_bindings,
                            ported_chain_collection_name, relocalise_node_frames,
                            remap_collider_attachments)
from .i18n import T
from .mesh_port_ops import collection_armatures, is_mesh_collection, mesh_collections
from .port_consent import gate

#: Games this is offered for, keyed by the ``game_code`` in the bone preset -- which
#: is **not** always the section key, though it now agrees for every game here.
#: Keying off the preset is what makes ``_preset_by_game()`` resolve.
#:
#: Deliberately three, not five:
#: * **MHWI** is not RE Engine at all -- its physics goes through mhw_ctc, and its
#:   chain code is off-limits per the refactor backlog.
#: * **SF6 / DMC5** have no reference skeleton to validate against.
#:
#: MHRS joined on 2026-08-16, once it had a native bone table and a reference
#: skeleton.  It is the first entry that writes ``.chain`` v48 rather than a
#: ``.chain2``, so every MHRS pair crosses the container boundary in one direction
#: or the other and leans on ``translate_group_attr``.
#:
#: The mapping layer already handles all of them (`build_cross_game_map` composes any
#: pair); this list is only about which ones have been *validated end to end*.
PORTABLE_GAMES = ("MHWS", "RE4", "RE9", "MHRS")

#: EnumProperty item callbacks must keep a persistent reference to what they return.
#: Blender's C side holds the strings, and a list built inside the callback is freed
#: the moment Python drops it, leaving dangling pointers -- the same trap documented
#: in core/ref_skeleton.py.
_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _preset_by_game():
    """``{game_code: (filename, display_name)}`` from assets/presets/bone/*.json."""
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
        # first preset wins: several files can share a game_code (mhwi_world and
        # mhwi_world_legacy), and the alternates are not what we want here
        if code and code not in out:
            out[code] = (fname, info.get("name") or code)
    return out


def _chain_collections():
    """Collections holding an imported chain -- identified by their header object.

    Direct membership only (c.objects, not all_objects). A chain's header always
    sits at the collection's own level -- confirmed live: CHAIN_HEADER's own
    users_collection is exactly the leaf .chain/.chain2 collection, never a
    parent. Recursing into all_objects instead also matches every *ancestor*
    "master" collection that merely nests this one alongside completely
    unrelated siblings (.mesh, .mdf2, .sfur, .clsp) -- confirmed 2026-08-14 as a
    real incident, not a hypothetical: duplicate_chain_collection ran against
    one of those masters and copied its *entire* contents (mesh, armature, MDF
    materials, everything) into what should have been a chain-only collection.
    """
    return [c for c in bpy.data.collections
            if any(o.get("TYPE") == "RE_CHAIN_HEADER" for o in c.objects)]


def _collection_items(self, context):
    items = [(c.name, c.name, "", 'OUTLINER_COLLECTION', i)
             for i, c in enumerate(_chain_collections())]
    if not items:
        items = [("NONE", T("core.chain_convert_ops.no_chain_collection"), "", 'ERROR', 0)]
    return _cached("collection", items)


def _target_game_items(self, context):
    presets = _preset_by_game()
    items = []
    for code in PORTABLE_GAMES:
        if code == self.source_game or code not in presets:
            continue
        items.append((code, presets[code][1], "", len(items)))
    if not items:
        items = [("NONE", "-", "", 0)]
    return _cached("target_game", items)


def _target_mesh_collection_items(self, context):
    # Same picker mesh_port_ops.MODDER_OT_PortMeshCrossGame itself offers for
    # its own source_collection -- a .mesh collection is the unit a rig and
    # its meshes come as, and it is what a chain's colliders actually need to
    # be re-bound onto, not a bare armature name with no context.
    items = [(c.name, f"{c.name}  ({len(collection_armatures(c))})", "",
              'OUTLINER_COLLECTION', i) for i, c in enumerate(mesh_collections())]
    if not items:
        items = [("NONE", "-", "", 'ERROR', 0)]
    return _cached("target_mesh_collection", items)


def _collection_armature(collection):
    """The armature a collection's colliders are bound to, or None.

    Read from the constraints rather than guessed, since a scene can hold several
    rigs and the collection itself records no owner.
    """
    for _obj, con in iter_collider_bindings(collection):
        if getattr(con, "target", None) is not None and con.target.type == 'ARMATURE':
            return con.target
    return None


def _collection_game_code(collection, prefer_game=None):
    """Game code detected from the armature *collection*'s colliders are
    bound to, or None when there's no armature or no matching preset.

    *prefer_game* settles a tie in the caller's favour: RE4R and MHWilds name the
    standard bones identically, so both presets score 1.0 on either rig and the
    winner was decided by filename order -- which reported every RE4 rig as MHWS.
    """
    arm = _collection_armature(collection)
    if arm is None:
        return None
    detected = auto_detect_preset(arm, False, prefer_game=prefer_game)
    if not detected:
        return None
    mgr = BoneMapManager()
    if not mgr.load_preset(detected):
        return None
    return mgr.preset_info.get("game_code")


@gate
class MODDER_OT_ConvertChainCrossGame(bpy.types.Operator):
    bl_idname = "modder.convert_chain_cross_game"
    bl_label = "Port Chain to Another Game"
    bl_options = {'REGISTER', 'UNDO'}

    source_game: bpy.props.StringProperty(options={'HIDDEN'})
    source_collection: bpy.props.EnumProperty(
        name="Chain Collection", items=_collection_items)
    target_game: bpy.props.EnumProperty(name="Target Game", items=_target_game_items)
    target_mesh_collection: bpy.props.EnumProperty(
        name="Target Mesh Collection", items=_target_mesh_collection_items)
    replace_original: bpy.props.BoolProperty(
        name="Replace the Original", default=False,
        description="Convert the original in place instead of converting a copy")

    @classmethod
    def description(cls, context, properties):
        return T("core.chain_convert_ops.desc")

    @classmethod
    def poll(cls, context):
        return bool(_chain_collections())

    def _prefill(self, context):
        """Default source_collection off the active object, and
        target_mesh_collection off whatever RE Mesh port would have produced
        for it.

        source_collection: same shape as modder.port_mesh_cross_game/
        port_mdf_material_cross_game's own _prefill -- whichever chain
        collection the active object belongs to. Walks all_objects (not just
        users_collection) purely because the active object may itself be a
        collider one level under the chain collection, not the header; the
        candidate list itself is already narrowed to real leaf chain
        collections by _chain_collections()'s own direct-membership check,
        so this can't re-widen back onto an ancestor "master" collection.
        Skipped when the collection's own detected game doesn't match
        source_game, so a wrong-game collection (most likely one this same
        operator just produced) is left alone rather than guessed into place.

        target_mesh_collection: mesh_port_ops.duplicate_mesh_collection names
        its output "<stem>_<GAME>.mesh" -- if the chain's own armature lives
        in a .mesh collection and that naming convention already produced a
        <stem>_<target_game>.mesh collection (i.e. the mesh side of this same
        character was already ported), that is almost certainly what the
        colliders should be re-bound onto.
        """
        obj = context.active_object
        source_col = None
        if obj is not None:
            for col in _chain_collections():
                if any(o == obj for o in col.all_objects):
                    code = _collection_game_code(col, self.source_game)
                    if code is None or code == self.source_game:
                        source_col = col
                        try:
                            self.source_collection = col.name
                        except (TypeError, ValueError):
                            pass
                    break

        if source_col is None:
            source_col = bpy.data.collections.get(self.source_collection)
        if source_col is None or self.target_game in ('', 'NONE'):
            return
        src_arm = _collection_armature(source_col)
        if src_arm is None:
            return
        mesh_col = next((c for c in src_arm.users_collection if is_mesh_collection(c)), None)
        if mesh_col is None:
            return
        stem = mesh_col.name[:-5] if mesh_col.name.endswith(".mesh") else mesh_col.name
        guess = bpy.data.collections.get(f"{stem}_{self.target_game}.mesh")
        if guess is not None:
            try:
                self.target_mesh_collection = guess.name
            except (TypeError, ValueError):
                pass

    def invoke(self, context, event):
        self._lines = []
        self._blocked = True
        self._prefill(context)
        return context.window_manager.invoke_props_dialog(self, width=460)

    def check(self, context):
        """Re-run the preflight whenever a field changes, and redraw.

        A dry run over a few dozen colliders is cheap, so the report can just track
        the fields instead of hiding behind a separate button.
        """
        self._preflight()
        return True

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection",
                    text=T("core.chain_convert_ops.source_collection"))
        layout.prop(self, "target_game", text=T("core.chain_convert_ops.target_game"))
        layout.prop(self, "target_mesh_collection",
                    text=T("core.chain_convert_ops.target_mesh_collection"))
        layout.prop(self, "replace_original",
                    text=T("core.port.replace_original"))

        if not getattr(self, "_lines", None):
            self._preflight()

        box = layout.box()
        for icon, text in self._lines:
            box.label(text=text, icon=icon)

    # ── preflight ────────────────────────────────────────────────────────────

    def _resolve(self):
        """``(collection, armature, cross_map, error_line)``; any may be None."""
        presets = _preset_by_game()
        col = bpy.data.collections.get(self.source_collection)
        mesh_col = bpy.data.collections.get(self.target_mesh_collection)
        if col is None or mesh_col is None:
            return None, None, None, ('INFO', T("core.chain_convert_ops.pick_target"))

        # A .mesh collection is expected to hold exactly one rig, same
        # constraint mesh_port_ops.MODDER_OT_PortMeshCrossGame enforces on its
        # own source_collection -- two would mean the colliders' new home is
        # ambiguous, not a choice this operator should make for the user.
        arms = collection_armatures(mesh_col)
        if not arms:
            return None, None, None, ('ERROR', T("core.chain_convert_ops.target_no_armature"))
        if len(arms) > 1:
            return None, None, None, ('ERROR', T("core.chain_convert_ops.target_many_armatures").format(
                n=len(arms), names=", ".join(a.name for a in arms[:3])))
        arm = arms[0]

        # The section fixed the source game, so make sure the collection agrees --
        # otherwise clicking this in the wrong section converts the wrong direction.
        code = _collection_game_code(col, self.source_game)
        if code and self.source_game and code != self.source_game:
            return None, None, None, ('ERROR', T(
                "core.chain_convert_ops.wrong_source_game").format(
                    found=code, expected=self.source_game))

        src = presets.get(self.source_game)
        dst = presets.get(self.target_game)
        if not src or not dst:
            return None, None, None, ('ERROR', T("core.chain_convert_ops.pick_target"))
        return col, arm, build_cross_game_map(src[0], dst[0]), None

    def _preflight(self):
        self._lines = []
        self._blocked = True
        col, arm, cross_map, err = self._resolve()
        if err is not None:
            self._lines = [err]
            return
        if cross_map is None:
            self._lines = [('ERROR', T("core.chain_convert_ops.pick_target"))]
            return

        rep = remap_collider_attachments(col, cross_map, target_armature=arm,
                                         dry_run=True)
        self._report = rep
        total = len(rep.remapped) + rep.unchanged
        self._lines.append(('INFO', T("core.chain_convert_ops.stat_bindings").format(
            total=total, remapped=len(rep.remapped), kept=rep.unchanged)))

        if rep.unmapped:
            names = sorted({b for _o, b in rep.unmapped})
            self._lines.append(('ERROR', T("core.chain_convert_ops.unmapped").format(
                n=len(names), names=", ".join(names[:4]))))
        if rep.missing_in_target:
            names = sorted({b for _o, b in rep.missing_in_target})
            self._lines.append(('ERROR', T("core.chain_convert_ops.missing").format(
                n=len(names), names=", ".join(names[:4]))))
        if rep.ok:
            self._lines.append(('CHECKMARK', T("core.chain_convert_ops.all_resolved")))
        if rep.collapsed:
            tgt, srcs = sorted(rep.collapsed.items())[0]
            self._lines.append(('ERROR', T("core.chain_convert_ops.merged").format(
                n=len(rep.collapsed), example=f"{tgt} <- {', '.join(srcs)}")))
        self._blocked = not rep.ok

    # ── execute ──────────────────────────────────────────────────────────────

    def execute(self, context):
        self._preflight()
        if self._blocked:
            self.report({'ERROR'}, T("core.chain_convert_ops.blocked"))
            return {'CANCELLED'}

        col, arm, cross_map, err = self._resolve()
        if err is not None or cross_map is None:
            self.report({'ERROR'}, err[1] if err else T("core.chain_convert_ops.blocked"))
            return {'CANCELLED'}

        if not self.replace_original:
            col, _mapping = duplicate_chain_collection(
                col, ported_chain_collection_name(col.name, self.target_game))

        rep = remap_collider_attachments(col, cross_map, target_armature=arm)

        # Colliders are bound by bone *name*; a node's angle limit is a rotation
        # stored relative to its bone, so it needs the bone's new orientation, not
        # its new name.  Crossing to or from RE9 moves every physics bone by the
        # convention relabel (measured: 90 degrees on all 293 chain bones of the
        # reference asset), and a frame carried verbatim goes with it.  Inside one
        # family the two orientations are equal and this is an identity.
        frames = relocalise_node_frames(col, arm)

        # Bone re-binding is only half a port: the collider filter path and the
        # chain2 subdata are per-game and invisible in the outliner, so a port
        # without them looks finished and fails at load time.
        applied = apply_target_game_settings(col, self.target_game,
                                             self.source_game)

        # RE-Chain-Editor's export dialog preselects its version from the *last
        # imported* file (scene["REChainLastImportedChain(2)Version"]), which
        # after a port is the source game's. Point it at the target instead --
        # otherwise the obvious next click writes the source game's format.
        idname, version = export_operator_for(self.target_game)
        key = ("REChainLastImportedChain2Version" if is_chain2(self.target_game)
               else "REChainLastImportedChainVersion")
        context.scene[key] = version

        # Same problem one level up, and a worse one. ``chainFileType`` is a
        # *scene* enum that RE-Chain-Editor only ever writes in
        # createChainCollection, from the collection-name suffix at import time
        # (blender_re_chain.py:96-100). Nothing re-derives it from the active
        # object, so after a port it still says whatever the last *import* was --
        # the source game's container.
        #
        # It is not cosmetic. It picks the Set Attribute Flag vocabulary and the
        # dialog's own "Type:" label (re_chain_operators.py:2092, :2123, :2155),
        # which fields the header / settings / group / node panels draw
        # (ui_re_chain_panels.py:202, :318, :452-457, :551), the chain2 subdata
        # panel's poll (:416), and every create-operator (:25, :247, :425, :458,
        # :498, :574, :651). Left stale, a ported .chain is edited with chain2's
        # bit meanings -- exactly the mismeaning translate_group_attr just fixed,
        # reintroduced by hand on the user's next edit.
        #
        # The collection pointer moves with it, deliberately: type without
        # collection is worse than neither, because the create-operators would
        # then build target-flavoured objects into the *source* collection.
        toolpanel = getattr(context.scene, "re_chain_toolpanel", None)
        if toolpanel is not None:
            try:
                toolpanel.chainFileType = ("chain2" if is_chain2(self.target_game)
                                           else "chain")
                toolpanel.chainCollection = col
            except (AttributeError, TypeError, ValueError):
                pass

        self.report({'INFO'}, T("core.chain_convert_ops.done").format(
            game=self.target_game, remapped=len(rep.remapped), kept=rep.unchanged))
        if frames['relocalised']:
            self.report({'INFO'}, T("core.chain_convert_ops.frames_relocalised").format(
                n=frames['relocalised'], kept=frames['unchanged']))
        if frames['missing'] or frames['no_source']:
            self.report({'WARNING'}, T("core.chain_convert_ops.frames_skipped").format(
                n=len(frames['missing']) + len(frames['no_source'])))
        if applied['filter_set']:
            self.report({'INFO'}, T("core.chain_convert_ops.filter_applied").format(
                n=applied['filter_set'],
                path=applied['filter_path'] or T("core.chain_convert_ops.filter_empty")))
        if applied['subdata_added']:
            self.report({'INFO'}, T("core.chain_convert_ops.subdata_added").format(
                n=applied['subdata_added']))
        # Worth reporting even though it is automatic: the numbers in the Attribute
        # Flags field change, and a user comparing them against the source file
        # would otherwise read that as the port corrupting them.
        if applied['attr_translated']:
            self.report({'INFO'}, T("core.chain_convert_ops.attr_translated").format(
                n=applied['attr_translated']))
        if applied['attr_dropped']:
            self.report({'WARNING'}, T("core.chain_convert_ops.attr_dropped").format(
                names=", ".join(applied['attr_dropped'])))
        # The container is chosen by which operator the user runs, and nothing in
        # the scene decides it -- so saying which one is part of the result.
        self.report({'INFO'}, T("core.chain_convert_ops.export_with").format(
            op=idname, version=version))
        return {'FINISHED'}


classes = [MODDER_OT_ConvertChainCrossGame]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
