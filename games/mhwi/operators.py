import bpy
from ...core import bone_utils
from . import data_maps
from .core.bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from .core import weight_utils

# ==========================================
# 1. 对齐 MHWI 非物理骨骼
# ==========================================
class MHWI_OT_AlignNonPhysics(bpy.types.Operator):
    """对齐 MHWI 骨骼 (跳过 150-245 物理骨)"""
    bl_idname = "mhwi.align_non_physics"
    bl_label = "对齐非物理骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        
        if len(selected_objects) != 2 or not active_obj:
            self.report({'ERROR'}, "请选择两个骨架 (源 -> 目标)")
            return {'CANCELLED'}

        target_armature = active_obj
        source_armature = [obj for obj in selected_objects if obj != target_armature][0]
        
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        
        # 预读取源骨骼
        source_heads = {}
        s_matrix = source_armature.matrix_world
        for b in source_armature.data.bones:
            source_heads[b.name] = s_matrix @ b.head_local.copy()

        context.view_layer.objects.active = target_armature
        bpy.ops.object.mode_set(mode='EDIT')
        target_edit_bones = target_armature.data.edit_bones
        t_matrix_inv = target_armature.matrix_world.inverted()
        
        aligned_count = 0
        skip_count = 0
        
        for t_bone in target_edit_bones:
            name = t_bone.name
            # 过滤物理骨骼
            if name.startswith("MhBone_") or name.startswith("bonefunction_"):
                try:
                    num = int(name.split("_")[-1])
                    if 150 <= num <= 245:
                        skip_count += 1
                        continue
                except: pass

            if name in source_heads:
                s_head_world = source_heads[name]
                old_head = t_bone.head.copy()
                new_head = t_matrix_inv @ s_head_world
                
                orig_vec = t_bone.tail - t_bone.head
                t_bone.head = new_head
                t_bone.tail = new_head + orig_vec
                
                # 递归移动
                bone_utils.propagate_movement(t_bone, new_head - old_head)
                aligned_count += 1
            
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"对齐: {aligned_count}, 跳过物理骨: {skip_count}")
        return {'FINISHED'}

# ==========================================
# 2. VRC -> MHWI 工具
# ==========================================
class MHWI_OT_VRC_Rename(bpy.types.Operator):
    """VRChat 顶点组重命名为 MHWI 格式"""
    bl_idname = "mhwi.vrc_rename"
    bl_label = "VRC -> MHWI 重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type == "MESH":
                vgroups = obj.vertex_groups
                prefix = "MhBone_"
                for vg in vgroups:
                    if "bonefunction_" in vg.name:
                        prefix = "bonefunction_"
                        break
                
                for src_name, dst_base in data_maps.VRC_TO_MHWI_MAP.items():
                    if src_name in vgroups:
                        final_dst = dst_base.replace("MhBone_", prefix)
                        if final_dst not in vgroups:
                            vgroups[src_name].name = final_dst
                            count += 1
        self.report({'INFO'}, f"重命名了 {count} 个顶点组")
        return {'FINISHED'}

class MHWI_OT_VRC_Snap(bpy.types.Operator):
    """VRChat 骨骼吸附到 MHWI"""
    bl_idname = "mhwi.vrc_snap"
    bl_label = "VRC -> MHWI 吸附"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if not active_obj or len(selected) != 2:
            return {'CANCELLED'}
            
        target_arm = active_obj
        source_arm = [o for o in selected if o != target_arm][0]
        
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        
        vrc_data = {}
        s_mat = source_arm.matrix_world
        for b in source_arm.data.bones:
            vrc_data[b.name] = s_mat @ b.head_local.copy()
            
        prefix = "MhBone_"
        for b in target_arm.data.bones:
            if "bonefunction_" in b.name: prefix = "bonefunction_"
                
        context.view_layer.objects.active = target_arm
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target_arm.data.edit_bones
        t_mat_inv = target_arm.matrix_world.inverted()
        
        count = 0
        for vrc_name, mhw_base in data_maps.VRC_TO_MHWI_MAP.items():
            if vrc_name not in vrc_data: continue
            mhw_name = mhw_base.replace("MhBone_", prefix)
            t_bone = edit_bones.get(mhw_name)
            if t_bone:
                try:
                    src_pos = vrc_data[vrc_name]
                    new_head = t_mat_inv @ src_pos
                    old_head = t_bone.head.copy()
                    
                    t_bone.use_connect = False
                    orig_vec = t_bone.tail - t_bone.head
                    t_bone.head = new_head
                    t_bone.tail = new_head + orig_vec
                    
                    bone_utils.propagate_movement(t_bone, new_head - old_head)
                    count += 1
                except: pass
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"吸附了 {count} 根骨骼")
        return {'FINISHED'}

# ==========================================
# 3. Endfield -> MHWI 工具 (实装)
# ==========================================
class MHWI_OT_EndfieldMerge(bpy.types.Operator):
    """Endfield 转 MHWI (合并权重/重定向/重命名)"""
    bl_idname = "mhwi.endfield_merge"
    bl_label = "Endfield 转 MHWI"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中骨架")
            return {'CANCELLED'}
            
        # 使用 data_maps 中的映射
        name_mapping = data_maps.END_TO_MHWI_MAP
        prefix = "Bip001_"
        
        target_to_actual = {} # {MhBone_001: Spine}
        bones_to_merge = {}   # {Spine1: Spine} (需要被合并到 Spine)
        
        # 1. 规划阶段
        for bone in arm_obj.data.bones:
            orig_name = bone.name
            clean_name = orig_name[len(prefix):] if orig_name.startswith(prefix) else orig_name
            
            if clean_name in name_mapping:
                target_name = name_mapping[clean_name]
                if target_name not in target_to_actual:
                    target_to_actual[target_name] = orig_name
                else:
                    # 目标已存在，当前骨骼需要被合并
                    bones_to_merge[orig_name] = target_to_actual[target_name]
        
        # 2. 权重合并阶段
        meshes = [o for o in bpy.data.objects if o.type == 'MESH' and \
                  any(m.type=='ARMATURE' and m.object==arm_obj for m in o.modifiers)]
        
        for mesh in meshes:
            context.view_layer.objects.active = mesh
            for src, dst in bones_to_merge.items():
                if src in mesh.vertex_groups and dst in mesh.vertex_groups:
                    mod = mesh.modifiers.new(name="TempMix", type='VERTEX_WEIGHT_MIX')
                    mod.vertex_group_a = dst
                    mod.vertex_group_b = src
                    mod.mix_mode = 'ADD'
                    mod.mix_set = 'ALL'
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    mesh.vertex_groups.remove(mesh.vertex_groups[src])
        
        # 3. 骨骼编辑阶段
        context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        
        # 重定向子级并删除
        for src, dst in bones_to_merge.items():
            src_b = edit_bones.get(src)
            dst_b = edit_bones.get(dst)
            if src_b and dst_b:
                for child in src_b.children:
                    child.parent = dst_b
                edit_bones.remove(src_b)
                
        # 重命名保留的骨骼
        for target, current in target_to_actual.items():
            b = edit_bones.get(current)
            if b: b.name = target
            
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 4. 修正网格顶点组名称
        for mesh in meshes:
            for target, original in target_to_actual.items():
                clean_orig = original[len(prefix):] if original.startswith(prefix) else original
                if original in mesh.vertex_groups:
                    mesh.vertex_groups[original].name = target
                elif clean_orig in mesh.vertex_groups:
                    mesh.vertex_groups[clean_orig].name = target
                    
        self.report({'INFO'}, "Endfield -> MHWI 转换完成")
        return {'FINISHED'}

# ==========================================
# 4. MMD -> MHWI 吸附 (实装)
# ==========================================
class MHWI_OT_MMDSnap(bpy.types.Operator):
    """MMD 骨骼吸附 (含手肘/脚趾修正)"""
    bl_idname = "mhwi.mmd_snap"
    bl_label = "MMD 骨骼吸附"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected) != 2: return {'CANCELLED'}
        
        target = active_obj # MMD
        source = [o for o in selected if o != target][0] # MHWI (Source)
        
        # 检测语言映射
        all_bones = [b.name for b in target.data.bones]
        if "下半身" in all_bones: mapping = data_maps.JP_MMD_MAP
        elif "Hips" in all_bones: mapping = data_maps.EN_MMD_MAP
        else:
            self.report({'WARNING'}, "未识别到 MMD 骨骼")
            return {'CANCELLED'}
            
        # 预读取源数据
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        src_heads = {b.name: source.matrix_world @ b.head_local for b in source.data.bones}
        src_tails = {b.name: source.matrix_world @ b.tail_local for b in source.data.bones}
        
        context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = target.data.edit_bones
        t_mat_inv = target.matrix_world.inverted()
        
        # 记录手肘前位置用于修正辅助骨
        elbow_before = None
        if "MhBone_007" in edit_bones: elbow_before = edit_bones["MhBone_007"].head.copy()
        
        for mmd_name, mhw_name in mapping:
            if mmd_name not in edit_bones: continue
            if mhw_name not in src_heads: continue
            
            t_bone = edit_bones[mmd_name]
            
            # 吸附位置
            t_bone.head = t_mat_inv @ src_heads[mhw_name]
            t_bone.tail = t_mat_inv @ src_tails[mhw_name]
            
            # 脚趾修正
            if mmd_name in ["足先EX.L", "Left toe", "足先EX.R", "Right toe"]:
                t_bone.head.y = -104.611
                t_bone.tail.y = -104.607
                
        # 辅助骨骼修正
        if elbow_before and "MhBone_007" in edit_bones:
            elbow_now = edit_bones["MhBone_007"].head
            offset = elbow_now - elbow_before
            for aux in ["MhBone_101", "MhBone_102", "MhBone_103", "MhBone_104"]:
                if aux in edit_bones:
                    edit_bones[aux].head += offset
                    edit_bones[aux].tail += offset
                    
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "MMD 吸附完成")
        return {'FINISHED'}
    
class MHWI_OT_ApplyStandardX(bpy.types.Operator):
    """执行标准化 X 流程：根据预设合并权重、删除辅助骨并重命名为主骨"""
    bl_idname = "mhwi.apply_standard_x"
    bl_label = "1. 标准化重命名 (X)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.mhw_suite_settings # 使用你定义的 settings
        arm_obj = context.active_object
        
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中一个骨架")
            return {'CANCELLED'}

        # 1. 实例化加载器并读取 X 预设
        mapper = BoneMapManager()
        if not mapper.load_preset(settings.import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, f"无法加载预设: {settings.import_preset_enum}")
            return {'CANCELLED'}

        # 2. 预分析 (锁定哪些骨头要变，哪些要并)
        analysis = {} # { standard_key: (main_bone_name, [aux_bone_names]) }
        for std_key in STANDARD_BONE_NAMES:
            main, auxs = mapper.get_matches_for_standard(arm_obj, std_key)
            if main:
                analysis[std_key] = (main, auxs)

        if not analysis:
            self.report({'WARNING'}, "当前骨架与所选预设没有匹配项")
            return {'CANCELLED'}

        # 3. 权重合并阶段 (需要在 OBJECT 模式下对 Mesh 进行操作)
        # 找到所有受此骨架影响的 Mesh
        meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm_obj]
        
        original_mode = context.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        for mesh_obj in meshes:
            for std_key, (main_name, aux_list) in analysis.items():
                if aux_list:
                    # 将辅助骨的权重合并给主骨
                    weight_utils.merge_vgroups_for_mapping(mesh_obj, main_name, aux_list)

        # 4. 骨骼重命名与清理阶段 (需要在 EDIT 模式下操作)
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        
        rename_count = 0
        deleted_count = 0

        # 为了防止改名冲突，我们先统一收集所有要操作的动作
        for std_key, (main_name, aux_list) in analysis.items():
            if main_name in edit_bones:
                # 重命名主骨为标准名 (如 Bip001_L_Arm -> upperarm_L)
                edit_bones[main_name].name = std_key
                rename_count += 1
            
            # 删除辅助骨 (因为权重已经并入主骨，这些骨头现在是废骨)
            for aux_name in aux_list:
                if aux_name in edit_bones:
                    edit_bones.remove(edit_bones[aux_name])
                    deleted_count += 1

        # 切回原始模式
        bpy.ops.object.mode_set(mode=original_mode)
        
        self.report({'INFO'}, f"标准化完成：重命名 {rename_count} 根，清理 {deleted_count} 根辅助骨")
        return {'FINISHED'}

# 注册所有类
classes = [
    MHWI_OT_AlignNonPhysics, 
    MHWI_OT_VRC_Rename, 
    MHWI_OT_VRC_Snap,
    MHWI_OT_EndfieldMerge,
    MHWI_OT_MMDSnap,
    MHWI_OT_ApplyStandardX,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)