import bpy
from ...core import bone_utils
from . import data_maps

# ==========================================
# RE4 假骨工具 (FakeBone Tools)
# ==========================================

class RE4_OT_FakeBody_Process(bpy.types.Operator):
    """创建身体 End 骨骼"""
    bl_idname = "re4.fake_body_process"
    bl_label = "创建身体 End 骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected) != 2:
            self.report({'ERROR'}, "请选择两个骨架 (源 -> 目标)")
            return {'CANCELLED'}
        
        SourceModel_Original = context.active_object
        RulerModel_Original = [o for o in selected if o != SourceModel_Original][0]
        
        bpy.ops.object.select_all(action='DESELECT')
        SourceModel_Original.select_set(True)
        context.view_layer.objects.active = SourceModel_Original
        bpy.ops.object.duplicate()
        SourceModel = context.active_object
        
        bpy.ops.object.select_all(action='DESELECT')
        RulerModel_Original.select_set(True)
        context.view_layer.objects.active = RulerModel_Original
        bpy.ops.object.duplicate()
        RulerModel = context.active_object

        BoneName = data_maps.FAKEBONE_BODY_BONES
        armature = RulerModel
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='POSE')

        for bone_name in BoneName:
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                crc = bone.constraints.new('COPY_ROTATION')
                crc.target = SourceModel
                crc.subtarget = bone_name
        
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints: b.constraints.remove(c)
            
        bpy.ops.pose.armature_apply()
        bpy.ops.object.mode_set(mode='EDIT')

        for b in [b for b in armature.data.edit_bones if "end" in b.name]:
            armature.data.edit_bones.remove(b)
            
        FakeName = data_maps.FAKEBONE_BODY_FAKES
        ParentName = data_maps.FAKEBONE_BODY_PARENTS
        
        for fake in FakeName:
            if fake not in armature.data.edit_bones: continue
            bone = armature.data.edit_bones[fake]
            for pname in ParentName[fake]:
                if pname not in armature.data.edit_bones: continue
                suffix = "_end"
                if (pname[0] in ['L', 'R']) and len(ParentName[fake]) > 1:
                    suffix = f"_end{pname[0]}"
                new_bone = armature.data.edit_bones.new(bone.name + suffix)
                new_bone.head = bone.head
                new_bone.tail = bone.tail
                new_bone.roll = bone.roll
                new_bone.parent = armature.data.edit_bones[pname]
                new_bone.use_connect = bone.use_connect

        bpy.ops.object.mode_set(mode='POSE')
        for bone_name in BoneName:
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                csc = bone.constraints.new('COPY_SCALE')
                csc.target = SourceModel
                csc.subtarget = bone_name
                clc = bone.constraints.new('COPY_LOCATION')
                clc.target = SourceModel
                clc.subtarget = bone_name
                
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints: b.constraints.remove(c)
        bpy.ops.pose.armature_apply()
        
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in list(armature.data.edit_bones):
            if "end" not in bone.name:
                armature.data.edit_bones.remove(bone)
                
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(SourceModel)
        
        self.report({'INFO'}, "身体 End 骨骼创建完成")
        return {'FINISHED'}

class RE4_OT_FakeFingers_Process(bpy.types.Operator):
    """创建手指 End 骨骼"""
    bl_idname = "re4.fake_fingers_process"
    bl_label = "创建手指 End 骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected_armatures = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
        
        if len(selected_armatures) != 2:
            self.report({'ERROR'}, f"请选择两个骨架对象（当前选中了 {len(selected_armatures)} 个）")
            return {'CANCELLED'}
        
        SourceModel_Original = bpy.context.active_object
        RulerModel_Original = [obj for obj in selected_armatures if obj != SourceModel_Original][0]
        
        # 复制骨架
        bpy.ops.object.select_all(action='DESELECT')
        SourceModel_Original.select_set(True)
        bpy.context.view_layer.objects.active = SourceModel_Original
        bpy.ops.object.duplicate()
        SourceModel = bpy.context.active_object
        SourceModel.name = SourceModel_Original.name + "_temp_source"
        
        bpy.ops.object.select_all(action='DESELECT')
        RulerModel_Original.select_set(True)
        bpy.context.view_layer.objects.active = RulerModel_Original
        bpy.ops.object.duplicate()
        RulerModel = bpy.context.active_object
        RulerModel.name = RulerModel_Original.name + "_end_bones"
        
        BoneName = data_maps.FAKEBONE_FINGER_BONES
        ParentName = {}

        armature = RulerModel
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='POSE')

        # 1. 旋转约束
        for bone_name in BoneName:
            if bone_name not in armature.pose.bones: continue
            bone = armature.pose.bones[bone_name]
            copy_rotation = bone.constraints.new('COPY_ROTATION')
            copy_rotation.target = SourceModel
            copy_rotation.subtarget = bone_name

        # 2. 建立父级关系表
        for bone_name in BoneName:
            if bone_name == "R_Hand" or bone_name == "L_Hand": continue
            if bone_name not in armature.pose.bones: continue
            bone = armature.pose.bones[bone_name]
            
            pname = bone.parent.name
            if pname not in ParentName:
                ParentName[pname] = [bone_name]
            else:
                ParentName[pname].append(bone_name)

        # 应用约束
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints: b.constraints.remove(c)
        bpy.ops.pose.armature_apply()
        
        bpy.ops.object.mode_set(mode='EDIT')

        # 删除旧end
        for bone in list(armature.data.edit_bones):
            if "end" in bone.name:
                armature.data.edit_bones.remove(bone)

        # 3. 创建新 End 骨骼
        for fake in ParentName:
            if fake not in armature.data.edit_bones: continue
            bone = armature.data.edit_bones[fake]
            
            for child_name in ParentName[fake]:
                if child_name not in armature.data.edit_bones: continue
                
                if (child_name.startswith('L') or child_name.startswith('R')) and len(ParentName[fake]) > 1:
                    # 这里的魔法数字 [2] 是根据 RE4 命名规范：R_Index... -> I
                    suffix = "_end{}".format(child_name[2])
                    new_bone = armature.data.edit_bones.new(bone.name + suffix)
                else:
                    new_bone = armature.data.edit_bones.new(bone.name + "_end")
                
                new_bone.head = bone.head
                new_bone.tail = bone.tail
                new_bone.roll = bone.roll
                
                parent_bone = armature.data.edit_bones[child_name]
                new_bone.parent = parent_bone
                new_bone.use_connect = bone.use_connect
        
        bpy.ops.object.mode_set(mode='POSE')

        # 4. 缩放和位置约束
        for bone_name in BoneName:
            if bone_name not in armature.pose.bones: continue
            bone = armature.pose.bones[bone_name]
            
            csc = bone.constraints.new('COPY_SCALE')
            csc.target = SourceModel
            csc.subtarget = bone_name
            clc = bone.constraints.new('COPY_LOCATION')
            clc.target = SourceModel
            clc.subtarget = bone_name

        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.visual_transform_apply()
        for b in armature.pose.bones:
            for c in b.constraints: b.constraints.remove(c)
        bpy.ops.pose.armature_apply()
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 删除所有非 end 骨骼
        for bone in list(armature.data.edit_bones):
            if "end" not in bone.name:
                armature.data.edit_bones.remove(bone)
        
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(SourceModel)
        
        # 选中新骨架
        bpy.ops.object.select_all(action='DESELECT')
        armature.select_set(True)
        context.view_layer.objects.active = armature
        
        self.report({'INFO'}, "手指 End 骨骼创建完成")
        return {'FINISHED'}

class RE4_OT_FakeBody_Merge(bpy.types.Operator):
    """合并身体骨骼"""
    bl_idname = "re4.fake_body_merge"
    bl_label = "合并身体骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected) != 2: return {'CANCELLED'}
        target = context.active_object
        end_arm = [o for o in selected if o != target][0]
        
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        end_arm.select_set(True)
        context.view_layer.objects.active = target
        bpy.ops.object.join()
        
        bpy.ops.object.mode_set(mode='EDIT')
        arm = target.data
        
        # 简单父子绑定逻辑
        for bone in arm.edit_bones:
            if "_end" in bone.name:
                base = bone.name.split("_end")[0]
                if base in arm.edit_bones:
                    bone.parent = arm.edit_bones[base]
                    bone.use_connect = False
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "身体骨骼合并完成")
        return {'FINISHED'}

class RE4_OT_FakeFingers_Merge(bpy.types.Operator):
    """合并手指骨骼"""
    bl_idname = "re4.fake_fingers_merge"
    bl_label = "合并手指骨骼"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected_armatures = [obj for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
        if len(selected_armatures) != 2: return {'CANCELLED'}
        
        target_armature = context.active_object
        end_armature = [obj for obj in selected_armatures if obj != target_armature][0]
        
        bpy.ops.object.select_all(action='DESELECT')
        target_armature.select_set(True)
        end_armature.select_set(True)
        bpy.context.view_layer.objects.active = target_armature
        bpy.ops.object.join()
        
        armature = target_armature
        bpy.ops.object.mode_set(mode='EDIT')

        # 1. 挂载 fakebones 到父级
        fakebones = [b for b in armature.data.edit_bones if "_end" in b.name]
        for fakebone in fakebones:
            base_name = fakebone.name.split("_end")[0]
            if base_name in armature.data.edit_bones:
                fakebone.parent = armature.data.edit_bones[base_name]
                fakebone.use_connect = False

        # 2. 挂载手指第一节到 End 骨骼 (Mapping)
        parent_mappings = data_maps.FAKEBONE_FINGER_MERGE_MAP
        for child_name, parent_name in parent_mappings.items():
            if child_name in armature.data.edit_bones and parent_name in armature.data.edit_bones:
                child = armature.data.edit_bones[child_name]
                parent = armature.data.edit_bones[parent_name]
                child.parent = parent
                child.use_connect = False

        # 3. 挂载手指后续指节 (Pattern)
        finger_patterns = data_maps.FAKEBONE_FINGER_PATTERNS
        for finger_base, num_segments in finger_patterns:
            for i in range(2, num_segments + 1):
                child_name = f"{finger_base}{i}"
                parent_name = f"{finger_base}{i-1}_end"
                
                if child_name in armature.data.edit_bones and parent_name in armature.data.edit_bones:
                    child = armature.data.edit_bones[child_name]
                    parent = armature.data.edit_bones[parent_name]
                    child.parent = parent
                    child.use_connect = False
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "手指骨骼合并完成")
        return {'FINISHED'}

class RE4_OT_AlignBones(bpy.types.Operator):
    """完全对齐同名骨骼"""
    bl_idname = "re4.align_bones_full"
    bl_label = "完全对齐"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected) != 2: return {'CANCELLED'}
        target = active_obj
        source = [o for o in selected if o != target][0]
        
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        
        src_data = {}
        s_mat = source.matrix_world
        for b in source.data.bones:
            src_data[b.name] = {'head': s_mat @ b.head_local.copy(), 'tail': s_mat @ b.tail_local.copy()}
            
        context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode='EDIT')
        t_mat_inv = target.matrix_world.inverted()
        
        count = 0
        for b in target.data.edit_bones:
            if b.name in src_data:
                old_head = b.head.copy()
                new_head = t_mat_inv @ src_data[b.name]['head']
                b.head = new_head
                b.tail = t_mat_inv @ src_data[b.name]['tail']
                
                bone_utils.propagate_movement(b, new_head - old_head)
                count += 1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"完全对齐了 {count} 根骨骼")
        return {'FINISHED'}

class RE4_OT_AlignBones_Pos(bpy.types.Operator):
    """仅对齐位置"""
    bl_idname = "re4.align_bones_pos"
    bl_label = "仅对齐位置"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        selected = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected) != 2: return {'CANCELLED'}
        target = active_obj
        source = [o for o in selected if o != target][0]
        
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        
        src_heads = {b.name: source.matrix_world @ b.head_local for b in source.data.bones}
        
        context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode='EDIT')
        t_mat_inv = target.matrix_world.inverted()
        
        count = 0
        for b in target.data.edit_bones:
            if b.name in src_heads:
                old_head = b.head.copy()
                new_head = t_mat_inv @ src_heads[b.name]
                orig_vec = b.tail - b.head
                
                b.head = new_head
                b.tail = new_head + orig_vec
                
                bone_utils.propagate_movement(b, new_head - old_head)
                count += 1
                
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"位置对齐了 {count} 根骨骼")
        return {'FINISHED'}

classes = [
    RE4_OT_FakeBody_Process, RE4_OT_FakeFingers_Process,
    RE4_OT_FakeBody_Merge, RE4_OT_FakeFingers_Merge,
    RE4_OT_AlignBones, RE4_OT_AlignBones_Pos,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)