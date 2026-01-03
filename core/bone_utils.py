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
    """
    为选中的末端骨骼添加垂直子骨骼
    """
    count = 0
    for bone in selected_bones:
        
        tail_pos = bone.tail.copy()
        
        # 创建新骨骼
        try:
            new_bone = edit_bones.new(bone.name + "_tail")
            new_bone.head = tail_pos
            # 默认长度为父骨骼长度，若父骨骼长度为0则设为0.1
            length = bone.length if bone.length > 0 else 0.1
            # 垂直向上 (Z轴)
            new_bone.tail = tail_pos + mathutils.Vector((0, 0, length))
            
            new_bone.parent = bone
            new_bone.use_connect = False
            
            count += 1
        except Exception as e:
            print(f"Error adding tail for {bone.name}: {e}")
            
    return count

def mirror_bone_transform(edit_bones, bone_names):
    """以 X+ 为基准镜像对齐 X-"""
    if len(bone_names) != 2:
        return False, "请选中两个骨骼"
    
    b1 = edit_bones.get(bone_names[0])
    b2 = edit_bones.get(bone_names[1])
    
    if not b1 or not b2:
        return False, "骨骼未找到"
        
    # 判定基准 (X > 0 为基准)
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
    
    # 同步 Roll (通常镜像需要取反或保持，视骨骼轴向而定，这里简单复制处理，视情况可调整)
    mirror.roll = -ref.roll 
    
    return True, f"已将 {mirror.name} 对齐到 {ref.name}"

def propagate_movement(bone, offset_vec):
    """递归移动子骨骼"""
    for child in bone.children:
        if child.use_connect:
            child.tail += offset_vec
        else:
            child.head += offset_vec
            child.tail += offset_vec
        propagate_movement(child, offset_vec)

def find_bone_smart(bones, name):
    """
    智能查找骨骼：
    1. 精确查找
    2. 尝试互换 'MhBone_' 和 'bonefunction_' 前缀
    3. 忽略大小写查找 (兼容 3.x)
    """
    # 1. 精确匹配
    if name in bones:
        return bones[name]
    
    # 2. 前缀互换
    alt_name = None
    if "MhBone_" in name:
        alt_name = name.replace("MhBone_", "bonefunction_")
    elif "bonefunction_" in name:
        alt_name = name.replace("bonefunction_", "MhBone_")
    
    if alt_name and alt_name in bones:
        return bones[alt_name]
    
    # 3. 最后的手段：忽略大小写遍历 (较慢，仅作兜底)
    target_lower = name.lower()
    alt_lower = alt_name.lower() if alt_name else ""
    
    for b in bones:
        b_lower = b.name.lower()
        if b_lower == target_lower or (alt_lower and b_lower == alt_lower):
            return b
            
    return None

def get_preset_items(subdir):
    """
    通用函数：扫描指定子目录下的所有 .json 文件
    subdir: "import_presets" 或 "bone_presets"
    """
    # 获取插件根目录
    # 假设当前脚本位于 core/ 或 ui/ 目录下
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    preset_dir = os.path.join(root_dir, "assets", subdir)
    
    items = []
    
    if not os.path.exists(preset_dir):
        return [('NONE', "未找到文件夹", "请检查 assets 目录")]

    files = [f for f in os.listdir(preset_dir) if f.endswith('.json')]
    
    for i, f in enumerate(files):
        # identifier, name, description
        # identifier 用文件名，name 去掉后缀
        display_name = f.replace("_preset.json", "").replace(".json", "").upper()
        items.append((f, display_name, f"加载 {f} 预设"))
        
    if not items:
        return [('NONE', "无预设文件", "")]
        
    return items

# --- 回调函数接口 ---

def get_import_presets_callback(self, context):
    return get_preset_items("import_presets")

def get_target_presets_callback(self, context):
    return get_preset_items("bone_presets")