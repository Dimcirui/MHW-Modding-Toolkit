"""
姿态转换模块 (Pose Convert)

三层架构：
1. 方向计算: 简易工具，仅旋转上臂到水平
2. RE Engine 矩阵归零: RE Engine 专用的绝对矩阵覆盖
3. 姿态变换记录器: 通用相对变换系统
   - 录制: 从 A 姿态和 B 姿态骨架计算每根骨骼的相对旋转变换
   - 正向应用 (A→B): 施加变换
   - 逆向应用 (B→A): 施加逆变换
"""

import bpy
import json
import math
import os
import copy
import mathutils
from .i18n import T
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES, resolve_preset
from .bone_utils import get_import_presets_callback


# ============================================================
# 路径与枚举
# ============================================================

def _get_pose_presets_dir():
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(addon_dir, "assets", "presets", "pose")
    os.makedirs(d, exist_ok=True)
    return d

_pose_preset_cache = []

def _read_pose_preset_name(filepath, fallback):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f).get('preset_info', {}).get('name') or fallback
    except Exception:
        return fallback

def get_pose_presets_callback(self, context):
    global _pose_preset_cache
    _pose_preset_cache = []
    d = _get_pose_presets_dir()
    if os.path.exists(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                fallback = f[:-5]  # strip .json
                name = _read_pose_preset_name(os.path.join(d, f), fallback)
                _pose_preset_cache.append((f, name, ""))
    if not _pose_preset_cache:
        _pose_preset_cache.append(('NONE', T("core.pose_ops.no_record"), ""))
    return _pose_preset_cache


# ============================================================
# 1. MMD A转Tpose（固定只服务 MMD 骨架，不经过通用骨架预设）
# ============================================================

class MODDER_OT_MmdAToTPose(bpy.types.Operator):
    bl_idname = "modder.mmd_a_to_tpose"
    bl_label = "MMD A-Pose to T-Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.mmd_a_to_tpose_desc")

    def execute(self, context):
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.pose_ops.select_armature_first"))
            return {'CANCELLED'}

        # 固定使用 MMD 骨骼预设做模糊匹配，不再暴露通用预设下拉框——这个工具天生
        # 只服务 MMD 骨架（旋转上臂到水平方向，为 MMD 的 A-Pose 模型服务）。
        mapper = BoneMapManager()
        if not mapper.load_preset("MMD.json", is_import_x=True):
            self.report({'ERROR'}, T("core.pose_ops.cannot_load_armature_preset"))
            return {'CANCELLED'}

        arm_mw = arm_obj.matrix_world
        targets = [("upperarm_L", 1.0), ("upperarm_R", -1.0)]
        
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        pose_bones = arm_obj.pose.bones
        count = 0
        
        for std_key, sign in targets:
            main_name, __ = mapper.get_matches_for_standard(arm_obj, std_key)
            if not main_name or main_name not in pose_bones:
                continue
            
            pb = pose_bones[main_name]
            bone = arm_obj.data.bones[main_name]
            bone_vec = (arm_mw.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()
            target_dir = mathutils.Vector((sign, 0.0, 0.0))
            rotation = bone_vec.rotation_difference(target_dir)
            
            current_mat = pb.matrix.copy()
            rot_mat = rotation.to_matrix().to_4x4()
            new_mat = rot_mat @ current_mat
            new_mat[0][3] = current_mat[0][3]
            new_mat[1][3] = current_mat[1][3]
            new_mat[2][3] = current_mat[2][3]
            pb.matrix = new_mat
            bpy.context.view_layer.update()
            count += 1
        
        if count == 0:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'WARNING'}, T("core.pose_ops.upperarm_not_found"))
            return {'CANCELLED'}

        mesh_count = _apply_and_rebind(arm_obj)
        self.report({'INFO'}, T("core.pose_ops.mmd_a_to_tpose_done").format(bones=count, meshes=mesh_count))
        return {'FINISHED'}


# ============================================================
# 2. REE转Tpose（私有 RE Engine 骨架名单，自动识别游戏，不经过通用骨架预设）
# ============================================================
# 归零目标：把骨骼的世界朝向强制设成这一个固定基（骨骼 Y 轴对准世界 +Z）。实测荒野的标准
# T-pose 在名单内 28/28 根骨骼上精确等于这个基（0.00°），所以它就是"标准姿势"的定义。
_REE_ZERO_BASIS = mathutils.Matrix(((1.0, 0.0, 0.0),
                                    (0.0, 0.0, -1.0),
                                    (0.0, 1.0, 0.0)))

# RE9 的骨骼轴向约定逐骨骼不同（原生骨骼距上面这个基平均 118.8°，且左右不一致），没法用
# 同一个"朝上"目标——这正是它以前没法归零的原因。所以每根骨骼额外带一个修正矩阵 C，目标
# 变成 _REE_ZERO_BASIS @ C。整张表只有 6 个不同的值，按部位 + 左右分组：左臂/左手与
# family A 完全一致，右侧整体绕 X 翻 180°，腿绕 Z 转 90°，脚趾自成一套。
# 数值取自实测并已吸附成精确整数（原始值距 0/±1 最大只差 1.45e-3，det 均为 +1）。
_C_IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
_C_FLIP_X = ((1, 0, 0), (0, -1, 0), (0, 0, -1))
_C_LEG_L = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
_C_LEG_R = ((0, 1, 0), (1, 0, 0), (0, 0, -1))
_C_TOE_L = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
_C_TOE_R = ((0, 1, 0), (0, 0, -1), (-1, 0, 0))
# 中轴骨（髋/脊/颈/头）绕 Z 转 +90°，正好是 _C_LEG_L 的转置。只给跨游戏 C 用，见
# _build_re9_c_supplement。
_C_TORSO = ((0, -1, 0), (1, 0, 0), (0, 0, 1))

# 拇指：**唯一一组不是带符号置换阵的 C**，因为拇指本来就不轴对齐。原先按最近置换阵
# （绕 X 转 90°）吸附，与第三方参考脚本 RE4_to_RE9_Convert 的实测值差 44.7°(第一节)、
# 17.8°、18.9° —— 那三个数太大，不能再算"吸附残差"。这里直接采用脚本的实测矩阵：它是
# 目前唯一有实机验证的来源，而闸门只管反解出来的 C，表里的值原样使用。
# 右侧不是左侧的镜像取反那么简单（第二、三行整体变号，第一行不变），所以两侧都列全。
_C_THUMB = {
    "L_Hand_ThumbF_1": (( 0.77393, -0.44248, -0.45304),
                        (-0.25685,  0.43458, -0.86323),
                        ( 0.57884,  0.78445,  0.22268)),
    "L_Hand_ThumbF_2": (( 0.99539, -0.08890, -0.03592),
                        (-0.00840,  0.29229, -0.95630),
                        ( 0.09551,  0.95219,  0.29019)),
    "L_Hand_ThumbF_3": (( 0.98800, -0.10028, -0.11746),
                        (-0.08358,  0.29236, -0.95265),
                        ( 0.12987,  0.95103,  0.28047)),
    "R_Hand_ThumbF_1": (( 0.77393, -0.44248, -0.45304),
                        ( 0.25685, -0.43458,  0.86323),
                        (-0.57884, -0.78445, -0.22268)),
    "R_Hand_ThumbF_2": (( 0.99539, -0.08890, -0.03592),
                        ( 0.00840, -0.29229,  0.95629),
                        (-0.09551, -0.95219, -0.29019)),
    "R_Hand_ThumbF_3": (( 0.98800, -0.10028, -0.11745),
                        ( 0.08357, -0.29236,  0.95265),
                        (-0.12987, -0.95103, -0.28048)),
}


def _build_re9_correction():
    fingers = tuple(f"Hand_{finger}_{i}"
                    for finger in ("IndexF", "MiddleF", "RingF", "PinkyF")
                    for i in (1, 2, 3))
    out = {}
    for suffix in ("Arm_Upper", "Arm_Lower", "Arm_Hand", "Hand_Palm") + fingers:
        out["L_" + suffix] = _C_IDENTITY
        out["R_" + suffix] = _C_FLIP_X

    for suffix in ("Leg_Upper", "Leg_Lower", "Leg_Ankle"):
        out["L_" + suffix] = _C_LEG_L
        out["R_" + suffix] = _C_LEG_R
    out["L_Leg_Toes"] = _C_TOE_L
    out["R_Leg_Toes"] = _C_TOE_R
    return out


# 只有需要逐骨骼修正的游戏在这里出现；没有条目就等于全部用 _REE_ZERO_BASIS。
_REE_BONE_CORRECTION = {"RE9": _build_re9_correction()}


def _build_re9_c_supplement():
    """跨游戏轴向修正专用的补充条目 —— **刻意不进 T-Pose 归零名单**。

    这两组骨原先两张表里都没有，于是跨游戏移植时没有可信的 C 可用，被原样留在源游戏
    约定里 —— 右锁骨因此整根差 180°（实测对照手作 RE9 骨架 179.8°，拇指 89–106°）。

    数值是实测反解的，不是猜的：素材是同一个模型由作者手工分别做成 MHWS / RE4R / RE9
    三版（三版都在游戏里可用），把 MHWS 与 RE9 两具骨架归一化姿态后逐骨反解，取最近的
    带符号置换阵 —— 锁骨与手臂链同规律（左单位阵、右绕 X 翻 180°），拇指绕 X 转 90°、
    右侧镜像。

    ⚠ **为什么单独放一张表**：`_REE_TPOSE_BONES["RE9"]` 是直接取 `_REE_BONE_CORRECTION`
    的键构造的，所以往那张表里加骨等于让 `ree_to_tpose` 去**真的掰动**这些骨。拇指被
    刻意排除在归零名单之外是有理由的 —— 归零会改变它的实际朝向，而拇指的朝向要尽量
    保持原样。这里只补 C，不动归零名单。

    **中轴骨（髋/脊/颈/头）2026-08-19 补入，理由同上。** 它们同样不在归零名单里，于是
    C 只能靠反解，而反解量到的是"约定 + 两具骨架的脊椎曲度差"——曲度差随参考骨架换人而
    变，1.3° 的置换阵闸门有时放行有时拦下。实测 RE4R Leon 对 RE9 Leon：Hip 0.00°、
    Spine_1 0.90°（过闸）、Head 2.36°、Neck_1 3.29°、Spine_0 4.03°、Spine_2 4.95°
    （全被拦），**六根量到的都是同一个置换阵**，残差是曲度不是约定。被拦下的那几根于是
    保留源约定，同一条脊椎上一节转了一节没转 —— 就是用户报的"spine1 朝右、spine2 朝左"。
    换参考骨架（leon.fbx → grace.fbx）症状会变，这本身就说明它不该由反解来定。

    拇指原先也吸附成了置换阵（绕 X 转 90°），残差 27–29° 记在这里当已知损失。
    2026-08-19 改成实测矩阵，见 _C_THUMB。
    """
    out = {"L_Arm_Clavicle": _C_IDENTITY, "R_Arm_Clavicle": _C_FLIP_X}
    out.update(_C_THUMB)
    for name in ("Hip", "Spine_0", "Spine_1", "Spine_2",
                 "Neck_0", "Neck_1", "Head_0"):
        out[name] = _C_TORSO
    return out


#: 只供跨游戏移植使用的 C；合并方式见 core/mesh_port_ops.py。
_REE_C_SUPPLEMENT = {"RE9": _build_re9_c_supplement()}

# RE4R 与 MHWS 同属一个骨骼约定族——56 根基础骨名字完全相同，且在同一物理姿势下轴向
# 也一致（143 根里 115 根在 1° 内），所以 RE4R 不需要修正矩阵。但辅助骨命名两边不同
# （RE4 是 L_UpperArm_Twist_s1，荒野是 L_UpperArmTwist_HJ_01），得各自列。
_RE4R_LIMBS = (
    "L_UpperArm", "R_UpperArm", "L_Forearm", "R_Forearm", "L_Hand", "R_Hand",
    "L_Palm", "R_Palm",
    "L_IndexF1", "L_IndexF2", "L_IndexF3", "R_IndexF1", "R_IndexF2", "R_IndexF3",
    "L_MiddleF1", "L_MiddleF2", "L_MiddleF3", "R_MiddleF1", "R_MiddleF2", "R_MiddleF3",
    "L_RingF1", "L_RingF2", "L_RingF3", "R_RingF1", "R_RingF2", "R_RingF3",
    "L_PinkyF1", "L_PinkyF2", "L_PinkyF3", "R_PinkyF1", "R_PinkyF2", "R_PinkyF3",
    "L_Thigh", "R_Thigh", "L_Shin", "R_Shin", "L_Foot", "R_Foot", "L_Toe", "R_Toe",
)
# 这些扭转/辅助骨同时也是 RE4R 的识别特征：少了它们，荒野骨架对 RE4R 名单的覆盖率会
# 达到 1.0 而盖过 MHWS 自己的 0.987，导致误判。
_RE4R_TWISTS = (
    "L_UpperArm_Twist_s1", "L_UpperArm_Twist_s2", "L_Forearm_Twist_s1", "L_Forearm_Twist_s2",
    "R_UpperArm_Twist_s1", "R_UpperArm_Twist_s2", "R_Forearm_Twist_s1", "R_Forearm_Twist_s2",
    "L_Wrist_Twist_s", "R_Wrist_Twist_s", "L_Thigh_Twist_s", "R_Thigh_Twist_s",
    "L_Shin_Twist_s", "R_Shin_Twist_s",
    "L_Help_Elbow_s", "R_Help_Elbow_s", "L_Help_Knee_s", "R_Help_Knee_s",
)

# 街霸6 (SF6) 也属 family A——实测把肢体骨归到 _REE_ZERO_BASIS 后手臂精确水平（0.00°）、
# 各指骨链完全笔直（0.00°），所以同样不需要修正矩阵。但命名自成一套：中轴骨带 C_ 前缀
# （C_Hip/C_Spine1/C_Chest/C_Head）、ForeArm 的 A 大写、小腿叫 Knee、没有 Palm、无名指和
# 小指各有 4 节。扭转骨（L_ForeArm_1..5 / L_Shin_1..5）不必列出，_expand_inchain_helpers
# 会自动纳入；也不像 RE4R 那样需要靠辅助骨去区分，其他游戏对这份名单最高只有 0.25 分。
# 归零后无名指/小指掌骨仍有 6.5°/13.5° 张开角，这是解剖角度不是误差——family A 自己的标准
# T-pose 在同一关节上是 8~53°（荒野小指 26.8°、RE4R 食指 52.6°），SF6 比它们还小。
_SF6_LIMBS = (
    "L_UpperArm", "R_UpperArm", "L_ForeArm", "R_ForeArm", "L_Hand", "R_Hand",
    "L_Index1", "L_Index2", "L_Index3", "R_Index1", "R_Index2", "R_Index3",
    "L_Middle1", "L_Middle2", "L_Middle3", "R_Middle1", "R_Middle2", "R_Middle3",
    "L_Ring1", "L_Ring2", "L_Ring3", "L_Ring4", "R_Ring1", "R_Ring2", "R_Ring3", "R_Ring4",
    "L_Pinky1", "L_Pinky2", "L_Pinky3", "L_Pinky4",
    "R_Pinky1", "R_Pinky2", "R_Pinky3", "R_Pinky4",
    "L_Thigh", "R_Thigh", "L_Knee", "R_Knee", "L_Foot", "R_Foot",
)

# 崛起/曙光 (MHRS) 同属 family A——实测其标准 T-pose 骨架的 38 根肢体骨已经全部落在
# _REE_ZERO_BASIS 上（均值 0.278°，最大 0.352°），且往返验证通过：把它扰动成 A-pose
# （手臂水平度 61.1°）再归零，回到与原始逐位相同的 1.078°/0.156°，所以不需要修正矩阵。
# 名字取自 assets/presets/bone/mhwr.json 的 main 映射（老 RE Engine 命名：L_Arm_01 上臂、
# L_Arm_02 前臂、L_Arm_03 手、L_Leg_00..03 腿、L_Finger_00..15 手指）。注意右手无名指和
# 小指的编号比左手整体少 1（右手确实少一根骨），所以**不能靠左右镜像生成**这份名单。
# 扭转/权重骨（_T/_W）和拇指都不必列出：_expand_inchain_helpers 会按实测朝向决定——MHRS
# 的拇指与手同朝向（0.00°）会被纳入且不产生形变，荒野的拇指斜 45.56° 则自动落选。
_MHRS_LIMBS = (
    "L_Arm_01", "R_Arm_01", "L_Arm_02", "R_Arm_02", "L_Arm_03", "R_Arm_03",
    "L_Leg_00", "R_Leg_00", "L_Leg_01", "R_Leg_01",
    "L_Leg_02", "R_Leg_02", "L_Leg_03", "R_Leg_03",
    "L_Finger_03", "L_Finger_04", "L_Finger_05",      # 食指
    "R_Finger_03", "R_Finger_04", "R_Finger_05",
    "L_Finger_06", "L_Finger_07", "L_Finger_08",      # 中指
    "R_Finger_06", "R_Finger_07", "R_Finger_08",
    "L_Finger_10", "L_Finger_11", "L_Finger_12",      # 无名指（右手偏移 -1）
    "R_Finger_09", "R_Finger_10", "R_Finger_11",
    "L_Finger_13", "L_Finger_14", "L_Finger_15",      # 小指（右手偏移 -1）
    "R_Finger_12", "R_Finger_13", "R_Finger_14",
)

# 荒野 (MHWS) 名单直接照搬 MBT (Modder-Batch-Tool) MHWildstpose 算子里的完整骨骼名单——
# 跨游戏通用的 standard-key 预设系统只覆盖主链骨骼，没有 Knee/Instep/Palm 和全部扭转/物理
# 辅助骨 (_HJ_) 的标准键，归零后这些子骨仍停留在原始姿态，父骨被摆正后会跟着扭曲。
# 注意名单里没有锁骨和拇指——锁骨保持原朝向（UpperArm 挂在其骨尾上，一起摆正反而会带偏
# 位置），拇指天生斜向生长，用同一套"零"朝向硬掰只会拉直变形，因此也不包含它们。
# 以后要支持其他 RE Engine 游戏，在这里加一个新的 {game_code: bone_tuple} 条目即可；若该
# 游戏的轴向约定和 family A 不同，再往 _REE_BONE_CORRECTION 里加一份逐骨骼修正矩阵。
_REE_TPOSE_BONES = {
    "MHWS": (
        "L_UpperArm", "R_UpperArm", "L_Forearm", "R_Forearm", "L_Hand", "R_Hand",
        "L_Palm", "R_Palm",
        "L_IndexF1", "L_IndexF2", "L_IndexF3", "R_IndexF1", "R_IndexF2", "R_IndexF3",
        "L_MiddleF1", "L_MiddleF2", "L_MiddleF3", "R_MiddleF1", "R_MiddleF2", "R_MiddleF3",
        "L_RingF1", "L_RingF2", "L_RingF3", "R_RingF1", "R_RingF2", "R_RingF3",
        "L_PinkyF1", "L_PinkyF2", "L_PinkyF3", "R_PinkyF1", "R_PinkyF2", "R_PinkyF3",
        "L_HandRZ_HJ_00", "R_HandRZ_HJ_00",
        "L_IndexF_HJ_00", "L_IndexF_HJ_01", "L_IndexF_HJ_02", "L_IndexF_HJ_03", "L_IndexF_HJ_04",
        "R_IndexF_HJ_00", "R_IndexF_HJ_01", "R_IndexF_HJ_02", "R_IndexF_HJ_03", "R_IndexF_HJ_04",
        "L_MiddleF_HJ_00", "L_MiddleF_HJ_01", "L_MiddleF_HJ_02", "L_MiddleF_HJ_03", "L_MiddleF_HJ_04",
        "R_MiddleF_HJ_00", "R_MiddleF_HJ_01", "R_MiddleF_HJ_02", "R_MiddleF_HJ_03", "R_MiddleF_HJ_04",
        "L_RingF_HJ_00", "L_RingF_HJ_01", "L_RingF_HJ_02", "L_RingF_HJ_03", "L_RingF_HJ_04",
        "R_RingF_HJ_00", "R_RingF_HJ_01", "R_RingF_HJ_02", "R_RingF_HJ_03", "R_RingF_HJ_04",
        "L_PinkyF_HJ_00", "L_PinkyF_HJ_01", "L_PinkyF_HJ_02", "L_PinkyF_HJ_03", "L_PinkyF_HJ_04",
        "R_PinkyF_HJ_00", "R_PinkyF_HJ_01", "R_PinkyF_HJ_02", "R_PinkyF_HJ_03", "R_PinkyF_HJ_04",
        "L_Hand_HJ_00", "L_Hand_HJ_01", "R_Hand_HJ_00", "R_Hand_HJ_01",
        "L_ForearmTwist_HJ_00", "L_ForearmTwist_HJ_01", "L_ForearmTwist_HJ_02",
        "R_ForearmTwist_HJ_00", "R_ForearmTwist_HJ_01", "R_ForearmTwist_HJ_02",
        "L_ForearmRY_HJ_00", "L_ForearmRY_HJ_01", "R_ForearmRY_HJ_00", "R_ForearmRY_HJ_01",
        "L_Elbow_HJ_00", "R_Elbow_HJ_00",
        "L_UpperArmTwist_HJ_01", "L_UpperArmTwist_HJ_02", "R_UpperArmTwist_HJ_01", "R_UpperArmTwist_HJ_02",
        "L_Triceps_HJ_00", "R_Triceps_HJ_00",
        "L_Biceps_HJ_00", "L_Biceps_HJ_01", "R_Biceps_HJ_00", "R_Biceps_HJ_01",
        "L_Deltoid_HJ_00", "L_Deltoid_HJ_01", "L_Deltoid_HJ_02",
        "R_Deltoid_HJ_00", "R_Deltoid_HJ_01", "R_Deltoid_HJ_02",
        "L_Thigh", "R_Thigh", "L_Knee", "R_Knee", "L_Shin", "R_Shin",
        "L_Foot", "R_Foot", "L_Instep", "R_Instep", "L_Toe", "R_Toe",
        "L_Foot_HJ_00", "R_Foot_HJ_00", "L_Calf_HJ_00", "R_Calf_HJ_00",
        "L_Shin_HJ_00", "L_Shin_HJ_01", "R_Shin_HJ_00", "R_Shin_HJ_01",
        "L_Knee_HJ_00", "R_Knee_HJ_00", "L_KneeRX_HJ_00", "R_KneeRX_HJ_00",
        "L_ThighTwist_HJ_00", "L_ThighTwist_HJ_01", "L_ThighTwist_HJ_02",
        "R_ThighTwist_HJ_00", "R_ThighTwist_HJ_01", "R_ThighTwist_HJ_02",
        "L_ThighRZ_HJ_00", "L_ThighRZ_HJ_01", "R_ThighRZ_HJ_00", "R_ThighRZ_HJ_01",
        "L_ThighRX_HJ_00", "L_ThighRX_HJ_01", "R_ThighRX_HJ_00", "R_ThighRX_HJ_01",
        "L_Hip_HJ_00", "L_Hip_HJ_01", "R_Hip_HJ_00", "R_Hip_HJ_01",
    ),
    "RE4R": _RE4R_LIMBS + _RE4R_TWISTS,
    "RE9": tuple(_REE_BONE_CORRECTION["RE9"]),
    "SF6": _SF6_LIMBS,
    "MHRS": _MHRS_LIMBS,
    # DMC5 的真实骨架用的是和 RE4R 一模一样的肢体骨名（实测 pl0100：40 根一根不缺，
    # 脊椎是 Hip→Waist→Stomach→Chest，40 根肢体骨原生就落在 _REE_ZERO_BASIS 上），
    # 所以名单直接复用。注意 assets/presets/bone/dmc5.json 里那套 L_Arm_01/L_Finger_00
    # 命名对不上真实骨架（0/38 解析），别拿它当依据。
    # 光靠覆盖率无法把 DMC5 和 RE4R/荒野分开——三者共用这 40 个名字，所以靠下面的
    # _REE_SIGNATURE_BONES 定案。
    "DMC5": _RE4R_LIMBS,
}

# 识别用的特征骨：只参与游戏判定，不参与归零。某个游戏在这里有条目时，特征骨必须全部
# 存在才允许被判定为该游戏。
# 为什么需要：DMC5 与 RE4R 的肢体骨名完全相同，两者互认其实无害（实测同一骨架走两条路
# 得到的归零骨骼集完全一致），但 DMC5 名单会在**所有** family A 骨架上拿到 0.909 分，
# 一个残缺的荒野骨架可能被它抢走——那才是真问题：荒野走 DMC5 路只会处理 128 根而不是
# 148 根，少掉的 20 根辅助骨会被摆正的父骨带着扭曲。
# RE4R 明确没有 Stomach，DMC5 有，这一根就够定案（已在五套骨架上逐个核对）。
_REE_SIGNATURE_BONES = {
    "DMC5": ("Stomach",),
}

# 覆盖率门槛：匹配到的骨骼数 / 该游戏名单总数，达到此比例才认定为该游戏骨架
_REE_MIN_COVERAGE = 0.3


def _detect_ree_game(arm_obj):
    """在私有 REE 游戏名单里按骨骼名覆盖率找最匹配的游戏，返回 game_code 或 None。
    在 _REE_SIGNATURE_BONES 里登记过特征骨的游戏，特征骨缺一根就不参与竞争。"""
    existing = arm_obj.data.bones.keys()
    best_code, best_ratio = None, 0.0
    for code, bone_list in _REE_TPOSE_BONES.items():
        signature = _REE_SIGNATURE_BONES.get(code)
        if signature and not all(name in existing for name in signature):
            continue
        ratio = sum(1 for name in bone_list if name in existing) / len(bone_list)
        if ratio > best_ratio:
            best_code, best_ratio = code, ratio
    return best_code if best_ratio >= _REE_MIN_COVERAGE else None


def _bone_depth(bone):
    depth, parent = 0, bone.parent
    while parent is not None:
        depth += 1
        parent = parent.parent
    return depth


def _expand_inchain_helpers(arm_obj, bone_names, corrections, tol_deg=0.5):
    """把"骑"在已归零骨骼上的链内辅助骨一起纳入，返回 (追加的骨骼名, 追加的修正矩阵)。

    只摆正主链会把辅助骨留在原始朝向，父骨一摆正它们就跟着扭曲。这里不手写名单，而是
    按两个可证的条件挑：最近的已归零祖先存在，且自身静止朝向与该祖先一致——这种骨骼本来
    就随父骨刚性移动，给它同一个目标朝向等于"保持跟随"，不会引入新的形变。朝向与祖先不
    同的（头发、裙摆、挂件等）自动落选，因为它们的祖先（Head/Hip/Spine）本就不在名单里。

    实测：荒野新增 0 根（现有手写名单对该骨架已完备，所以这一步对荒野是无操作）、
    RE4R 新增 2 根（扭转骨已显式列入名单，剩下的是 L/R_Wep 武器挂点）、
    RE9 里昂新增 178 根、RE9 Grace 新增 170 根。
    """
    listed = set(bone_names)
    extra_names, extra_corrections = [], {}
    for bone in arm_obj.data.bones:
        if bone.name in listed:
            continue
        ancestor = bone.parent
        while ancestor is not None and ancestor.name not in listed:
            ancestor = ancestor.parent
        if ancestor is None:
            continue
        delta = (bone.matrix_local.to_3x3().normalized().inverted()
                 @ ancestor.matrix_local.to_3x3().normalized())
        if math.degrees(delta.to_quaternion().angle) >= tol_deg:
            continue
        extra_names.append(bone.name)
        if corrections is not None and ancestor.name in corrections:
            extra_corrections[bone.name] = corrections[ancestor.name]
    return extra_names, extra_corrections


def zero_pose_bone_rotations(arm_obj, bone_names, corrections=None):
    """将 bone_names 中每根骨骼的姿态旋转矩阵强制设为归零朝向（保留原有位置不变）。

    corrections 给出逐骨骼的轴向修正矩阵 C，目标为 _REE_ZERO_BASIS @ C；缺省或某根骨骼
    不在其中时直接用 _REE_ZERO_BASIS（family A 的行为）。调用方自行处理模式切换；返回
    处理的骨骼数。

    **按骨骼深度分批求值**，而不是每根骨写完就求值一次。每根骨的位置要读父骨摆正之后的
    结果，所以父子之间必须有一次依赖图求值——但同一深度的骨彼此不是祖先关系，它们的父骨
    在上一批就已经就位，因此一层只需要一次。写姿态会让骨架及其依赖项一起失效重算，代价
    远高于一次空求值：实测（RE9 骨架 190 根骨，场景里挂着上千个 CHILD_OF 到这些骨的链
    物件）单次空求值 0.7 ms，而逐骨求值下每根骨要 24 ms、整体 4.5 秒；分批后求值次数从
    骨骼数降到骨架深度（十几次）。
    """
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='DESELECT')
    pose_bones = arm_obj.pose.bones
    data_bones = arm_obj.data.bones

    def depth(name):
        n, bone = 0, data_bones.get(name)
        while bone is not None and bone.parent is not None:
            n, bone = n + 1, bone.parent
        return n

    levels = {}
    for bone_name in bone_names:
        if bone_name in pose_bones:
            levels.setdefault(depth(bone_name), []).append(bone_name)

    count = 0
    for level in sorted(levels):
        bpy.context.view_layer.update()     # parents of this level are now in place
        for bone_name in levels[level]:
            correction = None if corrections is None else corrections.get(bone_name)
            basis = (_REE_ZERO_BASIS if correction is None
                     else _REE_ZERO_BASIS @ mathutils.Matrix(correction))
            pb = pose_bones[bone_name]
            zero = pb.matrix.copy()
            for row in range(3):
                for col in range(3):
                    zero[row][col] = basis[row][col]
            zero[3][0] = 0.0;  zero[3][1] = 0.0;  zero[3][2] = 0.0;  zero[3][3] = 1.0
            pb.matrix = zero
            count += 1
    bpy.context.view_layer.update()
    return count


class MODDER_OT_ReeToTPose(bpy.types.Operator):
    bl_idname = "modder.ree_to_tpose"
    bl_label = "REE to T-Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.ree_to_tpose_desc")

    def execute(self, context):
        arm_obj = context.active_object

        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.pose_ops.select_armature_first"))
            return {'CANCELLED'}

        game_code = _detect_ree_game(arm_obj)
        if game_code is None:
            self.report({'ERROR'}, T("core.pose_ops.ree_game_not_recognized"))
            return {'CANCELLED'}

        bones = arm_obj.data.bones
        bone_names = [name for name in _REE_TPOSE_BONES[game_code] if name in bones]
        corrections = _REE_BONE_CORRECTION.get(game_code)

        extra_names, extra_corrections = _expand_inchain_helpers(arm_obj, bone_names, corrections)
        bone_names += extra_names
        if extra_corrections:
            corrections = {**corrections, **extra_corrections}
        # 父骨必须先摆正——子骨的位置读的是父骨摆正后的结果。按层级深度排序保证这一点；
        # 荒野原有的手写顺序本就是拓扑序，所以排序对它是无操作。
        bone_names.sort(key=lambda name: _bone_depth(bones[name]))

        count = zero_pose_bone_rotations(arm_obj, bone_names, corrections)
        mesh_count = _apply_and_rebind(arm_obj)
        self.report(
            {'INFO'},
            T("core.pose_ops.ree_to_tpose_done").format(game=game_code, bones=count, meshes=mesh_count)
        )
        return {'FINISHED'}


# ============================================================
# 3. 姿态变换记录器（相对变换系统）
# ============================================================

class MODDER_OT_RecordTransform(bpy.types.Operator):
    bl_idname = "modder.record_transform"
    bl_label = "Record Transform"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.record_transform_desc")

    preset_name: bpy.props.StringProperty(
        name="Name",
        default="新姿态变换",
        description="Filename for the saved transform record (e.g. MMD A-Pose to T-Pose)"
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name", text=T("core.pose_ops.record_name_label"))
        self.layout.label(text=T("core.pose_ops.record_transform_hint"), icon='INFO')

    def execute(self, context):
        # 1. 获取两个骨架
        selected_arms = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected_arms) < 2:
            self.report({'ERROR'}, T("core.pose_ops.select_two_armatures"))
            return {'CANCELLED'}

        if not self.preset_name.strip():
            self.report({'ERROR'}, T("core.pose_ops.name_cannot_be_empty"))
            return {'CANCELLED'}

        # 活动对象 = B 姿态 (后选的), 另一个 = A 姿态 (先选的)
        arm_b = context.active_object
        arm_a = None
        for obj in selected_arms:
            if obj != arm_b:
                arm_a = obj
                break

        if not arm_a or not arm_b or arm_a.type != 'ARMATURE' or arm_b.type != 'ARMATURE':
            self.report({'ERROR'}, T("core.pose_ops.ensure_two_armatures"))
            return {'CANCELLED'}
        
        # 2. 收集 A 骨架每根骨骼的局部朝向 (相对于父级的 rest pose 朝向)
        local_rots_a = {}
        for bone in arm_a.data.bones:
            if bone.parent:
                local_mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local_mat = bone.matrix_local.copy()
            local_rots_a[bone.name] = local_mat.to_quaternion()
        
        # 3. 收集 B 骨架每根骨骼的局部朝向
        local_rots_b = {}
        for bone in arm_b.data.bones:
            if bone.parent:
                local_mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
            else:
                local_mat = bone.matrix_local.copy()
            local_rots_b[bone.name] = local_mat.to_quaternion()
        
        # 4. 计算相对变换: delta = Qb × Qa⁻¹ (每根骨骼各自的局部旋转差异)
        #    这是骨骼相对于自身父级的旋转变化量, 不含父子累积
        transforms = {}
        common_bones = set(local_rots_a.keys()) & set(local_rots_b.keys())

        if not common_bones:
            self.report({'ERROR'}, T("core.pose_ops.no_common_bones"))
            return {'CANCELLED'}
        
        significant_count = 0
        for bone_name in common_bones:
            qa = local_rots_a[bone_name]
            qb = local_rots_b[bone_name]
            
            # delta = Qb × Qa⁻¹ (从 A 朝向旋转到 B 朝向的变化量)
            qa_inv = qa.copy()
            qa_inv.invert()
            delta = qb @ qa_inv
            
            # 检查是否接近单位四元数 (即几乎没有变化的骨骼)
            identity_dot = abs(delta.w)
            if identity_dot > 0.9999:
                continue
            
            transforms[bone_name] = [delta.w, delta.x, delta.y, delta.z]
            significant_count += 1
        
        if significant_count == 0:
            self.report({'WARNING'}, T("core.pose_ops.poses_nearly_identical"))
            return {'CANCELLED'}
        
        filename = self.preset_name.strip()
        for ch in '<>:"/\\|?*':
            filename = filename.replace(ch, '')

        # 5. 保存 JSON
        data = {
            "preset_info": {
                "name": filename,
            },
            "type": "pose_relative_transform",
            "version": "2.0",
            "source_a": arm_a.data.name,
            "source_b": arm_b.data.name,
            "description": f"{arm_a.name} -> {arm_b.name}",
            "bone_count": significant_count,
            "transforms": transforms
        }
        filepath = os.path.join(_get_pose_presets_dir(), filename + ".json")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.report({'INFO'}, T("core.pose_ops.recorded_transform").format(
                n=significant_count, filename=filename + ".json"))
        except Exception as e:
            self.report({'ERROR'}, T("core.pose_ops.save_failed").format(err=e))
            return {'CANCELLED'}
        
        # 恢复活动对象
        bpy.context.view_layer.objects.active = arm_b
        return {'FINISHED'}


class MODDER_OT_ApplyTransformForward(bpy.types.Operator):
    bl_idname = "modder.apply_transform_forward"
    bl_label = "Forward (A->B)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.apply_forward_desc")

    def execute(self, context):
        return _apply_transform(self, context, inverse=False)


class MODDER_OT_ApplyTransformInverse(bpy.types.Operator):
    bl_idname = "modder.apply_transform_inverse"
    bl_label = "Inverse (B->A)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.apply_inverse_desc")

    def execute(self, context):
        return _apply_transform(self, context, inverse=True)


def _apply_transform(operator, context, inverse=False):
    """应用相对变换的核心逻辑 (正向或逆向)"""
    settings = context.scene.mhw_suite_settings
    arm_obj = context.active_object

    if not arm_obj or arm_obj.type != 'ARMATURE':
        operator.report({'ERROR'}, T("core.pose_ops.select_armature_first"))
        return {'CANCELLED'}

    selected_file = settings.pose_preset_enum
    if not selected_file or selected_file == 'NONE':
        operator.report({'ERROR'}, T("core.pose_ops.no_transform_selected"))
        return {'CANCELLED'}

    # 读取 JSON
    filepath = os.path.join(_get_pose_presets_dir(), selected_file)
    if not os.path.exists(filepath):
        operator.report({'ERROR'}, T("core.pose_ops.file_not_found").format(name=selected_file))
        return {'CANCELLED'}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        operator.report({'ERROR'}, T("core.pose_ops.read_failed").format(err=e))
        return {'CANCELLED'}

    transforms = data.get("transforms", {})
    if not transforms:
        operator.report({'ERROR'}, T("core.pose_ops.no_transform_data"))
        return {'CANCELLED'}
    
    # 通过骨架预设建立骨骼名映射 (变换记录中的名字 -> 目标骨架的名字)
    mapper = BoneMapManager()
    bone_mapping = {}  # {target_bone_name: transform_bone_name}
    
    _pose_preset, _resolve_err = resolve_preset(settings.pose_import_preset_enum, arm_obj, True)
    if _pose_preset and mapper.load_preset(_pose_preset, is_import_x=True):
        # 通过预设的标准键做桥接
        # 先建立: transform_bone_name -> std_key 的映射
        # 再建立: std_key -> target_bone_name 的映射
        # 注意: transforms 里的骨骼名来自录制时的骨架, 可能和目标骨架不同
        for std_key in STANDARD_BONE_NAMES:
            tgt_name, __ = mapper.get_matches_for_standard(arm_obj, std_key)
            if tgt_name:
                # 检查 transforms 里有没有这个名字
                if tgt_name in transforms:
                    bone_mapping[tgt_name] = tgt_name
    
    # 同名匹配兜底
    if not bone_mapping:
        for bone in arm_obj.data.bones:
            if bone.name in transforms:
                bone_mapping[bone.name] = bone.name
    
    if not bone_mapping:
        operator.report({'ERROR'}, T("core.pose_ops.no_matching_bones"))
        return {'CANCELLED'}
    
    # 按骨骼层级顺序排列 (从根到叶)
    # 使用骨架自身的骨骼顺序, 它天然是父级在前子级在后
    ordered_bones = []
    for bone in arm_obj.data.bones:
        if bone.name in bone_mapping:
            ordered_bones.append(bone.name)
    
    # 应用变换
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='DESELECT')
    pose_bones = arm_obj.pose.bones
    count = 0
    
    for tgt_name in ordered_bones:
        if tgt_name not in pose_bones:
            continue
        
        transform_name = bone_mapping[tgt_name]
        quat_data = transforms[transform_name]
        delta = mathutils.Quaternion((quat_data[0], quat_data[1], quat_data[2], quat_data[3]))
        
        if inverse:
            delta.invert()
        
        pb = pose_bones[tgt_name]
        bone = arm_obj.data.bones[tgt_name]
        
        # delta 是在父级空间中的旋转差 (parent-relative)
        # matrix_basis 是在骨骼自身的 rest 朝向空间中的变换
        # 需要将 delta 从父级空间转换到骨骼 rest 朝向空间:
        #   basis_rot = rest_rot⁻¹ × delta × rest_rot
        # 其中 rest_rot 是骨骼相对于父级的 rest 朝向
        if bone.parent:
            rest_local = bone.parent.matrix_local.inverted() @ bone.matrix_local
        else:
            rest_local = bone.matrix_local.copy()
        
        rest_rot = rest_local.to_quaternion()
        rest_rot_inv = rest_rot.copy()
        rest_rot_inv.invert()
        
        # 转换到骨骼局部空间
        local_delta = rest_rot_inv @ delta @ rest_rot
        
        # 构建旋转矩阵并应用到 matrix_basis
        rot_mat = local_delta.to_matrix().to_4x4()
        current_basis = pb.matrix_basis.copy()
        new_basis = rot_mat @ current_basis
        # 保留局部位移
        new_basis[0][3] = current_basis[0][3]
        new_basis[1][3] = current_basis[1][3]
        new_basis[2][3] = current_basis[2][3]
        
        pb.matrix_basis = new_basis
        count += 1
    
    bpy.context.view_layer.update()
    
    direction = "B->A" if inverse else "A->B"
    mesh_count = _apply_and_rebind(arm_obj)
    operator.report({'INFO'}, T("core.pose_ops.transform_done").format(
        direction=direction, bones=count, meshes=mesh_count))
    return {'FINISHED'}


class MODDER_OT_DeletePosePreset(bpy.types.Operator):
    bl_idname = "modder.delete_pose_preset"
    bl_label = "Delete Record"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("core.pose_ops.delete_preset_desc")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        selected_file = settings.pose_preset_enum
        if not selected_file or selected_file == 'NONE':
            return {'CANCELLED'}

        filepath = os.path.join(_get_pose_presets_dir(), selected_file)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                self.report({'INFO'}, T("core.pose_ops.deleted").format(name=selected_file))
            except Exception as e:
                self.report({'ERROR'}, T("core.pose_ops.delete_failed").format(err=e))
        return {'FINISHED'}


# ============================================================
# 共用的网格处理函数
# ============================================================

def _apply_and_rebind(arm_obj):
    bpy.ops.object.mode_set(mode='OBJECT')
    
    mesh_children = [obj for obj in bpy.data.objects 
                     if obj.type == 'MESH' and obj.find_armature() == arm_obj]
    
    if mesh_children:
        for child in mesh_children:
            child.hide_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE', extend=True)
        bpy.ops.object.convert(target='MESH')
    
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=True)
    bpy.ops.pose.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    if mesh_children:
        bpy.ops.object.select_hierarchy(direction='CHILD', extend=False)
        if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
            modifier = bpy.context.active_object.modifiers.new(name="Armature", type='ARMATURE')
            modifier.object = arm_obj
            bpy.ops.object.make_links_data(type='MODIFIERS')
        bpy.ops.object.select_hierarchy(direction='PARENT', extend=False)
    
    bpy.ops.object.select_hierarchy(direction='CHILD', extend=True)
    bpy.context.view_layer.objects.active = arm_obj
    return len(mesh_children)


# ============================================================
# 注册
# ============================================================

classes = [
    MODDER_OT_MmdAToTPose,
    MODDER_OT_ReeToTPose,
    MODDER_OT_RecordTransform,
    MODDER_OT_ApplyTransformForward,
    MODDER_OT_ApplyTransformInverse,
    MODDER_OT_DeletePosePreset,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)