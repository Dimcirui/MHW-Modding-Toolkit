import bpy
import mathutils

def set_roll_to_zero_recursive(root_bones):
    """递归将骨骼 Roll 设为 0"""
    processed = set()
    for root in root_bones:
        processed.add(root)
        for child in root.children_recursive:
            processed.add(child)
    
    count = 0
    for bone in processed:
        bone.roll = 0
        count += 1
    return count

def add_vertical_tail_bone(edit_bones, selected_bones):
    """为选中的末端骨骼添加垂直子骨骼"""
    count = 0
    for bone in selected_bones:
        # 只处理没有子级或者明确选中的末端
        # (原脚本逻辑：选中且 use_connect=False，这里泛化一下)
        if bone in edit_bones:
            tail_pos = bone.tail.copy()
            new_bone = edit_bones.new(bone.name + "_tail")
            new_bone.head = tail_pos
            # 默认长度为父骨骼长度，方向 Z+
            length = bone.length if bone.length > 0 else 0.1
            new_bone.tail = tail_pos + mathutils.Vector((0, 0, length))
            new_bone.parent = bone
            new_bone.use_connect = False
            count += 1
    return count

def mirror_bone_transform(edit_bones, bone_names):
    """以 X+ 为基准镜像对齐 X-"""
    if len(bone_names) != 2:
        return False, "请选中两个骨骼"
    
    b1 = edit_bones.get(bone_names[0])
    b2 = edit_bones.get(bone_names[1])
    
    if not b1 or not b2:
        return False, "骨骼未找到"
        
    # 判定基准
    if b1.head.x > 0:
        ref, mirror = b1, b2
    else:
        ref, mirror = b2, b1
        
    # 执行镜像
    mirror.head.x = -ref.head.x
    mirror.head.y = ref.head.y
    mirror.head.z = ref.head.z
    
    mirror.tail.x = -ref.tail.x
    mirror.tail.y = ref.tail.y
    mirror.tail.z = ref.tail.z
    
    return True, f"已将 {mirror.name} 对齐到 {ref.name}"

def propagate_movement(bone, offset_vec):
    """递归移动子骨骼，被所有游戏模块共享"""
    for child in bone.children:
        if child.use_connect:
            child.tail += offset_vec
        else:
            child.head += offset_vec
            child.tail += offset_vec
        propagate_movement(child, offset_vec)

def find_bone_fuzzy(bones, name):
    """模糊查找骨骼的通用逻辑"""
    return bones.get(name)