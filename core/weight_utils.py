import bpy
from mathutils import Vector

def merge_weights_and_delete_bones(armature_obj, bone_pairs):
    """
    bone_pairs: List of (keep_bone_name, delete_bone_name)
    """
    # 构建辅助结构：被删除骨骼集合，以及子→父映射
    deleted_set = {delete for _, delete in bone_pairs}
    child_to_parent = {child: parent for parent, child in bone_pairs}

    def find_final_target(bone_name):
        """沿父骨链向上，找到第一个不被删除的骨骼（最终存活祖先）。"""
        visited = set()
        current = bone_name
        while current in deleted_set and current not in visited:
            visited.add(current)
            parent = child_to_parent.get(current)
            if parent is None:
                break
            current = parent
        return current

    # 为每个被删除骨骼，直接计算其最终存活祖先（跳过中间已删除的骨骼）
    merge_map = {delete: find_final_target(parent)
                 for parent, delete in bone_pairs}

    # 1. 找到受该骨架影响的所有网格
    # 主：通过姿态修改器绑定
    bound_meshes = {o for o in bpy.data.objects
                    if o.type == 'MESH' and
                    any(m.type == 'ARMATURE' and m.object == armature_obj for m in o.modifiers)}
    # 补充：未绑定修改器但作为该骨架子级、且含有待删除骨骼同名顶点组的网格
    delete_names = set(merge_map.keys())
    extra_meshes = {o for o in bpy.data.objects
                    if o.type == 'MESH' and o not in bound_meshes and
                    o.parent == armature_obj and
                    any(vg.name in delete_names for vg in o.vertex_groups)}
    mesh_objects = bound_meshes | extra_meshes

    # 2. 遍历网格，将每个被删除骨骼的权重直接合并到其最终存活祖先
    #
    # 按**顶点**扫一遍，而不是「每根待删骨 × 全部顶点」。后者是这里原本的写法，代价
    # O(待删骨数 × 顶点数)，且每个顶点都要靠 vertex_group.weight() 抛 RuntimeError 来
    # 判断「不在这个组里」—— 异常在 Python 里极贵。合并整套表情骨时这是 370 × 全网格
    # 顶点数次带异常的调用。
    #
    # 换成遍历 vert.groups：它只列出该顶点**真正属于**的组，所以总代价降到「权重条目
    # 数」这个量级，而且一次异常都不抛。实测（荒野女性参考模型，32,291 顶点，合并
    # 370 根表情骨）：旧写法 40 根就要 1.32 秒（370 根按线性外推约 12 秒），新写法
    # 40 根 0.11 秒、**370 根 0.18 秒** —— 耗时几乎不再随合并骨数增长。
    for obj in mesh_objects:
        vg = obj.vertex_groups
        # 组索引 -> 目标组，一次解析好；顺带按需新建目标组
        targets = {}
        for delete, final_target in merge_map.items():
            delete_vg = vg.get(delete)
            if delete_vg is None:
                continue
            targets[delete_vg.index] = vg.get(final_target) or vg.new(name=final_target)
        if not targets:
            continue

        # 先收集再写入：写入会改变顶点的所属组，边遍历 vert.groups 边写有可能读到
        # 正在变动的集合。
        pending = {}
        for vert in obj.data.vertices:
            for g in vert.groups:
                target_vg = targets.get(g.group)
                if target_vg is not None and g.weight:
                    pending.setdefault(target_vg.index, []).append((vert.index, g.weight))

        for target_index, entries in pending.items():
            target_vg = vg[target_index]
            for vert_index, weight in entries:
                # 'ADD' 累加到已有权重（顶点原本不在组里时等同于赋值），Blender 自己
                # 把结果钳在 [0, 1]，与原先显式 min(..., 1.0) 的行为一致。
                target_vg.add([vert_index], weight, 'ADD')

        for delete in merge_map:
            delete_vg = vg.get(delete)
            if delete_vg is not None:
                vg.remove(delete_vg)

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
    
def merge_vgroups_multi(obj, source_names, target_name):
    """
    将多个源顶点组权重合并到目标组（单次顶点遍历，上限1.0），合并后删除源组。
    obj: Mesh 对象
    source_names: 源顶点组名列表
    target_name: 目标顶点组名
    """
    target_vg = obj.vertex_groups.get(target_name)
    if target_vg is None:
        target_vg = obj.vertex_groups.new(name=target_name)

    active_sources = [vg for vg in (obj.vertex_groups.get(n) for n in source_names) if vg is not None]
    if not active_sources:
        return

    # 遍历顶点自己的 groups，而不是对每个组问一次 vg.weight()——后者对不在组里的
    # 顶点会抛 RuntimeError，等于把异常当控制流用，顶点一多开销就很可观。
    source_indices = {vg.index for vg in active_sources}
    target_index = target_vg.index

    # 先收集再写入：写入会改变顶点的所属组，边遍历 vert.groups 边写有可能读到
    # 正在变动的集合。
    pending = []
    for vert in obj.data.vertices:
        total_src_w = 0.0
        tgt_w = 0.0
        for g in vert.groups:
            if g.group in source_indices:
                total_src_w += g.weight
            elif g.group == target_index:
                tgt_w = g.weight
        if total_src_w <= 0.0:
            continue
        pending.append((vert.index, min(tgt_w + total_src_w, 1.0)))

    for vert_index, weight in pending:
        target_vg.add([vert_index], weight, 'REPLACE')

    for src_vg in active_sources:
        obj.vertex_groups.remove(src_vg)


def rename_or_merge_vgroup(obj, old_name, new_name):
    """
    将顶点组重命名（目标不存在时）或合并权重（目标已存在时），合并后删除旧组。
    返回 True 表示执行了操作，False 表示旧组不存在。
    """
    old_vg = obj.vertex_groups.get(old_name)
    if old_vg is None:
        return False
    existing_vg = obj.vertex_groups.get(new_name)
    if existing_vg is None:
        old_vg.name = new_name
        return True
    old_index = old_vg.index
    existing_index = existing_vg.index
    pending = []
    for vert in obj.data.vertices:
        old_w = None
        existing_w = 0.0
        for g in vert.groups:
            if g.group == old_index:
                old_w = g.weight
            elif g.group == existing_index:
                existing_w = g.weight
        if old_w is None:
            continue
        pending.append((vert.index, min(existing_w + old_w, 1.0)))

    for vert_index, weight in pending:
        existing_vg.add([vert_index], weight, 'REPLACE')
    obj.vertex_groups.remove(old_vg)
    return True


def shape_key_to_weights(obj, active_kb, basis_kb, ignore_threshold=0.001,
                         weight_strength=1.0, smooth_factor=0.5,
                         smooth_iters=10, sync_seams=True, direction=None,
                         vg_name=None):
    """
    Convert a shape key to a vertex group using normalized, Laplacian-smoothed weights.

    Weights are normalized so the vertex with the largest displacement always gets 1.0,
    with others scaled proportionally. Coincident vertices (UV seam duplicates) are
    synced after each smoothing pass to prevent tearing.

    direction: optional normalized Vector. When set, only vertices whose displacement
    projects positively onto this axis contribute; weight = dot product magnitude.
    This lets you split a single shape key (e.g. blink) into per-direction groups
    (upper eyelid vs lower eyelid) by running the operator twice with opposite signs.

    Returns the number of affected vertices, or None if no valid displacement is found.
    """
    vertices = obj.data.vertices
    v_count = len(vertices)
    raw_weights = [0.0] * v_count
    max_val = 0.0
    valid_count = 0

    filter_dir = Vector(direction).normalized() if direction is not None else None
    world_mat3 = obj.matrix_world.to_3x3() if filter_dir is not None else None

    seam_groups = []
    if sync_seams:
        coincident = {}
        for i, v in enumerate(vertices):
            key = (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
            coincident.setdefault(key, []).append(i)
        # Split coincident groups by normal similarity: true UV-seam duplicates share
        # nearly identical normals, while touching-but-separate geometry (e.g. upper/lower
        # lip when mouth is closed) faces opposite directions and must not be averaged.
        for group in coincident.values():
            if len(group) < 2:
                continue
            sub: list[list[int]] = []
            for v_idx in group:
                n = vertices[v_idx].normal
                for sg in sub:
                    if vertices[sg[0]].normal.dot(n) > 0.9:
                        sg.append(v_idx)
                        break
                else:
                    sub.append([v_idx])
            seam_groups.extend(sg for sg in sub if len(sg) > 1)

    for i in range(v_count):
        disp = active_kb.data[i].co - basis_kb.data[i].co
        if filter_dir is not None:
            val = (world_mat3 @ disp).dot(filter_dir)
            if val <= ignore_threshold:
                continue
        else:
            val = disp.length
            if val <= ignore_threshold:
                continue
        if val > max_val:
            max_val = val
        raw_weights[i] = val
        valid_count += 1

    if valid_count == 0 or max_val == 0:
        return None

    for i in range(v_count):
        if raw_weights[i] > 0:
            raw_weights[i] = min(1.0, (raw_weights[i] / max_val) * weight_strength)

    for group in seam_groups:
        avg = sum(raw_weights[idx] for idx in group) / len(group)
        for idx in group:
            raw_weights[idx] = avg

    if smooth_iters > 0:
        adj = {i: [] for i in range(v_count)}
        for edge in obj.data.edges:
            adj[edge.vertices[0]].append(edge.vertices[1])
            adj[edge.vertices[1]].append(edge.vertices[0])

        for _ in range(smooth_iters):
            new_weights = raw_weights.copy()
            for i in range(v_count):
                neighbors = adj[i]
                if not neighbors:
                    continue
                avg_n = sum(raw_weights[n] for n in neighbors) / len(neighbors)
                new_weights[i] = (raw_weights[i] * (1.0 - smooth_factor)
                                  + avg_n * smooth_factor)
            if sync_seams:
                for group in seam_groups:
                    avg = sum(new_weights[idx] for idx in group) / len(group)
                    for idx in group:
                        new_weights[idx] = avg
            raw_weights = new_weights

    if vg_name is None:
        vg_name = active_kb.name
    existing = obj.vertex_groups.get(vg_name)
    if existing:
        obj.vertex_groups.remove(existing)
    vg = obj.vertex_groups.new(name=vg_name)

    for i, w in enumerate(raw_weights):
        if w > 0.001:
            vg.add([i], min(1.0, w), 'REPLACE')

    return valid_count


def bone_has_weights(bone_name, mesh_objects):
    """检查骨骼在绑定网格中是否有任何顶点权重（用于尾骨判断）"""
    for obj in mesh_objects:
        vg = obj.vertex_groups.get(bone_name)
        if vg is None:
            continue
        vg_index = vg.index
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group == vg_index and g.weight > 0:
                    return True
    return False


def build_bone_chains(selected_names, arm_obj):
    """
    从选中骨骼中重建链结构（需在 EDIT 模式下调用）。
    返回 list of lists，每个子列表是一条从根到末的骨骼名链。
    分叉点处截断当前链，每个分支各自开始新链。
    """
    selected_set = set(selected_names)
    bones = arm_obj.data.edit_bones
    chains = []

    def traverse(name, current_chain):
        current_chain.append(name)
        bone = bones.get(name)
        if not bone:
            chains.append(list(current_chain))
            return
        sel_children = [c.name for c in bone.children if c.name in selected_set]
        if len(sel_children) == 0:
            chains.append(list(current_chain))
        elif len(sel_children) == 1:
            traverse(sel_children[0], current_chain)
        else:
            # 分叉：当前链在此截断，每个分支独立开始
            chains.append(list(current_chain))
            for child_name in sel_children:
                traverse(child_name, [])

    roots = [n for n in selected_names
             if bones.get(n) and
             (bones[n].parent is None or bones[n].parent.name not in selected_set)]

    for root in roots:
        traverse(root, [])

    return chains


def build_chain_from_head(head_name, arm_obj):
    """
    从 head_name 骨骼向下遍历，返回骨骼名列表（从根到末）。
    遇到分叉（多个子骨）时截断，不进入任何分支。
    需在 EDIT 模式下调用。
    """
    bones = arm_obj.data.edit_bones
    chain = []
    current = head_name
    while current:
        bone = bones.get(current)
        if bone is None:
            break
        chain.append(current)
        children = bone.children
        if len(children) == 1:
            current = children[0].name
        else:
            break
    return chain