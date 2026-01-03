import bpy
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES
from . import weight_utils

class MODDER_OT_ApplyStandardX(bpy.types.Operator):
    """执行标准化 X：合并权重并重命名为基础名"""
    bl_idname = "modder.apply_standard_x"
    bl_label = "1. 标准化重命名 (X)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 引用你定义的 mhw_suite_settings
        settings = context.scene.mhw_suite_settings 
        arm_obj = context.active_object
        
        # 1. 加载预设 (此时 BoneMapManager 已能正确找路径)
        mapper = BoneMapManager()
        if not mapper.load_preset(settings.import_preset_enum, is_import_x=True):
            self.report({'ERROR'}, "预设加载失败")
            return {'CANCELLED'}

        # 2. 匹配分析
        analysis = {}
        for std_key in STANDARD_BONE_NAMES:
            main, auxs = mapper.get_matches_for_standard(arm_obj, std_key)
            if main: analysis[std_key] = (main, auxs)

        # 3. 权重合并 (调用同级目录的 weight_utils)
        meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm_obj]
        bpy.ops.object.mode_set(mode='OBJECT')
        for mesh_obj in meshes:
            for std_key, (main_name, aux_list) in analysis.items():
                if aux_list:
                    weight_utils.merge_vgroups_for_mapping(mesh_obj, main_name, aux_list)

        # 4. 骨骼重命名 (Edit Mode)
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_obj.data.edit_bones
        for std_key, (main_name, aux_list) in analysis.items():
            if main_name in edit_bones:
                edit_bones[main_name].name = std_key
            for aux_name in aux_list:
                if aux_name in edit_bones:
                    edit_bones.remove(edit_bones[aux_name])

        bpy.ops.object.mode_set(mode='OBJECT')
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