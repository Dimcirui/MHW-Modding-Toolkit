import bpy
import copy
from . import data_maps

class MHWILDS_OT_TPoseConvert(bpy.types.Operator):
    """强制将 MHWilds 骨骼转为 MHWI 标准 T-Pose"""
    bl_idname = "mhwilds.tpose_convert"
    bl_label = "转为 MHWI T-Pose"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选择一个骨架对象")
            return {'CANCELLED'}

        # 从数据表中提取所有需要重置的 MHWilds 骨骼名 (List item[1])
        wilds_bones = [item[1] for item in data_maps.WILDS_TPOSE_LIST]

        # --- 阶段 1: 姿态强制对齐 ---
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')

        # 选中列表中的骨骼
        for b_name in wilds_bones:
            if b_name in arm_obj.pose.bones:
                arm_obj.pose.bones[b_name].bone.select = True

        # 强制设置归零矩阵 (模拟 T-Pose 旋转)
        for p_bone in context.selected_pose_bones:
            zero = copy.deepcopy(p_bone.matrix)
            # 这里的矩阵操作是原脚本的核心：
            # 设置 Rotation 部分为单位矩阵的变体，Translation 部分归零
            zero[0][0], zero[0][1], zero[0][2] = 1.0, 0.0, 0.0
            zero[1][0], zero[1][1], zero[1][2] = 0.0, 0.0, -1.0
            zero[2][0], zero[2][1], zero[2][2] = 0.0, 1.0, 0.0
            zero[3][0], zero[3][1], zero[3][2] = 0.0, 0.0, 0.0
            p_bone.matrix = zero
        
        context.view_layer.update()

        # --- 阶段 2: 烘焙网格顶点 (应用现有修改器) ---
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 找到骨架下的所有网格物体
        meshes = [child for child in arm_obj.children if child.type == 'MESH']
        
        if meshes:
            bpy.ops.object.select_all(action='DESELECT')
            for m in meshes:
                m.hide_set(False)
                m.select_set(True)
            
            # 激活其中一个作为主物体以便操作
            context.view_layer.objects.active = meshes[0]
            
            # 将修改器应用到网格数据 (Convert to Mesh)
            bpy.ops.object.convert(target='MESH')

        # --- 阶段 3: 应用骨架的当前 Pose 为默认 Pose ---
        context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.armature_apply(selected=True)

        # --- 阶段 4: 重新为网格挂载骨架修改器 ---
        bpy.ops.object.mode_set(mode='OBJECT')
        for m in meshes:
            # 检查是否已有 armature modifier，没有则添加
            has_mod = False
            for mod in m.modifiers:
                if mod.type == 'ARMATURE':
                    has_mod = True
                    break
            
            if not has_mod:
                mod = m.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = arm_obj
        
        self.report({'INFO'}, f"MHWilds -> MHWI T-Pose 转换成功 (处理了 {len(meshes)} 个网格)")
        return {'FINISHED'}
    
class MHWILDS_OT_Endfield_Snap(bpy.types.Operator):
    """根据映射表将 Endfield 骨骼位置对齐到 MHWilds (位置只读，保留原方向)"""
    bl_idname = "mhwilds.endfield_snap"
    bl_label = "Endfield -> MHWs 骨骼对齐"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        
        if len(selected_objects) != 2 or not active_obj:
            self.report({'ERROR'}, "请选择两个骨架 (先选参考源，后选目标/活动骨架)")
            return {'CANCELLED'}

        target_armature = active_obj # B (MHWs/Endfield)
        source_armature = [obj for obj in selected_objects if obj != target_armature][0] # A (参考源)
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        source_bones = source_armature.data.bones
        target_edit_bones = target_armature.data.edit_bones
        
        # 构建 B -> A 的映射字典
        # 列表格式是 [A, B]，我们要让 B 找 A，所以 key 是 B，value 是 A
        bone_map = {}
        for pair in data_maps.ENDFIELD_SNAP_MAP:
            src_name = pair[0] # A
            tgt_name = pair[1] # B
            bone_map[tgt_name] = src_name
            
        aligned_count = 0
        
        try:
            for t_bone in target_edit_bones:
                b_name = t_bone.name
                
                if b_name in bone_map:
                    a_name = bone_map[b_name]
                    
                    if a_name in source_bones:
                        s_bone = source_bones[a_name]
                        
                        # 计算
                        orig_vec = t_bone.tail - t_bone.head
                        orig_len = orig_vec.length
                        if orig_len == 0: continue
                        
                        orig_dir = orig_vec.normalized()
                        
                        # 坐标转换
                        s_matrix = source_armature.matrix_world
                        s_head_world = s_matrix @ s_bone.head_local
                        
                        t_matrix_inv = target_armature.matrix_world.inverted()
                        new_head_local = t_matrix_inv @ s_head_world
                        
                        # 应用
                        t_bone.head = new_head_local
                        t_bone.tail = new_head_local + (orig_dir * orig_len)
                        
                        aligned_count += 1
                        
        except Exception as e:
            self.report({'ERROR'}, f"执行出错: {e}")
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'CANCELLED'}
            
        bpy.ops.object.mode_set(mode='OBJECT')
        
        if aligned_count > 0:
            self.report({'INFO'}, f"成功对齐 {aligned_count} 根骨骼")
        else:
            self.report({'WARNING'}, "未找到任何匹配骨骼")
            
        return {'FINISHED'}

classes = [MHWILDS_OT_TPoseConvert, MHWILDS_OT_Endfield_Snap]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)