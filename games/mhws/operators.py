import os
import sys
import time
import bpy
from ...core.i18n import T
from ...core import weight_utils, facial_maps
from ...core import bone_utils
from ...core import ref_skeleton
from ...core import facial_bones
from ...core.bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from ...core.re_chain_utils import (
    REChainConfig,
    _decompose_chains,
    _is_valid_chain_collection,
    _patch_chain_cleanup,
    _build_physics_bones_set,
    auto_create_re_chains,
)
from ...core.standard_ops import _run_bone_color_refresh

# ============================================================
# Endfield 面部顶点组改名 (Endfield → MHWilds)
# ============================================================

# 表在 assets/facial_maps/endfield_to_mhws.json —— 见 core/facial_maps.py 的说明：
# 面部对应是人标的数据，不是逻辑，同一份东西不该在代码和 assets 下各存一份。
# 顺序有意义（先到的拿名字，后到的并进去），别对那个 JSON 做键排序。
def _endfield_to_mhws():
    return facial_maps.load("endfield_to_mhws")




class MHWS_OT_EndfieldFaceRename(bpy.types.Operator):
    bl_idname = "mhws.endfield_face_rename"
    bl_label = "Endfield Face Rename"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.endfield_face_rename_desc")

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        total = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for old_name, new_name in _endfield_to_mhws():
                if weight_utils.rename_or_merge_vgroup(obj, old_name, new_name):
                    total += 1
        self.report({'INFO'}, T("mhws.operators.endfield_processed").format(n=total))
        return {'FINISHED'}


# ============================================================
# 面部权重简化 (通用)
# ============================================================



def _transfer_partial(obj, source_names, targets_with_ratios):
    """从源顶点组按比例分配权重到多个目标，源保留剩余"""
    total_ratio = sum(r for __, r in targets_with_ratios)
    remain_ratio = 1.0 - total_ratio

    target_vgs = []
    for tgt_name, ratio in targets_with_ratios:
        tgt_vg = obj.vertex_groups.get(tgt_name)
        if tgt_vg is None:
            tgt_vg = obj.vertex_groups.new(name=tgt_name)
        target_vgs.append((tgt_vg, ratio))

    for src_name in source_names:
        src_vg = obj.vertex_groups.get(src_name)
        if src_vg is None:
            continue
        for vert in obj.data.vertices:
            try:
                src_w = src_vg.weight(vert.index)
            except RuntimeError:
                continue
            if src_w <= 0.0:
                continue
            for tgt_vg, ratio in target_vgs:
                try:
                    tgt_w = tgt_vg.weight(vert.index)
                except RuntimeError:
                    tgt_w = 0.0
                tgt_vg.add([vert.index], min(tgt_w + src_w * ratio, 1.0), 'REPLACE')
            src_vg.add([vert.index], src_w * remain_ratio, 'REPLACE')


class MHWS_OT_FaceWeightSimplify(bpy.types.Operator):
    bl_idname = "mhws.face_weight_simplify"
    bl_label = "Face Weight Simplify"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.face_weight_simplify_desc")

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        
        # 1. 合并到 Head
        weight_utils.merge_vgroups_multi(obj, [
            "L_malarFat_B_LOD01", "R_malarFat_B_LOD01",
            "L_CheekBone_LOD02", "R_CheekBone_LOD02",
            "C_Nose_LOD01", "C_TongueA_LOD01",
            "UpperTeeth", "HeadAll_SCL",
        ], "Head")
        
        # 2. 合并到 C_Chin_LOD01
        weight_utils.merge_vgroups_multi(obj, [
            "L_JawLine_LOD01", "R_JawLine_LOD01",
            "L_Cheek_LOD02", "R_Cheek_LOD02",
            "C_TongueB_LOD01", "C_TongueC_LOD01",
            "LowerTeeth",
        ], "C_Chin_LOD01")
        
        # 3. 下眼睑 60% -> 主骨骼
        _transfer_partial(obj, ["L_LoEyeLid_B_LOD00", "L_LoEyeLid_A_LOD00"],
                          [("L_LoEyeLid_LOD01", 0.6)])
        _transfer_partial(obj, ["R_LoEyeLid_B_LOD00", "R_LoEyeLid_A_LOD00"],
                          [("R_LoEyeLid_LOD01", 0.6)])
        
        # 4. 上眼睑 60% -> 主骨骼
        _transfer_partial(obj, ["R_UpEyeLid_B_LOD00", "R_UpEyeLid_A_LOD00"],
                          [("R_UpEyeLid_LOD01", 0.6)])
        _transfer_partial(obj, ["L_UpEyeLid_B_LOD00", "L_UpEyeLid_A_LOD00"],
                          [("L_UpEyeLid_LOD01", 0.6)])
        
        # 5. 眉毛 60% -> 主骨骼
        _transfer_partial(obj, ["R_EyeBrow_A_LOD01", "R_EyeBrow_C_LOD01"],
                          [("R_EyeBrow_B_LOD01", 0.6)])
        _transfer_partial(obj, ["L_EyeBrow_A_LOD01", "L_EyeBrow_C_LOD01"],
                          [("L_EyeBrow_B_LOD01", 0.6)])
        
        # 6. 双眼皮 60% -> 主骨骼
        _transfer_partial(obj, ["L_DoubleEyeLid_A_LOD00", "L_DoubleEyeLid_LOD01"],
                          [("L_DoubleEyeLid_B_LOD00", 0.6)])
        _transfer_partial(obj, ["R_DoubleEyeLid_A_LOD00", "R_DoubleEyeLid_LOD01"],
                          [("R_DoubleEyeLid_B_LOD00", 0.6)])
        
        # 7. 下嘴唇
        _transfer_partial(obj, ["L_loLip_AT_LOD00"], [("L_loLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["L_loLip_BT_LOD00"],
                          [("L_loLip_T_LOD01", 0.3), ("L_cornerLip_B_LOD01", 0.3)])
        _transfer_partial(obj, ["R_loLip_AT_LOD00"], [("R_loLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["R_loLip_BT_LOD00"],
                          [("R_loLip_T_LOD01", 0.3), ("R_cornerLip_B_LOD01", 0.3)])
        
        # 8. 上嘴唇
        _transfer_partial(obj, ["L_upLip_AT_LOD00"], [("L_upLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["L_upLip_BT_LOD00"],
                          [("L_upLip_T_LOD01", 0.3), ("L_cornerLip_B_LOD01", 0.3)])
        _transfer_partial(obj, ["R_upLip_AT_LOD00"], [("R_upLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["R_upLip_BT_LOD00"],
                          [("R_upLip_T_LOD01", 0.3), ("R_cornerLip_B_LOD01", 0.3)])
        
        # 9. 左右唇 60% -> 中央唇
        _transfer_partial(obj, ["R_loLip_T_LOD01", "L_loLip_T_LOD01"],
                          [("C_loLip_T_LOD01", 0.6)])
        _transfer_partial(obj, ["R_upLip_T_LOD01", "L_upLip_T_LOD01"],
                          [("C_upLip_T_LOD01", 0.6)])
        
        self.report({'INFO'}, T("mhws.operators.face_weight_simplify_done"))
        return {'FINISHED'}


# ============================================================
# 一键创建 RE Chain（实验性）
# ============================================================

# invoke 时动态填充，供 EnumProperty 回调使用
_chain_col_items = []


def _get_chain_col_items(self, context):
    return _chain_col_items


def _get_settings_mode_items(self, context):
    return [
        ('SHARED',   T("core.re_chain_utils.settings_mode_shared"),   T("core.re_chain_utils.settings_mode_shared_desc")),
        ('SEPARATE', T("core.re_chain_utils.settings_mode_separate"), T("mhws.operators.settings_mode_separate_desc")),
        ('GUESS',    T("mhws.operators.settings_mode_guess"),    T("mhws.operators.settings_mode_guess_desc")),
    ]


def _get_chain_format_items(self, context):
    return [
        ('.chain2', "Chain2", T("core.re_chain_utils.chain_format_chain2_desc")),
        ('.chain',  "Chain",  T("mhws.operators.chain_format_chain_desc")),
    ]


_MHWS_TUNING = {
    'calculateMode': '3', 'chainAttrFlags': '4',
    'calculateStepTime': 2.0, 'modelCollisionSearch': 1,
    'highFPSCalculateMode': '2',
    'wilds_unkn1': 1, 'wilds_unkn2': 1,
}


class MHWS_OT_AutoCreateChains(bpy.types.Operator):
    bl_idname = "mhws.auto_create_chains"
    bl_label = "One-Click Create RE Chain"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.auto_create_chains_desc")

    chain_collection: bpy.props.EnumProperty(
        name="Chain Collection",
        description="Select the Chain Collection to write to",
        items=_get_chain_col_items,
    )
    settings_mode: bpy.props.EnumProperty(
        name="Settings Mode",
        items=_get_settings_mode_items,
    )
    auto_create_collection: bpy.props.BoolProperty(
        name="Auto-create Collection",
        description="When checked, automatically create the Chain Collection and Header, no manual prep needed",
        default=False,
    )
    collection_name: bpy.props.StringProperty(
        name="Collection Name",
        description="Name of the newly created Chain Collection (without extension)",
        default="",
    )
    chain_format: bpy.props.EnumProperty(
        name="Chain Format",
        items=_get_chain_format_items,
    )
    apply_mhwilds_tuning: bpy.props.BoolProperty(
        name="Use Wilds-Tuned Header",
        description="Override Header parameters with MHWilds calibration values (calculateMode=Quality, etc.)",
        default=False,
    )
    straighten_orientation: bpy.props.BoolProperty(
        name="Bone Orientation Preprocessing",
        description="Before creation, reset all physics bones to point straight up with zero twist",
        default=False,
    )
    has_no_markers: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    auto_refresh: bpy.props.BoolProperty(
        name="Create Directly (auto-refresh bone colors)",
        description="Automatically run bone color refresh first, then attempt to create",
        default=False,
    )
    apply_angle_ramp: bpy.props.BoolProperty(
        name="Auto-apply Angle Ramp",
        description="After chain creation, automatically call apply_angle_limit_ramp (max 60°, 4-step ramp)",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE'
                and context.active_object is not None
                and context.active_object.type == 'ARMATURE'
                and hasattr(bpy.ops, 're_chain')
                and hasattr(bpy.ops.re_chain, 'create_chain_settings'))

    def invoke(self, context, event):
        arm = context.active_object
        self.has_no_markers = not any(
            pb.get("chain_role") in ("head", "branch_head")
            for pb in (arm.pose.bones if arm and arm.type == 'ARMATURE' else [])
        )

        global _chain_col_items
        _chain_col_items = [
            (col.name, col.name, "")
            for col in bpy.data.collections
            if _is_valid_chain_collection(col)
        ]

        # 预填集合名称：取骨架所属 mod3 集合名
        if not self.collection_name:
            col_name = context.scene.get("REMeshLastImportedCollection", "")
            if col_name and ".mesh" in col_name:
                self.collection_name = col_name.split(".mesh")[0]

        # 预选当前 RE Chain 面板已设置的集合
        toolpanel = getattr(context.scene, 're_chain_toolpanel', None)
        if toolpanel and toolpanel.chainCollection:
            cur = toolpanel.chainCollection.name
            if any(i[0] == cur for i in _chain_col_items):
                self.chain_collection = cur

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        if self.has_no_markers:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text=T("mhws.operators.no_markers_warning1"), icon='ERROR')
            col.label(text=T("mhws.operators.no_markers_warning2"))
            layout.prop(self, "auto_refresh", text=T("mhws.operators.auto_refresh_name"))
            if not self.auto_refresh:
                return
            layout.separator()
        row = layout.row()
        row.prop(self, "auto_create_collection", text=T("mhws.operators.auto_create_collection_name"))
        if self.auto_create_collection:
            layout.prop(self, "collection_name", text=T("core.re_chain_utils.collection"))
            layout.prop(self, "chain_format", expand=True, text=T("core.re_chain_utils.chain_format"))
            if self.chain_format == '.chain2':
                layout.prop(self, "apply_mhwilds_tuning", text=T("mhws.operators.apply_mhwilds_tuning_name"))
        else:
            layout.prop(self, "chain_collection")
        layout.prop(self, "settings_mode", expand=True, text=T("core.re_chain_utils.settings_mode"))
        layout.prop(self, "straighten_orientation", text=T("mhws.operators.straighten_orientation_name"))
        layout.prop(self, "apply_angle_ramp", text=T("mhws.operators.apply_angle_ramp_name"))

    def execute(self, context):
        armature = context.active_object
        if self.has_no_markers:
            if not self.auto_refresh:
                return {'CANCELLED'}
            ok, msg = _run_bone_color_refresh(context, armature)
            if not ok:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}

        config = REChainConfig(
            chain_format=self.chain_format,
            chain_file_type="chain2",
            auto_create_collection=self.auto_create_collection,
            collection_name=self.collection_name,
            tuning=_MHWS_TUNING if (self.auto_create_collection and self.apply_mhwilds_tuning) else None,
            settings_mode=self.settings_mode,
            selected_collection=self.chain_collection,
            straighten_orientation=self.straighten_orientation,
            collider_filter_path="System/Collision/Filter/Character/Character_Chain.cfil",
            apply_angle_ramp=self.apply_angle_ramp,
        )

        armature = context.active_object
        status = auto_create_re_chains(context, armature, config)

        if status == {'CANCELLED'}:
            self.report({'ERROR'}, T("mhws.operators.chain_create_failed"))
            return {'CANCELLED'}

        self.report({'INFO'}, T("mhws.operators.chain_create_done"))
        return {'FINISHED'}


# ============================================================
# 一键导入并对齐荒野模型 (MHWs)
# ============================================================

_PREPROCESS_X_CANDIDATES = ("MMD.json", "VRChat.json")
_PREPROCESS_MIN_RATIO = 0.30
_MHWS_REF_SKELETON_FILE = "MHWilds_Female.fbx"
_PREPROCESS_REF_ARM_BONES = (
    "L_UpperArm", "R_UpperArm",
    "L_Forearm",  "R_Forearm",
    "L_Hand",     "R_Hand",
)
_PREPROCESS_ARM_SLOTS = (
    "upperarm_L", "upperarm_R",
    "forearm_L",  "forearm_R",
    "hand_L",     "hand_R",
)

# 参考骨架(荒野原生模型)自带的表情骨照搬 MBT importMHWildsfmesh 的 merge_bone_list：
# 导入后先把这些表情骨合并/删除掉，再转 T-Pose——参考骨架本身没有网格，这一步纯粹是为了
# 让残留在场景里的参考骨架不至于带着两百多根表情骨，跟 MBT 的行为保持一致。
# fcParam_000~200 是表情捕捉用的驱动骨，数量固定，用生成式写更不容易抄错。
_MHWS_FACIAL_MERGE_BONES = (
    'HeadAll_SCL', 'Ear_SCL', 'Head_SCL', 'C_ForeHead_LOD02', 'L_ForeHead_LOD01',
    'R_ForeHead_LOD01', 'C_EyeBrow_LOD02', 'L_BetweenEyeBrow_LOD01', 'R_BetweenEyeBrow_LOD01',
    'L_EyeBrow_LOD02', 'L_EyeBrow_A_LOD01', 'L_EyeBrow_B_LOD01', 'L_EyeBrow_C_LOD01',
    'R_EyeBrow_LOD02', 'R_EyeBrow_A_LOD01', 'R_EyeBrow_B_LOD01', 'R_EyeBrow_C_LOD01',
    'L_Eye_Master', 'L_EyeJ_LOD02', 'L_DoubleEyeLidJ_LOD02', 'L_DoubleEyeLid_LOD01',
    'L_DoubleEyeLid_A_LOD00', 'L_DoubleEyeLid_B_LOD00', 'L_UpEyeLidJ_LOD02', 'L_UpEyeLid_LOD01',
    'L_UpEyeLid_A_LOD00', 'L_UpEyeLid_B_LOD00', 'L_LoEyeLidJ_LOD02', 'L_LoEyeLid_LOD01',
    'L_LoEyeLid_A_LOD00', 'L_LoEyeLid_B_LOD00', 'L_EyeBagJ_LOD02', 'L_EyeBagJ_LOD01',
    'L_EyeBagJ_A_LOD00', 'L_EyeBagJ_B_LOD00', 'L_OuterEyeJ_LOD02', 'L_UpOuterEyeJ_LOD01',
    'L_LoOuterEyeJ_LOD01', 'L_InnerEyeJ_LOD02', 'L_LoInnerEyeJ_LOD01', 'L_UpInnerEyeJ_LOD01',
    'R_Eye_Master', 'R_EyeJ_LOD02', 'R_DoubleEyeLidJ_LOD02', 'R_DoubleEyeLid_LOD01',
    'R_DoubleEyeLid_A_LOD00', 'R_DoubleEyeLid_B_LOD00', 'R_UpEyeLidJ_LOD02', 'R_UpEyeLid_LOD01',
    'R_UpEyeLid_A_LOD00', 'R_UpEyeLid_B_LOD00', 'R_LoEyeLidJ_LOD02', 'R_LoEyeLid_LOD01',
    'R_LoEyeLid_A_LOD00', 'R_LoEyeLid_B_LOD00', 'R_EyeBagJ_LOD02', 'R_EyeBagJ_LOD01',
    'R_EyeBagJ_A_LOD00', 'R_EyeBagJ_B_LOD00', 'R_InnerEyeJ_LOD02', 'R_UpInnerEyeJ_LOD01',
    'R_LoInnerEyeJ_LOD01', 'R_OuterEyeJ_LOD02', 'R_UpOuterEyeJ_LOD01', 'R_LoOuterEyeJ_LOD01',
    'C_Nose_Master', 'C_Nose_LOD02', 'L_NoseNaso_LOD02', 'R_NoseNaso_LOD02',
    'C_Nose_Master_LOD02', 'C_Nose_LOD01', 'L_Nose_LOD01', 'L_NoseUnder_LOD00', 'R_Nose_LOD01',
    'R_NoseUnder_LOD00', 'L_Naso_LOD02', 'R_Naso_LOD02', 'L_CheekBone_LOD02',
    'L_malarFat_A_LOD01', 'L_malarFat_B_LOD01', 'R_CheekBone_LOD02', 'R_malarFat_A_LOD01',
    'R_malarFat_B_LOD01', 'L_NasoB_LOD02', 'R_NasoB_LOD02', 'L_Cheek_LOD02', 'L_Cheek_LOD01',
    'C_Mouth_Master', 'C_upLip_LOD02', 'C_upLip_LOD01', 'C_upLip_T_LOD01', 'L_upLip_LOD02',
    'L_upLip_LOD01', 'L_upLip_A_LOD01', 'L_upLip_A_LOD00', 'L_upLip_AT_LOD00', 'L_upLip_B_LOD01',
    'L_upLip_B_LOD00', 'L_upLip_BT_LOD00', 'L_upLip_T_LOD01', 'R_upLip_LOD02', 'R_upLip_LOD01',
    'R_upLip_A_LOD01', 'R_upLip_A_LOD00', 'R_upLip_AT_LOD00', 'R_upLip_B_LOD01',
    'R_upLip_B_LOD00', 'R_upLip_BT_LOD00', 'R_upLip_T_LOD01', 'L_cornerLip_LOD02',
    'L_cornerLip_A_LOD01', 'L_cornerLip_B_LOD01', 'L_cornerLipInner_LOD01', 'R_cornerLip_LOD02',
    'R_cornerLip_A_LOD01', 'R_cornerLip_B_LOD01', 'R_cornerLipInner_LOD01', 'C_loLip_LOD02',
    'C_loLip_LOD01', 'C_loLip_T_LOD01', 'L_loLip_LOD02', 'L_loLip_LOD01', 'L_loLip_A_LOD01',
    'L_loLip_A_LOD00', 'L_loLip_AT_LOD00', 'L_loLip_B_LOD01', 'L_loLip_B_LOD00',
    'L_loLip_BT_LOD00', 'L_loLip_T_LOD01', 'R_loLip_LOD02', 'R_loLip_LOD01', 'R_loLip_A_LOD01',
    'R_loLip_A_LOD00', 'R_loLip_AT_LOD00', 'R_loLip_B_LOD01', 'R_loLip_B_LOD00',
    'R_loLip_BT_LOD00', 'R_loLip_T_LOD01', 'C_Jaw_LOD02', 'C_Chin_LOD01', 'C_Chin_LOD00',
    'L_JawLine_LOD01', 'L_JawLine_LOD00', 'R_JawLine_LOD01', 'R_JawLine_LOD00',
    'C_TongueA_LOD01', 'C_TongueB_LOD01', 'R_TongueB_LOD00', 'C_TongueC_LOD01',
    'L_TongueC_LOD00', 'R_TongueC_LOD00', 'L_TongueB_LOD00', 'LowerTeeth', 'C_UnderJaw_LOD02',
    'L_UnderJaw_LOD02', 'R_UnderJaw_LOD02', 'L_Temporal_LOD01', 'R_Temporal_LOD01',
    'L_Masseter_LOD01', 'R_Masseter_LOD01', 'R_Cheek_LOD02', 'R_Cheek_LOD01', 'HelmJoint_L_Hoho',
    'HelmJoint_L_Era', 'HelmJoint_Mayu', 'HelmJoint_Ago', 'HelmJoint_R_Era', 'HelmJoint_R_Hoho',
    'UpperTeeth',
) + tuple(f"fcParam_{i:03d}" for i in range(201))


def _merge_facial_bones_on_reference(armature_obj):
    """照搬 MBT 的合并算法：对 _MHWS_FACIAL_MERGE_BONES 里的每根骨骼，沿父链向上找到
    第一个不在这份名单里的祖先，合并权重并删除该骨骼。参考骨架没有网格，这里实际只做
    删骨骼；权重合并对将来有网格的调用方同样正确。返回实际删除的骨骼数。"""
    facial_set = set(_MHWS_FACIAL_MERGE_BONES)
    bones = armature_obj.data.bones
    pairs = []
    for name in _MHWS_FACIAL_MERGE_BONES:
        bone = bones.get(name)
        if bone is None:
            continue
        parent = bone.parent
        while parent is not None and parent.parent is not None and parent.name in facial_set:
            parent = parent.parent
        if parent is None:
            continue
        pairs.append((parent.name, name))

    if not pairs:
        return 0
    weight_utils.merge_weights_and_delete_bones(armature_obj, pairs)
    return len(pairs)


def _detect_mhws_y_preset(ref_arm_obj=None):
    """Detect the MHWS bone (Y) preset filename.

    Primary:  scan presets/bone/ for the first JSON whose preset_info.game_code
              equals 'MHWS' (filename-agnostic, survives renames/translations).
    Fallback: coverage-based auto-detection against *ref_arm_obj* — the MHWS
              reference armature imported in Step 3 — requires ≥ 95 % coverage.
    Returns the filename string (e.g. "怪猎荒野.json"), or None on failure.
    """
    import json as _json
    from ...core.bone_mapper import auto_detect_preset

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bone_dir = os.path.join(root_dir, "assets", "presets", "bone")
    if os.path.isdir(bone_dir):
        for fname in sorted(os.listdir(bone_dir)):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(bone_dir, fname), encoding='utf-8') as fh:
                    data = _json.load(fh)
                if data.get('preset_info', {}).get('game_code') == 'MHWS':
                    return fname
            except Exception:
                continue

    # Fallback: coverage detection against the imported MHWS reference armature
    if ref_arm_obj is not None:
        return auto_detect_preset(ref_arm_obj, is_import_x=False)
    return None


def _detect_source_preset(source_arm_obj):
    """Check MMD.json / VRChat.json coverage; return filename or None."""
    from ...core.ui_config import OPTIONAL_BONES
    best_preset = None
    best_ratio = 0.0
    for filename in _PREPROCESS_X_CANDIDATES:
        mapper = BoneMapManager()
        if not mapper.load_preset(filename, is_import_x=True):
            continue
        total = matched = 0
        for std_key in STANDARD_BONE_NAMES:
            if std_key in OPTIONAL_BONES:
                continue
            total += 1
            main, _ = mapper.get_matches_for_standard(source_arm_obj, std_key)
            if main:
                matched += 1
        if total == 0:
            continue
        ratio = matched / total
        if ratio > best_ratio:
            best_ratio = ratio
            best_preset = filename
    return best_preset if best_ratio >= _PREPROCESS_MIN_RATIO else None


def _calc_arm_scale(source_arm_obj, ref_arm_obj, detected_preset):
    """Return source/reference arm-bone average world-Z ratio."""
    mw_ref = ref_arm_obj.matrix_world
    ref_z = [
        (mw_ref @ ref_arm_obj.pose.bones[n].head).z
        for n in _PREPROCESS_REF_ARM_BONES
        if ref_arm_obj.pose.bones.get(n)
    ]

    mapper = BoneMapManager()
    mapper.load_preset(detected_preset, is_import_x=True)
    mw_src = source_arm_obj.matrix_world
    src_z = []
    for slot in _PREPROCESS_ARM_SLOTS:
        main_name, _ = mapper.get_matches_for_standard(source_arm_obj, slot)
        if main_name and source_arm_obj.pose.bones.get(main_name):
            src_z.append((mw_src @ source_arm_obj.pose.bones[main_name].head).z)

    if not ref_z or not src_z:
        return 1.0
    return (sum(ref_z) / len(ref_z)) / (sum(src_z) / len(src_z))


def _calc_y_offset(source_arm_obj, ref_arm_obj, detected_preset):
    """Return mean(ref_y) - mean(src_y) using arm-bone world-Y positions."""
    mw_ref = ref_arm_obj.matrix_world
    ref_y = [
        (mw_ref @ ref_arm_obj.pose.bones[n].head).y
        for n in _PREPROCESS_REF_ARM_BONES
        if ref_arm_obj.pose.bones.get(n)
    ]

    mapper = BoneMapManager()
    mapper.load_preset(detected_preset, is_import_x=True)
    mw_src = source_arm_obj.matrix_world
    src_y = []
    for slot in _PREPROCESS_ARM_SLOTS:
        main_name, _ = mapper.get_matches_for_standard(source_arm_obj, slot)
        if main_name and source_arm_obj.pose.bones.get(main_name):
            src_y.append((mw_src @ source_arm_obj.pose.bones[main_name].head).y)

    if not ref_y or not src_y:
        return 0.0
    return (sum(ref_y) / len(ref_y)) - (sum(src_y) / len(src_y))


class MHWS_OT_PreprocessModel(bpy.types.Operator):
    bl_idname = "mhws.preprocess_model"
    bl_label = "One-Click Import & Align Wilds Model"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.preprocess_model_desc")

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.type == 'ARMATURE'
        )

    def execute(self, context):
        settings = context.scene.mhw_suite_settings

        source_arm_obj = context.active_object
        if not source_arm_obj or source_arm_obj.type != 'ARMATURE':
            self.report({'WARNING'}, T("core.standard_ops.select_armature_first"))
            return {'CANCELLED'}

        # Step 1: auto-detect X preset (MMD / VRChat only)
        detected = _detect_source_preset(source_arm_obj)
        if detected is None:
            self.report({'WARNING'}, T("mhws.operators.mmd_vrchat_only"))
            return {'CANCELLED'}

        settings.import_preset_enum = detected
        settings.pose_import_preset_enum = detected

        # Step 2: MMD only — 方向计算
        if detected == "MMD.json":
            bpy.ops.object.select_all(action='DESELECT')
            source_arm_obj.select_set(True)
            context.view_layer.objects.active = source_arm_obj
            bpy.ops.modder.mmd_a_to_tpose()

        # Step 3: import reference skeleton (bundled, default A-Pose) + merge its facial
        # bones + convert to T-Pose (照搬 MBT importMHWildsfmesh 的两个选项，都默认开启)
        # + arm-scale calibration. T-Pose 转换必须先做——后面的缩放/偏移/对齐计算全都假定
        # 参考骨架是 T-Pose。
        ref_arm_obj = ref_skeleton.import_reference_armature('mhws', _MHWS_REF_SKELETON_FILE)
        if ref_arm_obj is None:
            self.report({'ERROR'}, T("mhws.operators.ref_skeleton_import_failed").format(name=_MHWS_REF_SKELETON_FILE))
            return {'CANCELLED'}

        _merge_facial_bones_on_reference(ref_arm_obj)

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        ref_arm_obj.select_set(True)
        context.view_layer.objects.active = ref_arm_obj
        bpy.ops.modder.ree_to_tpose()

        # Detect Y (bone) preset: game_code first, then coverage fallback
        y_preset = _detect_mhws_y_preset(ref_arm_obj)
        if y_preset is None:
            self.report({'WARNING'}, T("mhws.operators.no_wilds_preset_detected"))
            return {'CANCELLED'}
        settings.target_preset_enum = y_preset

        scale = _calc_arm_scale(source_arm_obj, ref_arm_obj, detected)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        source_arm_obj.select_set(True)
        context.view_layer.objects.active = source_arm_obj
        bpy.ops.transform.resize(value=(scale, scale, scale))
        bpy.ops.object.transform_apply(scale=True)

        # Step 4: Y-axis offset alignment
        context.view_layer.update()
        dy = _calc_y_offset(source_arm_obj, ref_arm_obj, detected)
        if abs(dy) > 1e-4:
            source_arm_obj.location.y += dy
            bpy.ops.object.select_all(action='DESELECT')
            source_arm_obj.select_set(True)
            for child in source_arm_obj.children:
                if child.type == 'MESH':
                    child.select_set(True)
            context.view_layer.objects.active = source_arm_obj
            bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

        # Step 5: skeleton alignment (source selected, ref as active)
        bpy.ops.object.select_all(action='DESELECT')
        source_arm_obj.select_set(True)
        ref_arm_obj.select_set(True)
        context.view_layer.objects.active = ref_arm_obj
        bpy.ops.modder.universal_snap()

        # Step 6: 对齐后自动跑经验修正。优化荒野骨架只做几何摆位，操作对象是 universal_snap
        # 真正改动的骨架——ref_arm_obj（荒野骨架，snap 时作为 active/Y 被吸附成这具模型的比例），
        # 不是 source_arm_obj（还挂着原始 MMD 骨架名，且网格此时仍绑定在它自己身上）。
        # 优化辅助骨骼及权重需要一具「Wilds 命名骨骼 + 已绑定该骨架的网格」同时具备的对象，
        # 但这一步流程里两者还没合到一起（网格仍绑在 source_arm_obj 上），放这里无法生效，不调用。
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        ref_arm_obj.select_set(True)
        context.view_layer.objects.active = ref_arm_obj
        bpy.ops.mhws.optimize_skeleton()

        self.report({'INFO'}, T("mhws.operators.preprocess_done"))
        return {'FINISHED'}


# ============================================================
# 一键添加表情骨 (从原版荒野骨架移植表情骨到目标骨架)
# ============================================================

_FACIAL_ROOT_BONE = "HeadAll_SCL"
_BLINK_TARGET_BONES = ("L_UpEyeLidJ_LOD02", "R_UpEyeLidJ_LOD02")


class MHWS_OT_AddFacialBones(bpy.types.Operator):
    bl_idname = "mhws.add_facial_bones"
    bl_label = "One-Click Add Facial Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.add_facial_bones_desc")

    target_armature: bpy.props.EnumProperty(
        name="Armature",
        description="Select the armature to add facial bones to",
        items=bone_utils.get_armature_enum_items,
    )
    increase_blink_amplitude: bpy.props.BoolProperty(
        name="Increase Blink Amplitude (for anime-style models)",
        description="Apply the fake-head method to the upper eyelid bones, increasing the deformation amplitude "
                    "of the eye-closing motion",
        default=False,
    )
    blink_radius_mult: bpy.props.FloatProperty(
        name="Blink Amplitude",
        description="How many times further the eyelid sweeps. 1 leaves the amplitude as authored. Exact on RE4 and MHWS, where the eyelid already pivots on the eyeball centre; on RE9 the lid joints pivot on the lid margin itself, so the same value there means a sweep of that many eyeball radii and 1 is already an increase",
        # The pivot only slides along +/-Y, so it can never get closer to the lid than
        # the perpendicular distance to the rotation axis -- measured at 0.22-0.32 eyeball
        # radii across all five reference skeletons. 0.5 keeps the whole range live.
        default=4.0, min=0.5, max=10.0,
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'ARMATURE' for o in bpy.data.objects)

    def invoke(self, context, event):
        active = context.active_object
        if active and active.type == 'ARMATURE':
            self.target_armature = active.name
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        note = layout.row()
        note.active = False
        note.label(text=T("mhws.operators.facial_bones_note"))
        layout.separator()
        layout.prop(self, "target_armature", text=T("mhws.operators.target_armature_name"))
        layout.prop(self, "increase_blink_amplitude", text=T("mhws.operators.increase_blink_amplitude_name"))
        if self.increase_blink_amplitude:
            row = layout.row()
            row.prop(self, "blink_radius_mult", text=T("core.facial_bones.blink_radius_mult"), slider=True)

    def execute(self, context):
        target_arm = bpy.data.objects.get(self.target_armature)
        if target_arm is None or target_arm.type != 'ARMATURE':
            self.report({'WARNING'}, T("core.re_chain_utils.select_valid_armature"))
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Step 1: 导入参考猎人骨架（内置资源，不依赖外部插件）
        ref_arm_obj = ref_skeleton.import_reference_armature('mhws', _MHWS_REF_SKELETON_FILE)
        if ref_arm_obj is None:
            self.report({'ERROR'}, T("mhws.operators.ref_skeleton_import_failed").format(name=_MHWS_REF_SKELETON_FILE))
            return {'CANCELLED'}

        try:
            # Step 2: 让参考骨架与选中骨架对齐（按同名骨骼对齐，仅位置）
            bone_utils.align_armatures_by_name(target_arm, ref_arm_obj, mode='POS_ONLY')

            # Step 3: 移植 HeadAll_SCL 及其所有子级
            created = facial_bones.graft_facial_bones(ref_arm_obj, target_arm, _FACIAL_ROOT_BONE)
            if created == 0:
                self.report({'WARNING'}, T("mhws.operators.no_facial_root_bone").format(name=_FACIAL_ROOT_BONE))
                return {'CANCELLED'}

            # Step 4: 假头法增加眨眼幅度
            fake_count = 0
            if self.increase_blink_amplitude:
                for bone_name in _BLINK_TARGET_BONES:
                    if facial_bones.apply_blink_fake_bone(target_arm, bone_name, self.blink_radius_mult):
                        fake_count += 1
        finally:
            # 参考骨架仅用于移植数据，用完即清除，避免残留在场景中
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            if ref_arm_obj.name in bpy.data.objects:
                bpy.data.objects.remove(ref_arm_obj, do_unlink=True)

        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target_arm.select_set(True)

        msg = T("core.facial_bones.facial_bones_added").format(n=created)
        if self.increase_blink_amplitude:
            msg += T("mhws.operators.blink_amplitude_added").format(n=fake_count)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# ============================================================
# 优化荒野骨架 (对齐后的经验修正，只操作目标骨架自身)
# ============================================================

# 需要移动到 Head/Neck_0 中点的骨骼
_OPT_NECK_BONES = ['Neck_1', 'HeadRX_HJ_01', 'Neck_1_HJ_00']
# Spine_1 头部在荒野骨架 rest 空间的原始局部坐标。
# MBT 里 2 段来源下 Spine_1 不被吸附、停在原位；但我们的 universal_snap 会随动把它平移走，
# 所以这里用死数据还原（编辑骨骼坐标为骨架局部空间，不受物体缩放/位移影响，对标准荒野骨架恒定）。
_OPT_SPINE1_REST_HEAD = (0.0, 0.000001, 1.141)
# Spine_1 相关骨骼（还原到原位）
_OPT_SPINE1_BONES = ['Spine_1', 'Spine_1_HJ_00']
# 需要移动到 Spine_1/Neck_0 中点的骨骼（照搬 MBT：Spine_2 落在 Spine_1 与 Neck_0 之间）
_OPT_SPINE2_BONES = ['Spine_2', 'Spine_2_HJ_00']
# 需要与 Hip 同点的骨骼
_OPT_SPINE0_BONES = ['Spine_0', 'Spine_0_HJ_00']
# 脚背贴地 Z 坐标 (与 MBT 一致)
_OPT_INSTEP_Z = 0.019999


def _opt_move_head_keep_direction(edit_bones, bone_name, new_head):
    """移动骨骼头部到 new_head，保持原有长度和方向。骨骼不存在时忽略。"""
    bone = edit_bones.get(bone_name)
    if bone is None:
        return
    original_length = (bone.tail - bone.head).length
    if original_length == 0:
        bone.head = new_head
        return
    direction = (bone.tail - bone.head).normalized()
    bone.head = new_head
    bone.tail = bone.head + direction * original_length


class MHWS_OT_OptimizeSkeleton(bpy.types.Operator):
    bl_idname = "mhws.optimize_skeleton"
    bl_label = "Optimize Wilds Skeleton"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.optimize_skeleton_desc")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm_obj = context.active_object

        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones

        # Neck_1 应位于 Head 与 Neck_0 的中点
        head_bone = edit_bones.get('Head')
        neck0_bone = edit_bones.get('Neck_0')
        if head_bone and neck0_bone:
            center = (head_bone.head + neck0_bone.head) / 2
            for name in _OPT_NECK_BONES:
                _opt_move_head_keep_direction(edit_bones, name, center)

        # 先把 Spine_1 还原到荒野原始位置（universal_snap 的随动会把它平移走），
        # 再让 Spine_2 落在 Spine_1 与 Neck_0 中点——复刻 MBT
        for name in _OPT_SPINE1_BONES:
            _opt_move_head_keep_direction(edit_bones, name, _OPT_SPINE1_REST_HEAD)
        spine1_bone = edit_bones.get('Spine_1')
        if spine1_bone and neck0_bone:
            center = (spine1_bone.head + neck0_bone.head) / 2
            for name in _OPT_SPINE2_BONES:
                _opt_move_head_keep_direction(edit_bones, name, center)

        # Instep 应位于 Foot 与 Toe 的中点，且 Z 坐标与 Toe 平齐（脚底贴地）
        for side in ('L', 'R'):
            foot_bone = edit_bones.get(f'{side}_Foot')
            toe_bone = edit_bones.get(f'{side}_Toe')
            if foot_bone and toe_bone:
                _opt_move_head_keep_direction(
                    edit_bones, f'{side}_Toe',
                    (toe_bone.head.x, toe_bone.head.y, _OPT_INSTEP_Z)
                )
                center = (
                    (foot_bone.head.x + toe_bone.head.x) / 2,
                    (foot_bone.head.y + toe_bone.head.y) / 2,
                    toe_bone.head.z,
                )
                _opt_move_head_keep_direction(edit_bones, f'{side}_Instep', center)

        # Knee 对齐到膝关节，Shin 在其正下方 0.01：
        # universal_snap 已把 Shin 头对齐到膝关节位置，先把 Knee 平移到该点（保持自身方向长度），
        # 再把 Shin 整体下移 0.01，使 Knee 恰在 Shin 正上方（仅 Z 相差），与 MBT 一致
        for side in ('L', 'R'):
            shin = edit_bones.get(f'{side}_Shin')
            if shin is None:
                continue
            knee = edit_bones.get(f'{side}_Knee')
            if knee is not None:
                offset = shin.head - knee.head
                knee.tail = knee.tail + offset
                knee.head = shin.head.copy()
            shin.head.z -= 0.01
            shin.tail.z -= 0.01

        # Spine_0 应与 Hip 同点，避免骑乘时臀部顶起
        hip_bone = edit_bones.get('Hip')
        if hip_bone:
            hip_head = hip_bone.head.copy()
            for name in _OPT_SPINE0_BONES:
                _opt_move_head_keep_direction(edit_bones, name, hip_head)

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, T("mhws.operators.optimize_skeleton_done"))
        return {'FINISHED'}


# ============================================================
# 优化辅助骨骼及权重 (HJ bones)
# ============================================================

# 将 HJ 辅助骨整体平移，使其头部与目标基础骨头部重合（保持 HJ 骨自身方向和长度）。
# 基础骨已由 universal_snap 对齐到位。映射参考 MBT MHWilds 的 HJ 吸附表，
# 转换为游戏骨架内部的基础骨目标。

# 中心骨（无侧别）：HJ 骨 -> 基础骨
_HJ_TO_BASE_CENTER = {
    "Neck_1_HJ_00":  "Neck_1",
    "Neck_0_HJ_00":  "Neck_0",
    "Spine_2_HJ_00": "Spine_2",
    "Spine_1_HJ_00": "Spine_1",
    "Spine_0_HJ_00": "Spine_0",
    "Hip_HJ_00":     "Hip",
}

# 侧别模板 {s} = L / R：HJ 骨 -> 基础骨（吸附到该基础骨头部）
_HJ_TO_BASE_SIDED = {
    # 肩部
    "{s}_Shoulder_HJ_00": "{s}_Shoulder",
    "{s}_Traps_HJ_00":    "{s}_Shoulder",
    "{s}_Traps_HJ_01":    "{s}_Shoulder",
    "{s}_Pec_HJ_00":      "{s}_Shoulder",
    "{s}_Pec_HJ_01":      "{s}_Shoulder",
    "{s}_Lats_HJ_00":     "{s}_Shoulder",
    "{s}_Lats_HJ_01":     "{s}_Shoulder",
    # 上臂
    "{s}_UpperArm_HJ_00":       "{s}_UpperArm",
    "{s}_UpperArmDouble_HJ_00": "{s}_UpperArm",
    "{s}_UpperArmTwist_HJ_00":  "{s}_UpperArm",
    "{s}_Deltoid_HJ_00":        "{s}_UpperArm",
    "{s}_Deltoid_HJ_01":        "{s}_UpperArm",
    "{s}_Deltoid_HJ_02":        "{s}_UpperArm",
    # 肘 / 前臂
    "{s}_Elbow_HJ_00":         "{s}_Forearm",
    "{s}_Forearm_HJ_00":       "{s}_Forearm",
    "{s}_ForearmDouble_HJ_00": "{s}_Forearm",
    "{s}_ForearmRY_HJ_00":     "{s}_Forearm",
    "{s}_ForearmRY_HJ_01":     "{s}_Forearm",
    "{s}_ForearmTwist_HJ_00":  "{s}_Forearm",
    # 手
    "{s}_Hand_HJ_00":   "{s}_Hand",
    "{s}_Hand_HJ_01":   "{s}_Hand",
    "{s}_HandRZ_HJ_00": "{s}_Hand",
    "{s}_Palm":         "{s}_Hand",
    # 大腿
    "{s}_Hip_HJ_00":       "{s}_Thigh",
    "{s}_Hip_HJ_01":       "{s}_Thigh",
    "{s}_ThighRZ_HJ_00":   "{s}_Thigh",
    "{s}_ThighRZ_HJ_01":   "{s}_Thigh",
    "{s}_ThighRX_HJ_00":   "{s}_Thigh",
    "{s}_ThighRX_HJ_01":   "{s}_Thigh",
    "{s}_ThighTwist_HJ_00": "{s}_Thigh",
    "{s}_ThighTwist_HJ_01": "{s}_Thigh",
    # 膝 / 小腿（膝关节位置由 {s}_Shin 头部代表）
    "{s}_ThighTwist_HJ_02": "{s}_Shin",
    "{s}_Calf_HJ_00":       "{s}_Shin",
    "{s}_Shin_HJ_00":       "{s}_Shin",
    "{s}_Shin_HJ_01":       "{s}_Shin",
    "{s}_Knee_HJ_00":       "{s}_Shin",
    "{s}_KneeDouble_HJ_00": "{s}_Shin",
    "{s}_KneeRX_HJ_00":     "{s}_Shin",
    # 脚
    "{s}_Foot_HJ_00": "{s}_Foot",
}

# 扭转类 HJ 骨 -> 两关节头部中点。MBT 里这些吸附到 MMD 的中段扭转骨
# (zArmTwist / zHandTwist)，游戏骨架内无对应参考点，用肢段中点近似。
_HJ_TO_MIDPOINT_SIDED = {
    "{s}_UpperArmTwist_HJ_01": ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_UpperArmTwist_HJ_02": ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_Triceps_HJ_00":       ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_Biceps_HJ_00":        ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_Biceps_HJ_01":        ("{s}_UpperArm", "{s}_Forearm"),
    "{s}_ForearmTwist_HJ_01":  ("{s}_Forearm",  "{s}_Hand"),
    "{s}_ForearmTwist_HJ_02":  ("{s}_Forearm",  "{s}_Hand"),
}


def _build_hj_move_tables():
    """展开侧别模板，返回 (direct, midpoint)。
    direct: {hj_name: base_name}；midpoint: {hj_name: (jointA, jointB)}"""
    direct = dict(_HJ_TO_BASE_CENTER)
    midpoint = {}
    for s in ("L", "R"):
        for hj_t, base_t in _HJ_TO_BASE_SIDED.items():
            direct[hj_t.format(s=s)] = base_t.format(s=s)
        for hj_t, (a_t, b_t) in _HJ_TO_MIDPOINT_SIDED.items():
            midpoint[hj_t.format(s=s)] = (a_t.format(s=s), b_t.format(s=s))
    return direct, midpoint

_HJ_MOVE_DIRECT, _HJ_MOVE_MIDPOINT = _build_hj_move_tables()

# 权重转移仍只针对原本这几对 (base_bone, hj_bone)：把基础骨顶点组改名/合并到 HJ 骨
_HJ_WEIGHT_PAIRS = [
    ("Neck_1",     "Neck_1_HJ_00"),
    ("Neck_0",     "Neck_0_HJ_00"),
    ("L_Shoulder", "L_Shoulder_HJ_00"),
    ("R_Shoulder", "R_Shoulder_HJ_00"),
    ("Spine_2",    "Spine_2_HJ_00"),
    ("Spine_1",    "Spine_1_HJ_00"),
    ("Spine_0",    "Spine_0_HJ_00"),
    ("L_Knee",     "L_Knee_HJ_00"),
    ("R_Knee",     "R_Knee_HJ_00"),
    ("Hip",        "Hip_HJ_00"),
]


class MHWS_OT_OptimizeAuxBones(bpy.types.Operator):
    bl_idname = "mhws.optimize_aux_bones"
    bl_label = "Optimize Auxiliary Bones & Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("mhws.operators.optimize_aux_bones_desc")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        arm_obj = context.active_object

        # --- Step 1: 编辑模式下移动 HJ 骨 ---
        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = arm_obj.data.edit_bones
        moved = 0

        def rigid_move(bone, target_head):
            offset = target_head - bone.head
            bone.tail = bone.tail + offset
            bone.head = target_head.copy()

        # 直接吸附到基础骨头部
        for hj_name, base_name in _HJ_MOVE_DIRECT.items():
            hj_bone = edit_bones.get(hj_name)
            base_bone = edit_bones.get(base_name)
            if hj_bone is None or base_bone is None:
                continue
            rigid_move(hj_bone, base_bone.head)
            moved += 1

        # 扭转类吸附到两关节头部中点
        for hj_name, (a_name, b_name) in _HJ_MOVE_MIDPOINT.items():
            hj_bone = edit_bones.get(hj_name)
            a_bone = edit_bones.get(a_name)
            b_bone = edit_bones.get(b_name)
            if hj_bone is None or a_bone is None or b_bone is None:
                continue
            rigid_move(hj_bone, (a_bone.head + b_bone.head) / 2)
            moved += 1

        bpy.ops.object.mode_set(mode='OBJECT')

        # --- Step 2: 权重转移（仅原本几对） ---
        bones = arm_obj.data.bones
        active_pairs = [
            (base, hj) for base, hj in _HJ_WEIGHT_PAIRS
            if bones.get(base) is not None and bones.get(hj) is not None
        ]

        mesh_objects = [
            o for o in bpy.data.objects
            if o.type == 'MESH'
            and any(m.type == 'ARMATURE' and m.object == arm_obj for m in o.modifiers)
        ]

        renamed = 0
        for obj in mesh_objects:
            for base_name, hj_name in active_pairs:
                if weight_utils.rename_or_merge_vgroup(obj, base_name, hj_name):
                    renamed += 1

        self.report(
            {'INFO'},
            T("mhws.operators.optimize_aux_bones_done").format(moved=moved, renamed=renamed)
        )
        return {'FINISHED'}


classes = [
    MHWS_OT_EndfieldFaceRename,
    MHWS_OT_FaceWeightSimplify,
    MHWS_OT_AutoCreateChains,
    MHWS_OT_PreprocessModel,
    MHWS_OT_AddFacialBones,
    MHWS_OT_OptimizeSkeleton,
    MHWS_OT_OptimizeAuxBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)