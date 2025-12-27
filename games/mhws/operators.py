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

classes = [MHWILDS_OT_TPoseConvert]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)