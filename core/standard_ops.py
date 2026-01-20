import bpy, mathutils
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from . import weight_utils, bone_utils

class MODDER_OT_ApplyStandardX(bpy.types.Operator):
    """执行标准化 X：合并权重并重命名为基础名"""
    bl_idname = "modder.apply_standard_x"
    bl_label = "1. 标准化重命名 (X)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings 
        arm_obj = context.active_object
        
        # 1. 加载预设
        mapper = BoneMapManager()
        if not mapper.load_preset(settings.import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "预设加载失败")
            return {'CANCELLED'}

        # 2. 匹配分析
        analysis = {}
        for std_key in STANDARD_BONE_NAMES:
            main, auxs = mapper.get_matches_for_standard(arm_obj, std_key)
            if main or auxs: analysis[std_key] = (main, auxs)

        # 3. 权重合并
        meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm_obj]
        bpy.ops.object.mode_set(mode='OBJECT')
        for mesh_obj in meshes:
            for std_key, (main_name, aux_list) in analysis.items():
                if aux_list:
                    # 没找到主骨名时，使用标准名作为目标顶点组，方便后续手动处理
                    target_vg = main_name if main_name else std_key
                    weight_utils.merge_vgroups_to_main(mesh_obj, target_vg, aux_list)

        # 4. 骨骼重命名 (Edit Mode)
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        
        rename_count = 0
        deleted_count = 0
        
        for std_key, (main_name, aux_list) in analysis.items():
            # 只有当主骨存在时，才执行重命名
            if main_name and main_name in edit_bones:
                edit_bones[main_name].name = std_key
                rename_count += 1
            
            # 无论主骨是否存在，辅助骨都要清理 (因为权重已经转移了)
            for aux_name in aux_list:
                if aux_name in edit_bones:
                    edit_bones.remove(edit_bones[aux_name])
                    deleted_count += 1

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"标准化完成: 重命名 {rename_count} 根, 清理 {deleted_count} 根辅助骨")
        return {'FINISHED'}

class MODDER_OT_ApplyStandardY(bpy.types.Operator):
    """执行标准化 Y：将基础名转为目标游戏名"""
    bl_idname = "modder.apply_standard_y"
    bl_label = "2. 转换为游戏名 (Y)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        
        mapper = BoneMapManager()
        if not mapper.load_preset(settings.target_preset_enum, is_import_x=False):
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        for std_key in STANDARD_BONE_NAMES:
            if std_key in edit_bones:
                target_data = mapper.mapping_data.get(std_key)
                if target_data and target_data.get("main"):
                    edit_bones[std_key].name = target_data["main"][0]

        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
    
class MODDER_OT_DirectConvert(bpy.types.Operator):
    """将选中网格的顶点组转换成目标游戏的格式"""
    bl_idname = "modder.direct_convert"
    bl_label = "一键转换 (X -> Y)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        
        # 1. 获取选中的所有网格对象
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
        
        if not selected_meshes:
            self.report({'ERROR'}, "请至少选中一个网格 (Mesh)")
            return {'CANCELLED'}

        # 2. 加载映射表
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(settings.import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "无法加载 X 预设")
            return {'CANCELLED'}
            
        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(settings.target_preset_enum, is_import_x=False):
            self.report({'ERROR'}, "无法加载 Y 预设")
            return {'CANCELLED'}

        # 3. 预计算转换规则
        # 需要知道：标准键 -> (源主名, 源辅助列表, 目标主名)
        conversion_rules = []
        
        for std_key in STANDARD_BONE_NAMES:
            # A. 从 X 表获取源信息
            src_entry = mapper_x.mapping_data.get(std_key)
            if not src_entry: continue
            
            src_mains = src_entry.get("main", [])
            src_auxs = src_entry.get("aux", [])
            
            # B. 从 Y 表获取目标信息
            tgt_entry = mapper_y.mapping_data.get(std_key)
            if not tgt_entry: continue
            tgt_mains = tgt_entry.get("main", [])
            
            if src_mains and tgt_mains:
                # 规则：(源主名列表, 源辅助名列表, 目标主名)
                # 取第一个目标主名作为最终名字
                conversion_rules.append((src_mains, src_auxs, tgt_mains[0]))

        if not conversion_rules:
            self.report({'WARNING'}, "X与Y预设之间没有共同的骨骼映射")
            return {'CANCELLED'}

        # 4. 开始处理网格 (Object Mode)
        bpy.ops.object.mode_set(mode='OBJECT')
        
        processed_count = 0
        
        for mesh_obj in selected_meshes:
            vgs = mesh_obj.vertex_groups
            mesh_updated = False
            
            for src_mains, src_auxs, tgt_name in conversion_rules:
                # 步骤 A: 确定当前网格上实际存在哪个“源主顶点组”
                # (X预设里 main 可能有多个候选，如 ["UpperArm_L", "Left Arm"]，我们要找 Mesh 上有的那个)
                real_src_main = None
                for candidate in src_mains:
                    if candidate in vgs:
                        real_src_main = candidate
                        break
                
                # 如果没找到主组，跳过此骨骼（可能这个网格只是个手套，没有腿骨权重）
                # if not real_src_main:
                #     continue
                
                # 确定权重的去向：
                # 有 源主组 -> 合并到源主组 (稍后改名)
                # 无 源主组 -> 直接合并到目标名 (tgt_name)
                target_vg = real_src_main if real_src_main else tgt_name

                # 步骤 B: 合并辅助权重
                # 找出当前网格上实际存在的辅助组
                real_auxs = [aux for aux in src_auxs if aux in vgs]
                if real_auxs:
                    weight_utils.merge_vgroups_to_main(mesh_obj, target_vg, real_auxs)
                    mesh_updated = True
                
                # 步骤 C: 重命名主顶点组 -> 目标名
                # 只有当名字不同时才改名，防止报错
                if real_src_main and real_src_main != tgt_name:
                    if tgt_name in vgs: vgs.remove(vgs[tgt_name])
                    vgs[real_src_main].name = tgt_name
                    mesh_updated = True
            
            if mesh_updated:
                processed_count += 1

        self.report({'INFO'}, f"处理完成: 已更新 {processed_count} 个网格的顶点组")
        return {'FINISHED'}
    
class MODDER_OT_UniversalSnap(bpy.types.Operator):
    """将目标游戏骨架的身体骨骼对齐来源预设骨骼（后选要修改的目标骨架）"""
    bl_idname = "modder.universal_snap"
    bl_label = "0. 骨架对齐 (Snap)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings
        selected_objs = [o for o in context.selected_objects if o.type == 'ARMATURE']
        
        # 1. 检查选中项
        if len(selected_objs) != 2 or not context.active_object:
            self.report({'ERROR'}, "操作对象错误: 请先选中源骨架(X)，再按住Shift选中目标骨架(Y)")
            return {'CANCELLED'}
            
        target_arm = context.active_object  # 活动的是目标 (Y, 如 MHWI)
        source_arm = [o for o in selected_objs if o != target_arm][0] # 另一个是源 (X, 如 VRC)
        
        # 2. 加载映射表
        mapper_x = BoneMapManager()
        if not mapper_x.load_preset(settings.import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "无法加载 X 预设")
            return {'CANCELLED'}
            
        mapper_y = BoneMapManager()
        if not mapper_y.load_preset(settings.target_preset_enum, is_import_x=False):
            self.report({'ERROR'}, "无法加载 Y 预设")
            return {'CANCELLED'}

        # 3. 预计算源骨骼的世界坐标 (在 Object 模式下进行)
        # 结构: { StandardName: Source_Head_World_Pos }
        source_positions = {} 
        source_mw = source_arm.matrix_world
        
        for std_key in STANDARD_BONE_NAMES:
            src_name, _ = mapper_x.get_matches_for_standard(source_arm, std_key)
            if src_name:
                try:
                    b = source_arm.data.bones[src_name]
                    # 我们只需要头部坐标即可，尾部会通过刚性移动自动计算
                    source_positions[std_key] = source_mw @ b.head_local
                except KeyError:
                    pass

        # 4. 进入编辑模式执行对齐
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones
        target_mw_inv = target_arm.matrix_world.inverted()
        
        aligned_count = 0
        
        # 按 STANDARD_BONE_NAMES 的顺序遍历 (通常是 Hips -> Spine -> Head)
        # 这样父级移动后，子级会先跟随移动，然后子级再根据自己的目标进行微调
        for std_key in STANDARD_BONE_NAMES:
            if std_key not in source_positions:
                continue
                
            # 获取目标骨名 (从 Y 表)
            tgt_entry = mapper_y.mapping_data.get(std_key)
            if not tgt_entry or not tgt_entry.get('main'):
                continue
                
            tgt_name = tgt_entry['main'][0]
            if tgt_name not in edit_bones:
                continue
                
            t_bone = edit_bones[tgt_name]
            
            # --- 核心对齐逻辑 ---
            
            # A. 计算目标点 (转为 Target 本地坐标)
            src_head_world = source_positions[std_key]
            target_head_local = target_mw_inv @ src_head_world
            
            # B. 计算移动向量
            old_head = t_bone.head.copy()
            offset = target_head_local - old_head
            
            # C. 移动当前骨骼 (保持长度和方向)
            t_bone.head = target_head_local
            t_bone.tail += offset # 尾部跟随移动，保持骨骼向量不变
            
            # D. 刚性传递：递归移动所有子级
            bone_utils.propagate_movement(t_bone, offset)
            
            aligned_count += 1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"刚性对齐完成: {aligned_count} 根骨骼")
        return {'FINISHED'}
    
class MODDER_OT_SmartGraftBones(bpy.types.Operator):
    """
    物理骨移植 (仅支持_graft结尾的来源预设):
    1. 不修改任何骨架姿态 (默认用户已对齐)。
    2. 移植非身体基础骨。
    3. 自动处理骨骼朝向和扭转、重定向父级，使其满足物理骨要求。
    实验性功能：很可能会同时移植大量辅助骨，请自行检查、删除。
    """
    bl_idname = "modder.smart_graft"
    bl_label = "3. 物理骨移植 (Fix Connected)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # --- 1. 场景校验 ---
        sel_objs = context.selected_objects
        target_arm = context.active_object # Out (目标)

        if not target_arm or target_arm.type != 'ARMATURE':
            self.report({'ERROR'}, "操作失败：请先选择 In 骨架，再 Shift 加选 Out 骨架(Out需为黄色激活状态)")
            return {'CANCELLED'}
        
        source_arm = None # In (来源)
        for obj in sel_objs:
            if obj != target_arm and obj.type == 'ARMATURE':
                source_arm = obj
                break
        
        if not source_arm:
            self.report({'ERROR'}, "操作失败：未找到来源(In)骨架")
            return {'CANCELLED'}

        # --- 2. 加载预设 (只为识别谁是"非物理骨") ---
        from .bone_mapper import BoneMapManager
        mapper = BoneMapManager()
        settings = context.scene.mhw_suite_settings
        
        # 加载 In 预设
        if not mapper.load_preset(settings.import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "无法加载源预设 (In)")
            return {'CANCELLED'}
        src_data = mapper.mapping_data 

        # 加载 Out 预设
        if not mapper.load_preset(settings.target_preset_enum, is_import_x=False):
            self.report({'ERROR'}, "无法加载目标预设 (Out)")
            return {'CANCELLED'}
        tgt_data = mapper.mapping_data

        # --- 3. 构建查找表 ---
        # src_to_std: In骨骼名 -> 标准名 (包含 Main 和 Aux)
        # all_preset_bones_src: 用于排除法识别物理骨
        src_to_std = {}
        all_preset_bones_src = set()
        
        for std_key, entry in src_data.items():
            for m in entry.get('main', []):
                src_to_std[m] = std_key
                all_preset_bones_src.add(m)
            for a in entry.get('aux', []):
                src_to_std[a] = std_key 
                all_preset_bones_src.add(a)

        # std_to_tgt_bone: 标准名 -> Out骨骼名
        std_to_tgt_bone = {}
        for std_key, entry in tgt_data.items():
            mains = entry.get('main', [])
            if mains:
                std_to_tgt_bone[std_key] = mains[0]

        # --- 4. 筛选物理骨 ---
        physics_bones = [b.name for b in source_arm.data.bones if b.name not in all_preset_bones_src]
        
        if not physics_bones:
            self.report({'WARNING'}, "未检测到物理骨骼 (可能是所有骨骼都在预设里？)")
            return {'FINISHED'}

        # --- 5. 核心移植逻辑 ---
        bpy.context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones

        created_count = 0
        new_bones_map = {} # {src_name: new_bone_name}

        # 计算 Out 的逆矩阵，用于将世界坐标转为 Out 的本地编辑坐标
        tgt_mat_inv = target_arm.matrix_world.inverted()

        for p_name in physics_bones:
            src_bone = source_arm.data.bones.get(p_name)
            src_pb = source_arm.pose.bones.get(p_name)
            
            if not src_bone or not src_pb: continue
            
            # 5.1 创建/获取骨骼
            if p_name in edit_bones:
                eb = edit_bones[p_name]
            else:
                eb = edit_bones.new(p_name)
            new_bones_map[p_name] = eb.name

            # 5.2 核心修复: 必须先断开连接，否则无法修改 Head 位置！
            eb.use_connect = False 

            # 5.3 计算位置 (世界空间 -> Target本地空间)
            src_world_head = source_arm.matrix_world @ src_pb.head
            target_local_head = tgt_mat_inv @ src_world_head
            
            # 5.4 强制重置 (竖直朝上 & Roll归零)
            eb.head = target_local_head
            # 长度沿用原骨骼长度
            length = src_bone.length if src_bone.length > 0.001 else 0.1
            eb.tail = target_local_head + mathutils.Vector((0, 0, length))
            eb.roll = 0

            created_count += 1

        # --- 6. 智能重建父级 ---
        for src_name, tgt_name in new_bones_map.items():
            eb = edit_bones.get(tgt_name)
            src_bone = source_arm.data.bones.get(src_name)
            
            if not src_bone or not src_bone.parent:
                continue
            
            src_p_name = src_bone.parent.name
            target_parent_name = None

            # 情况 A: 父级也是物理骨
            if src_p_name in new_bones_map:
                target_parent_name = new_bones_map[src_p_name]
            
            # 情况 B: 父级是映射骨 (Main或Aux)
            elif src_p_name in src_to_std:
                std_key = src_to_std[src_p_name]
                if std_key in std_to_tgt_bone:
                    target_parent_name = std_to_tgt_bone[std_key]

            # 应用父级连接
            if target_parent_name and target_parent_name in edit_bones:
                parent_bone = edit_bones[target_parent_name]
                eb.parent = parent_bone
                
                # 再次强调: 物理骨绝不使用 Connected，否则刚才的竖直重置会失效
                eb.use_connect = False 

        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"移植完成: {created_count} 根物理骨骼 (已断开连接并重置竖直)")
        return {'FINISHED'}

classes = [
    MODDER_OT_ApplyStandardX,
    MODDER_OT_ApplyStandardY,
    MODDER_OT_DirectConvert,
    MODDER_OT_UniversalSnap,
    MODDER_OT_SmartGraftBones,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)