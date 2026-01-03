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
    
def merge_vgroups_to_main(obj, main_name, aux_names):
    """
    将多个辅助顶点组的权重合并到主顶点组
    obj: Mesh 对象
    main_name: 主顶点组名 (String)
    aux_names: 辅助顶点组名列表 (List of Strings)
    """
    if main_name not in obj.vertex_groups:
        obj.vertex_groups.new(name=main_name)
    
    target_vg = obj.vertex_groups[main_name]
    
    for aux_name in aux_names:
        if aux_name in obj.vertex_groups:
            # 使用 Blender 内置的 Mix 修饰符逻辑或简单通过顶点遍历
            # 这里采用最稳妥的顶点遍历合并
            source_vg = obj.vertex_groups[aux_name]
            
            for v in obj.data.vertices:
                try:
                    # 获取辅助组的权重
                    weight = source_vg.get_weight(v.index)
                    if weight > 0:
                        # 叠加到主组
                        target_vg.add([v.index], weight, 'ADD')
                except RuntimeError:
                    pass # 该顶点不在辅助组中
            
            # 合并完后删除辅助组，防止重名冲突
            obj.vertex_groups.remove(source_vg)