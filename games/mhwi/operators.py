import bpy
from ...core import bone_utils
from . import data_maps
from ...core import bone_utils
from ...core import weight_utils
from ...core.bone_mapper import BoneMapManager, STANDARD_BONE_NAMES

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

# 注册所有类
classes = [
    MHWI_OT_AlignNonPhysics, 
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)