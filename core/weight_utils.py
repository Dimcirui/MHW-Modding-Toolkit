import bpy

def merge_weights_and_delete_bones(armature_obj, bone_pairs):
    """
    bone_pairs: List of (keep_bone_name, delete_bone_name)
    """
    # 1. 找到受该骨架影响的所有网格
    mesh_objects = [o for o in bpy.data.objects 
                   if o.type == 'MESH' and 
                   any(m.type == 'ARMATURE' and m.object == armature_obj for m in o.modifiers)]
    
    # 2. 遍历网格处理权重
    for obj in mesh_objects:
        # 激活物体以确保修改器操作正常
        bpy.context.view_layer.objects.active = obj
        vg = obj.vertex_groups
        
        for keep, delete in bone_pairs:
            # 检查两个组是否都存在于该网格
            if keep not in vg or delete not in vg:
                continue
            
            # 添加混合修改器
            mod = obj.modifiers.new(name="TempMerge", type='VERTEX_WEIGHT_MIX')
            mod.vertex_group_a = keep
            mod.vertex_group_b = delete
            mod.mix_mode = 'ADD'
            mod.mix_set = 'ALL'
            
            # 应用修改器
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as e:
                print(f"Warning: Failed to apply modifier on {obj.name}: {e}")
                # 如果应用失败，移除修改器以防堆积
                if mod.name in obj.modifiers:
                    obj.modifiers.remove(mod)
                continue
            
            if delete in vg:
                vg.remove(vg[delete])
            
    # 3. 删除骨骼
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_obj.data.edit_bones
    
    deleted_count = 0
    for _, delete in bone_pairs:
        if delete in edit_bones:
            edit_bones.remove(edit_bones[delete])
            deleted_count += 1
            
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"Deleted {deleted_count} bones.")