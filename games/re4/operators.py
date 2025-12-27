import bpy
from . import data_maps

class RE4_OT_MHWI_Rename(bpy.types.Operator):
    """将选中的 MHWI 骨架重命名为 RE4 标准"""
    bl_idname = "re4.mhwi_rename"
    bl_label = "MHWI -> RE4 重命名"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请选中一个骨架对象")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        
        count = 0
        for old, new in data_maps.MHWI_TO_RE4_MAP.items():
            if old in edit_bones:
                edit_bones[old].name = new
                count += 1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"已重命名 {count} 根骨骼")
        return {'FINISHED'}


class RE4_OT_Endfield_Convert(bpy.types.Operator):
    """将 Endfield 网格的顶点组重命名为 RE4 标准，并合并重名权重"""
    bl_idname = "re4.endfield_convert"
    bl_label = "Endfield -> RE4 权重转换"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            self.report({'ERROR'}, "请选中至少一个网格物体")
            return {'CANCELLED'}

        for obj in selected_meshes:
            self.process_mesh(obj)
            
        self.report({'INFO'}, f"处理了 {len(selected_meshes)} 个网格")
        return {'FINISHED'}

    def process_mesh(self, obj):
        mapping = data_maps.ENDFIELD_TO_RE4_MAP
        
        # 1. 重命名
        for old, new in mapping.items():
            if old in obj.vertex_groups:
                # 检查新名字是否已经存在（如果有，先临时改个名，后面让合并逻辑处理）
                if new in obj.vertex_groups:
                    # 如果目标名字已存在，我们不能直接 rename 覆盖，Blender 会报错或自动加后缀
                    # 所以我们保留它，让它自然变成 .001，后续合并逻辑会处理它
                    pass
                obj.vertex_groups[old].name = new

        # 2. 扫描需要合并的组 (name 与 name.001)
        merge_dict = {}
        for vg in obj.vertex_groups:
            # 提取基础名 (移除 .001 后缀)
            base = vg.name.split('.')[0]
            if base not in merge_dict:
                merge_dict[base] = []
            merge_dict[base].append(vg.name)

        # 3. 执行合并
        for base_name, group_list in merge_dict.items():
            if len(group_list) <= 1:
                continue
            
            # 确保目标组存在
            target_group = obj.vertex_groups.get(base_name)
            if not target_group:
                target_group = obj.vertex_groups.new(name=base_name)
            
            # 使用 Vertex Weight Mix 修改器合并权重
            
            for g_name in group_list:
                if g_name == base_name: continue
                
                # 使用修改器混合权重 (Add模式)
                mod = obj.modifiers.new(name="TempMerge", type='VERTEX_WEIGHT_MIX')
                mod.vertex_group_a = base_name
                mod.vertex_group_b = g_name
                mod.mix_mode = 'ADD'
                mod.mix_set = 'ALL'
                
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply(modifier=mod.name)
                
                # 删除旧组
                obj.vertex_groups.remove(obj.vertex_groups[g_name])

# 注册逻辑
classes = [RE4_OT_MHWI_Rename, RE4_OT_Endfield_Convert]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)