"""
core/i18n_strings/core.py — bilingual STRINGS table for core/*.py.

Covers: core/standard_ops.py, core/pose_ops.py, core/editor_ops.py,
core/editor_props.py, core/mdf_tex_processor_base.py, core/mdf_generator_base.py,
core/mdf_material_convert_base.py, core/update_ops.py.

Key naming convention: "core.<module_name_without_.py>.<short_purpose>".
Keys are namespaced per source module even where wording is repeated, so this
table stays a straightforward 1:1 mirror of "where does this string live".
"""

STRINGS = {

    # ══════════════════════════════════════════════════════════════════════
    # core/standard_ops.py
    # ══════════════════════════════════════════════════════════════════════

    # ── Operator bl_description (dynamic tooltip via description()) ────────
    "core.standard_ops.apply_standard_x_desc": {
        "EN": "Execute Standard X: merge weights and rename to base names",
        "ZH": "执行标准化 X：合并权重并重命名为基础名"},
    "core.standard_ops.apply_standard_y_desc": {
        "EN": "Execute Standard Y: convert base names to target game names",
        "ZH": "执行标准化 Y：将基础名转为目标游戏名"},
    "core.standard_ops.direct_convert_desc": {
        "EN": "Convert vertex groups of selected meshes to the target game format",
        "ZH": "将选中网格的顶点组转换成目标游戏的格式"},
    "core.standard_ops.universal_snap_desc": {
        "EN": "Align the body bones of the target game armature to the source preset bones (select target armature last)",
        "ZH": "将目标游戏骨架的身体骨骼对齐来源预设骨骼（后选要修改的目标骨架）"},
    "core.standard_ops.smart_graft_desc": {
        "EN": "Smart physics bone graft (with end-bone extension):\n"
              "1. Copy physics bones (direct world-space alignment).\n"
              "2. Auto-generate _End bones at the tip of physics chains (before verticalizing).\n"
              "3. Force-disconnect bones to prevent position snapping.\n"
              "4. Reset all grafted bones to point straight up (Z+).",
        "ZH": "智能物理骨移植 (末端延伸版):\n"
              "1. 复制物理骨骼 (直接世界坐标对齐)。\n"
              "2. 【新功能】自动为物理链末端添加 _End 骨骼 (在竖直重置前生成)。\n"
              "3. 强制断开连接，防止位置吸附。\n"
              "4. 统一将所有移植骨骼重置为竖直向上 (Z+)。"},
    "core.standard_ops.merge_physics_weights_desc": {
        "EN": "Merge physics bone vertex group weights into their nearest base bone (determined by X preset).\n"
              "For downgrade scenarios where physics is unsupported or unneeded",
        "ZH": "将物理骨骼的顶点组权重合并到其最近的基础骨骼上 (通过 X 预设判断)。\n用于不需要物理效果或目标游戏不支持物理的降级场景"},
    "core.standard_ops.rename_bones_desc": {
        "EN": "Rename base bones on the armature from source name (X) to target game name (Y).\n"
              "For manual alignment workflows: renamed bones match the target game for easier alignment and data transfer",
        "ZH": "将骨架上的基础骨骼名从来源名 (X) 改为目标游戏名 (Y)。\n用于手动对齐工作流: 改名后骨骼名与目标游戏一致, 方便手动对齐和数据传递"},
    "core.standard_ops.remove_non_base_desc": {
        "EN": "Delete all non-base bones in the armature (determined by X preset).\n"
              "Recommended to run Downgrade Physics Weights first",
        "ZH": "删除骨架中所有非基础骨骼 (通过 X 预设判断)。\n建议先执行物理权重降级再使用此功能"},
    "core.standard_ops.set_bone_visibility_desc": {
        "EN": "Control bone visibility by mode (All / Base Only / Physics Only); the latter two require loading the X preset",
        "ZH": "按模式控制骨骼可见性（全显 / 仅基础骨 / 仅物理骨），后两者需加载 X 预设"},
    "core.standard_ops.refresh_colors_desc": {
        "EN": "Refresh physics bone color marks based on the bone's chain_role custom property",
        "ZH": "根据骨骼的 chain_role 自定义属性刷新物理骨骼的颜色标记"},
    "core.standard_ops.mark_main_continue_desc": {
        "EN": "Mark selected bones as main chain continue (chain_role = main_continue) and color them amber gold.\n"
              "At forks, mark which child bone continues the main chain; unmarked children will be treated as branch heads",
        "ZH": "将选中骨骼标记为主链延伸 (chain_role = main_continue)，并染为琥珀金色。\n在分叉处标记哪个子骨是主链方向，未标记的子骨将被视为支链头"},
    "core.standard_ops.clear_chain_role_desc": {
        "EN": "Clear the chain_role mark on selected bones, reverting them to regular body bones (deep blue)",
        "ZH": "清除选中骨骼的 chain_role 标记，恢复为普通体骨（深蓝色）"},
    "core.standard_ops.merge_into_parent_desc": {
        "EN": "Merge selected bone vertex weights into its parent bone and delete the selected bone.\n"
              "For cleaning up functional root bones (connector bones without physics simulation, such as hair_root)",
        "ZH": "将选中骨骼的顶点权重合并到其父骨骼，并删除选中骨骼。\n用于清理功能性根骨（如 hair_root 等无物理模拟的连接器骨骼）"},

    # ── Shared error / status fragments ─────────────────────────────────────
    "core.standard_ops.preset_load_failed": {"EN": "Preset load failed", "ZH": "预设加载失败"},
    "core.standard_ops.cannot_load_y_preset": {"EN": "Cannot load Y preset", "ZH": "无法加载 Y 预设"},
    "core.standard_ops.cannot_load_x_preset": {"EN": "Cannot load X preset", "ZH": "无法加载 X 预设"},
    "core.standard_ops.select_at_least_one_mesh_paren": {
        "EN": "Please select at least one mesh", "ZH": "请至少选中一个网格 (Mesh)"},
    "core.standard_ops.select_at_least_one_mesh": {
        "EN": "Please select at least one mesh", "ZH": "请至少选中一个网格"},
    "core.standard_ops.direct_convert_auto_conflict": {
        "EN": "Cannot auto-detect both presets for Rename Vertex Groups (X+Y): the operation targets meshes, "
              "which have no independent target armature to identify the Y preset. Please select one of the presets manually",
        "ZH": "重命名顶点组 (X+Y) 无法同时自动识别两个预设，因为操作对象为网格，没有独立的目标骨架来识别 Y 预设。请手动选择其中一个预设"},
    "core.standard_ops.source_preset_x_prefix": {"EN": "Source Preset (X): ", "ZH": "来源预设 (X): "},
    "core.standard_ops.target_preset_y_prefix": {"EN": "Target Preset (Y): ", "ZH": "目标预设 (Y): "},
    "core.standard_ops.no_common_mapping": {
        "EN": "No common bone mappings between X and Y presets", "ZH": "X与Y预设之间没有共同的骨骼映射"},
    "core.standard_ops.snap_selection_error": {
        "EN": "Operation error: please select source armature (X) first, then Ctrl-select target armature (Y)",
        "ZH": "操作对象错误: 请先选中源骨架(X)，再按住Ctrl选中目标骨架(Y)"},
    "core.standard_ops.graft_no_target_arm": {
        "EN": "Operation failed: please select the In armature first, then Ctrl-select the Out armature (Out must be the active yellow object)",
        "ZH": "操作失败：请先选择 In 骨架，再 Ctrl 加选 Out 骨架(Out需为黄色激活状态)"},
    "core.standard_ops.graft_no_source_arm": {
        "EN": "Operation failed: source (In) armature not found", "ZH": "操作失败：未找到来源(In)骨架"},
    "core.standard_ops.cannot_load_source_in": {"EN": "Cannot load source preset (In)", "ZH": "无法加载源预设 (In)"},
    "core.standard_ops.cannot_load_target_out": {"EN": "Cannot load target preset (Out)", "ZH": "无法加载目标预设 (Out)"},
    "core.standard_ops.no_physics_bones_detected": {"EN": "No physics bones detected", "ZH": "未检测到物理骨骼"},
    "core.standard_ops.select_armature_first": {"EN": "Please select an armature first", "ZH": "请先选中一个骨架"},
    "core.standard_ops.mesh_no_armature": {
        "EN": "Selected meshes have no bound armature", "ZH": "选中的网格没有绑定骨架"},
    "core.standard_ops.no_physics_vgroups": {
        "EN": "No physics bone vertex groups detected", "ZH": "未检测到物理骨骼的顶点组"},
    "core.standard_ops.rename_bones_auto_conflict": {
        "EN": "Cannot auto-detect both presets for Rename Base Bones (X+Y): the operation targets a single armature, "
              "so X and Y cannot be distinguished. Please select one of the presets manually",
        "ZH": "基础骨骼改名 (X+Y) 无法同时自动识别两个预设，因为操作对象为单一骨架，无法区分 X 和 Y。请手动选择其中一个预设"},
    "core.standard_ops.no_bones_need_rename": {
        "EN": "No bones need renaming (source and target names already match)",
        "ZH": "没有需要改名的骨骼 (来源和目标名称已一致)"},
    "core.standard_ops.no_bones_to_remove": {"EN": "No bones to remove", "ZH": "没有需要剔除的骨骼"},
    "core.standard_ops.cannot_recognize_base_bones": {
        "EN": "Cannot recognize base bones, please select a preset manually",
        "ZH": "无法识别基础骨骼，请手动选择预设"},
    "core.standard_ops.cannot_load_auto_detected": {
        "EN": "Cannot load the auto-detected preset", "ZH": "无法加载自动识别的预设"},
    "core.standard_ops.auto_detect_failed_x": {
        "EN": "Could not auto-detect a preset; please select the X preset manually",
        "ZH": "未能自动识别预设，请手动选择 X 预设"},
    "core.standard_ops.colors_refreshed": {"EN": "Bone colors refreshed", "ZH": "骨骼颜色已刷新"},
    "core.standard_ops.select_bones_in_pose_mode": {
        "EN": "Please select bones in Pose Mode", "ZH": "请在姿态模式下选中骨骼"},
    "core.standard_ops.pose_or_edit_mode_required": {
        "EN": "Please operate in Pose Mode or Edit Mode", "ZH": "请在姿态模式或编辑模式下操作"},
    "core.standard_ops.no_valid_parent_bone": {
        "EN": "Selected bones have no valid parent bone", "ZH": "选中的骨骼没有可用的父骨骼"},

    # ── Template report messages ────────────────────────────────────────────
    "core.standard_ops.standardize_done": {
        "EN": "Standardization complete: renamed {rename} bone(s), cleaned {clean} auxiliary bone(s)",
        "ZH": "标准化完成: 重命名 {rename} 根, 清理 {clean} 根辅助骨"},
    "core.standard_ops.direct_convert_done": {
        "EN": "Done: updated vertex groups in {n} mesh(es)", "ZH": "处理完成: 已更新 {n} 个网格的顶点组"},
    "core.standard_ops.snap_done": {
        "EN": "Armature snap complete: {n} bone(s)", "ZH": "骨架对齐完成: {n} 根骨骼"},
    "core.standard_ops.graft_done": {
        "EN": "Graft complete: processed {n} bone(s) (including auto-generated end bones)",
        "ZH": "移植完成: 处理 {n} 根骨骼 (含自动生成的末端骨)"},
    "core.standard_ops.merge_physics_done": {
        "EN": "Physics weight downgrade complete: merged {groups} physics vertex group(s) across {meshes} mesh(es)",
        "ZH": "物理权重降级完成: 在 {meshes} 个网格上合并了 {groups} 个物理顶点组"},
    "core.standard_ops.renamed_to_target_done": {
        "EN": "Renamed {n} bone(s) to target game names", "ZH": "已将 {n} 根骨骼改名为目标游戏名"},
    "core.standard_ops.removed_non_base_bones": {
        "EN": "Removed {n} non-base bone(s)", "ZH": "已剔除 {n} 根非基础骨骼"},
    "core.standard_ops.bone_display_status": {
        "EN": "Bone display: {mode}", "ZH": "骨骼显示: {mode}"},
    "core.standard_ops.auto_detect_fallback": {
        "EN": "Could not auto-detect the target game preset; falling back to source preset [{name}] — consider switching manually",
        "ZH": "未能自动识别目标游戏预设，回退至来源预设 [{name}]，建议手动切换"},
    "core.standard_ops.refreshed_n_bones": {"EN": "Refreshed {n} bone(s)", "ZH": "已刷新 {n} 根骨骼"},
    "core.standard_ops.auto_detected_suffix": {
        "EN": " (auto-detected preset: {name})", "ZH": "（自动识别预设：{name}）"},
    "core.standard_ops.marked_main_continue": {
        "EN": "Marked {n} bone(s) as main continue", "ZH": "已标记 {n} 根骨骼为主链延伸"},
    "core.standard_ops.cleared_chain_role": {
        "EN": "Cleared chain role mark from {n} bone(s)", "ZH": "已清除 {n} 根骨骼的链角色标记"},
    "core.standard_ops.merged_into_parent": {
        "EN": "Merged {n} bone(s) into parent", "ZH": "已合并 {n} 根骨骼到父骨"},

    # ── bone_view_mode EnumProperty items (get_bone_view_mode_items callback) ─
    "core.standard_ops.mode_all": {"EN": "Show All", "ZH": "全显"},
    "core.standard_ops.mode_all_desc": {"EN": "Show all bones", "ZH": "显示所有骨骼"},
    "core.standard_ops.mode_base": {"EN": "Base Bones Only", "ZH": "仅基础骨"},
    "core.standard_ops.mode_base_desc": {
        "EN": "Hide physics bones, show only preset base bones", "ZH": "隐藏物理骨，只显示预设基础骨"},
    "core.standard_ops.mode_physics": {"EN": "Physics Bones Only", "ZH": "仅物理骨"},
    "core.standard_ops.mode_physics_desc": {
        "EN": "Hide base bones, show only physics bones", "ZH": "隐藏基础骨，只显示物理骨"},

    # ══════════════════════════════════════════════════════════════════════
    # core/pose_ops.py
    # ══════════════════════════════════════════════════════════════════════

    "core.pose_ops.no_record": {"EN": "No records", "ZH": "无记录"},

    "core.pose_ops.mmd_a_to_tpose_desc": {
        "EN": "MMD only: rotate upper arms to horizontal, converting an MMD A-Pose armature to T-Pose. Always "
              "matches against the MMD bone-name preset internally, no preset selection needed. If it does not "
              "work correctly, use the more general Pose Transform Recorder",
        "ZH": "仅限 MMD: 将上臂旋转到水平方向，把 MMD 的 A-Pose 骨架转为 T-Pose。内部固定按 MMD 骨骼名匹配，"
              "不需要选择预设。如果无法正确运作，请使用更通用的姿态变换记录器"},
    "core.pose_ops.ree_to_tpose_desc": {
        "EN": "RE Engine only: reset limb bone rotation matrices to T-Pose. Auto-detects the game from a private, "
              "built-in bone list (Wilds / RE4R / RE9 / SF6 / MHRS / DMC5) -- no preset selection needed",
        "ZH": "RE Engine 专用: 重置肢体骨骼旋转矩阵为 T-Pose。从内置的私有骨架名单里自动识别游戏"
              "（支持荒野/生化4重制/生化9/街霸6/崛起/鬼泣5），不需要选择预设"},
    "core.pose_ops.record_transform_desc": {
        "EN": "Record relative transform: select A-pose armature first, then Ctrl-select B-pose armature, "
              "compute and save A->B transform",
        "ZH": "录制相对变换: 先选 A 姿态骨架，再 Ctrl 选 B 姿态骨架，计算并保存 A->B 的变换"},
    "core.pose_ops.apply_forward_desc": {
        "EN": "Apply transform forward (A->B): convert selected armature from A-pose to B-pose",
        "ZH": "正向应用变换 (A->B): 将选中骨架从 A 姿态转换为 B 姿态"},
    "core.pose_ops.apply_inverse_desc": {
        "EN": "Apply transform inverse (B->A): convert selected armature from B-pose back to A-pose",
        "ZH": "逆向应用变换 (B->A): 将选中骨架从 B 姿态转换回 A 姿态"},
    "core.pose_ops.delete_preset_desc": {
        "EN": "Delete the selected transform record", "ZH": "删除选中的变换记录"},

    "core.pose_ops.select_armature_first": {"EN": "Please select an armature first", "ZH": "请先选中一个骨架"},
    "core.pose_ops.cannot_load_armature_preset": {
        "EN": "Cannot load armature preset", "ZH": "无法加载骨架预设"},
    "core.pose_ops.upperarm_not_found": {"EN": "Upper arm bones not found", "ZH": "未找到上臂骨骼"},
    "core.pose_ops.ree_game_not_recognized": {
        "EN": "Could not recognize a supported RE Engine game from this armature's bone names "
              "(supports Wilds / RE4R / RE9 / SF6 / MHRS / DMC5)",
        "ZH": "未能从骨骼名识别出受支持的 RE Engine 游戏（支持荒野/生化4重制/生化9/街霸6/崛起/鬼泣5）"},
    "core.pose_ops.record_name_label": {"EN": "Name", "ZH": "名称"},
    "core.pose_ops.record_name_desc": {
        "EN": "Filename for the saved transform record (e.g. MMD A-Pose to T-Pose)",
        "ZH": "保存的变换记录文件名 (例: MMD A-Pose到T-Pose)"},
    "core.pose_ops.record_transform_hint": {
        "EN": "Select the A-pose armature first, then Ctrl-select the B-pose armature",
        "ZH": "先选 A 姿态骨架, 再 Ctrl 选 B 姿态骨架"},
    "core.pose_ops.select_two_armatures": {
        "EN": "Please select two armatures: A-pose first, then Ctrl-select B-pose",
        "ZH": "请选中两个骨架: 先选 A 姿态, 再 Ctrl 选 B 姿态"},
    "core.pose_ops.name_cannot_be_empty": {"EN": "Name cannot be empty", "ZH": "名称不能为空"},
    "core.pose_ops.ensure_two_armatures": {
        "EN": "Please make sure two armature objects are selected", "ZH": "请确保选中了两个骨架对象"},
    "core.pose_ops.no_common_bones": {
        "EN": "The two armatures have no bones with the same name", "ZH": "两个骨架没有同名骨骼"},
    "core.pose_ops.poses_nearly_identical": {
        "EN": "The two armatures have nearly identical poses; no significant transform to record",
        "ZH": "两个骨架的姿态几乎相同, 没有显著变换可记录"},
    "core.pose_ops.no_transform_selected": {"EN": "No transform record selected", "ZH": "未选择变换记录"},
    "core.pose_ops.file_not_found": {"EN": "File does not exist: {name}", "ZH": "文件不存在: {name}"},
    "core.pose_ops.read_failed": {"EN": "Read failed: {err}", "ZH": "读取失败: {err}"},
    "core.pose_ops.no_transform_data": {"EN": "No transform data in record file", "ZH": "记录文件中没有变换数据"},
    "core.pose_ops.no_matching_bones": {
        "EN": "No matching bones found between armature and transform record (check armature preset)",
        "ZH": "骨架与变换记录之间找不到对应的骨骼 (请检查骨架预设)"},
    "core.pose_ops.save_failed": {"EN": "Save failed: {err}", "ZH": "保存失败: {err}"},
    "core.pose_ops.deleted": {"EN": "Deleted: {name}", "ZH": "已删除: {name}"},
    "core.pose_ops.delete_failed": {"EN": "Delete failed: {err}", "ZH": "删除失败: {err}"},

    "core.pose_ops.mmd_a_to_tpose_done": {
        "EN": "MMD A to T-Pose complete: {bones} upper arm bone(s), {meshes} mesh(es)",
        "ZH": "MMD A转Tpose完成: {bones} 根上臂骨骼, {meshes} 个网格"},
    "core.pose_ops.ree_to_tpose_done": {
        "EN": "REE to T-Pose complete ({game}): {bones} bone(s), {meshes} mesh(es)",
        "ZH": "REE转Tpose完成 ({game}): {bones} 根骨骼, {meshes} 个网格"},
    "core.pose_ops.recorded_transform": {
        "EN": "Recorded transforms for {n} bone(s) -> {filename}", "ZH": "已录制 {n} 根骨骼的变换 -> {filename}"},
    "core.pose_ops.transform_done": {
        "EN": "Transform complete ({direction}): {bones} bone(s), {meshes} mesh(es)",
        "ZH": "变换完成 ({direction}): {bones} 根骨骼, {meshes} 个网格"},

    # ══════════════════════════════════════════════════════════════════════
    # core/editor_ops.py
    # ══════════════════════════════════════════════════════════════════════

    "core.editor_ops.init_editor_desc": {
        "EN": "Initialize the preset editor list", "ZH": "初始化预设编辑器列表"},
    "core.editor_ops.pick_bone_desc": {
        "EN": "Fill the specified slot with the currently selected bone "
              "(or the bone matching the active vertex group)",
        "ZH": "将当前选中的骨骼（或激活顶点组对应的骨骼）填入指定槽位"},
    "core.editor_ops.clear_slot_desc": {"EN": "Clear slot contents", "ZH": "清除槽位内容"},
    "core.editor_ops.mirror_mapping_desc": {
        "EN": "Mirror left-side mapping rules to the right side", "ZH": "将左侧映射规则镜像到右侧"},
    "core.editor_ops.save_preset_desc": {
        "EN": "Save preset JSON (saves as X or Y preset depending on edit mode)",
        "ZH": "保存预设 JSON（根据编辑模式保存为 X 或 Y 预设）"},
    "core.editor_ops.load_preset_desc": {
        "EN": "Load the selected preset into the editor for modification", "ZH": "读取选中的预设到编辑器中进行修改"},
    "core.editor_ops.delete_preset_desc": {
        "EN": "Delete the currently selected preset file", "ZH": "删除当前选中的预设文件"},
    "core.editor_ops.open_folder_desc": {
        "EN": "Open the folder containing the current preset in the file manager",
        "ZH": "在文件管理器中打开当前预设所在的文件夹"},
    "core.editor_ops.convert_preset_desc": {
        "EN": "Copy the current preset to the other type's directory (X→Y or Y→X), appending a conversion marker to the filename",
        "ZH": "复制当前预设到另一类型目录（X→Y 或 Y→X），文件名加转换标记"},

    "core.editor_ops.editor_reset": {"EN": "Editor has been reset", "ZH": "编辑器已重置"},
    "core.editor_ops.no_active_vgroup": {"EN": "No active vertex group", "ZH": "没有激活的顶点组"},
    "core.editor_ops.no_bound_armature": {
        "EN": "Cannot find a bound armature; make sure the mesh has an Armature modifier",
        "ZH": "找不到绑定骨架，请确认网格有 Armature 修改器"},
    "core.editor_ops.vgroup_no_matching_bone": {
        "EN": "Vertex group '{name}' has no matching bone in the armature, skipped",
        "ZH": "顶点组 '{name}' 在骨架中没有同名骨骼，跳过"},
    "core.editor_ops.enter_pose_or_edit_mode": {
        "EN": "Please enter Pose/Edit mode to select bones, or activate a vertex group in Weight Paint mode",
        "ZH": "请进入 Pose / Edit 模式选择骨骼，或在权重绘制模式下激活顶点组"},
    "core.editor_ops.no_bones_selected": {"EN": "No bones selected", "ZH": "没有选中任何骨骼"},
    "core.editor_ops.batch_added_aux_bones": {
        "EN": "Batch added {n} auxiliary bone(s)", "ZH": "已批量添加 {n} 个辅助骨"},
    "core.editor_ops.no_new_bones_added": {
        "EN": "No new bones added (possibly duplicates or the main bone was reselected)",
        "ZH": "未添加任何新骨骼 (可能是重复或选重了主骨)"},
    "core.editor_ops.cannot_determine_active_bone": {
        "EN": "Cannot determine active bone, please click a specific bone", "ZH": "无法确定活动骨骼，请点击具体的一根骨骼"},
    "core.editor_ops.mirror_done": {
        "EN": "Smart mirror complete: updated {n} item(s)", "ZH": "智能镜像完成: 更新 {n} 项"},
    "core.editor_ops.list_empty_not_saved": {"EN": "List is empty, nothing saved", "ZH": "列表为空，未保存"},
    "core.editor_ops.preset_saved": {
        "EN": "{kind} preset saved: {filename}", "ZH": "{kind} 预设已保存: {filename}"},
    "core.editor_ops.save_failed": {"EN": "Save failed: {err}", "ZH": "保存失败: {err}"},
    "core.editor_ops.no_preset_selected": {"EN": "No preset selected", "ZH": "未选择任何预设"},
    "core.editor_ops.cannot_load_file": {"EN": "Cannot load file: {name}", "ZH": "无法加载文件: {name}"},
    "core.editor_ops.preset_loaded": {
        "EN": "Successfully loaded {kind} preset: {name} ({n} mapping(s))",
        "ZH": "成功加载{kind}预设: {name} ({n} 个映射)"},
    "core.editor_ops.deleted": {"EN": "Deleted: {name}", "ZH": "已删除: {name}"},
    "core.editor_ops.delete_failed": {"EN": "Delete failed: {err}", "ZH": "删除失败: {err}"},
    "core.editor_ops.file_not_exist": {"EN": "File does not exist", "ZH": "文件不存在"},
    "core.editor_ops.folder_not_exist": {"EN": "Folder does not exist: {path}", "ZH": "文件夹不存在: {path}"},
    "core.editor_ops.source_file_not_exist": {
        "EN": "Source file does not exist: {name}", "ZH": "源文件不存在: {name}"},
    "core.editor_ops.target_file_exists": {
        "EN": "Target file already exists: {name}, skipped overwrite", "ZH": "目标文件已存在: {name}，已跳过覆盖"},
    "core.editor_ops.copied": {"EN": "Copied ({direction}): {filename}", "ZH": "已复制 ({direction}): {filename}"},
    "core.editor_ops.convert_failed": {"EN": "Conversion failed: {err}", "ZH": "转换失败: {err}"},

    # ══════════════════════════════════════════════════════════════════════
    # core/editor_props.py
    # ══════════════════════════════════════════════════════════════════════

    "core.editor_props.source_bone_desc": {
        "EN": "The corresponding main bone name", "ZH": "对应的主骨骼名称"},
    "core.editor_props.new_preset_name_label": {"EN": "Preset Name", "ZH": "预设名称"},
    "core.editor_props.search_label": {"EN": "Search", "ZH": "搜索"},
    "core.editor_props.search_desc": {"EN": "Filter bone names", "ZH": "过滤骨骼名称"},
    "core.editor_props.edit_mode_label": {"EN": "Edit Mode", "ZH": "编辑模式"},
    "core.editor_props.edit_mode_x": {"EN": "X Preset (Source)", "ZH": "X 预设 (来源)"},
    "core.editor_props.edit_mode_x_desc": {
        "EN": "Edit the bone mapping preset for the source game", "ZH": "编辑来源游戏的骨骼映射预设"},
    "core.editor_props.edit_mode_y": {"EN": "Y Preset (Target)", "ZH": "Y 预设 (目标)"},
    "core.editor_props.edit_mode_y_desc": {
        "EN": "Edit the bone mapping preset for the target game", "ZH": "编辑目标游戏的骨骼映射预设"},

    # ══════════════════════════════════════════════════════════════════════
    # core/mdf_tex_processor_base.py
    # ══════════════════════════════════════════════════════════════════════

    "core.mdf_tex_processor_base.pbr_color": {"EN": "Base Color (Albedo)", "ZH": "基础色 (Albedo)"},
    "core.mdf_tex_processor_base.pbr_alpha": {"EN": "Alpha Mask", "ZH": "Alpha 遮罩"},
    "core.mdf_tex_processor_base.pbr_emissive": {"EN": "Emissive", "ZH": "自发光 (Emissive)"},
    "core.mdf_tex_processor_base.pbr_normal": {"EN": "Normal", "ZH": "法线 (Normal)"},
    "core.mdf_tex_processor_base.pbr_roughness": {"EN": "Roughness", "ZH": "粗糙度 (Roughness)"},
    "core.mdf_tex_processor_base.pbr_metallic": {"EN": "Metallic", "ZH": "金属度 (Metallic)"},
    "core.mdf_tex_processor_base.pbr_ao": {"EN": "AO", "ZH": "AO"},
    "core.mdf_tex_processor_base.pbr_cavity": {"EN": "Cavity", "ZH": "Cavity (缝隙遮蔽)"},
    "core.mdf_tex_processor_base.pbr_translucency": {"EN": "Translucency", "ZH": "Translucency (半透)"},

    "core.mdf_tex_processor_base.prop_invert": {"EN": "Invert", "ZH": "反相"},
    "core.mdf_tex_processor_base.normal_flip_g_desc": {
        "EN": "Flip the normal map's G channel when composing (OpenGL to DirectX)",
        "ZH": "合成时翻转法线G通道 (OpenGL转DirectX)"},

    "core.mdf_tex_processor_base.slot_mode_label": {"EN": "Mode", "ZH": "模式"},
    "core.mdf_tex_processor_base.mode_compose": {"EN": "PBR Compose", "ZH": "PBR转换"},
    "core.mdf_tex_processor_base.mode_compose_desc": {
        "EN": "Compose channels from the PBR inputs above and convert", "ZH": "从上方 PBR 输入合成通道并转换"},
    "core.mdf_tex_processor_base.mode_direct": {"EN": "Direct Select", "ZH": "直接选择"},
    "core.mdf_tex_processor_base.mode_direct_desc": {
        "EN": "Directly select an already-packed image/DDS/TEX file", "ZH": "直接选择已打包好的图片/DDS/TEX文件"},
    "core.mdf_tex_processor_base.mode_default": {"EN": "Default Null Texture", "ZH": "默认空贴图"},
    "core.mdf_tex_processor_base.mode_default_desc": {
        "EN": "Write this slot's corresponding in-game null texture path", "ZH": "写入该槽位对应的游戏内空贴图路径"},
    "core.mdf_tex_processor_base.mode_skip": {"EN": "No Change", "ZH": "不修改"},
    "core.mdf_tex_processor_base.mode_skip_desc": {
        "EN": "Keep the existing path unchanged", "ZH": "保持现有路径不变"},

    "core.mdf_tex_processor_base.generate_mipmaps_label": {"EN": "Generate MipMaps", "ZH": "生成 MipMaps"},
    "core.mdf_tex_processor_base.skip_textures_label": {"EN": "Material Only", "ZH": "仅生成材质"},
    "core.mdf_tex_processor_base.skip_textures_desc": {
        "EN": "Skip texture composition/conversion; only update texture paths in the material definition",
        "ZH": "跳过贴图合成与转换，仅更新材质定义中的贴图路径"},

    "core.mdf_tex_processor_base.select_mdf_collection": {
        "EN": "Please select an MDF collection first", "ZH": "请先选择 MDF 集合"},
    "core.mdf_tex_processor_base.loaded_materials": {
        "EN": "Loaded {n} material(s)", "ZH": "已加载 {n} 个材质"},
    "core.mdf_tex_processor_base.copied_material": {"EN": "Copied {name}", "ZH": "已复制 {name}"},
    "core.mdf_tex_processor_base.clipboard_empty": {"EN": "Clipboard is empty", "ZH": "剪贴板为空"},
    "core.mdf_tex_processor_base.pasted_to_material": {"EN": "Pasted to {name}", "ZH": "已粘贴到 {name}"},
    "core.mdf_tex_processor_base.set_natives_root": {
        "EN": "Please set the Natives Root directory first (the parent folder of natives)",
        "ZH": "请先设置 Natives Root 目录（natives 的上级文件夹）"},
    "core.mdf_tex_processor_base.fill_base_path": {
        "EN": "Please fill in the Base Path", "ZH": "请填写 Base Path"},
    "core.mdf_tex_processor_base.click_refresh_first": {
        "EN": "Please click Refresh to load materials first", "ZH": "请先点击 Refresh 加载材质"},
    "core.mdf_tex_processor_base.process_done_with_fail": {
        "EN": "Done: generated {export}, failed {fail}, skipped {skip}",
        "ZH": "完成: 生成 {export}, 失败 {fail}, 跳过 {skip}"},
    "core.mdf_tex_processor_base.process_done": {
        "EN": "Done: generated {export}, skipped {skip}", "ZH": "完成: 生成 {export}, 跳过 {skip}"},

    # ══════════════════════════════════════════════════════════════════════
    # core/mdf_generator_base.py
    # ══════════════════════════════════════════════════════════════════════

    "core.mdf_generator_base.set_channel_size_desc": {
        "EN": "Adjust this channel's output resolution (limited to powers of 2 ≤ native size, minimum 256)",
        "ZH": "调整该通道的输出分辨率（仅限 ≤ 原生尺寸的 2 的幂次方，最小 256）"},
    "core.mdf_generator_base.set_channel_size_label": {"EN": "Set Output Size", "ZH": "调整输出尺寸"},
    "core.mdf_generator_base.output_size_label": {"EN": "Output Size", "ZH": "输出尺寸"},
    "core.mdf_generator_base.output_size_desc": {
        "EN": "Final output resolution for the baked/direct channel (square side length)",
        "ZH": "烘焙 / 直接通道的最终输出分辨率（边长，正方形）"},
    "core.mdf_generator_base.native_size_label": {
        "EN": "Native size: {size}×{size}", "ZH": "原生尺寸: {size}×{size}"},

    "core.mdf_generator_base.select_mesh_collection": {
        "EN": "Please select a mesh collection first", "ZH": "请先选择网格集合"},
    "core.mdf_generator_base.no_materials_in_collection": {
        "EN": "No materials found in the collection", "ZH": "集合中没有找到材质"},
    "core.mdf_generator_base.scanned_materials": {
        "EN": "Scanned {n} material(s)", "ZH": "已扫描 {n} 个材质"},
    "core.mdf_generator_base.set_natives_root": {
        "EN": "Please set the Natives Root directory first (the parent folder of natives)",
        "ZH": "请先设置 Natives Root 目录（natives 的上级文件夹）"},
    "core.mdf_generator_base.fill_base_path": {
        "EN": "Please fill in the Base Path", "ZH": "请填写 Base Path"},
    "core.mdf_generator_base.click_refresh_first": {
        "EN": "Please click Refresh to load materials first", "ZH": "请先点击 Refresh 加载材质"},
    "core.mdf_generator_base.cannot_load_preset_tool": {
        "EN": "Cannot load the RE Mesh Editor preset tool", "ZH": "无法加载 RE Mesh Editor Preset 工具"},
    "core.mdf_generator_base.process_done_with_fail": {
        "EN": "Done: {export} succeeded, {fail} failed", "ZH": "完成: 成功 {export}, 失败 {fail}"},
    "core.mdf_generator_base.process_done": {
        "EN": "Done: generated MDF2 + textures for {n} material(s)", "ZH": "完成: 成功生成 {n} 个材质的 MDF2 + 贴图"},

    # ══════════════════════════════════════════════════════════════════════
    # core/mdf_material_convert_base.py
    # ══════════════════════════════════════════════════════════════════════

    # ── migrate_mode EnumProperty items (_migrate_mode_items callback) ─────
    "core.mdf_material_convert_base.mode_custom_tex": {
        "EN": "Custom Textures Only", "ZH": "仅迁移自定义贴图路径"},
    "core.mdf_material_convert_base.mode_custom_tex_desc": {
        "EN": "Only migrate texture paths that are not part of the vanilla game assets",
        "ZH": "仅迁移不属于原版游戏资产的自定义贴图路径"},
    "core.mdf_material_convert_base.mode_all_tex": {
        "EN": "All Textures", "ZH": "迁移全部贴图路径"},
    "core.mdf_material_convert_base.mode_all_tex_desc": {
        "EN": "Migrate every texture binding path, vanilla or custom",
        "ZH": "迁移全部贴图绑定路径，无论是否为原版"},
    "core.mdf_material_convert_base.mode_all_tex_params": {
        "EN": "Textures + All Params", "ZH": "迁移贴图路径与全部参数"},
    "core.mdf_material_convert_base.mode_all_tex_params_desc": {
        "EN": "Migrate every texture binding path and every shader param that exists on the target preset",
        "ZH": "迁移全部贴图绑定路径，以及目标预设中存在同名项的全部参数"},

    "core.mdf_material_convert_base.preset_choice_label": {"EN": "Target Preset", "ZH": "目标预设材质"},
    "core.mdf_material_convert_base.delete_original_label": {"EN": "Delete Original Material", "ZH": "删除原材质"},

    "core.mdf_material_convert_base.no_preset_selected": {
        "EN": "Please select a target preset material", "ZH": "请选择目标预设材质"},
    "core.mdf_material_convert_base.no_targets": {
        "EN": "Select one or more MDF material objects first", "ZH": "请先选中一个或多个 MDF 材质物体"},
    "core.mdf_material_convert_base.cannot_load_preset_tool": {
        "EN": "Cannot load the RE Mesh Editor preset tool", "ZH": "无法加载 RE Mesh Editor Preset 工具"},
    "core.mdf_material_convert_base.done": {
        "EN": "Converted {done} material(s): {tex} texture(s) migrated (vanilla skipped {vskip}, no matching slot {noslot})",
        "ZH": "已转换 {done} 个材质: 迁移贴图 {tex} 处 (原版跳过 {vskip}, 无对应槛位跳过 {noslot})"},
    "core.mdf_material_convert_base.done_with_params": {
        "EN": "Converted {done} material(s): {tex} texture(s) migrated (vanilla skipped {vskip}, no matching slot {noslot}); "
              "{pmig} param(s) migrated ({pskip} skipped)",
        "ZH": "已转换 {done} 个材质: 迁移贴图 {tex} 处 (原版跳过 {vskip}, 无对应槛位跳过 {noslot}); 参数迁移 {pmig} 处 (跳过 {pskip})"},
    "core.mdf_material_convert_base.done_with_fail": {
        "EN": "Done: {done} succeeded, {failed} failed (see console)", "ZH": "完成: 成功 {done}, 失败 {failed} (详见控制台)"},

    # ══════════════════════════════════════════════════════════════════════
    # core/mdf_port_ops.py
    # ══════════════════════════════════════════════════════════════════════

    "core.mdf_port_ops.desc": {
        "EN": "Port this MDF material (and its custom textures) to a different RE Engine game, "
              "rebuilding it from that game's nearest equivalent prefab material",
        "ZH": "将该 MDF 材质 (及其自定义贴图) 移植到另一款 RE Engine 游戏, 基于该游戏最接近的预设材质重建"},

    "core.mdf_port_ops.source_collection_label": {"EN": "MDF Collection", "ZH": "MDF 集合"},
    "core.mdf_port_ops.source_game_label": {"EN": "Source Game: {game}", "ZH": "源游戏: {game}"},
    "core.mdf_port_ops.target_game_label": {"EN": "Target Game", "ZH": "目标游戏"},
    "core.mdf_port_ops.target_game_label_plain": {"EN": "Target Game: {game}", "ZH": "目标游戏: {game}"},
    "core.mdf_port_ops.convert_textures_label": {"EN": "Convert Textures", "ZH": "贴图转换"},
    "core.mdf_port_ops.mod_root_label": {"EN": "Mod Root", "ZH": "Mod 根目录"},
    "core.mdf_port_ops.dest_base_path_label": {"EN": "Destination Base Path", "ZH": "目标路径"},
    "core.mdf_port_ops.delete_original_label": {"EN": "Delete Original Material", "ZH": "删除原材质"},

    # ── migrate_params EnumProperty items (_migrate_params_items callback) ──
    "core.mdf_port_ops.migrate_params_label": {"EN": "Migrate Params", "ZH": "参数迁移"},
    "core.mdf_port_ops.params_basic": {
        "EN": "Basic Params", "ZH": "迁移基础属性"},
    "core.mdf_port_ops.params_basic_desc": {
        "EN": "Migrate the material's authored look: base color, roughness, metallic, "
              "translucency and the like, matched across the two games' different names",
        "ZH": "迁移材质的外观参数：基础色、粗糙度、金属度、透光等，已跨两个游戏的不同命名对齐"},
    "core.mdf_port_ops.params_all": {
        "EN": "All Params", "ZH": "迁移全部属性"},
    "core.mdf_port_ops.params_all_desc": {
        "EN": "Also migrate every remaining param the two shaders happen to share by name, "
              "including shader-internal and runtime gameplay values",
        "ZH": "额外迁移两个 shader 中所有同名同类型的参数，包括 shader 内部常量与游戏运行时状态值"},
    "core.octahedral_normals.label": {
        "EN": "Hemi-Octahedral Normals", "ZH": "法线使用半八面体编码"},
    "core.mdf_port_ops.migrate_flags_label": {"EN": "Migrate Flags", "ZH": "迁移 Flags"},
    "core.mdf_port_ops.done_params": {
        "EN": ", params {migrated} migrated / {skipped} skipped",
        "ZH": "，参数 {migrated} 项已迁移 / {skipped} 项跳过"},

    "core.mdf_port_ops.no_mdf_collection": {
        "EN": "No MDF collection found in this file", "ZH": "文件中没有找到 MDF 集合"},
    "core.mdf_port_ops.source_root_missing_warning": {
        "EN": "Please set the source mod root, or the source textures cannot be found!",
        "ZH": "请设置来源 Mod 根目录，否则无法寻找贴图！"},
    "core.mdf_port_ops.dest_root_missing_warning": {
        "EN": "Please set the destination mod root, or the textures cannot be written!",
        "ZH": "请设置目标 Mod 根目录，否则无法放置贴图！"},
    "core.mdf_port_ops.no_source_tex_found_error": {
        "EN": "No source textures found at all -- check the mod root is correct and not still packed as .pak",
        "ZH": "找不到来源贴图，请确认目录选择正确，且不是 .pak 打包格式！"},
    "core.mdf_port_ops.partial_missing_tex_warning": {
        "EN": "Texture(s) not found, fell back to the destination default -- please check and fill in yourself: {paths}",
        "ZH": "未找到贴图，回退默认路径，请自行检查并补充：{paths}"},
    "core.mdf_port_ops.and_n_more": {"EN": " (+{n} more)", "ZH": "（及其他 {n} 个）"},
    "core.mdf_port_ops.null_fallback_warning": {
        "EN": "{n} slot(s) with no vanilla default fell back to a null texture (skin will look "
              "pallid). Set the destination Mod Root and enable texture conversion to write the "
              "real placeholder instead",
        "ZH": "{n} 个无原版默认贴图的槽位已回退为空贴图（皮肤会显得惨白）。"
              "设置目标 Mod 根目录并开启「贴图转换」即可改为写出真正的占位贴图"},
    "core.mdf_port_ops.no_target_selected": {
        "EN": "No target game selected", "ZH": "未选择目标游戏"},
    "core.mdf_port_ops.missing_tex_config": {
        "EN": "Missing texture pipeline config for the source or target game",
        "ZH": "源游戏或目标游戏缺少贴图处理配置"},
    "core.mdf_port_ops.no_targets": {
        "EN": "Select one or more MDF material objects first", "ZH": "请先选中一个或多个 MDF 材质物体"},
    "core.mdf_port_ops.cannot_load_preset_tool": {
        "EN": "Cannot load the RE Mesh Editor preset tool", "ZH": "无法加载 RE Mesh Editor Preset 工具"},
    "core.mdf_port_ops.done_with_fail": {
        "EN": "Ported {done} material(s), {failed} failed (see console)",
        "ZH": "已移植 {done} 个材质, 失败 {failed} 个 (详见控制台)"},
    "core.mdf_port_ops.done": {
        "EN": "Ported {done} material(s) ({unsupported} unsupported shader fallback); "
              "textures: {tex} written, {placeholder} placeholder (no vanilla default exists), "
              "{pending} pending (no destination mod root set), "
              "{vskip} vanilla skipped, {noslot} no matching destination slot, {nosrc} source texture not found",
        "ZH": "已移植 {done} 个材质 (其中 {unsupported} 个材质着色器未识别, 已回退); "
              "贴图: 已写出 {tex}, 占位 {placeholder} 张 (无原版默认可用), "
              "待写出 {pending} (未设置目标 Mod 根目录), "
              "原版跳过 {vskip}, 无对应槛位跳过 {noslot}, 未找到源贴图 {nosrc}"},

    # ══════════════════════════════════════════════════════════════════════
    # core/update_ops.py
    # ══════════════════════════════════════════════════════════════════════

    "core.update_ops.check_updates_desc": {"EN": "Check for addon updates", "ZH": "检查插件更新"},
    "core.update_ops.new_version_found": {
        "EN": "New version found: v{remote} (current: v{local})", "ZH": "发现新版本: v{remote} (当前: v{local})"},
    "core.update_ops.already_latest": {
        "EN": "You are already on the latest version", "ZH": "当前已是最新版本"},
    "core.update_ops.check_failed": {
        "EN": "Update check failed: {err}", "ZH": "检查更新失败: {err}"},

    # ══════════════════════════════════════════════════════════════════════
    # core/tex_convert_base.py
    # ══════════════════════════════════════════════════════════════════════

    # ── source-image select EnumProperty items (get_src_items callback) ────
    "core.tex_convert_base.src_image_a": {"EN": "Image A", "ZH": "图 A"},
    "core.tex_convert_base.src_image_b": {"EN": "Image B", "ZH": "图 B"},
    "core.tex_convert_base.src_const0":  {"EN": "Constant 0", "ZH": "常量 0"},
    "core.tex_convert_base.src_const1":  {"EN": "Constant 1", "ZH": "常量 1"},

    # ── format EnumProperty items (get_format_items callback; only the two
    #    pinned entries have translatable labels, the rest are format codes) ─
    "core.tex_convert_base.format_bc7_srgb": {"EN": "BC7_sRGB (Color Map)", "ZH": "BC7_sRGB (色彩贴图)"},
    "core.tex_convert_base.format_bc7_linear": {"EN": "BC7_Linear (Non-Color / Normal Map)", "ZH": "BC7_Linear (非色彩/法线贴图)"},

    # ── preset EnumProperty items (get_preset_items callback) ──────────────
    "core.tex_convert_base.preset_name": {"EN": "Preset", "ZH": "预设"},
    "core.tex_convert_base.preset_color": {"EN": "Color Map", "ZH": "色彩贴图"},
    "core.tex_convert_base.preset_color_desc": {
        "EN": "BC7_sRGB with mipmaps. Albedo, BML, EMI, and other color data",
        "ZH": "BC7_sRGB + 生成 mipmap。Albedo、BML、EMI 等色彩数据",
    },
    "core.tex_convert_base.preset_noncolor": {"EN": "Non-Color / Normal Map", "ZH": "非色彩/法线贴图"},
    "core.tex_convert_base.preset_noncolor_desc": {
        "EN": "BC7_Linear with mipmaps. Normal maps, Alpha, RMT, CMM, XM, FM, and every other mask",
        "ZH": "BC7_Linear + 生成 mipmap。法线图、Alpha、RMT、CMM、XM、FM 等所有遮罩",
    },
    # Shown instead of preset_noncolor for any target whose normal-roughness
    # slots use the hemi-octahedral G/A packing (MHWS/MHRS/RE4/RE9, and DDS
    # since the encoding depends on the shader, not the .tex container) --
    # "Normal Map" alone would be ambiguous once NRRO/NRRC exists as a
    # separate choice right next to it.
    "core.tex_convert_base.preset_noncolor_nrmr": {"EN": "Non-Color / NRMR", "ZH": "非色彩/NRMR"},
    "core.tex_convert_base.preset_noncolor_nrmr_desc": {
        "EN": "BC7_Linear with mipmaps. Plain (unpacked) normal maps, Alpha, and every other mask -- "
              "not NRRO/NRRC, which packs a normal into G/A instead (see that preset)",
        "ZH": "BC7_Linear + 生成 mipmap。普通（未打包）法线图、Alpha 及其他遮罩 —— 不适用于把法线打包"
              "进 G/A 的 NRRO/NRRC（见下面的预设）",
    },
    "core.tex_convert_base.preset_nrro": {"EN": "NRRO / NRRC", "ZH": "NRRO/NRRC"},
    "core.tex_convert_base.preset_nrro_desc": {
        "EN": "BC7_Linear with mipmaps. G/A are run through the hemi-octahedral encode RE Engine expects "
              "there instead of a plain normal -- always applied, since there is no reliable way to tell "
              "an already-packed source from a plain one. Everything else composes as usual",
        "ZH": "BC7_Linear + 生成 mipmap。G/A 会被转换成 RE Engine 需要的半八面体编码，而不是普通法线——"
              "始终会转换，因为没有可靠的办法从像素本身判断源图是否已经打包过。其余槛位照常合成",
    },
    "core.tex_convert_base.preset_ui": {"EN": "UI / Decals", "ZH": "UI、贴纸等"},
    "core.tex_convert_base.preset_ui_desc": {
        "EN": "BC7_sRGB, no mipmaps. UI art and decals are drawn at a fixed size, so mips would only blur them",
        "ZH": "BC7_sRGB + 不生成 mipmap。UI 与贴纸按固定尺寸绘制，mipmap 只会让它变模糊",
    },
    "core.tex_convert_base.preset_custom": {"EN": "Custom", "ZH": "自定义"},
    "core.tex_convert_base.preset_custom_desc": {
        "EN": "Format and mipmap setting picked by hand",
        "ZH": "手动指定格式与 mipmap 设置",
    },

    # ── channel_mode EnumProperty items (get_channel_mode_items callback) ──
    "core.tex_convert_base.mode_single":      {"EN": "Single Image", "ZH": "单图"},
    "core.tex_convert_base.mode_single_desc": {"EN": "One image provides the full RGBA source", "ZH": "一张图片作为完整 RGBA 来源"},
    "core.tex_convert_base.mode_rgb_a":        {"EN": "RGB+A", "ZH": "RGB+A"},
    "core.tex_convert_base.mode_rgb_a_desc":   {"EN": "One image provides RGB, another provides Alpha", "ZH": "一张图片提供 RGB，另一张提供 Alpha"},
    "core.tex_convert_base.mode_rgba":         {"EN": "R·G·B·A", "ZH": "R·G·B·A"},
    "core.tex_convert_base.mode_rgba_desc":    {"EN": "Pick a source image/constant and invert flag per channel", "ZH": "逐通道指定来源图片/常量与是否翻转"},

    # ── TexConvertSettings PropertyGroup name= (English fallback only; the
    #    switchable label lives at each layout.prop() draw-site override) ───
    "core.tex_convert_base.channel_mode_name":  {"EN": "Channel Source", "ZH": "通道来源"},
    "core.tex_convert_base.src_a_name":         {"EN": "Source Image", "ZH": "源图片"},
    "core.tex_convert_base.invert_name":        {"EN": "Invert", "ZH": "翻转"},
    "core.tex_convert_base.src_b_name":         {"EN": "Alpha Source", "ZH": "Alpha 来源"},
    "core.tex_convert_base.format_name":        {"EN": "DXGI Format", "ZH": "DXGI 格式"},
    "core.tex_convert_base.generate_mipmaps_name": {"EN": "Generate Mipmaps", "ZH": "生成 Mipmaps"},
    "core.tex_convert_base.output_path_name":   {"EN": "Output Path", "ZH": "输出贴图位置"},

    # ── MT_OT_TexConvertGuessFormat ─────────────────────────────────────────
    "core.tex_convert_base.guess_format_desc": {
        "EN": "Re-guess the DXGI format from the source image's filename", "ZH": "根据源图片文件名重新猜测 DXGI 格式"},
    "core.tex_convert_base.select_src_image_first": {"EN": "Please select a source image first", "ZH": "请先选择源图片"},
    "core.tex_convert_base.guessed_format": {"EN": "Guessed {fmt} from filename", "ZH": "已按文件名猜测为 {fmt}"},
    "core.tex_convert_base.guess_failed": {
        "EN": "Could not recognize the texture type from the filename, please pick a format manually",
        "ZH": "未能从文件名识别贴图类型，请手动选择格式"},

    # ── MT_OT_TexConvertDialog ───────────────────────────────────────────────
    "core.tex_convert_base.dialog_title": {"EN": "Texture Conversion", "ZH": "贴图处理"},
    "core.tex_convert_base.dialog_desc": {
        "EN": "Convert a single image directly to the target game's .tex texture: manually pick the format "
              "(with filename pre-guessing), single/RGB+A/per-channel modes for channel filtering and inversion",
        "ZH": "将单张图片直接转换为目标游戏的 .tex 贴图：手动指定格式（带文件名预猜测），"
              "支持单图/RGB+A/逐通道三种模式做通道过滤与翻转"},
    "core.tex_convert_base.guess_fallback_warning": {
        "EN": "Unrecognized filename, fell back to the current format — please confirm manually", "ZH": "未识别命名，已回退当前格式，请手动确认"},
    "core.tex_convert_base.rgb_source_label": {"EN": "RGB Source", "ZH": "RGB 来源"},
    "core.tex_convert_base.alpha_fill_black_name": {"EN": "Fill Alpha with Black", "ZH": "使用黑色填充 Alpha 通道"},
    "core.tex_convert_base.adjust_header": {"EN": "Adjust", "ZH": "调整"},
    "core.tex_convert_base.invert_rgb_name": {"EN": "Invert RGB", "ZH": "RGB 翻转"},
    "core.tex_convert_base.invert_alpha_name": {"EN": "Invert Alpha", "ZH": "Alpha 翻转"},
    "core.tex_convert_base.invert_a_label": {"EN": "Invert Image A", "ZH": "图 A 翻转"},
    "core.tex_convert_base.invert_b_label": {"EN": "Invert Image B", "ZH": "图 B 翻转"},
    "core.tex_convert_base.output_empty_hint": {
        "EN": "Leave empty, or point at a folder, to name the file after the source image",
        "ZH": "留空或只填文件夹路径时，会自动用来源图片的文件名"},
    "core.tex_convert_base.channel_compose_failed": {
        "EN": "Channel composition failed, please check the source image(s)", "ZH": "通道合成失败，请检查源图片"},
    "core.tex_convert_base.mhwtex_convert_unavailable": {
        "EN": "Could not load the MHW Model Editor texture conversion function, please make sure it is installed and enabled",
        "ZH": "无法加载 MHW Model Editor 贴图转换函数，请确认已安装并启用"},
    "core.tex_convert_base.generated": {"EN": "Generated: {name}", "ZH": "已生成: {name}"},
    "core.tex_convert_base.convert_failed": {"EN": "Conversion failed: {err}", "ZH": "转换失败: {err}"},

    # ── Detail normal map overlay (SINGLE mode only) ───────────────────────
    "core.tex_convert_base.detail_enabled_name": {"EN": "Overlay Detail Normal Map", "ZH": "叠加细节法线图"},
    "core.tex_convert_base.detail_map_name": {"EN": "Detail Map", "ZH": "细节图"},
    "core.tex_convert_base.detail_tiling_x_name": {"EN": "Tiling X", "ZH": "Tiling X"},
    "core.tex_convert_base.detail_tiling_y_name": {"EN": "Tiling Y", "ZH": "Tiling Y"},
    "core.tex_convert_base.detail_blend_failed": {
        "EN": "Detail map blend failed, please check the detail image", "ZH": "细节图混合失败，请检查细节图片"},

    # ── Color adjust (COLOR/CUSTOM preset only) ─────────────────────────────
    "core.tex_convert_base.color_adjust_enabled_name": {"EN": "Color Adjust", "ZH": "色彩调整"},
    "core.tex_convert_base.adjust_exposure_name": {"EN": "Exposure", "ZH": "曝光度"},
    "core.tex_convert_base.adjust_saturation_name": {"EN": "Saturation", "ZH": "饱和度"},
    "core.tex_convert_base.adjust_vibrance_name": {"EN": "Vibrance", "ZH": "自然饱和度"},

    # ── generator: which packed-shader panel to export from ────────────────
    "core.mdf_generator_base.shader_source_pbr": {
        "EN": "Use PBR Inputs", "ZH": "使用PBR槽位组"},
    "core.mdf_generator_base.shader_source_pbr_desc": {
        "EN": "Compose each texture from the packed shader's PBR inputs",
        "ZH": "从打包着色器的 PBR 输入合成每张贴图"},
    "core.mdf_generator_base.shader_source_slot": {
        "EN": "Use Game Slots", "ZH": "使用游戏槽位组"},
    "core.mdf_generator_base.shader_source_slot_desc": {
        "EN": "Take each texture straight from the packed shader's game slot sockets",
        "ZH": "直接取打包着色器游戏槽位上的贴图"},
    "core.mdf_generator_base.global_disable_mipmaps": {
        "EN": "Disable MipMaps (Global)",
        "ZH": "全局禁用 MipMaps"},
    "core.mdf_generator_base.global_disable_mipmaps_desc": {
        "EN": "Overrides every material's own Generate MipMaps checkbox below and skips "
              "mipmap generation for all of them",
        "ZH": "覆盖下面每个材质自己的生成 MipMaps 选项，对全部材质都不生成 MipMaps"},
    "core.mdf_generator_base.global_use_toon": {
        "EN": "Use Toon Shading (Global, Emissive = Base Color Texture)",
        "ZH": "全局启用三渲二（自发光使用基础色贴图）"},
    "core.mdf_generator_base.global_use_toon_desc": {
        "EN": "Overrides every material's own Use Toon Shading checkbox below and forces "
              "it on for all of them",
        "ZH": "覆盖下面每个材质自己的三渲二选项，对全部材质都强制启用"},

    # ══════════════════════════════════════════════════════════════════════
    # core/shader_ops.py — packed shader operators and panel
    # ══════════════════════════════════════════════════════════════════════

    "core.shader_ops.add_desc": {
        "EN": "Add a packed shader whose inputs are the game's own texture slots",
        "ZH": "添加打包着色器，其输入端就是游戏自身的贴图槽位"},
    "core.shader_ops.convert_desc": {
        "EN": "Rebuild materials on the packed shader. The previous nodes are "
              "disconnected, not deleted",
        "ZH": "用打包着色器重建材质。原有节点只断开连接，不会删除"},
    "core.shader_ops.convert_active": {
        "EN": "Convert this material", "ZH": "转换当前材质"},
    "core.shader_ops.no_materials": {
        "EN": "No materials found on the selection",
        "ZH": "所选对象上没有找到材质"},
    "core.shader_ops.converted": {
        "EN": "Converted {done} material(s)", "ZH": "已转换 {done} 个材质"},
    "core.shader_ops.converted_with_warnings": {
        "EN": "Converted {done} material(s); {warned} had warnings (see the node "
              "sidebar or the system console)",
        "ZH": "已转换 {done} 个材质；{warned} 个有警告（见节点侧边栏或系统控制台）"},
    "core.shader_ops.converted_with_fail": {
        "EN": "Converted {done}, failed {failed} (see the system console)",
        "ZH": "已转换 {done} 个，失败 {failed} 个（见系统控制台）"},
    "core.shader_ops.all_already_converted": {
        "EN": "Nothing to do: {skipped} material(s) already use the packed shader",
        "ZH": "无需转换：{skipped} 个材质已经在使用打包着色器"},
    "core.shader_ops.converted_some_skipped": {
        "EN": "Converted {done}; skipped {skipped} already using it",
        "ZH": "已转换 {done} 个；跳过 {skipped} 个已在使用的"},
    "core.shader_ops.warnings_title": {
        "EN": "{n} thing(s) could not be carried over",
        "ZH": "有 {n} 项无法完整转换"},
    "core.shader_ops.add_shader_named": {
        "EN": "Add {name} Shader", "ZH": "添加 {name} 着色器"},
    "core.shader_ops.preview_only": {
        "EN": "Preview only — not a match for the in-game look",
        "ZH": "仅供预览，不保证还原游戏内画面"},
    "core.shader_ops.use_prefab": {
        "EN": "Use Plugin Prefab Material",
        "ZH": "使用插件预制材质"},
    "core.shader_ops.prefab_standard": {
        "EN": "Standard (cloth, most armour and parts)",
        "ZH": "标准（布料、大部分护甲和部件）"},
    "core.shader_ops.prefab_standard_desc": {
        "EN": "BaseDielectricMap / NormalRoughnessOcclusionMap / EmissiveMap / "
              "AlphaTranslucentOcclusionSSSMap, plus detail maps and colour-layer "
              "mask. Bundled from RE Mesh Editor's own cloth.json preset, unmodified",
        "ZH": "BaseDielectricMap / NormalRoughnessOcclusionMap / EmissiveMap / "
              "AlphaTranslucentOcclusionSSSMap，以及细节贴图和颜色层遮罩。"
              "内置自 RE Mesh Editor 自身的 cloth.json 预设，未作修改"},
    "core.shader_ops.prefab_weapon": {
        "EN": "Weapon",
        "ZH": "武器"},
    "core.shader_ops.prefab_weapon_desc": {
        "EN": "Same core slots as Standard but its own Master Material Path, plus "
              "wind and VFX slots instead of Standard's detail-multiblend/ripple. "
              "Bundled from RE Mesh Editor's own weapon.json preset, unmodified",
        "ZH": "核心槽位与标准相同，但主材质不同，且带有风力和 VFX 槽位（标准则是细节"
              "多重混合/波纹）。内置自 RE Mesh Editor 自身的 weapon.json 预设，未作修改"},
    "core.shader_ops.prefab_skin": {
        "EN": "Skin",
        "ZH": "皮肤"},
    "core.shader_ops.prefab_skin_desc": {
        "EN": "Adds SkinMap / BlendNormalMap, which have no PBR recipe and no "
              "vanilla null texture -- left at their bundled placeholder unless "
              "overridden. Bundled from RE Mesh Editor's own skin.json preset, "
              "unmodified",
        "ZH": "增加 SkinMap / BlendNormalMap，这两个槽位没有 PBR 合成方案也没有"
              "官方空白贴图，除非手动覆盖，否则使用插件内置的占位贴图。"
              "内置自 RE Mesh Editor 自身的 skin.json 预设，未作修改"},
    "core.shader_ops.prefab_hair": {
        "EN": "Hair",
        "ZH": "毛发"},
    "core.shader_ops.prefab_hair_desc": {
        "EN": "BaseAlphaMap instead of BaseDielectricMap (not metallic, real "
              "opacity), plus hair flow/shift/overlay slots. Bundled from RE "
              "Mesh Editor's own hair.json preset, unmodified",
        "ZH": "使用 BaseAlphaMap 而非 BaseDielectricMap（非金属，含真实透明度），"
              "以及毛发流向/偏移/叠加槽位。内置自 RE Mesh Editor 自身的 "
              "hair.json 预设，未作修改"},
    "core.shader_ops.prefab_basic": {
        "EN": "Basic (general-purpose)",
        "ZH": "通用（不确定用哪个就用这个）"},
    "core.shader_ops.prefab_basic_desc": {
        "EN": "Same core slots as Standard, plus wind/VFX/hair-overlay/"
              "multi-blend slots -- MHWILDS's own general-purpose fallback "
              "material (Base_Equip.mmtr). Bundled from RE Mesh Editor's own "
              "Character.json preset, unmodified",
        "ZH": "核心槽位与标准相同，额外带风力/VFX/毛发叠加/多重混合槽位——"
              "是荒野本身的通用兜底材质（Base_Equip.mmtr）。内置自 RE Mesh "
              "Editor 自身的 Character.json 预设，未作修改"},
    "core.shader_ops.prefab_re4_standard": {
        "EN": "Standard (body/cloth)",
        "ZH": "标准（身体/布料）"},
    "core.shader_ops.prefab_re4_standard_desc": {
        "EN": "BaseDielectricMap / NormalRoughnessMap (plain normal decode) / "
              "AlphaTranslucentOcclusionCavityMap, plus detail/record-system/"
              "rain slots. Sanitized from RE Mesh Editor's real pbr_cloth.json "
              "preset -- texture paths replaced with vanilla Null placeholders, "
              "everything else unmodified",
        "ZH": "BaseDielectricMap / NormalRoughnessMap（普通法线解码）/ "
              "AlphaTranslucentOcclusionCavityMap，以及细节/记录系统/雨水槽位。"
              "脱敏自 RE Mesh Editor 真实的 pbr_cloth.json 预设——贴图路径换成了"
              "官方空白占位贴图，其余未作修改"},
    "core.shader_ops.prefab_re4_hair": {
        "EN": "Hair",
        "ZH": "毛发"},
    "core.shader_ops.prefab_re4_hair_desc": {
        "EN": "BaseShiftMap instead of BaseDielectricMap (no metallic-alpha "
              "convention), plus secondary-albedo/rim-light slots. Sanitized "
              "from RE Mesh Editor's real pbr_hair.json preset",
        "ZH": "使用 BaseShiftMap 而非 BaseDielectricMap（没有反转 Alpha 表示"
              "金属度的约定），以及第二颜色/边缘光槽位。脱敏自 RE Mesh Editor "
              "真实的 pbr_hair.json 预设"},
    "core.shader_ops.prefab_re4_emissive": {
        "EN": "Emissive (general-purpose)",
        "ZH": "自发光（通用）"},
    "core.shader_ops.prefab_re4_emissive_desc": {
        "EN": "NormalRoughnessCavityMap (hemi-octahedral normal decode) / "
              "OcclusionMap / AlphaTranslucentOcclusionSSSMap / a real "
              "EmissiveMap slot -- a genuinely general-purpose emissive "
              "master material, not eye-specific. Sanitized from RE Mesh "
              "Editor's real Eye_EMI.json preset",
        "ZH": "NormalRoughnessCavityMap（半八面体法线解码）/ OcclusionMap / "
              "AlphaTranslucentOcclusionSSSMap / 真正的 EmissiveMap 槽位——是"
              "通用自发光主材质，不是眼睛专用。脱敏自 RE Mesh Editor 真实的 "
              "Eye_EMI.json 预设"},
    "core.shader_ops.prefab_re9_standard": {
        "EN": "Standard (body/cloth)",
        "ZH": "标准（身体/布料）"},
    "core.shader_ops.prefab_re9_standard_desc": {
        "EN": "BaseDielectricMap / NormalRoughnessMap / "
              "AlphaCavityOcclusionTranslucentMap, plus the Record-system "
              "damage/wet/rain slots. Sanitized from RE Mesh Editor's real "
              "PBR_Cloth.json preset",
        "ZH": "BaseDielectricMap / NormalRoughnessMap / "
              "AlphaCavityOcclusionTranslucentMap，以及 Record 系统的损伤/"
              "潮湿/雨水槽位。脱敏自 RE Mesh Editor 真实的 PBR_Cloth.json 预设"},
    "core.shader_ops.prefab_re9_skin": {
        "EN": "Skin",
        "ZH": "皮肤"},
    "core.shader_ops.prefab_re9_skin_desc": {
        "EN": "SSSCavityOcclusionTranslucentMap instead of "
              "AlphaCavityOcclusionTranslucentMap -- its R is a fixed "
              "constant (no real opacity data), only AO. Sanitized from RE "
              "Mesh Editor's real PBR_Skin.json preset",
        "ZH": "使用 SSSCavityOcclusionTranslucentMap 而非 "
              "AlphaCavityOcclusionTranslucentMap——它的 R 是固定常量（没有"
              "真实透明度数据），只有 AO。脱敏自 RE Mesh Editor 真实的 "
              "PBR_Skin.json 预设"},
    "core.shader_ops.prefab_re9_hair": {
        "EN": "Hair",
        "ZH": "毛发"},
    "core.shader_ops.prefab_re9_hair_desc": {
        "EN": "BaseShiftMap instead of BaseDielectricMap (no metallic-alpha "
              "convention), plus secondary-albedo/specular-flow/rim-light "
              "slots. Sanitized from RE Mesh Editor's real PBR_Hair.json preset",
        "ZH": "使用 BaseShiftMap 而非 BaseDielectricMap（没有反转 Alpha 表示"
              "金属度的约定），以及第二颜色/高光流向/边缘光槽位。脱敏自 RE "
              "Mesh Editor 真实的 PBR_Hair.json 预设"},
    "core.shader_ops.prefab_re9_emissive": {
        "EN": "Emissive (general-purpose)",
        "ZH": "自发光（通用）"},
    "core.shader_ops.prefab_re9_emissive_desc": {
        "EN": "NormalRoughnessCavityMap (hemi-octahedral normal decode) / "
              "OcclusionMap / AlphaTranslucentOcclusionSSSMap / a real "
              "EmissiveMap slot -- confirmed general-purpose (cloth/body/hair "
              "all use the identical Env_Default_Emissive.mmtr). Sanitized "
              "from RE Mesh Editor's real EMI_Body.json preset",
        "ZH": "NormalRoughnessCavityMap（半八面体法线解码）/ OcclusionMap / "
              "AlphaTranslucentOcclusionSSSMap / 真正的 EmissiveMap 槽位——"
              "确认是通用材质（布料/身体/毛发用的都是同一个 "
              "Env_Default_Emissive.mmtr）。脱敏自 RE Mesh Editor 真实的 "
              "EMI_Body.json 预设"},
    "core.shader_ops.no_preset_selected": {
        "EN": "Pick a prefab or an external preset before converting",
        "ZH": "转换前请先选择一个预制材质或外部预设"},

    # ── core/shapekey_utils.py ───────────────────────────────────────────
    "core.shapekey_utils.err_no_shape_keys": {
        "EN": "This mesh has no shape keys beyond the basis",
        "ZH": "这个网格除了基型没有其它形态键"},
    "core.shapekey_utils.err_no_modifiers": {
        "EN": "No viewport-enabled modifiers to apply",
        "ZH": "没有在视图中启用的修改器可应用"},
    "core.shapekey_utils.err_unstable_modifier": {
        "EN": "These modifiers change topology per shape key, so the keys cannot survive: {names}",
        "ZH": "这些修改器在不同形态键下会改变拓扑，形态键无法保留：{names}"},
    "core.shapekey_utils.err_bone_envelopes": {
        "EN": "The armature modifier uses bone envelopes, whose weights depend on the rest position and therefore differ per shape key",
        "ZH": "骨架修改器启用了骨骼包络，其权重依赖静置位置，在不同形态键下并不相同"},
    "core.shapekey_utils.err_vertex_count": {
        "EN": "Vertex count differs between shape keys ({a} vs {b}); a modifier is welding geometry",
        "ZH": "不同形态键下的点数不一致（{a} vs {b}），有修改器在焊接几何"},

    "core.tex_convert_base.target_name": {"EN": "Output Format", "ZH": "目标输出格式"},
    "core.tex_convert_base.target_dds":  {"EN": "DDS (native)", "ZH": "DDS (原生)"},
    "core.tex_convert_base.target_dds_desc": {
        "EN": "Stop at the DDS the pipeline already produces, without wrapping it in any game's .tex container",
        "ZH": "停在流程本来就会产出的 DDS，不再套任何游戏的 .tex 封装"},

    "core.tex_convert_base.drop_desc": {
        "EN": "Convert the dropped images to DDS. Names that don't match a known slot fall back to BC7 sRGB",
        "ZH": "把拖入的图片转换为 DDS。名字识别不出用途的默认按 BC7 sRGB 处理"},
    "core.tex_convert_base.drop_count":   {"EN": "{n} file(s)", "ZH": "共 {n} 个文件"},
    "core.tex_convert_base.drop_no_files":{"EN": "No files to convert", "ZH": "没有可转换的文件"},
    "core.tex_convert_base.drop_done":    {"EN": "Converted {n} file(s) to DDS", "ZH": "已转换 {n} 个文件为 DDS"},
    "core.tex_convert_base.drop_partial": {"EN": "Converted {n} file(s); failed: {failed}",
                                            "ZH": "已转换 {n} 个；失败：{failed}"},

    "core.tex_convert_base.drop_png_desc": {
        "EN": "Decode the dropped DDS to PNG. Stored bytes only, no gamma conversion — "
              "safe to feed back into PBR compose without shifting the colour curve",
        "ZH": "把拖入的 DDS 解码为 PNG。只还原存储字节，不做任何 gamma 变换——"
              "可以放心喂回 PBR 合成，不会偏移色彩曲线"},
    "core.tex_convert_base.drop_png_done": {"EN": "Decoded {n} file(s) to PNG", "ZH": "已解码 {n} 个文件为 PNG"},
    "core.tex_convert_base.drop_png_partial": {"EN": "Decoded {n} file(s); failed: {failed}",
                                                "ZH": "已解码 {n} 个；失败：{failed}"},

    "core.tex_convert_base.output_size_label":   {"EN": "Output size: {w} x {h}", "ZH": "输出尺寸：{w} x {h}"},
    "core.tex_convert_base.output_size_unknown": {"EN": "Output size: pick a source image to see it",
                                                   "ZH": "输出尺寸：选择来源图片后显示"},
    "core.tex_convert_base.npot_warning": {
        "EN": "Not a power of two — this can crash the game!",
        "ZH": "尺寸不为 2 的 n 次幂，可能会导致游戏崩溃！"},
    "core.tex_convert_base.resize_name": {"EN": "Resize Output", "ZH": "调整输出尺寸"},
    "core.tex_convert_base.width_name":  {"EN": "Width",  "ZH": "宽"},
    "core.tex_convert_base.height_name": {"EN": "Height", "ZH": "高"},
    "core.tex_convert_base.snap_size_desc": {
        "EN": "Fill in the recommended size: snap to the nearest power of two when it is within 15%, otherwise round up to the next one",
        "ZH": "填入推荐尺寸：与最近的 2 的 n 次幂相差 15% 以内时贴到该值，超过 15% 则向上取下一个 2 的 n 次幂"},

    # ── Shared across games ─────────────────────────────────────────────────
    # Collapsed from per-game copies of one identical string; see the D entry
    # in the refactor notes. Reuse these rather than adding a sixth copy.
    "core.export_prep.armor_pack": {"EN": "Armor Pack", "ZH": "装备包"},
    "core.export_prep.export_done": {"EN": "Done: exported {export}, skipped {skip}", "ZH": "完成: 导出 {export}, 跳过 {skip}"},
    "core.export_prep.export_done_with_fail": {"EN": "Done: exported {export}, failed {fail}, skipped {skip}", "ZH": "完成: 导出 {export}, 失败 {fail}, 跳过 {skip}"},
    "core.export_prep.no_armor": {"EN": "No armor", "ZH": "无装备"},
    "core.export_prep.no_armor_pack": {"EN": "No armor pack", "ZH": "无装备包"},
    "core.export_prep.not_set": {"EN": "Not set", "ZH": "未设置"},
    "core.export_prep.pick_armor_placeholder": {"EN": "Select armor...", "ZH": "选择装备..."},
    "core.export_prep.select_all": {"EN": "Select All", "ZH": "全选"},
    "core.export_prep.select_armor_first": {"EN": "Please select an armor set first", "ZH": "请先选择一套装备"},
    "core.export_prep.set_mod_root_first": {"EN": "Please set the Mod Root directory first (the parent folder of natives)", "ZH": "请先设置 Mod Root 目录（natives 的上级文件夹）"},
    "core.facial_bones.facial_bones_added": {"EN": "Added {n} facial bone(s)", "ZH": "已添加 {n} 根表情骨"},
    "core.facial_bones.blink_radius_mult": {
        "EN": "Blink Amplitude", "ZH": "眨眼幅度倍率"},
    "core.mdf_generator_base.active_obj_no_material": {"EN": "The active object has no material", "ZH": "激活物体没有材质"},
    "core.mdf_generator_base.auto": {"EN": "Auto: {name}", "ZH": "自动: {name}"},
    "core.mdf_generator_base.strat_alpha": {"EN": "Alpha", "ZH": "Alpha"},
    "core.mdf_generator_base.strat_color": {"EN": "Base Color", "ZH": "基础色"},
    "core.mdf_generator_base.strat_emissive": {"EN": "Emissive", "ZH": "自发光"},
    "core.mdf_generator_base.strat_metallic": {"EN": "Metallic", "ZH": "金属度"},
    "core.mdf_generator_base.strat_normal": {"EN": "Normal", "ZH": "法线"},
    "core.mdf_generator_base.strat_roughness": {"EN": "Roughness", "ZH": "粗糙度"},
    "core.re_chain_utils.chain_format": {"EN": "Chain Format", "ZH": "Chain 格式"},
    "core.re_chain_utils.chain_format_chain2_desc": {"EN": "New format, used by MHWilds / RE9", "ZH": "新格式，用于 MHWilds / RE9"},
    "core.re_chain_utils.collection": {"EN": "Collection Name", "ZH": "集合名称"},
    "core.re_chain_utils.create_chain_failed": {"EN": "Failed to create RE Chain", "ZH": "创建 RE Chain 失败"},
    "core.re_chain_utils.reference_character": {"EN": "Reference Character", "ZH": "参考角色"},
    "core.re_chain_utils.select_valid_armature": {"EN": "Please select a valid armature", "ZH": "请选择一个有效的骨架"},
    "core.re_chain_utils.settings_mode": {"EN": "Settings Mode", "ZH": "Settings 模式"},
    "core.re_chain_utils.settings_mode_separate": {"EN": "Separate", "ZH": "各自独立"},
    "core.re_chain_utils.settings_mode_shared": {"EN": "Shared", "ZH": "共享同一"},
    "core.re_chain_utils.settings_mode_shared_desc": {"EN": "All chains share the same Chain Settings", "ZH": "所有链共用同一个 Chain Settings"},
    "core.shader_pack.albd": {"EN": "BaseDielectricMap — RGB base colour, A inverted metallic (not opacity)", "ZH": "BaseDielectricMap — RGB 基础色, A 反转金属度 (不是透明度)"},
    "core.shader_pack.atosss": {"EN": "AlphaTranslucentOcclusionSSSMap — R alpha (real opacity), B AO", "ZH": "AlphaTranslucentOcclusionSSSMap — R 透明度 (真正的不透明度), B 环境光遮蔽"},
    "core.shader_pack.baseshift": {"EN": "BaseShiftMap — RGB base colour. Hair's equivalent of BaseDielectricMap (hair has no metallic-alpha convention)", "ZH": "BaseShiftMap — RGB 基础色。是毛发用来代替 BaseDielectricMap 的槽位（毛发没有反转 Alpha 表示金属度的约定）"},
    "core.shader_pack.emissive": {"EN": "EmissiveMap — emissive colour", "ZH": "EmissiveMap — 自发光颜色"},
    "core.shader_pack.nrm": {"EN": "NormalRoughnessMap — R/G plain tangent-space normal, B unused, A roughness", "ZH": "NormalRoughnessMap — R/G 普通切线空间法线, B 未使用, A 粗糙度"},
    "core.shader_pack.occ": {"EN": "OcclusionMap — a second, plain-greyscale AO source (R=G=B)", "ZH": "OcclusionMap — 第二个环境光遮蔽来源 (纯灰度, R=G=B)"},
    "core.shader_pack.panel_pbr": {"EN": "PBR Inputs", "ZH": "PBR 输入"},
    "core.shader_pack.panel_slots": {"EN": "Game Slots (packed)", "ZH": "游戏槽位 (打包)"},
    "core.shader_pack.panel_slots_emissive": {"EN": "Game Slots (packed) — Emissive", "ZH": "游戏槽位 (打包) — 自发光"},
    "core.shader_pack.panel_slots_hair": {"EN": "Game Slots (packed) — Hair", "ZH": "游戏槽位 (打包) — 毛发"},
    "core.shader_pack.panel_slots_skin": {"EN": "Game Slots (packed) — Skin", "ZH": "游戏槽位 (打包) — 皮肤"},
    "core.shader_pack.panel_slots_standard": {"EN": "Game Slots (packed) — Standard", "ZH": "游戏槽位 (打包) — 标准"},
    "core.shader_pack.pbr_ao_strength": {"EN": "AO strength: 0 = off, 1 = the full map", "ZH": "AO 强度：0 为关闭，1 为完整应用"},
    "core.shader_pack.pbr_emission_strength": {"EN": "Emission strength", "ZH": "自发光强度"},

    # --- chain_convert_ops: cross-game chain port -------------------------------
    "core.chain_convert_ops.desc": {
        "EN": "Re-bind an imported chain collection's colliders to another game's "
              "skeleton, in place. Only the bone each collider hangs off changes; "
              "offsets, radii and the chain nodes themselves are kept as authored. "
              "The target should be a skeleton produced by the RE Mesh port. Merging "
              "two source bones onto one target bone is lossy and cannot be undone "
              "by converting back",
        "ZH": "把已导入的物理链集合的碰撞体改绑到另一个游戏的骨架上，就地修改。"
              "只改碰撞体挂的骨骼，偏移、半径与链节点本身原样保留。目标骨架应当是"
              "「RE Mesh 移植」产出的那一份。两根源骨合并到同一根目标骨是有损的，"
              "反向转换无法还原"},
    "core.chain_convert_ops.source_collection": {
        "EN": "Chain Collection", "ZH": "物理链集合"},
    "core.chain_convert_ops.target_game": {"EN": "Target Game", "ZH": "目标游戏"},
    "core.chain_convert_ops.target_mesh_collection": {
        "EN": "Target Mesh Collection", "ZH": "目标 Mesh 集合"},
    "core.chain_convert_ops.target_no_armature": {
        "EN": "That mesh collection has no armature", "ZH": "该 Mesh 集合没有骨架"},
    "core.chain_convert_ops.target_many_armatures": {
        "EN": "That mesh collection holds {n} armatures ({names}), expected exactly one",
        "ZH": "该 Mesh 集合里有 {n} 个骨架 ({names})，应该只有一个"},
    # Shared by both cross-game ports (chain and mesh): off by default, so the
    # destructive choice is the one that needs an explicit tick.
    "core.port.replace_original": {
        "EN": "Replace the Original", "ZH": "替换原目标"},
    "core.port.replace_original_desc": {
        "EN": "Convert the original in place instead of converting a copy",
        "ZH": "就地转换原对象，而不是转换一份副本"},
    "core.chain_convert_ops.no_chain_collection": {
        "EN": "No chain collection found. Import a .chain/.chain2 first",
        "ZH": "未找到物理链集合，请先导入 .chain/.chain2"},
    "core.chain_convert_ops.pick_target": {
        "EN": "Pick a target mesh collection to check the result",
        "ZH": "选择目标 Mesh 集合后即可查看预检结果"},
    "core.chain_convert_ops.wrong_source_game": {
        "EN": "This collection's armature looks like {found}, not {expected}. "
              "Use the {found} section instead",
        "ZH": "该集合的骨架看起来是 {found}，不是 {expected}。请改用 {found} 板块"},
    "core.chain_convert_ops.stat_bindings": {
        "EN": "{total} collider binding(s): {remapped} re-bound, {kept} unchanged",
        "ZH": "{total} 个碰撞体绑定：{remapped} 个重绑，{kept} 个保持"},
    "core.chain_convert_ops.all_resolved": {
        "EN": "All land on bones the target armature has",
        "ZH": "全部落在目标骨架真实存在的骨骼上"},
    "core.chain_convert_ops.unmapped": {
        "EN": "{n} bone(s) have no mapping: {names}",
        "ZH": "{n} 根骨骼没有映射：{names}"},
    "core.chain_convert_ops.missing": {
        "EN": "{n} bone(s) absent from this armature: {names}. Wrong body part?",
        "ZH": "{n} 根骨骼在此骨架上不存在：{names}。是否选错了部位？"},
    "core.chain_convert_ops.merged": {
        "EN": "{n} target bone(s) merged, e.g. {example} — lossy, not reversible",
        "ZH": "{n} 根目标骨发生合并，例如 {example} —— 有损，不可逆"},
    "core.chain_convert_ops.done": {
        "EN": "Chain ported to {game}: {remapped} collider(s) re-bound, {kept} unchanged",
        "ZH": "物理链已移植到 {game}：{remapped} 个碰撞体重绑，{kept} 个保持"},
    "core.chain_convert_ops.frames_relocalised": {
        "EN": "{n} angle limit direction(s) re-derived for the target rig's bone "
              "orientation, {kept} needed none",
        "ZH": "{n} 个角度限制朝向已按目标骨架的骨骼朝向重新推算，{kept} 个无需改动"},
    "core.chain_convert_ops.frames_skipped": {
        "EN": "{n} node(s) kept their angle limit as-is: the bone is missing from the "
              "target rig, or the source rig it was measured on is gone",
        "ZH": "{n} 个节点的角度限制保持原样：目标骨架上没有对应骨骼，"
              "或用于测量原朝向的源骨架已不存在"},
    "core.chain_convert_ops.filter_applied": {
        "EN": "Collider Filter Info set on {n} chain setting(s): {path}",
        "ZH": "已为 {n} 个 Chain Settings 设定 Collider Filter Info：{path}"},
    "core.chain_convert_ops.filter_empty": {
        "EN": "(empty, as this game requires)", "ZH": "（按本游戏要求留空）"},
    "core.chain_convert_ops.subdata_added": {
        "EN": "Added the missing chain2 subdata to {n} chain setting(s)",
        "ZH": "已为 {n} 个 Chain Settings 补上缺失的 chain2 subdata"},
    "core.chain_convert_ops.attr_translated": {
        "EN": "Re-encoded the attribute flags on {n} group/setting(s): .chain and "
              ".chain2 number these bits differently, so the value changes but the "
              "meaning is kept",
        "ZH": "已重新编码 {n} 个 Group/Settings 的属性标记：.chain 与 .chain2 的位定义"
              "不同，数值会变但含义保持不变"},
    "core.chain_convert_ops.attr_dropped": {
        "EN": "Attribute flag(s) the target format has no equivalent for were "
              "dropped: {names}",
        "ZH": "目标格式没有对应位的属性标记已被丢弃：{names}"},
    "core.chain_convert_ops.export_with": {
        "EN": "Export with {op}, version {version}",
        "ZH": "请用 {op} 导出，版本 {version}"},
    "core.chain_convert_ops.blocked": {
        "EN": "Cannot convert: some colliders would end up bound to nothing",
        "ZH": "无法转换：部分碰撞体会绑到不存在的骨骼上"},

    # --- mesh_port_ops: cross-game rig port -------------------------------------
    "core.mesh_port_ops.desc": {
        "EN": "Port a model to another RE Engine game by converting its skeleton: "
              "rename the bones, merge the ones the target game does not have "
              "(moving their weights), add the ones it needs, and re-express bone "
              "axes in the target's convention. Always works on a copy of the "
              "armature and its meshes. Port the skeleton first, then its chain",
        "ZH": "把模型移植到另一个 RE Engine 游戏 —— 转换它的骨架：重命名骨骼、"
              "合并目标游戏没有的骨（连同权重）、补上它需要的骨、并把骨骼轴向"
              "改写成目标游戏的约定。始终在骨架与其网格的副本上操作。"
              "先移植骨架，再移植物理链"},
    "core.mesh_port_ops.skeleton_only": {
        "EN": "Skeleton Only", "ZH": "仅转换骨架"},
    "core.mesh_port_ops.source_collection": {
        "EN": "Mesh Collection", "ZH": "网格集合"},
    "core.mesh_port_ops.no_mesh_collection": {
        "EN": "No .mesh collection in the scene", "ZH": "场景里没有 .mesh 集合"},
    "core.mesh_port_ops.pick_collection": {
        "EN": "Pick the .mesh collection to port", "ZH": "请选择要移植的 .mesh 集合"},
    "core.mesh_port_ops.collection_no_armature": {
        "EN": "This collection holds no armature",
        "ZH": "该集合里没有骨架"},
    "core.mesh_port_ops.collection_many_armatures": {
        "EN": "This collection holds {n} armatures ({names}) -- a .mesh collection "
              "should hold exactly one, so the port would have to guess",
        "ZH": "该集合里有 {n} 个骨架（{names}）—— 正常的 .mesh 集合只应有一个，"
              "否则移植只能靠猜"},
    "core.mesh_port_ops.source_armature": {
        "EN": "Source Armature", "ZH": "源骨架"},
    "core.mesh_port_ops.target_game": {"EN": "Target Game", "ZH": "目标游戏"},
    "core.mesh_port_ops.reference_skeleton": {
        "EN": "Reference Skeleton", "ZH": "参考骨架"},
    "core.mesh_port_ops.pick_target": {
        "EN": "Pick a source armature and target game",
        "ZH": "请选择源骨架与目标游戏"},
    "core.mesh_port_ops.wrong_source_game": {
        "EN": "This armature looks like {found}, not {expected}. "
              "Use the {found} section instead",
        "ZH": "该骨架看起来是 {found}，不是 {expected}。请改用 {found} 板块"},
    "core.mesh_port_ops.stat_plan": {
        "EN": "{renamed} renamed, {merged} merged, {inserted} inserted, {kept} kept",
        "ZH": "{renamed} 根重命名，{merged} 根合并，{inserted} 根新增，{kept} 根保持"},
    "core.mesh_port_ops.name_clash": {
        "EN": "{n} bone(s) collide with a renamed bone and are merged into it, "
              "weights included: {names}",
        "ZH": "{n} 根骨骼与重命名后的骨撞名，已连同权重合并进去：{names}"},
    "core.mesh_port_ops.unplaceable": {
        "EN": "{n} bone(s) the target game needs have no placement rule: {names}",
        "ZH": "{n} 根目标游戏需要的骨骼没有放置规则：{names}"},
    "core.mesh_port_ops.needs_correction": {
        "EN": "Crosses axis conventions: a reference skeleton is required, and both "
              "rigs must be in the same pose (run REE to T-Pose on both)",
        "ZH": "跨轴向约定：必须提供参考骨架，且两套骨架需处于同一姿态"
              "（对两者各跑一次「REE 转 T-Pose」）"},
    "core.mesh_port_ops.all_resolved": {
        "EN": "Every bone has a destination", "ZH": "每根骨骼都有去处"},
    "core.mesh_port_ops.need_reference": {
        "EN": "This direction needs a reference skeleton to derive the axis "
              "correction from",
        "ZH": "该方向需要参考骨架来推导轴向修正矩阵"},
    "core.mesh_port_ops.pose_mismatch": {
        "EN": "{rejected} bones failed the axis check — the two rigs are not in the "
              "same pose. Run REE to T-Pose on both, then retry",
        "ZH": "{rejected} 根骨骼未通过轴向检验 —— 两套骨架姿态不一致。"
              "请对两者各跑一次「REE 转 T-Pose」后重试"},
    "core.mesh_port_ops.copy_failed": {
        "EN": "Could not copy the armature", "ZH": "复制骨架失败"},
    "core.mesh_port_ops.blocked": {
        "EN": "Cannot port: {detail}", "ZH": "无法移植：{detail}"},
    "core.mesh_port_ops.done": {
        "EN": "Ported to {game} as {name}: {renamed} renamed, {merged} merged, "
              "{inserted} inserted, {corrected} re-oriented, {reparented} re-parented, "
              "{synced} synced to parent",
        "ZH": "已移植到 {game}，产出 {name}：{renamed} 根重命名，{merged} 根合并，"
              "{inserted} 根新增，{corrected} 根改轴，{reparented} 根改挂父骨，"
              "{synced} 根同步父骨朝向"},
    "core.mesh_port_ops.rejected": {
        "EN": "{n} bone(s) kept the source convention (no trustworthy correction): "
              "{names}",
        "ZH": "{n} 根骨骼保留了源约定（没有可信的修正矩阵）：{names}"},

    # --- mhwi_port_ops: MHWI -> MHWS rebuild --------------------------------------
    "core.mhwi_port_ops.desc": {
        "EN": "Convert a .mod3 collection into a .mesh collection",
        "ZH": "将 mod3 集合转换为 mesh 集合"},
    "core.mhwi_port_ops.rebuild_note": {
        "EN": "Wilds' reference model is imported automatically (T-posed, facial "
              "bones merged) and becomes the output skeleton",
        "ZH": "会自动导入荒野参考模型（转 T-Pose、合并面部骨），并以它作为产出骨架"},
    # MHWI's importer produces .mod3 collections, not the .mesh ones every RE-side
    # tool talks about; saying ".mesh" here sent users looking for the wrong thing.
    "core.mhwi_port_ops.no_mod3_collection": {
        "EN": "No .mod3 collection in the scene", "ZH": "场景中没有 .mod3 集合"},
    "core.mhwi_port_ops.source_collection": {
        "EN": "Source Collection", "ZH": "源集合"},
    "core.mhwi_port_ops.reference_skeleton": {
        "EN": "Wilds Reference", "ZH": "荒野参考骨架"},
    "core.mhwi_port_ops.tpose_note": {
        "EN": "The reference is T-posed automatically: MHWI's bind pose is already an "
              "exact T-pose, while Wilds ships in an A-pose 42 degrees away",
        "ZH": "参考骨架会自动转 T-Pose：世界的绑定姿势本身就是精确 T-Pose，"
              "而荒野原生是相差 42° 的 A-Pose"},
    "core.mhwi_port_ops.pick_collection": {
        "EN": "Pick a .mod3 collection holding exactly one armature",
        "ZH": "请选择一个恰好含一具骨架的 .mod3 集合"},
    "core.mhwi_port_ops.not_mhwi": {
        "EN": "That rig is not from MHW Model Editor (its bones are not MhBone_NNN)",
        "ZH": "该骨架不是 MHW Model Editor 导入的（骨骼名不是 MhBone_NNN）"},
    "core.mhwi_port_ops.need_reference": {
        "EN": "A Wilds reference skeleton is required: MHWI stores no bone "
              "orientation at all, so it can only come from the reference",
        "ZH": "必须提供荒野参考骨架：世界的骨架完全不存骨骼朝向，只能取自参考"},
    "core.mhwi_port_ops.preset_load_failed": {
        "EN": "Could not load the MHWI/Wilds bone presets",
        "ZH": "加载世界／荒野骨骼预设失败"},
    "core.mhwi_port_ops.stat": {
        "EN": "Rebuilt as {name}: {bones} bones, {meshes} mesh(es), "
              "{thumbs} thumb joint(s) swung, {grafted} physics bone(s) grafted",
        "ZH": "已重建为 {name}：{bones} 根骨骼，{meshes} 个网格，"
              "{thumbs} 节拇指旋转，{grafted} 根物理骨嫁接"},
    "core.mhwi_port_ops.physics_orphans": {
        "EN": "{n} physics bone(s) hang off a bone the new rig has no counterpart "
              "for and were not grafted: {names}",
        "ZH": "{n} 根物理骨挂在新骨架没有对应物的骨上，未嫁接：{names}"},
    "core.mhwi_port_ops.physics_rehomed": {
        "EN": "{n} physics bone(s) attached further up, their own parent having no "
              "MHWilds counterpart: {pairs}. They will follow more of that limb's "
              "motion than they did in World",
        "ZH": "{n} 根物理骨改挂到了更上一级，因为它们原本的父骨在荒野没有对应：{pairs}。"
              "它们会比在世界里跟随更多该肢体的运动"},
    "core.mhwi_port_ops.unknown_ids": {
        "EN": "{n} bone id(s) are neither base skeleton nor a physics id, and were "
              "kept as-is: {names}",
        "ZH": "{n} 根骨骼的 ID 既不属于基础骨架也不在物理骨范围内，已原样保留：{names}"},
    "core.mhwi_port_ops.ref_missing": {
        "EN": "{n} target bone(s) are absent from the chosen reference and were not "
              "aligned: {names}",
        "ZH": "{n} 根目标骨骼在所选参考骨架中不存在，未参与对齐：{names}"},

    # --- ctc_port_ops: MHWI physics -> MHWilds physics ---------------------------
    "core.ctc_port_ops.desc": {
        "EN": "Convert a .ctc collection into a .chain2 collection. Collision shapes imported from a .ccl come across into the same collection; that collection can then be exported as a .clsp",
        "ZH": "将 ctc 集合转换为 chain2 集合。如果 ctc 集合内包含了通过 ccl 导入的碰撞体，也会一并转换到 chain2 集合内，导出时可将包含碰撞体的 chain2 导出为 clsp"},
    "core.ctc_port_ops.no_ctc_collection": {
        "EN": "No .ctc collection in the scene", "ZH": "场景中没有 .ctc 集合"},
    "core.ctc_port_ops.no_armature": {
        "EN": "No armature in the scene", "ZH": "场景中没有骨架"},
    "core.ctc_port_ops.source_collection": {
        "EN": "Source .ctc", "ZH": "源 .ctc 集合"},
    "core.ctc_port_ops.target_armature": {
        "EN": "Target Armature", "ZH": "目标骨架"},
    "core.ctc_port_ops.migrate_flags": {
        "EN": "Migrate Flags", "ZH": "迁移标志位"},
    "core.ctc_port_ops.flags_basic": {"EN": "Basic", "ZH": "基础"},
    "core.ctc_port_ops.flags_basic_desc": {
        "EN": "Angle limit only -- the one flag measured to behave the same in both "
              "games. The rest keep MHWilds' own defaults rather than MHWI's values",
        "ZH": "只迁移角度限制 —— 实测中唯一在两个游戏里行为一致的标志位。"
              "其余保留荒野自己的默认值，而不是照搬 MHWI 的取值"},
    "core.ctc_port_ops.flags_all": {"EN": "All", "ZH": "全部"},
    "core.ctc_port_ops.flags_all_desc": {
        "EN": "Every flag with a same-named counterpart. Reproduces the source "
              "exactly, but the names match where the behaviour does not -- expect "
              "to adjust",
        "ZH": "迁移所有同名对应的标志位。能精确复现源文件，"
              "但这些标志位名字相同而行为并不相同，预计需要手动调整"},
    "core.ctc_port_ops.deferred_flags": {
        "EN": "{n} flag(s) left at MHWilds' defaults (Basic mode)",
        "ZH": "{n} 个标志位保留荒野默认值（基础模式）"},
    "core.ctc_port_ops.rebuild_note": {
        "EN": "Pick the ported rig, not the MHWI one. Physics bones keep their "
              "names; base bones are remapped with the same table the model port used",
        "ZH": "请选移植后的骨架，而不是 MHWI 的。物理骨保持原名，"
              "基础骨用与模型移植同一张映射表改名"},
    "core.ctc_port_ops.game_mhwi": {"EN": "MHWI", "ZH": "怪猎世界"},
    "core.ctc_port_ops.detect_ok": {
        "EN": "Target armature reads as {game} -- matches the chosen target",
        "ZH": "目标骨架识别为{game}，与所选目标游戏一致"},
    "core.ctc_port_ops.detect_mismatch": {
        "EN": "Target armature reads as {found}, but the target game is {chosen}. "
              "Base bones would be renamed to {chosen}'s names on a rig that is not "
              "one",
        "ZH": "目标骨架识别为{found}，但目标游戏选的是{chosen}。"
              "基础骨会按{chosen}的命名改名，而这根骨架并不是{chosen}的"},
    "core.ctc_port_ops.detect_is_source": {
        "EN": "That is the MHWI rig the .ctc came off, not a ported one -- pick the "
              "output of the model port instead",
        "ZH": "这是 .ctc 所属的 MHWI 源骨架，不是移植后的骨架——请改选模型移植的产出"},
    "core.ctc_port_ops.detect_unknown": {
        "EN": "Could not tell which game this armature is from. Pick the ported rig, "
              "not the MHWI one -- base bones are remapped, physics bones keep their "
              "names",
        "ZH": "无法识别这根骨架属于哪个游戏。请选移植后的骨架而不是 MHWI 的——"
              "基础骨会改名，物理骨保持原名"},
    "core.ctc_port_ops.pick_inputs": {
        "EN": "Pick a .ctc collection and a target armature",
        "ZH": "请选择一个 .ctc 集合和目标骨架"},
    "core.ctc_port_ops.need_chain_editor": {
        "EN": "RE Chain Editor is not enabled -- this port is built through its own "
              "operators",
        "ZH": "未启用 RE Chain Editor —— 本移植通过它自己的算子构建"},
    "core.ctc_port_ops.preset_load_failed": {
        "EN": "Could not load the MHWI/MHWilds bone presets",
        "ZH": "无法加载 MHWI／荒野骨骼预设"},
    "core.ctc_port_ops.nothing_to_port": {
        "EN": "That collection has no chains and no collision shapes",
        "ZH": "该集合里既没有链条也没有碰撞体"},
    "core.ctc_port_ops.build_failed": {
        "EN": "Could not create the chain2 collection",
        "ZH": "无法创建 chain2 集合"},
    "core.ctc_port_ops.stat": {
        "EN": "Built {name}: {settings} settings, {groups} groups, {nodes} nodes, "
              "{colliders} colliders, {frames} angle limits",
        "ZH": "已生成 {name}：{settings} 组参数、{groups} 条链、{nodes} 个节点、"
              "{colliders} 个碰撞体、{frames} 个角度限制朝向"},
    "core.ctc_port_ops.unresolved_bones": {
        "EN": "{n} binding(s) landed on no bone of the target rig and will do "
              "nothing in game: {names}",
        "ZH": "{n} 处绑定在目标骨架上找不到对应骨骼，进游戏后不会起作用：{names}"},
    "core.ctc_port_ops.chains_failed": {
        "EN": "{n} chain(s) could not be built", "ZH": "{n} 条链未能建立"},
    "core.ctc_port_ops.colliders_failed": {
        "EN": "{n} collision shape(s) could not be built",
        "ZH": "{n} 个碰撞体未能建立"},
    "core.ctc_port_ops.node_mismatch": {
        "EN": "{n} chain(s) came out with their nodes in an unexpected order -- "
              "their parameters were left alone rather than written to the wrong node",
        "ZH": "{n} 条链的节点顺序与源文件不符 —— 其参数已跳过写入，"
              "以免写到错误的节点上"},
    "core.ctc_port_ops.unmapped_enums": {
        "EN": "{n} node(s) use a mode with no MHWilds equivalent and kept the default",
        "ZH": "{n} 个节点使用了荒野没有对应值的模式，已保留默认值"},
    "core.ctc_port_ops.dropped": {
        "EN": "Not carried over (no MHWilds counterpart): {names}",
        "ZH": "未搬运（荒野无对应）：{names}"},

    # --- mrl3_port_ops: MHWI material -> MHWilds material -------------------------
    "core.mrl3_port_ops.desc": {
        "EN": "Convert a .mrl3 collection into a .mdf2 collection. Every material uses the Base_Equip material; to switch one, use \"Convert to another MDF material\" in the MHWS section",
        "ZH": "将 mrl3 集合转换为 mdf2 集合。所有材质将使用 Base_Equip 材质，如有需求请使用 MHWS 板块的「转换为其他 MDF 材质」来换用其他材质"},
    "core.mrl3_port_ops.no_mrl3_collection": {
        "EN": "No .mrl3 collection in the scene", "ZH": "场景中没有 .mrl3 集合"},
    "core.mrl3_port_ops.source_collection": {
        "EN": "Source Collection", "ZH": "源集合"},
    "core.mrl3_port_ops.dest_base_path": {
        "EN": "Texture Base Path", "ZH": "贴图基础路径"},
    # An example rather than a description: the field wants the segment between the
    # game's texture root and the file name, and showing one is shorter than saying it.
    "core.mrl3_port_ops.base_path_example": {
        "EN": "Example: Author/Name", "ZH": "路径示例：Author/Name"},
    "core.mrl3_port_ops.export_root_hint": {
        "EN": "Where the converted textures are written",
        "ZH": "导出目录"},
    "core.mrl3_port_ops.migrate_params": {
        "EN": "Migrate Params", "ZH": "迁移参数"},
    # ── MHWI -> MHRS batch port ────────────────────────────────────────────────
    # Part names, gender labels and the texture-path pair are deliberately absent:
    # this dialog reuses mhrs.batch_export.part_* / gender_* and
    # core.mrl3_port_ops.dest_base_path, because they are the same words about the
    # same things and a second copy would be a second thing to keep in step.
    "core.mhwi_batch_port_ops.desc": {
        "EN": "Port a whole MHWI armor set to MH Rise in one pass: model, materials "
              "and physics for every part, then export",
        "ZH": "一次性将整套 MHWI 装备移植到怪猎崛起：逐部位的模型、材质、物理，并导出"},
    "core.mhwi_batch_port_ops.scan": {"EN": "Scan", "ZH": "解析"},
    "core.mhwi_batch_port_ops.source_root_missing": {
        "EN": "Set the MHWI mod root first", "ZH": "请先设置 MHWI Mod 根目录"},
    "core.mhwi_batch_port_ops.not_scanned": {
        "EN": "Not scanned yet", "ZH": "尚未解析"},
    "core.mhwi_batch_port_ops.scan_stale": {
        "EN": "This list was scanned from a different MHWI root - it will be "
              "re-scanned before porting",
        "ZH": "这个列表来自另一个 MHWI 根目录 —— 移植前会自动重新解析"},
    "core.mhwi_batch_port_ops.rescanned": {
        "EN": "MHWI root changed - re-scanned before porting",
        "ZH": "MHWI 根目录已变更 —— 移植前已重新解析"},
    "core.mhwi_batch_port_ops.set_gone": {
        "EN": "That set is not in the new MHWI root - pick one again",
        "ZH": "新的 MHWI 根目录里没有这套装备，请重新选择"},
    "core.mhwi_batch_port_ops.nothing_found": {
        "EN": "No armor found under nativePC/pl/{f,m}_equip",
        "ZH": "在 nativePC/pl/{f,m}_equip 下没有找到装备"},
    "core.mhwi_batch_port_ops.source_group": {
        "EN": "Source Set", "ZH": "来源装备"},
    "core.mhwi_batch_port_ops.skip_no_mod3": {
        "EN": "no .mod3 - skipped", "ZH": "缺 mod3，跳过"},
    "core.mhwi_batch_port_ops.skip_no_mrl3": {
        "EN": "no .mrl3 - skipped", "ZH": "缺 mrl3，跳过"},
    "core.mhwi_batch_port_ops.no_physics": {
        "EN": "no physics - inherits the body's",
        "ZH": "无物理，继承躯干"},
    "core.mhwi_batch_port_ops.no_physics_alone": {
        "EN": "no physics", "ZH": "无物理"},
    "core.mhwi_batch_port_ops.full": {
        "EN": "model + materials + physics", "ZH": "模型 + 材质 + 物理"},
    "core.mhwi_batch_port_ops.target_hint": {
        "EN": "Which vanilla armor slot the ported set replaces",
        "ZH": "移植后的装备覆盖哪一套原版装备"},
    "core.mhwi_batch_port_ops.target_armor": {
        "EN": "Target Armor", "ZH": "目标装备"},
    "core.mhwi_batch_port_ops.skip_textures": {
        "EN": "Skip Textures", "ZH": "不处理贴图"},
    # No key for the checkbox's own tooltip: Blender reads a property's
    # ``description`` once at registration, so a T() there would freeze whichever
    # language was active at import.  The caveat is drawn as a label instead, which
    # is re-translated every redraw.
    "core.mhwi_batch_port_ops.skip_textures_hint": {
        "EN": "Paths are filled, but the .tex must already be on disk from an "
              "earlier full port",
        "ZH": "路径照常填写，但 .tex 须已由此前的完整移植写入磁盘"},
    "core.mhwi_batch_port_ops.import_failed": {
        "EN": "Import failed - is MHW Model Editor enabled?",
        "ZH": "导入失败 —— 是否已启用 MHW Model Editor？"},
    "core.mhwi_batch_port_ops.no_portable_part": {
        "EN": "No part has both a .mod3 and a .mrl3",
        "ZH": "没有任何部位同时具备 mod3 和 mrl3"},
    # No file count.  The obvious one to reach for is the number of bindings, and
    # it is wrong by a wide margin: the blank files, the ``user.2``, the shadow mesh
    # and every ``.tex`` are all written without one.  Naming the destination is
    # both true and the thing the user actually needs next.
    "core.mhwi_batch_port_ops.stat": {
        "EN": "Batch port done: {ported} part(s) ported, {skipped} skipped -> {armor}",
        "ZH": "批量移植完成：移植 {ported} 个部位，跳过 {skipped} 个 → {armor}"},

    # ── MHWS -> MHRS batch ──
    # Per-step failures, recorded on the part rather than raised: one part failing
    # does not stop the set.  Each is reported when the step's own output
    # collection is not there afterwards, which is the only reliable signal --
    # the operators return FINISHED whether or not their dynamic enum inputs
    # resolved.  The traceback, when there is one, goes to the console.
    "core.mhws_batch_port.mesh_failed": {
        "EN": "Model port produced nothing", "ZH": "模型移植没有产出"},
    "core.mhws_batch_port.mdf_failed": {
        "EN": "Material port produced nothing", "ZH": "材质移植没有产出"},
    "core.mhws_batch_port.chain_failed": {
        "EN": "Physics port produced nothing", "ZH": "物理移植没有产出"},
    "core.mhws_batch_port.skip_no_mesh": {
        "EN": "no .mesh - skipped", "ZH": "缺 mesh，跳过"},
    "core.mhws_batch_port.skip_no_mdf2": {
        "EN": "no .mdf2 - skipped", "ZH": "缺 mdf2，跳过"},
    "core.ctc_port_ops.target_label": {"EN": "Target Game", "ZH": "目标游戏"},
    "core.ctc_port_ops.target_mhws": {"EN": "MHWS", "ZH": "怪猎荒野"},
    "core.ctc_port_ops.target_mhws_desc": {
        "EN": "Build a MHWilds .chain2", "ZH": "生成怪猎荒野的 .chain2"},
    "core.ctc_port_ops.target_mhrs": {"EN": "MHRS", "ZH": "怪猎崛起"},
    "core.ctc_port_ops.target_mhrs_desc": {
        "EN": "Build a MH Rise .chain (v48). The scene objects are the same either "
              "way -- only the export format and the group attribute bits differ, "
              "and those are re-encoded rather than carried",
        "ZH": "生成怪猎崛起的 .chain（v48）。两者的场景对象完全相同——"
              "只有导出格式和 Group 属性位不同，而后者会被重新编码而非照搬"},
    "core.mhwi_port_ops.target_label": {"EN": "Target Game", "ZH": "目标游戏"},
    "core.mhwi_port_ops.target_mhws": {"EN": "MHWS", "ZH": "怪猎荒野"},
    "core.mhwi_port_ops.target_mhws_desc": {
        "EN": "Rebuild onto MHWilds' skeleton: lift to its ground origin, swing the "
              "thumbs 29 degrees onto its splay, then run its two skeleton passes",
        "ZH": "重建到怪猎荒野骨架：抬升到其地面原点、把拇指旋转 29 度对上其外张角度，"
              "再跑荒野的两个骨架优化"},
    "core.mhwi_port_ops.target_mhrs": {"EN": "MHRS", "ZH": "怪猎崛起"},
    "core.mhwi_port_ops.target_mhrs_desc": {
        "EN": "Rebuild onto MH Rise's skeleton. Measured to share MHWI's rest frame "
              "exactly, so there is no lift and no thumb swing -- this is a rename "
              "and a rig swap, nothing is moved",
        "ZH": "重建到怪猎崛起骨架。实测与 MHWI 处于同一静止姿态坐标系，"
              "所以既不抬升也不旋转拇指——只是重命名加换骨架，不移动任何东西"},
    "core.mrl3_port_ops.target_label": {"EN": "Target Game", "ZH": "目标游戏"},
    "core.mrl3_port_ops.target_mhws": {"EN": "MHWS", "ZH": "怪猎荒野"},
    "core.mrl3_port_ops.target_mhws_desc": {
        "EN": "Build MHWilds materials from the MRL3 -- the direct conversion",
        "ZH": "从 MRL3 直接生成怪猎荒野材质"},
    "core.mrl3_port_ops.target_mhrs": {"EN": "MHRS", "ZH": "怪猎崛起"},
    "core.mrl3_port_ops.target_mhrs_desc": {
        "EN": "Build MHWilds materials, then port those to MHRS in the same click. "
              "MHRS has one shader with far fewer knobs, so most parameters have "
              "nowhere to land -- 6 of 23 survive, and a direct conversion could "
              "only manage 8",
        "ZH": "先生成怪猎荒野材质，再在同一次操作里转到怪猎崛起。崛起只有一个着色器、"
              "旋钮少得多，所以多数参数无处可去——23 个里只有 6 个能保留，"
              "即使做直连转换也只能到 8 个"},
    "core.mrl3_port_ops.relayed": {
        "EN": "Then ported to MHRS: {name}, {n} material(s), {tex} texture "
              "binding(s) carried. The MHWilds intermediate was removed",
        "ZH": "已继续转到怪猎崛起：{name}，{n} 个材质，带过 {tex} 条贴图绑定。"
              "中间的荒野集合已删除"},
    "core.mrl3_port_ops.relay_failed": {
        "EN": "The MHWilds materials were built, but the MHRS step failed ({err}). "
              "The MHWilds collection was kept",
        "ZH": "荒野材质已生成，但转崛起这一步失败（{err}），荒野集合已保留"},
    "core.mrl3_port_ops.relay_no_result": {
        "EN": "The MHRS step reported success but produced no collection; the "
              "MHWilds collection was kept",
        "ZH": "转崛起这一步报告成功却没有产出集合，荒野集合已保留"},
    "core.mrl3_port_ops.params_basic": {"EN": "Basic", "ZH": "基础"},
    "core.mrl3_port_ops.params_basic_desc": {
        "EN": "Metallic, roughness and translucency only -- the three whose meaning "
              "and 0..1 scale are the same in both engines",
        "ZH": "只迁移金属度、粗糙度、半透明度 —— 这三个在两个引擎里含义与 0..1 "
              "量纲都相同"},
    "core.mrl3_port_ops.params_all": {"EN": "All", "ZH": "全部"},
    "core.mrl3_port_ops.params_all_desc": {
        "EN": "Everything that has a counterpart, including base colour and the "
              "emissive factor split into colour and power. Their scales are not "
              "calibrated between the engines, so expect to adjust them",
        "ZH": "迁移所有能对应的参数，包括基础色，以及拆成颜色与强度两项的自发光因子。"
              "这些量纲在两个引擎间未经标定，预计需要手动调整"},
    "core.mrl3_port_ops.convert_textures": {
        "EN": "Convert Textures", "ZH": "转换贴图"},
    "core.mrl3_port_ops.cull_unused": {
        "EN": "Cull Unused Materials", "ZH": "剔除未使用材质"},
    "core.mrl3_port_ops.mod3_collection": {
        "EN": "Reference .mod3", "ZH": "参考 mod3 集合"},
    "core.mrl3_port_ops.no_mod3_collection": {
        "EN": "No .mod3 collection in the scene", "ZH": "场景中没有 .mod3 集合"},
    "core.mrl3_port_ops.pick_mod3": {
        "EN": "Pick the .mod3 collection these materials belong to",
        "ZH": "请选择这些材质所属的 .mod3 集合"},
    "core.mrl3_port_ops.all_culled": {
        "EN": "No material matches a mesh in that .mod3 collection -- wrong "
              "collection picked?",
        "ZH": "没有任何材质匹配该 .mod3 集合中的网格 —— 是不是选错集合了？"},
    # Says which collection decides, and nothing else.  The reason the default is on
    # -- MHWilds refuses to load a model whose .mdf2 carries an unused material, where
    # MHWI merely ignores it -- lives on the ``cull_unused`` property in
    # mrl3_port_ops.py; it is a maintainer's fact, not something to re-read on every
    # run (user, 2026-08-16).
    "core.mrl3_port_ops.cull_note": {
        "EN": "Drops materials no mesh in this .mod3 collection uses",
        "ZH": "剔除 mod3 集合中没有使用到的材质"},
    "core.mrl3_port_ops.culled": {
        "EN": "{n} material(s) had no mesh and were dropped: {names}",
        "ZH": "{n} 个材质没有对应网格，已丢弃：{names}"},
    "core.mrl3_port_ops.no_targets": {
        "EN": "That collection holds no mrl3 materials",
        "ZH": "该集合中没有 mrl3 材质"},
    "core.mrl3_port_ops.no_prefab": {
        "EN": "The bundled MHWilds Base_Equip prefab is missing",
        "ZH": "缺少内置的荒野 Base_Equip 预制材质"},
    "core.mrl3_port_ops.source_root_missing": {
        "EN": "MHWI mod root is not set, so no texture could be read; materials were "
              "built without them",
        "ZH": "未设置 MHWI 的 Mod 根目录，无法读取任何贴图；材质已建立但不含贴图"},
    "core.mrl3_port_ops.stat": {
        "EN": "Built {name}: {built} material(s), {textures} texture(s) written, "
              "{migrated} param(s) migrated, {skipped} skipped",
        "ZH": "已生成 {name}：{built} 个材质，写出 {textures} 张贴图，"
              "迁移 {migrated} 个参数，跳过 {skipped} 个"},
    "core.mrl3_port_ops.failed": {
        "EN": "{n} material(s) could not be built", "ZH": "{n} 个材质建立失败"},
    "core.mrl3_port_ops.missing_tex": {
        "EN": "{n} source texture(s) could not be read: {names}",
        "ZH": "{n} 张源贴图无法读取：{names}"},
    "core.mrl3_port_ops.unportable": {
        "EN": "Dropped, MHWilds has no counterpart slot: {names}",
        "ZH": "已丢弃，荒野没有对应的贴图槽：{names}"},
    "core.mrl3_port_ops.rescaled": {
        "EN": "{n} texture(s) were rescaled to match the material's largest: {names}",
        "ZH": "{n} 张贴图被缩放到该材质的最大尺寸：{names}"},

    # --- ref_model / ref_model_ops: import a vanilla reference body ---------------
    "core.ref_model.female": {"EN": "Female", "ZH": "女性"},
    "core.ref_model.male": {"EN": "Male", "ZH": "男性"},
    "core.ref_model_ops.desc": {
        "EN": "Import the game's vanilla reference body. Optionally simplify it "
              "first: merge the facial rig and the auxiliary bones into the bones "
              "that carry them, then convert to T-pose",
        "ZH": "导入本游戏的原版参考模型。可选先做简化："
              "把脸部骨骼与辅助骨骼连同权重合并到承载它们的骨上，再转成 T-Pose"},
    "core.ref_model_ops.model": {"EN": "Model", "ZH": "模型"},
    "core.ref_model_ops.to_tpose": {"EN": "Convert to T-Pose", "ZH": "转 T-Pose"},
    "core.ref_model_ops.merge_facial": {
        "EN": "Merge Facial Bones", "ZH": "合并面部骨骼"},
    "core.ref_model_ops.merge_aux": {
        "EN": "Merge Auxiliary Bones", "ZH": "合并辅助骨骼"},
    "core.ref_model_ops.no_native_skeleton": {
        "EN": "No native skeleton is bundled for this game, so auxiliary bones "
              "cannot be told apart from base ones",
        "ZH": "本游戏未内置原生骨架，无法区分辅助骨与基础骨"},
    "core.ref_model_ops.no_model": {
        "EN": "No reference model registered for this game",
        "ZH": "本游戏未登记参考模型"},
    "core.ref_model_ops.file_missing": {
        "EN": "The bundled model file is missing", "ZH": "内置模型文件缺失"},
    "core.ref_model_ops.need_mbt": {
        "EN": "Needs Modder Batch Tool (and MHW Model Editor) installed and enabled",
        "ZH": "需要安装并启用 Modder Batch Tool（以及 MHW Model Editor）"},
    "core.ref_model_ops.import_failed": {
        "EN": "Import produced no armature", "ZH": "导入后未得到骨架"},
    "core.ref_model_ops.posed": {"EN": "T-posed", "ZH": "已转 T-Pose"},
    "core.ref_model_ops.done": {
        "EN": "Imported {name}: {facial} facial bone(s) merged, {aux} auxiliary, {pose}",
        "ZH": "已导入 {name}：合并面部骨 {facial} 根，辅助骨 {aux} 根，{pose}"},

    # ══════════════════════════════════════════════════════════════════════
    # core/pre_export_check_ops.py
    # ══════════════════════════════════════════════════════════════════════

    # ── Dialog headings. Passed as invoke_props_dialog(title=...) rather than
    #    left to bl_label, which is static English and resolved before the
    #    language is known (Blender 4.1+; older builds keep the bl_label).
    "core.pre_export_check_ops.title": {
        "EN": "Matching Check", "ZH": "匹配检查"},
    "core.pre_export_check_ops.confirm_run": {
        "EN": "Run Check", "ZH": "开始检查"},
    "core.pre_export_check_ops.report_title": {
        "EN": "Pre-export Check Result", "ZH": "导出前检查结果"},
    "core.pre_export_check_ops.confirm_done": {
        "EN": "Done", "ZH": "完成"},

    # ── Input dialog ───────────────────────────────────────────────────────
    "core.pre_export_check_ops.desc": {
        "EN": "Check whether one mesh/mdf pair's meshes, materials, and textures line up: "
              "missing textures, dangling materials, illegal names, duplicate materials. "
              "Batch export already runs this automatically over every pair it will "
              "actually export -- use this to check one pair on its own, e.g. before it is "
              "even wired into a batch export job.",
        "ZH": "检查一对 mesh/mdf 集合的模型、材质、贴图是否匹配：贴图缺失、悬空材质、"
              "命名不合法、材质重复。批量导出内部已经会自动检查这次要导出的全部 mesh/mdf 对，"
              "这里可以单独挑一对来查——比如资产还没配进批量导出流程时就想先自查一下。"},
    "core.pre_export_check_ops.label_mdf_collection": {
        "EN": "MDF Collection", "ZH": "MDF 集合"},
    "core.pre_export_check_ops.label_mesh_collection": {
        "EN": "Mesh Collection", "ZH": "Mesh 集合"},
    "core.pre_export_check_ops.mesh_collection_none": {
        "EN": "— skip material matching —", "ZH": "— 跳过材质匹配 —"},
    "core.pre_export_check_ops.no_mdf_collection": {
        "EN": "No .mdf2 collection found", "ZH": "未找到 .mdf2 集合"},

    # ── "what this run will do", recomputed live as the inputs change ──────
    "core.pre_export_check_ops.will_run": {
        "EN": "This run will:", "ZH": "本次将执行："},
    "core.pre_export_check_ops.run_tex": {
        "EN": "Check for missing textures", "ZH": "检查贴图缺失"},
    "core.pre_export_check_ops.run_match": {
        "EN": "Check that meshes and materials match", "ZH": "检查网格与材质是否匹配"},
    "core.pre_export_check_ops.run_names": {
        "EN": "Check naming, duplicate materials and multi-material meshes",
        "ZH": "检查命名、重复材质与多材质网格"},
    "core.pre_export_check_ops.skip_tex_no_root": {
        "EN": "Skip the texture check — Mod Root is not set",
        "ZH": "跳过贴图检查 —— 未设置 Mod 根目录"},
    "core.pre_export_check_ops.skip_tex_no_config": {
        "EN": "Skip the texture check — no vanilla texture list is bundled for {game}",
        "ZH": "跳过贴图检查 —— {game} 未内置原版贴图清单"},
    "core.pre_export_check_ops.skip_match_no_mesh": {
        "EN": "Skip material matching — no Mesh collection chosen",
        "ZH": "跳过材质匹配 —— 未选择 Mesh 集合"},

    # ── Category headings (the scrollable left column) ─────────────────────
    "core.pre_export_check_ops.cat_tex_missing": {
        "EN": "Missing Textures", "ZH": "贴图缺失"},
    "core.pre_export_check_ops.cat_tex_root_wrong": {
        "EN": "No Texture Found At All", "ZH": "找不到任何贴图"},
    "core.pre_export_check_ops.cat_tex_empty": {
        "EN": "Empty Texture Path", "ZH": "贴图路径为空"},
    "core.pre_export_check_ops.cat_mesh_unmatched": {
        "EN": "Dangling Meshes", "ZH": "悬空网格"},
    "core.pre_export_check_ops.cat_mat_unmatched": {
        "EN": "Dangling Materials", "ZH": "悬空材质"},
    "core.pre_export_check_ops.cat_mat_duplicate": {
        "EN": "Duplicate Materials", "ZH": "重复材质"},
    "core.pre_export_check_ops.cat_name_illegal": {
        "EN": "Illegal Names", "ZH": "命名不合法"},
    "core.pre_export_check_ops.cat_mesh_multi": {
        "EN": "Multi-material Meshes", "ZH": "多材质网格"},

    # ── Category detail (the right column) ────────────────────────────────
    "core.pre_export_check_ops.desc_tex_missing": {
        "EN": "These texture paths are neither vanilla assets nor present under the Mod "
              "Root. The game cannot load them.",
        "ZH": "以下贴图路径既不是原版资源，也不在 Mod 根目录下，游戏无法加载。"},
    "core.pre_export_check_ops.desc_tex_root_wrong": {
        "EN": "None of the {n} custom texture path(s) could be found under:\n{root}\n"
              "Either the Mod Root points at the wrong folder, or the textures have not "
              "been built yet -- every one of them is failing for the same single reason. "
              "The unique path(s), to help tell the two apart:",
        "ZH": "全部 {n} 条自定义贴图路径都无法在下面的目录中找到：\n{root}\n"
              "要么是 Mod 根目录选错了位置，要么是贴图还没做好——它们失败的原因完全相同。"
              "去重后的路径，方便自行判断是哪一种："},
    "core.pre_export_check_ops.desc_tex_empty": {
        "EN": "These texture slots have no path filled in at all.",
        "ZH": "以下贴图槽位没有填写任何路径。"},
    "core.pre_export_check_ops.desc_mesh_unmatched": {
        "EN": "These meshes derive a material name that no material in the mdf "
              "collection provides, so they will not export correctly.",
        "ZH": "以下网格推导出的材质名，在 mdf 集合中找不到对应材质，导出会出问题。"},
    "core.pre_export_check_ops.desc_mat_unmatched": {
        "EN": "No mesh asks for these materials. Usually this is a rename that only got "
              "done on one side.",
        "ZH": "没有任何网格使用这些材质，通常是改名只改了一侧。"},
    "core.pre_export_check_ops.desc_mat_duplicate": {
        "EN": "These material names appear more than once in this mdf collection:",
        "ZH": "本 mdf 集合中以下材质名重复出现："},
    "core.pre_export_check_ops.desc_name_illegal": {
        "EN": "Spaces, dots and a leading underscore all break the export. The fix "
              "button corrects the mdf material and its meshes together, so a name that "
              "matched before still matches afterwards.",
        "ZH": "空格、点号、开头的下划线都会导致导出出错。"
              "修复按钮会同时修正 mdf 材质和对应网格，原本匹配的名字修完仍然匹配。"},
    "core.pre_export_check_ops.desc_mesh_multi": {
        "EN": "These meshes carry more than one material. Only the first is exported, so "
              "the result may look wrong in game.",
        "ZH": "以下网格存在多材质，导出只取第一个，实际表现可能会出现异常。"},

    # ── Reason codes from core/pre_export_check.py ────────────────────────
    "core.pre_export_check_ops.reason_space": {
        "EN": "contains a space", "ZH": "含空格"},
    "core.pre_export_check_ops.reason_dot": {
        "EN": "contains a dot", "ZH": "含点号"},
    "core.pre_export_check_ops.reason_leading_underscore": {
        "EN": "starts with an underscore", "ZH": "以下划线开头"},
    "core.pre_export_check_ops.reason_empty": {
        "EN": "the name is empty", "ZH": "名称为空"},
    "core.pre_export_check_ops.reason_single_underscore": {
        "EN": "the material name should be preceded by a double underscore",
        "ZH": "材质名前应为双下划线"},
    "core.pre_export_check_ops.side_mdf": {"EN": "[MDF]", "ZH": "[MDF]"},
    "core.pre_export_check_ops.side_mesh": {"EN": "[Mesh]", "ZH": "[网格]"},
    "core.pre_export_check_ops.no_name": {"EN": "(no name)", "ZH": "（无名称）"},

    # ── Report dialog ─────────────────────────────────────────────────────
    "core.pre_export_check_ops.report_desc": {
        "EN": "Result of the pre-export check", "ZH": "导出前检查的结果"},
    "core.pre_export_check_ops.n_issues": {
        "EN": "Found {n} issue(s) to deal with before exporting",
        "ZH": "发现 {n} 处需要在导出前处理的问题"},
    "core.pre_export_check_ops.all_clear": {
        "EN": "No problems found", "ZH": "未发现问题"},
    "core.pre_export_check_ops.btn_fix": {
        "EN": "Fix Illegal Names", "ZH": "修复不合法命名"},
    "core.pre_export_check_ops.fix_datablock_note": {
        "EN": "A mesh with no Group_x_Sub_y__ name falls back to its Blender material, so "
              "fixing that one renames the material datablock — which can affect objects "
              "outside this check.",
        "ZH": "没有 Group_x_Sub_y__ 命名的网格会回退到 Blender 材质名，"
              "修复这类命名会改动材质数据块，可能影响本次检查范围之外的物体。"},
    "core.pre_export_check_ops.chk_select": {
        "EN": "Select all problem objects", "ZH": "选中所有有问题的对象"},
    "core.pre_export_check_ops.selected_n": {
        "EN": "Selected {n} object(s)", "ZH": "已选中 {n} 个对象"},
    "core.pre_export_check_ops.fix_desc": {
        "EN": "Correct the illegal names on the mdf materials and their meshes together, "
              "then run the check again",
        "ZH": "同时修正 mdf 材质与对应网格的不合法命名，然后重新检查"},
    "core.pre_export_check_ops.fix_done": {
        "EN": "Fixed {mat} material(s), {obj} mesh object(s), {data} material datablock(s)",
        "ZH": "已修复：材质 {mat} 个，网格物体 {obj} 个，材质数据块 {data} 个"},

    # ── Inline summary row, embedded in the batch export dialogs ───────────
    "core.pre_export_check_ops.btn_view_details": {
        "EN": "View Details", "ZH": "查看详情"},

    # ── Shared with the RE Mdf port dialog, which draws the same row ───────
    "core.mdf_port_ops.mod_root_hint": {
        "EN": "Choose the natives root directory the textures live under",
        "ZH": "选择贴图所在的 natives 根目录"},

    # ══════════════════════════════════════════════════════════════════════
    # core/stale_cleanup_ops.py
    # ══════════════════════════════════════════════════════════════════════

    "core.stale_cleanup_ops.button": {
        "EN": "Clean Up Leftover Files", "ZH": "清理残留文件"},
    "core.stale_cleanup_ops.desc": {
        "EN": "Updates only add and overwrite files, never remove them, so every file "
              "an older version shipped is still on disk. This finds them by comparing "
              "the folder against this version's own file list, and deletes them after "
              "you confirm",
        "ZH": "更新只会覆盖和新增、从不删除，所以旧版本装过的文件一直留在硬盘上。"
              "这里通过与本版本自带的文件清单比对找出它们，确认后删除"},
    "core.stale_cleanup_ops.hint": {
        "EN": "Updates never delete files, so old versions' files pile up",
        "ZH": "更新不会删除文件，旧版本的文件会一直堆积"},
    "core.stale_cleanup_ops.no_manifest": {
        "EN": "No MANIFEST.txt -- this install predates it, or is a source checkout. "
              "Reinstall from a release zip first; without the list there is nothing "
              "safe to compare against",
        "ZH": "没有 MANIFEST.txt —— 这是清单出现之前的安装，或者是源码检出。"
              "请先用发布版 zip 重装；没有清单就没有可靠的比对依据，不会删任何东西"},
    "core.stale_cleanup_ops.none_found": {
        "EN": "No leftover files -- the install matches this version exactly",
        "ZH": "没有残留文件 —— 安装目录与本版本完全一致"},
    "core.stale_cleanup_ops.found": {
        "EN": "{n} leftover file(s), {mb} MB, plus {pyc} __pycache__ folder(s):",
        "ZH": "残留 {n} 个文件，共 {mb} MB，另有 {pyc} 个 __pycache__ 目录："},
    "core.stale_cleanup_ops.and_more": {
        "EN": "... and {n} more", "ZH": "……另有 {n} 项"},
    "core.stale_cleanup_ops.kept_note": {
        "EN": "{n} file(s) under assets/presets/ are left alone -- the preset editor "
              "writes there, so your own presets look like leftovers too",
        "ZH": "assets/presets/ 下的 {n} 个文件不会动 —— 预设编辑器往那里写，"
              "你自建的预设也会被判成残留"},
    "core.stale_cleanup_ops.confirm": {
        "EN": "This cannot be undone. The full list is in the system console",
        "ZH": "此操作不可撤销。完整清单已打印到系统控制台"},
    "core.stale_cleanup_ops.done": {
        "EN": "Removed {files} file(s) and {dirs} folder(s), freeing {mb} MB",
        "ZH": "已删除 {files} 个文件、{dirs} 个目录，释放约 {mb} MB"},
    "core.stale_cleanup_ops.done_with_errors": {
        "EN": "Removed {files} file(s), {n} could not be deleted (see the console)",
        "ZH": "已删除 {files} 个文件，{n} 个删不掉（详见控制台）"},

    # ── MHWI mrl3 preset dropdown (core/mdf_generator_base.py) ────────────
    "core.mdf_generator_base.mhwi_preset_bundled": {
        "EN": "Standard (bundled)", "ZH": "Standard（内置）"},
    "core.mdf_generator_base.mhwi_preset_none": {
        "EN": "No MHWI presets found", "ZH": "未找到 MHWI 材质预设"},

    # ══════════════════════════════════════════════════════════════════════
    # core/port_consent.py
    # ══════════════════════════════════════════════════════════════════════
    # Line breaks in the body are hard-coded: UILayout does not wrap, and the
    # two languages break in different places.

    "core.port_consent.title": {
        "EN": "Cross-Game Porting -- Before You Start",
        "ZH": "跨游戏移植 · 使用须知"},
    "core.port_consent.body_1": {
        "EN": "This is for porting assets you made yourself, or that you have the\n"
              "author's permission to use.",
        "ZH": "本功能用于移植你自己创作的资产，或你已获得作者授权的资产。"},
    "core.port_consent.body_2": {
        "EN": "Before porting someone else's work -- including a publicly released\n"
              "mod -- get the original author's permission first.",
        "ZH": "移植他人作品（包括已公开发布的 mod）前，请先取得原作者许可。"},
    "core.port_consent.body_3": {
        "EN": "Credit the original author and keep the source noted.\n"
              "Passing off others' work as your own, or selling it, is not what\n"
              "this tool is for.",
        "ZH": "移植后请保留出处与原作者署名。\n"
              "将他人作品据为己有或用于牟利，不属于本工具的用途。"},
    "core.port_consent.confirm": {
        "EN": "I have read this", "ZH": "我已阅读并确认"},
    "core.port_consent.btn_unlock": {
        "EN": "Read Before Using", "ZH": "使用前请阅读"},
    "core.port_consent.btn_unlock_desc": {
        "EN": "Read the cross-game porting notice. Confirming unlocks these tools "
              "for good -- it is asked once, and survives updates",
        "ZH": "阅读跨游戏移植的使用须知。确认后这组功能将永久解锁 —— 只问一次，"
              "更新后也不会重置"},
    "core.port_consent.gate_hint": {
        "EN": "The porting tools unlock once you have read this",
        "ZH": "阅读并确认后即可使用移植功能"},
    "core.port_consent.poll_blocked": {
        "EN": "Read the cross-game porting notice first -- see the 移植 group in "
              "the Modding Toolkit panel",
        "ZH": "请先阅读并确认跨游戏移植使用须知（面板中的“移植”一组）"},
}
