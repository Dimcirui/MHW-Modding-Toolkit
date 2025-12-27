import bpy
from ...core import bone_utils  # 引用核心工具 (相对导入)
from . import data_maps         # 引用同目录下的数据

class MHWI_OT_AlignNonPhysics(bpy.types.Operator):
    bl_idname = "mhwi.align_non_physics"
    bl_label = "对齐非物理骨骼"
    
    def execute(self, context):
        # 使用 data_maps 中的数据
        mapping = data_maps.END_TO_MHWI_MAP
        
        # 使用 core 中的工具
        # bone_utils.propagate_movement(...)
        
        self.report({'INFO'}, "MHWI 对齐完成")
        return {'FINISHED'}

# 该文件负责注册自己的类
classes = [MHWI_OT_AlignNonPhysics]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)