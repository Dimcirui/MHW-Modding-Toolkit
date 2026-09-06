"""Mesh, normal, weight and shape-key operators.

Moved out of ui/main_panel.py unchanged -- same bl_idnames, same properties,
same code -- for the same reason as core/bone_ops.py: their algorithms live in
core/mesh_utils.py, core/normal_utils.py, core/shapekey_utils.py and
core/weight_utils.py, so the operators wrapping them belong here rather than
next to the panel that draws them.

MHW_OT_MergeRenamedVGroups is here rather than in core/bone_ops.py because it
edits mesh vertex groups, even though what it cleans up is the fallout of bone
renaming.

The `from . import ...` statements inside execute() bodies were `from ..core
import ...` before the move; the depth changed, the target module did not.
"""

import bpy
import re

from .i18n import T, get_lang
from . import weight_utils


def _face_normal_origin_items(self, context):
    return [
        ('OBJECT', T("ui.main_panel.fn_origin_object"), T("ui.main_panel.fn_origin_object_desc")),
        ('CURSOR', T("ui.main_panel.fn_origin_cursor"), ""),
        ('BBOX',   T("ui.main_panel.fn_origin_bbox"),   ""),
    ]
def _face_normal_axis_items(self, context):
    return [
        ('Z', T("ui.main_panel.fn_axis_z"), T("ui.main_panel.fn_axis_z_desc")),
        ('Y', T("ui.main_panel.fn_axis_y"), ""),
        ('X', T("ui.main_panel.fn_axis_x"), ""),
    ]
def _sk_enum_items(self, context):
    global _sk_enum_cache
    obj = context.active_object
    if not obj or not obj.data.shape_keys:
        _sk_enum_cache = [('1', 'No shape keys', '', 1)]
        return _sk_enum_cache
    items = []
    for i, kb in enumerate(obj.data.shape_keys.key_blocks):
        if i == 0:
            continue
        items.append((str(i), kb.name, '', i))
    _sk_enum_cache = items or [('1', 'No shape keys', '', 1)]
    return _sk_enum_cache
def _sk_filter_sign_items(self, context):
    return [
        ('+', T("ui.main_panel.sk_sign_pos"), ""),
        ('-', T("ui.main_panel.sk_sign_neg"), ""),
    ]
class MHW_OT_ShapeKeyToWeights(bpy.types.Operator):
    # Method inspired by: 光之影V, 幽玲乃昕
    """Convert a shape key to a vertex group (normalized weights + Laplacian smoothing + seam sync)"""
    bl_idname = "mhw.sk_to_weights"
    bl_label = "Shape Key to Weights"
    bl_options = {'REGISTER', 'UNDO'}

    shape_key_enum: bpy.props.EnumProperty(
        name="Shape Key",
        items=_sk_enum_items,
        description="Shape key to convert (Basis is excluded)",
    )
    ignore_threshold: bpy.props.FloatProperty(
        name="Ignore Threshold",
        default=0.001, min=0.0,
        description="Vertices with displacement smaller than this are ignored",
    )
    weight_strength: bpy.props.FloatProperty(
        name="Weight Strength",
        default=1.0, min=0.1, max=5.0,
        description="Multiplier applied after normalization",
    )
    smooth_factor: bpy.props.FloatProperty(
        name="Smooth Factor",
        default=0.5, min=0.0, max=1.0,
        description="How much weight diffuses to neighbors each Laplacian pass",
    )
    smooth_iters: bpy.props.IntProperty(
        name="Smooth Iterations",
        default=10, min=0, max=100,
        description="Number of Laplacian smoothing passes",
    )
    sync_seams: bpy.props.BoolProperty(
        name="Sync Seam Vertices",
        default=True,
        description="Force identical weights on spatially coincident vertices to prevent UV seam tearing",
    )
    use_direction_filter: bpy.props.BoolProperty(
        name="Direction Filter",
        default=False,
        description="Only include vertices whose displacement projects positively onto the chosen axis",
    )
    filter_axis: bpy.props.EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
    )
    filter_sign: bpy.props.EnumProperty(
        name="Direction",
        items=_sk_filter_sign_items,
        default=0,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1)

    def invoke(self, context, event):
        obj = context.active_object
        idx = obj.active_shape_key_index
        if idx > 0:
            self.shape_key_enum = str(idx)
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "shape_key_enum", text=T("ui.main_panel.sk_field_shape_key"))
        col.separator()
        col.prop(self, "ignore_threshold", text=T("ui.main_panel.sk_field_ignore_threshold"))
        col.prop(self, "weight_strength", text=T("ui.main_panel.sk_field_weight_strength"), slider=True)
        col.prop(self, "smooth_factor", text=T("ui.main_panel.sk_field_smooth_factor"), slider=True)
        col.prop(self, "smooth_iters", text=T("ui.main_panel.sk_field_smooth_iters"))
        col.prop(self, "sync_seams", text=T("ui.main_panel.sk_field_sync_seams"))
        col.separator()
        col.prop(self, "use_direction_filter", text=T("ui.main_panel.sk_field_direction_filter"))
        if self.use_direction_filter:
            row = col.row(align=True)
            row.prop(self, "filter_axis", text=T("ui.prop.filter_axis"), expand=True)
            row = col.row(align=True)
            row.prop(self, "filter_sign", text=T("ui.prop.filter_direction"), expand=True)

    def execute(self, context):
        obj = context.active_object
        key_blocks = obj.data.shape_keys.key_blocks
        idx = int(self.shape_key_enum)

        if idx <= 0 or idx >= len(key_blocks):
            self.report({'ERROR'}, T("ui.main_panel.sk_err_select_non_basis"))
            return {'CANCELLED'}

        active_kb = key_blocks[idx]
        basis_kb = obj.data.shape_keys.reference_key

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        direction = None
        if self.use_direction_filter:
            sign = 1.0 if self.filter_sign == '+' else -1.0
            direction = {'X': (sign, 0, 0), 'Y': (0, sign, 0), 'Z': (0, 0, sign)}[self.filter_axis]

        result = weight_utils.shape_key_to_weights(
            obj, active_kb, basis_kb,
            ignore_threshold=self.ignore_threshold,
            weight_strength=self.weight_strength,
            smooth_factor=self.smooth_factor,
            smooth_iters=self.smooth_iters,
            sync_seams=self.sync_seams,
            direction=direction,
        )

        if result is None:
            self.report({'WARNING'}, T("ui.main_panel.sk_warn_no_deformation").format(name=active_kb.name))
            return {'CANCELLED'}

        self.report({'INFO'}, T("ui.main_panel.sk_info_generated").format(name=active_kb.name, n=result))
        return {'FINISHED'}
# (shape_key_name, direction_xyz, part_id, mhwi_vg, mhws_vg, re4_vg, re9_vg)
# part_id is an internal English identifier (translated for display via
# _MMD_FACE_PART_KEYS below); it used to be the raw Chinese label itself.
_MMD_FACE_ENTRIES = [
    ("ウィンク２",  ( 0,  0, -1), "l_upper_eyelid", "MhBone_321", "L_UpEyeLid_LOD01",    "L_U_Eyelid3",   "L_UprLdEdge_02"),
    ("ウィンク２",  ( 0,  0,  1), "l_lower_eyelid", "MhBone_325", "L_LoEyeLid_LOD01",    "L_D_Eyelid3",   "L_LwrLdEdge_02"),
    ("ｳｨﾝｸ２右",  ( 0,  0, -1), "r_upper_eyelid", "MhBone_334", "R_UpEyeLid_LOD01",    "R_U_Eyelid3",   "R_UprLdEdge_02"),
    ("ｳｨﾝｸ２右",  ( 0,  0,  1), "r_lower_eyelid", "MhBone_338", "R_LoEyeLid_LOD01",    "R_D_Eyelid3",   "R_LwrLdEdge_02"),
    ("あ",          ( 0,  0,  1), "upper_lip",      "MhBone_381", "C_upLip_T_LOD01",     "C_UpperLip",    "C_UprLp_02"),
    ("あ",          ( 0,  0, -1), "lower_lip",      "MhBone_388", "C_loLip_T_LOD01",     "C_LowerLip",    "C_LwrLp_02"),
    ("あ",          ( 1,  0,  0), "l_mouth_corner", "MhBone_384", "L_cornerLip_B_LOD01", "L_MouthCorner", "L_LipCorner_02"),
    ("あ",          (-1,  0,  0), "r_mouth_corner", "MhBone_385", "R_cornerLip_B_LOD01", "R_MouthCorner", "R_LipCorner_02"),
]
_MMD_FACE_GAME_COL = {'MHWI': 3, 'MHWS': 4, 'RE4': 5, 'RE9': 6}
# The RE4 skeleton carries two complete sets of eyelid bones -- L_U_Eyelid01-04
# and L_U_Eyelid1-4 -- and every reference character has both. Which set the
# shipped model is actually skinned to differs per character: Leon uses the
# unpadded names, Ada and Ashley the zero-padded ones. The table above holds the
# unpadded form; this pads it for the characters that need it.
_MMD_RE4_PADDED_EYELID_CHARACTERS = {'ADA', 'ASHLEY'}

def _mmd_re4_vg_name(vg_name, character):
    if character in _MMD_RE4_PADDED_EYELID_CHARACTERS:
        return re.sub(r"(Eyelid)(\d)$", r"\g<1>0\2", vg_name)
    return vg_name
# T() keys for each part_id's display label (used in the done/skipped report message)
_MMD_FACE_PART_KEYS = {
    "l_upper_eyelid": "ui.main_panel.mmd_part_l_upper_eyelid",
    "l_lower_eyelid": "ui.main_panel.mmd_part_l_lower_eyelid",
    "r_upper_eyelid": "ui.main_panel.mmd_part_r_upper_eyelid",
    "r_lower_eyelid": "ui.main_panel.mmd_part_r_lower_eyelid",
    "upper_lip":      "ui.main_panel.mmd_part_upper_lip",
    "lower_lip":      "ui.main_panel.mmd_part_lower_lip",
    "l_mouth_corner": "ui.main_panel.mmd_part_l_mouth_corner",
    "r_mouth_corner": "ui.main_panel.mmd_part_r_mouth_corner",
}
# Custom ignore-threshold/weight-strength/smooth-factor/smooth-iterations are
# not user-configurable here; fixed per-part values are used instead.
# Upper eyelids get a higher deformation-capture precision (threshold 0,
# smooth factor 0) to avoid blink weights being over-smoothed.
_MMD_FACE_UPPER_EYELID_LABELS = {"l_upper_eyelid", "r_upper_eyelid"}
_MMD_FACE_FIXED_PARAMS = {
    True:  dict(ignore_threshold=0.0,   weight_strength=1.0, smooth_factor=0.0, smooth_iters=10),
    False: dict(ignore_threshold=0.001, weight_strength=1.0, smooth_factor=0.5, smooth_iters=10),
}
class MHW_OT_MMDFaceWeights(bpy.types.Operator):
    """Split MMD eyelid/mouth shape keys by direction into target-game facial vertex groups"""
    bl_idname = "mhw.mmd_face_weights"
    bl_label = "MMD Face Weights"
    bl_options = {'REGISTER', 'UNDO'}

    target_game: bpy.props.EnumProperty(
        name="Target Game",
        items=[
            ('MHWI', "MHWI", ""),
            ('MHWS', "MHWS", ""),
            ('RE4',  "RE4",  ""),
            ('RE9',  "RE9",  ""),
        ],
    )
    re4_character: bpy.props.EnumProperty(
        name="Character",
        description="RE4 only: which character's eyelid naming the mesh uses",
        items=[
            ('LEON',   "Leon",   "L_U_Eyelid3"),
            ('ADA',    "Ada",    "L_U_Eyelid03"),
            ('ASHLEY', "Ashley", "L_U_Eyelid03"),
        ],
        default='LEON',
    )
    sync_seams: bpy.props.BoolProperty(
        name="Sync Seam Vertices",
        default=True,
    )

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.mmd_face_weights_tip")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "target_game", text=T("ui.main_panel.mmd_target_game_label"))
        if self.target_game == 'RE4':
            col.prop(self, "re4_character", text=T("ui.main_panel.mmd_re4_character_label"))
        col.separator()
        col.prop(self, "sync_seams", text=T("ui.main_panel.mmd_sync_seams_label"))

    def execute(self, context):
        obj = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        key_blocks = obj.data.shape_keys.key_blocks
        basis_kb = obj.data.shape_keys.reference_key
        vg_col = _MMD_FACE_GAME_COL[self.target_game]

        done, skipped = [], []
        for sk_name, direction, part_id, *vg_names in _MMD_FACE_ENTRIES:
            kb = key_blocks.get(sk_name)
            if kb is None:
                skipped.append(part_id)
                continue
            target_vg = vg_names[vg_col - 3]
            if self.target_game == 'RE4':
                target_vg = _mmd_re4_vg_name(target_vg, self.re4_character)
            params = _MMD_FACE_FIXED_PARAMS[part_id in _MMD_FACE_UPPER_EYELID_LABELS]

            result = weight_utils.shape_key_to_weights(
                obj, kb, basis_kb,
                sync_seams=self.sync_seams,
                direction=direction,
                vg_name=target_vg,
                **params,
            )
            if result is None:
                skipped.append(part_id)
            else:
                done.append(part_id)

        if not done:
            self.report({'WARNING'}, T("ui.main_panel.mmd_warn_no_valid_shapekeys"))
            return {'CANCELLED'}

        join_sep = "、" if get_lang() == 'ZH' else ", "
        done_labels = [T(_MMD_FACE_PART_KEYS[p]) for p in done]
        msg = T("ui.main_panel.mmd_info_generated").format(n=len(done), parts=join_sep.join(done_labels))
        if skipped:
            skipped_labels = [T(_MMD_FACE_PART_KEYS[p]) for p in skipped]
            msg += T("ui.main_panel.mmd_info_skipped_suffix").format(parts=join_sep.join(skipped_labels))
        self.report({'INFO'}, msg)
        return {'FINISHED'}
class MHW_OT_CylindricalFaceNormals(bpy.types.Operator):
    """Replace the selected faces' custom split normals with a cylindrical field,
the way the shipped face meshes do it (see core/normal_utils.py).
Unselected faces keep their own normals; the boundary transitions on its own."""
    bl_idname = "mhw.cylindrical_face_normals"
    bl_label = "Cylindrical Face Normals"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis",
        items=_face_normal_axis_items,
        default=0,
    )
    origin: bpy.props.EnumProperty(
        name="Axis Center",
        items=_face_normal_origin_items,
        default=0,
    )
    only_selected: bpy.props.BoolProperty(
        name="Selected Faces Only",
        default=True,
        description="Only replace the selected faces' normals; unselected faces keep theirs",
    )
    smooth_boundary: bpy.props.BoolProperty(
        name="Boundary Transition",
        default=True,
        description="Boundary vertices take the angle-weighted average of both fields",
    )
    strength: bpy.props.FloatProperty(
        name="Strength",
        default=1.0, min=0.0, max=1.0, subtype='FACTOR',
        description="1 replaces fully; below 1 falls back toward the original normals",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.fn_cyl_tip")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "axis", text=T("ui.main_panel.fn_field_axis"))
        col.prop(self, "origin", text=T("ui.main_panel.fn_field_origin"))
        col.prop(self, "only_selected", text=T("ui.main_panel.fn_field_only_selected"))
        col.prop(self, "smooth_boundary", text=T("ui.main_panel.fn_field_smooth_boundary"))
        # Strength scales the whole result, so it sits last rather than being
        # read as the strength of whichever option happens to precede it
        col.separator()
        col.prop(self, "strength", text=T("ui.main_panel.fn_field_strength"), slider=True)

    def execute(self, context):
        import numpy as np
        import mathutils
        from . import normal_utils

        obj = context.active_object
        back_to_edit = context.mode == 'EDIT_MESH'
        if back_to_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            me = obj.data
            if not me.polygons:
                self.report({'ERROR'}, T("ui.main_panel.fn_err_no_faces"))
                return {'CANCELLED'}

            if self.only_selected:
                mask = np.empty(len(me.polygons), bool)
                me.polygons.foreach_get("select", mask)
                if not mask.any():
                    self.report({'ERROR'}, T("ui.main_panel.fn_err_no_selection"))
                    return {'CANCELLED'}
            else:
                mask = None

            if self.origin == 'CURSOR':
                center = np.array((obj.matrix_world.inverted() @ context.scene.cursor.location)[:])
            elif self.origin == 'BBOX':
                co, *_ = normal_utils.mesh_arrays(me)
                center = (co.min(0) + co.max(0)) * 0.5
            else:
                center = None

            # The axis is picked in world space — game meshes are usually
            # imported rotated (local Y up), so a local axis index would send
            # the field sideways.  Map it through the object's rotation instead
            # of snapping to the nearest local axis, so arbitrary orientations
            # still give a true cylinder.
            world_axis = mathutils.Vector((0.0, 0.0, 0.0))
            world_axis['XYZ'.index(self.axis)] = 1.0
            axis = obj.matrix_world.to_3x3().inverted() @ world_axis
            if axis.length < 1e-12:
                self.report({'ERROR'}, T("ui.main_panel.fn_err_bad_axis"))
                return {'CANCELLED'}

            n_faces, n_boundary = normal_utils.apply_cylindrical(
                me, axis=tuple(axis.normalized()), center=center, face_mask=mask,
                smooth_boundary=self.smooth_boundary,
                strength=self.strength,
            )
            self.report({'INFO'}, T("ui.main_panel.fn_info_applied").format(
                faces=n_faces, verts=n_boundary))
            # No boundary means nothing was preserved — the ears and the back of
            # the head get flattened, which is the failure mode of a naive
            # whole-mesh transfer
            if n_boundary == 0 and self.only_selected:
                self.report({'WARNING'}, T("ui.main_panel.fn_warn_all_selected"))
            return {'FINISHED'}
        finally:
            if back_to_edit:
                bpy.ops.object.mode_set(mode='EDIT')
class MHW_OT_ResetFaceNormals(bpy.types.Operator):
    """Reshade the selected meshes as if they were one uncut surface, without
touching the split vertices, sharp edges or material borders the game needs
(see core/normal_utils.py)"""
    bl_idname = "mhw.reset_face_normals"
    bl_label = "Reset Face Normals"
    bl_options = {'REGISTER', 'UNDO'}

    weld_distance: bpy.props.FloatProperty(
        name="Distance",
        default=1e-5, min=0.0, soft_max=1e-3, precision=6, step=0.01,
        description="Corners closer together than this count as one position (world units)",
    )
    angle_limit: bpy.props.FloatProperty(
        name="Angle Limit",
        default=180.0, min=0.0, max=180.0,
        description="180 averages every corner at a position together; below that, corners facing more than this far apart are kept separate",
    )
    shade_smooth: bpy.props.BoolProperty(
        name="Shade Smooth",
        default=True,
        description="Flat-shaded faces ignore custom normals, so the result would not show on them",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.fn_reset_tip")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "weld_distance", text=T("ui.main_panel.fn_field_weld_distance"))
        col.prop(self, "angle_limit", text=T("ui.main_panel.fn_field_weld_angle"))
        col.separator()
        col.prop(self, "shade_smooth", text=T("ui.main_panel.fn_field_shade_smooth"))

    def execute(self, context):
        from . import normal_utils

        back_to_edit = context.mode == 'EDIT_MESH'
        if back_to_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            # The whole point is to shade across the cuts, and a cut can fall
            # between two objects, so the operator works on the selection rather
            # than on the active object alone
            objects = [o for o in context.selected_objects if o.type == 'MESH']
            active = context.active_object
            if active is not None and active.type == 'MESH' and active not in objects:
                objects.append(active)
            objects = [o for o in objects if o.data.polygons]
            if not objects:
                self.report({'ERROR'}, T("ui.main_panel.fn_err_no_faces"))
                return {'CANCELLED'}

            n_obj, merged, degenerate = normal_utils.reset_normals(
                objects, distance=self.weld_distance,
                angle_limit=self.angle_limit, shade_smooth=self.shade_smooth)
            self.report({'INFO'}, T("ui.main_panel.fn_info_reset").format(
                objs=n_obj, n=merged))
            # Coincident surfaces facing opposite ways average to nothing.  They
            # keep their own face normal, but the user should know the setting
            # that would actually handle them
            if degenerate:
                self.report({'WARNING'}, T("ui.main_panel.fn_warn_opposed").format(
                    n=degenerate))
            return {'FINISHED'}
        finally:
            if back_to_edit:
                bpy.ops.object.mode_set(mode='EDIT')
def _mesh_object_items(self, context):
    """Every mesh object, as enum items.

    An EnumProperty rather than a ``prop_search`` string because the picker has
    to offer meshes *only*, and ``prop_search`` cannot filter its collection.
    A dynamic enum stores an index into a list rebuilt on every access, which is
    a hazard when the object list can change mid-operator -- these two operators
    never add or remove objects, so between the dialog and ``execute`` the list
    is the same one.
    """
    items = [(o.name, o.name, "") for o in bpy.data.objects if o.type == 'MESH']
    return items or [('NONE', T("ui.main_panel.pick_no_mesh"), "")]


#: ``(id, label key, description key)``.  Enum item labels are static text
#: Blender resolves at registration, before the language is known, so they have
#: to come from a callable that runs ``T()`` at draw time.
_BASE_SOURCE_ITEMS = (
    ('SELF', "ui.main_panel.fsk_base_self", "ui.main_panel.fsk_base_self_desc"),
    ('OBJECT', "ui.main_panel.fsk_base_object", "ui.main_panel.fsk_base_object_desc"),
)


def _base_source_items(self, context):
    return [(i, T(label), T(desc)) for i, label, desc in _BASE_SOURCE_ITEMS]


class MHW_OT_FixShapeKeyNormals(bpy.types.Operator):
    """Re-encode the custom split normals against the shape-keyed geometry, so
the directions that were authored survive the deformation instead of drifting
with the encoding basis (see core/normal_utils.py)"""
    bl_idname = "mhw.fix_shape_key_normals"
    bl_label = "Fix Shape Key Normals"
    bl_options = {'REGISTER', 'UNDO'}

    reset_intent: bpy.props.BoolProperty(
        name="Reset Target To Current Normals",
        default=False,
        description="Take the mesh's current normals as the new target. "
                    "Only needed after re-baking the normals by other means",
    )
    base_source: bpy.props.EnumProperty(
        name="Base Shape",
        items=_base_source_items,
        default=0,
    )
    base_object: bpy.props.EnumProperty(name="Reference Mesh", items=_mesh_object_items)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and obj.data.shape_keys is not None
                and len(obj.data.shape_keys.key_blocks) > 1)

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.fsk_tip")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "base_source", text=T("ui.main_panel.fsk_field_base_source"))
        if self.base_source == 'OBJECT':
            layout.prop(self, "base_object", text=T("ui.main_panel.fsk_field_base_object"))
        layout.prop(self, "reset_intent",
                    text=T("ui.main_panel.fsk_field_reset"))

    def _reference_base(self, obj):
        """The reference mesh's base geometry, or None after reporting why it
        cannot be used.

        Same topology is not optional: the positions are consumed corner for
        corner, so a different vertex count means the numbers line up against
        the wrong geometry rather than failing.

        The coordinates are taken as they are, *not* brought through the two
        objects' world transforms.  What the reference contributes is its
        shape, and the usual reference is a pristine copy of the same mesh
        parked off to one side to compare against -- honouring its transform
        would fold that parking rotation into the geometry and answer for a
        head that is turned.  Measured: a reference rotated 35 degrees about Z
        came back with every direction 35 degrees out.  A differing transform
        is still worth saying so, since then the two local frames do not
        describe the same orientation; translation alone is ignored because it
        cannot change a normal.
        """
        import numpy as np

        ref = bpy.data.objects.get(self.base_object) if self.base_object != 'NONE' else None
        if ref is None or ref.type != 'MESH':
            self.report({'ERROR'}, T("ui.main_panel.fsk_err_no_reference"))
            return None
        if ref.data is obj.data:
            self.report({'ERROR'}, T("ui.main_panel.fsk_err_reference_is_self"))
            return None
        rme = ref.data
        if (len(rme.vertices) != len(obj.data.vertices)
                or len(rme.polygons) != len(obj.data.polygons)
                or len(rme.loops) != len(obj.data.loops)):
            self.report({'ERROR'}, T("ui.main_panel.fsk_err_reference_topology").format(
                obj=ref.name))
            return None
        # Matching counts are not a correspondence.  Two exports of the same head
        # can carry the same counts in a different vertex and face order, and then
        # reading the reference's positions in its own order feeds this mesh
        # geometry that belongs to other corners -- which produces a plausible
        # result rather than an error.  Use "Transfer Normals" for that case.
        a = np.empty(len(obj.data.loops), np.int32)
        obj.data.loops.foreach_get("vertex_index", a)
        b = np.empty(len(rme.loops), np.int32)
        rme.loops.foreach_get("vertex_index", b)
        if not np.array_equal(a, b):
            self.report({'ERROR'}, T("ui.main_panel.fsk_err_reference_order").format(
                obj=ref.name, n=int((a != b).sum())))
            return None

        # The reference's *base*, not whatever its keys currently mix to
        src = (rme.shape_keys.reference_key.data if rme.shape_keys is not None
               else rme.vertices)
        co = np.empty(len(rme.vertices) * 3, np.float32)
        src.foreach_get("co", co)

        a = np.array(obj.matrix_world.to_3x3(), np.float64)
        b = np.array(ref.matrix_world.to_3x3(), np.float64)
        if not np.allclose(a, b, atol=1e-6):
            self.report({'WARNING'}, T("ui.main_panel.fsk_warn_reference_transform").format(
                obj=ref.name))
        return co.reshape(-1, 3).astype(np.float64)

    def execute(self, context):
        import numpy as np
        from . import normal_utils, shapekey_utils

        obj = context.active_object
        back_to_edit = context.mode == 'EDIT_MESH'
        if back_to_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            me = obj.data
            if not me.polygons:
                self.report({'ERROR'}, T("ui.main_panel.fn_err_no_faces"))
                return {'CANCELLED'}

            co = shapekey_utils.shape_key_mix(obj)
            if co is None:
                self.report({'ERROR'}, T("ui.main_panel.fsk_err_absolute"))
                return {'CANCELLED'}

            base = np.empty(len(me.vertices) * 3, np.float32)
            me.shape_keys.reference_key.data.foreach_get("co", base)
            moved = int((np.linalg.norm(
                co - base.reshape(-1, 3).astype(np.float64), axis=1) > 1e-9).sum())
            if not moved:
                # Every key sits at zero, so the stored encoding already decodes
                # against the geometry it was written for
                self.report({'WARNING'}, T("ui.main_panel.fsk_warn_no_deform"))
                return {'CANCELLED'}

            base_co = None
            if self.base_source == 'OBJECT':
                base_co = self._reference_base(obj)
                if base_co is None:
                    return {'CANCELLED'}

            n, fresh, resid = normal_utils.reencode_for_shape(
                me, co, reset_intent=self.reset_intent, base_co=base_co)
        finally:
            if back_to_edit:
                bpy.ops.object.mode_set(mode='EDIT')

        self.report({'INFO'}, T("ui.main_panel.fsk_done").format(
            n=n, verts=moved, mean=f"{resid.mean():.3f}", max=f"{resid.max():.2f}"))
        if fresh:
            self.report({'INFO'}, T("ui.main_panel.fsk_note_captured"))
        return {'FINISHED'}


class MHW_OT_TransferNormals(bpy.types.Operator):
    """Give the selected meshes the active mesh's normals, matched by position
and re-encoded against each one's own shape-keyed geometry
(see core/normal_utils.py)"""
    bl_idname = "mhw.transfer_normals"
    bl_label = "Transfer Normals"
    bl_options = {'REGISTER', 'UNDO'}

    reference: bpy.props.EnumProperty(name="Reference Mesh", items=_mesh_object_items)
    max_distance: bpy.props.FloatProperty(
        name="Match Distance",
        default=0.001, min=0.0, soft_max=0.05, precision=5, step=0.01,
        description="A corner with no source corner this close keeps the normal it has",
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.tn_tip")

    def invoke(self, context, event):
        # The active object is the likely reference, so open on it rather than on
        # whichever mesh happens to come first
        obj = context.active_object
        if obj is not None and obj.type == 'MESH':
            self.reference = obj.name
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "reference", text=T("ui.main_panel.tn_field_reference"))
        layout.prop(self, "max_distance", text=T("ui.main_panel.tn_field_distance"))

    @staticmethod
    def _rest_co(obj):
        """The mesh's rest positions -- the frame the two meshes have in common,
        whatever their keys are currently mixed to."""
        import numpy as np

        me = obj.data
        src = (me.shape_keys.reference_key.data if me.shape_keys is not None
               else me.vertices)
        co = np.empty(len(me.vertices) * 3, np.float32)
        src.foreach_get("co", co)
        return co.reshape(-1, 3).astype(np.float64)

    @staticmethod
    def _evaluated_world_normals(context, obj, normal_utils):
        """What the object actually shades with, in world space.  Read off the
        evaluated mesh rather than decoded by hand, so shape keys and the
        modifier stack are both already in it."""
        import numpy as np

        dg = context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            if len(me.loops) != len(obj.data.loops):
                return None
            n = np.empty(len(me.loops) * 3, np.float32)
            me.corner_normals.foreach_get("vector", n)
            n = n.reshape(-1, 3).astype(np.float64)
        finally:
            ev.to_mesh_clear()
        m = np.array(obj.matrix_world.to_3x3(), np.float64)
        return normal_utils.normalize(n @ np.linalg.inv(m))

    def execute(self, context):
        import numpy as np
        from . import normal_utils, shapekey_utils

        src = bpy.data.objects.get(self.reference) if self.reference != 'NONE' else None
        if src is None or src.type != 'MESH':
            self.report({'ERROR'}, T("ui.main_panel.tn_err_no_reference"))
            return {'CANCELLED'}
        targets = [o for o in context.selected_objects
                   if o.type == 'MESH' and o is not src and o.data is not src.data]
        if not targets:
            self.report({'ERROR'}, T("ui.main_panel.tn_err_no_targets"))
            return {'CANCELLED'}

        back_to_edit = context.mode == 'EDIT_MESH'
        if back_to_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            field = self._evaluated_world_normals(context, src, normal_utils)
            if field is None:
                self.report({'ERROR'}, T("ui.main_panel.tn_err_source_topology_changed"))
                return {'CANCELLED'}
            src_anchors = normal_utils.corner_anchors(
                src.data, src.matrix_world, self._rest_co(src))

            done = 0
            skipped_total = 0
            worst_resid = 0.0
            worst_dist = 0.0
            for obj in targets:
                me = obj.data
                anchors = normal_utils.corner_anchors(
                    me, obj.matrix_world, self._rest_co(obj))
                idx, dist = normal_utils.match_corners(src_anchors, anchors)
                worst_dist = max(worst_dist, float(dist.max()) if len(dist) else 0.0)

                m3 = np.array(obj.matrix_world.to_3x3(), np.float64)
                target = normal_utils.normalize(field[idx] @ m3)
                # Too far to be the same corner: leave that corner alone rather
                # than drag in a normal from somewhere else on the face
                far = dist > self.max_distance
                if far.any():
                    target[far] = normal_utils.corner_normals(me)[far]
                    skipped_total += int(far.sum())

                if me.shape_keys is not None and len(me.shape_keys.key_blocks) > 1:
                    deformed = shapekey_utils.shape_key_mix(obj)
                else:
                    deformed = None
                if deformed is None:
                    # Nothing to survive: the field can go in as-is
                    me.normals_split_custom_set(target.tolist())
                    normal_utils.clear_intent(me)
                    me.update()
                else:
                    # Store it as the target field, then encode so the deformed
                    # geometry is what decodes to it
                    normal_utils._intent_field(me, target)
                    _n, _fresh, resid = normal_utils.reencode_for_shape(me, deformed)
                    worst_resid = max(worst_resid, float(resid.max()) if len(resid) else 0.0)
                done += 1

            bpy.ops.ed.undo_push(message=MHW_OT_TransferNormals.bl_label)
            self.report({'INFO'}, T("ui.main_panel.tn_done").format(
                objs=done, src=src.name, dist=f"{worst_dist:.6f}",
                resid=f"{worst_resid:.3f}"))
            if skipped_total:
                self.report({'WARNING'}, T("ui.main_panel.tn_warn_unmatched").format(
                    n=skipped_total))
            return {'FINISHED'}
        finally:
            if back_to_edit:
                bpy.ops.object.mode_set(mode='EDIT')


class MHW_OT_SafeApplyTransform(bpy.types.Operator):
    """Bake the object's rotation and scale into the mesh while keeping the
custom split normals pointing where they were (see core/normal_utils.py)"""
    bl_idname = "mhw.safe_apply_transform"
    bl_label = "Safe Apply Base Transform"
    bl_options = {'REGISTER', 'UNDO'}

    apply_rotation: bpy.props.BoolProperty(name="Rotation", default=True)
    apply_scale: bpy.props.BoolProperty(name="Scale", default=True)
    apply_location: bpy.props.BoolProperty(name="Location", default=False)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.sat_tip")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(self, "apply_rotation", text=T("ui.main_panel.sat_field_rotation"))
        col.prop(self, "apply_scale", text=T("ui.main_panel.sat_field_scale"))
        col.prop(self, "apply_location", text=T("ui.main_panel.sat_field_location"))

    def execute(self, context):
        import numpy as np
        from . import normal_utils

        if not (self.apply_rotation or self.apply_scale or self.apply_location):
            self.report({'ERROR'}, T("ui.main_panel.sat_err_nothing"))
            return {'CANCELLED'}

        back_to_edit = context.mode == 'EDIT_MESH'
        if back_to_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            objects = [o for o in context.selected_objects if o.type == 'MESH']
            active = context.active_object
            if active is not None and active.type == 'MESH' and active not in objects:
                objects.append(active)
            # transform_apply refuses multi-user data, and it acts on the whole
            # selection, so the ones it would refuse have to leave the selection
            # rather than just be skipped in the loop below
            shared = [o for o in objects if o.data.users > 1]
            for o in shared:
                o.select_set(False)
            objects = [o for o in objects if o.data.users == 1]
            if not objects:
                self.report({'ERROR'}, T("ui.main_panel.sat_err_no_meshes"))
                return {'CANCELLED'}

            # The normals wait out the bake inside the mesh, so Blender's own
            # corner bookkeeping carries them across the winding flip
            stashed = [o for o in objects if normal_utils.stash_normals(o.data, o.matrix_world)]

            bpy.ops.object.transform_apply(
                location=self.apply_location, rotation=self.apply_rotation,
                scale=self.apply_scale)

            worst = 0.0
            for obj in stashed:
                resid = normal_utils.unstash_normals(obj.data, obj.matrix_world)
                if resid is None:
                    self.report({'ERROR'}, T("ui.main_panel.sat_err_lost_carry").format(
                        obj=obj.name))
                    return {'CANCELLED'}
                worst = max(worst, float(np.max(resid)) if len(resid) else 0.0)

            # normals_split_custom_set writes through bpy.data, which the undo
            # stack does not see on its own; without this the operator's own
            # 'UNDO' would roll back the transform and leave the normals rewritten
            bpy.ops.ed.undo_push(message=MHW_OT_SafeApplyTransform.bl_label)

            self.report({'INFO'}, T("ui.main_panel.sat_done").format(
                objs=len(objects), kept=len(stashed), max=f"{worst:.3f}"))
            if shared:
                self.report({'WARNING'}, T("ui.main_panel.sat_warn_shared").format(
                    n=len(shared)))
            return {'FINISHED'}
        finally:
            if back_to_edit:
                bpy.ops.object.mode_set(mode='EDIT')


class MHW_OT_ApplyModifiersKeepShapeKeys(bpy.types.Operator):
    """Apply the viewport-enabled modifiers to a mesh that has shape keys,
rebuilding every key on top of the result (see core/shapekey_utils.py)"""
    bl_idname = "mhw.apply_modifiers_keep_shape_keys"
    bl_label = "Apply Modifiers (Keep Shape Keys)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and obj.data.shape_keys
                and len(obj.data.shape_keys.key_blocks) > 1
                and any(m.show_viewport for m in obj.modifiers))

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.amk_tip")

    def execute(self, context):
        from . import shapekey_utils

        obj = context.active_object
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        ok, msg_key, fmt = shapekey_utils.check(obj)
        if not ok:
            self.report({'ERROR'}, T(msg_key).format(**fmt))
            return {'CANCELLED'}

        try:
            mods, keys, verts = shapekey_utils.apply_modifiers_keep_shape_keys(obj)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        self.report({'INFO'}, T("ui.main_panel.amk_done").format(
            mods=mods, keys=keys, verts=verts))
        return {'FINISHED'}
class MHW_OT_SeparateByMaterials(bpy.types.Operator):
    """Split the selected meshes into one object per material, then tidy up the
shape keys and vertex groups each fragment inherited (see core/mesh_utils.py)"""
    bl_idname = "mhw.separate_by_materials"
    bl_label = "Separate by Materials"
    bl_options = {'REGISTER', 'UNDO'}

    rename: bpy.props.BoolProperty(
        name="Rename to Material", default=True,
        description="Name each fragment after the material that defined it")
    prune_keys: bpy.props.BoolProperty(
        name="Prune Dead Shape Keys", default=True,
        description="Remove shape keys that no longer move anything on the fragment")
    prune_groups: bpy.props.BoolProperty(
        name="Prune Empty Vertex Groups", default=True,
        description="Remove vertex groups nothing in the fragment is weighted to")
    clean_suffix: bpy.props.BoolProperty(
        name="Strip Material .001 Suffix", default=True,
        description="Rename mat.001 back to mat before naming the fragments after it")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.sbm_tip")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "rename", text=T("ui.main_panel.sbm_field_rename"))
        if self.rename:
            col.prop(self, "clean_suffix", text=T("ui.main_panel.sbm_field_clean_suffix"))
        col.prop(self, "prune_keys", text=T("ui.main_panel.sbm_field_prune_keys"))
        col.prop(self, "prune_groups", text=T("ui.main_panel.sbm_field_prune_groups"))

    def execute(self, context):
        from . import mesh_utils

        objects = [o for o in context.selected_objects if o.type == 'MESH']
        n, keys, groups = mesh_utils.separate_by_materials(
            context, objects,
            rename=self.rename, prune_keys=self.prune_keys,
            prune_groups=self.prune_groups,
            clean_suffix=self.clean_suffix and self.rename)
        if not n:
            self.report({'ERROR'}, T("ui.main_panel.sbm_no_mesh"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("ui.main_panel.sbm_done").format(
            n=n, keys=keys, groups=groups))
        return {'FINISHED'}
class MHW_OT_CreateOutline(bpy.types.Operator):
    """Create a brand new dedicated "<name>_Outline" shell object for each
selected mesh (backface-culled black material + flipped-normal Solidify on a
full duplicate, auto-applied — vertex groups, shape keys and the modifier
stack, including any Armature binding, come along for the ride). The source
mesh itself is never touched. Every run is independent — no tracking back to
the source, so running it again just adds another shell rather than
replacing one (see core/mesh_utils.py)"""
    bl_idname = "mhw.create_outline"
    bl_label = "Create Outline"
    bl_options = {'REGISTER', 'UNDO'}

    vertex_group_name: bpy.props.StringProperty(
        name="Thickness Vertex Group", default="",
        description="Optional vertex group controlling per-vertex outline thickness "
                    "(0 = no outline there, e.g. eyes/mouth interior); leave empty for uniform thickness")
    thickness: bpy.props.FloatProperty(
        name="Thickness", default=0.001, min=0.0, precision=4,
        description="Solidify thickness on the newly created outline shell")
    ignore_collection_name: bpy.props.StringProperty(
        name="Ignore Collection", default="IgnoreExport",
        description="Objects in this collection (or its sub-collections) are skipped")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    @classmethod
    def description(cls, context, properties):
        return T("ui.main_panel.outline_tip")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        col = self.layout.column()
        obj = context.active_object
        if obj and obj.type == 'MESH':
            col.prop_search(self, "vertex_group_name", obj, "vertex_groups",
                             text=T("ui.main_panel.outline_field_vgroup"))
        else:
            col.prop(self, "vertex_group_name", text=T("ui.main_panel.outline_field_vgroup"))
        col.prop(self, "thickness", text=T("ui.main_panel.outline_field_thickness"))
        col.prop(self, "ignore_collection_name", text=T("ui.main_panel.outline_field_ignore_collection"))

    def execute(self, context):
        from . import mesh_utils

        objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not objects:
            self.report({'ERROR'}, T("ui.main_panel.outline_no_mesh"))
            return {'CANCELLED'}

        added, missing_vg, not_baked = mesh_utils.create_outline_shell(
            context, objects,
            vertex_group_name=self.vertex_group_name,
            thickness=self.thickness,
            ignore_collection_name=self.ignore_collection_name,
        )
        if not added:
            self.report({'WARNING'}, T("ui.main_panel.outline_all_ignored"))
            return {'CANCELLED'}

        msg = T("ui.main_panel.outline_done").format(added=added)
        if missing_vg:
            msg += T("ui.main_panel.outline_warn_missing_vgroup_suffix").format(n=missing_vg)
        if not_baked:
            msg += T("ui.main_panel.outline_warn_not_baked_suffix").format(n=not_baked)
        self.report({'INFO'}, msg)
        return {'FINISHED'}
_RENAMED_VG_PATTERN = re.compile(r'^(.+)\.\d{3}$')
class MHW_OT_MergeRenamedVGroups(bpy.types.Operator):
    """Merge vertex groups named 'a.001', 'a.002', etc. into 'a' for all selected meshes.
Groups whose suffixed name matches a real bone in the bound armature are skipped."""
    bl_idname = "mhw.merge_renamed_vgroups"
    bl_label = "Merge Renamed Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        total_merged = 0
        total_skipped = 0

        for obj in mesh_objects:
            bound_arm = next(
                (mod.object for mod in obj.modifiers
                 if mod.type == 'ARMATURE' and mod.object),
                None
            )
            arm_bone_names = {b.name for b in bound_arm.data.bones} if bound_arm else set()

            to_merge = {}
            for vg in obj.vertex_groups:
                m = _RENAMED_VG_PATTERN.match(vg.name)
                if not m:
                    continue
                if vg.name in arm_bone_names:
                    total_skipped += 1
                    continue
                base = m.group(1)
                to_merge.setdefault(base, []).append(vg.name)

            for base_name, suffix_names in to_merge.items():
                weight_utils.merge_vgroups_multi(obj, suffix_names, base_name)
                total_merged += len(suffix_names)

        self.report(
            {'INFO'},
            T("ui.main_panel.merge_vg_done").format(merged=total_merged, skipped=total_skipped)
        )
        return {'FINISHED'}


# ── register / unregister ─────────────────────────────────────────────────────

classes = [
    MHW_OT_ShapeKeyToWeights,
    MHW_OT_MMDFaceWeights,
    MHW_OT_CylindricalFaceNormals,
    MHW_OT_ResetFaceNormals,
    MHW_OT_FixShapeKeyNormals,
    MHW_OT_SafeApplyTransform,
    MHW_OT_TransferNormals,
    MHW_OT_ApplyModifiersKeepShapeKeys,
    MHW_OT_SeparateByMaterials,
    MHW_OT_CreateOutline,
    MHW_OT_MergeRenamedVGroups,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
