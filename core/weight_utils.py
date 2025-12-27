import bpy

def merge_weights_and_delete_bones(armature_obj, bone_pairs):
    """
    bone_pairs: List of (keep_bone_name, delete_bone_name)
    """
    mesh_objects = [o for o in bpy.data.objects 
                   if o.type == 'MESH' and 
                   any(m.type == 'ARMATURE' and m.object == armature_obj for m in o.modifiers)]
    
    for obj in mesh_objects:
        vg = obj.vertex_groups
        for keep, delete in bone_pairs:
            if keep not in vg or delete not in vg:
                continue
            
            vg_keep = vg[keep]
            vg_del = vg[delete]
            
            mod = obj.modifiers.new(name="TempMerge", type='VERTEX_WEIGHT_MIX')
            mod.vertex_group_a = keep
            mod.vertex_group_b = delete
            mod.mix_mode = 'ADD'
            mod.mix_set = 'ALL'
            
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            
            vg.remove(vg_del)
            
    # 删除骨骼
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_obj.data.edit_bones
    for _, delete in bone_pairs:
        if delete in edit_bones:
            edit_bones.remove(edit_bones[delete])
    bpy.ops.object.mode_set(mode='OBJECT')