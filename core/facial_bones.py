import bpy
import math
import mathutils
import re


def _is_end_bone(name):
    """FBX 导出时每个末端关节都会带一个 "_end"（有时嵌套为 "_end_end"）辅助节点，
    仅用于在其他工具里推断骨骼朝向/长度，Blender 骨骼本身自带 head/tail 不需要它，
    移植表情骨时应过滤掉，避免这些辅助节点被当成正常骨骼一并移植。"""
    return name.lower().endswith("_end")


def collect_facial_subtree(ref_arm, root_bone_name):
    """返回 (root_bone_name 及其所有子级的骨骼名列表, root_bone_name 原父级骨骼名)。
    自动过滤 FBX 导出产生的 "_end" 辅助节点。"""
    root_bone = ref_arm.data.bones.get(root_bone_name)
    if root_bone is None:
        return [], None
    names = [root_bone_name] + [
        b.name for b in root_bone.children_recursive if not _is_end_bone(b.name)
    ]
    parent_name = root_bone.parent.name if root_bone.parent else None
    return names, parent_name


def graft_facial_bones(ref_arm, target_arm, root_bone_name):
    """将 ref_arm 的 root_bone_name 及其所有子级完整移植到 target_arm。

    直接照搬来源世界坐标下的 head/tail/roll（不做竖直化，也不加尾骨），
    并按来源层级关系重建父子链；根骨骼本身挂到目标骨架中与来源同名的父级骨骼上。
    会先清除 target_arm 中已存在的同名旧骨骼。返回新建骨骼数。
    """
    subtree_names, root_parent_name = collect_facial_subtree(ref_arm, root_bone_name)
    if not subtree_names:
        return 0

    # 1. 在来源骨架 EDIT 模式下读取世界坐标 head/tail/roll 及父级名
    bpy.context.view_layer.objects.active = ref_arm
    bpy.ops.object.mode_set(mode='EDIT')
    ref_mat = ref_arm.matrix_world
    src_data = {}
    for name in subtree_names:
        eb = ref_arm.data.edit_bones.get(name)
        if eb is None:
            continue
        parent_name = eb.parent.name if eb.parent else None
        src_data[name] = (ref_mat @ eb.head, ref_mat @ eb.tail, eb.roll, parent_name)
    bpy.ops.object.mode_set(mode='OBJECT')

    if not src_data:
        return 0

    # 2. 目标骨架：清除同名旧骨骼，再逐个创建新骨骼
    bpy.context.view_layer.objects.active = target_arm
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = target_arm.data.edit_bones

    for name in subtree_names:
        if name in edit_bones:
            edit_bones.remove(edit_bones[name])

    tgt_mat_inv = target_arm.matrix_world.inverted()
    created = 0
    for name in subtree_names:
        if name not in src_data:
            continue
        head_w, tail_w, roll, _p = src_data[name]
        eb = edit_bones.new(name)
        eb.head = tgt_mat_inv @ head_w
        eb.tail = tgt_mat_inv @ tail_w
        eb.roll = roll
        eb.use_connect = False
        created += 1

    # 3. 按来源层级重建父子关系
    for name in subtree_names:
        eb = edit_bones.get(name)
        if eb is None or name not in src_data:
            continue
        if name == root_bone_name:
            if root_parent_name and root_parent_name in edit_bones:
                eb.parent = edit_bones[root_parent_name]
        else:
            _h, _t, _r, p_name = src_data[name]
            if p_name and p_name in edit_bones:
                eb.parent = edit_bones[p_name]

    bpy.ops.object.mode_set(mode='OBJECT')
    return created


# 支点在睑缘、又找不到眼球骨时的兜底眼球半径（米）。四套参考骨架实测 14.6~16.3 mm。
_FALLBACK_EYE_RADIUS = 0.015
# u=0（支点就在睑缘）判定阈值
_EPS = 1e-6
# 找不到子关节时，用来量眼球半径的眼球骨候选后缀，按 "<L|R>_" + 后缀 依次尝试
_EYE_BONE_SUFFIXES = ("Eye", "Eye_Master", "EyeBall")


def _eye_bone_radius(edit_bones, bone):
    """量 bone.head 到同侧眼球骨的距离，作为眼球半径。找不到则返回兜底值。"""
    side = bone.name[:2] if bone.name[:2] in ("L_", "R_") else ""
    for suffix in _EYE_BONE_SUFFIXES:
        eye = edit_bones.get(side + suffix)
        if eye is not None and eye is not bone:
            r = (eye.head - bone.head).length
            if r > _EPS:
                return r
    return _FALLBACK_EYE_RADIUS


def blink_offset_from_radius(arm_obj, bone, radius_mult):
    """把「眨眼扫过半径 = radius_mult 个眼球半径」换算成假头骨该后移的距离（米）。

    弧长 s = r·θ，假头法不改动画角度 θ，只把支点后推从而改 r。设 u = 睑缘几何 −
    支点 head（取第一个非 "_end" 子关节的位置；支点本身就在睑缘时 u=0），R 为眼球
    半径（u≠0 时即 |u|，否则量到眼球骨），要求后移 d 之后 |u − d·ŷ| = radius_mult·R：

        d = (u·ŷ) + sqrt( (u·ŷ)² + (radius_mult·R)² − |u|² )

    支点在眼球中心时退化为 d = R(−c + sqrt(c²+m²−1))（c = −û·ŷ，此时 m=1 给出 d=0）；
    支点在睑缘时 u=0，直接得 d = m·R。根号内为负说明该半径够不着，夹到 0。
    """
    child = next((c for c in bone.children if not _is_end_bone(c.name)), None)
    mat3 = arm_obj.matrix_world.to_3x3()
    u = mat3 @ ((child.head - bone.head) if child is not None else mathutils.Vector((0.0, 0.0, 0.0)))
    r = u.length
    radius = r if r > _EPS else _eye_bone_radius(arm_obj.data.edit_bones, bone)
    a = u.y
    target = radius_mult * radius
    return a + math.sqrt(max(0.0, a * a + target * target - r * r))


def apply_blink_fake_bone(arm_obj, bone_name, radius_mult=4.0):
    """假头法：在 bone_name(A) 与其父级(B) 之间插入一个从 B 原位复制出的假骨骼(B')，
    父子关系变为 B > B' > A，然后将 B' 与 A 一同沿 +Y (世界空间) 后移。

    两者位移**等量**是这套做法能成立的全部条件：A 相对 B' 的关系保持与原生逐位相同，
    引擎按骨骼名哈希取到 A、用相对父级的 TRS 覆写它时写回的正是原值；偏移由 B' 承担，
    而 B' 是新名字、查不到动画轨道，没人动它。

    位移距离由 radius_mult 经 blink_offset_from_radius() 算出（见其说明）。
    返回 True 表示已处理，A 不存在或没有父级时返回 False。
    """
    bpy.context.view_layer.objects.active = arm_obj
    if bpy.context.mode != 'EDIT_ARMATURE':
        bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm_obj.data.edit_bones

    a = edit_bones.get(bone_name)
    if a is None or a.parent is None:
        return False
    b = a.parent

    # 重复执行时，graft_facial_bones 已经把 A 删了重建、重新挂回真实父级 B——
    # 上一轮插入的假骨 B' 因此变成了 B 底下没有子级的孤儿，不会被 graft 清掉。
    # 这里先按命名规律把它找出来删掉，否则每点一次就多一层孤儿假骨，且新一轮的
    # 偏移是从 A 当前（已含上次偏移的）位置继续叠加
    fake_pattern = re.compile(rf"^{re.escape(b.name)}(_[LR])?_Fake(\.\d+)?$")
    for child in list(b.children):
        if child is not a and fake_pattern.match(child.name):
            edit_bones.remove(child)

    # 先量后改：算距离要读 A 的子关节，放在改动层级之前免得受任何后续编辑影响
    offset_y = blink_offset_from_radius(arm_obj, a, radius_mult)

    # L/R 两侧的睑缘骨常共用同一个父级（如 FacialDef_Face），若只用 b.name +
    # "_Fake" 命名会导致两侧假骨重名（被 Blender 自动加 .001）；按 A 的左右前缀
    # 区分，前缀不存在时才退回原始命名
    side = a.name[:2] if a.name[:2] in ("L_", "R_") else ""
    fake_name = f"{b.name}_{side}Fake" if side else f"{b.name}_Fake"
    b_prime = edit_bones.new(fake_name)
    b_prime.head = b.head.copy()
    b_prime.tail = b.tail.copy()
    b_prime.roll = b.roll
    b_prime.parent = b
    b_prime.use_connect = False

    a.parent = b_prime
    a.use_connect = False

    mat3 = arm_obj.matrix_world.to_3x3()
    local_offset = mat3.inverted() @ mathutils.Vector((0.0, offset_y, 0.0))

    b_prime.head += local_offset
    b_prime.tail += local_offset
    a.head += local_offset
    a.tail += local_offset

    return True
