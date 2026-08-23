"""Strings for ui/main_panel.py and ui/editor_panel.py.
Filled in incrementally as each panel is migrated."""

STRINGS = {
    # ── MHW_PT_SuiteSettings collapsible section headers ───────────────────────
    "ui.main_panel.basic_tools_header":     {"EN": "Basic Tools",               "ZH": "基础工具"},
    "ui.main_panel.std_converter_header":   {"EN": "Skeleton & Mesh Convert", "ZH": "骨架&网格转换"},
    "ui.main_panel.pose_convert_header":    {"EN": "Pose Convert",              "ZH": "姿态转换"},

    # ── MHW_PT_SuiteSettings property draw-site label overrides ────────────────
    # (property name= stays a short English fallback; these T() keys are the
    # bilingual label shown at the actual layout.prop() call site)
    "ui.main_panel.import_preset_label":       {"EN": "Source Preset (X)", "ZH": "来源预设 (X)"},
    "ui.main_panel.target_preset_label":       {"EN": "Target Game (Y)",   "ZH": "目标游戏 (Y)"},
    "ui.main_panel.show_mapping_details_label":{"EN": "Show Mapping Details", "ZH": "显示映射细节"},
    "ui.main_panel.pose_preset_field_label":   {"EN": "Skeleton Preset",   "ZH": "骨架预设"},

    # ── align_mode_override EnumProperty items (dynamic callback) ──────────────
    "ui.main_panel.align_mode_pos_only":      {"EN": "Position Only",   "ZH": "仅位置"},
    "ui.main_panel.align_mode_pos_only_desc": {"EN": "Align only the bone head position; keep the target skeleton's original direction and length",
                                                "ZH": "只对齐骨骼头部位置，保留目标骨架原有的方向和长度"},
    "ui.main_panel.align_mode_pos_roll":      {"EN": "Position + Roll", "ZH": "位置+扭转"},
    "ui.main_panel.align_mode_pos_roll_desc": {"EN": "Align head position and copy the source bone's roll; direction/length unchanged",
                                                "ZH": "对齐头部位置并复制来源骨骼的扭转(Roll)，长度方向不变"},
    "ui.main_panel.align_mode_full":          {"EN": "Full Align",      "ZH": "完全对齐"},
    "ui.main_panel.align_mode_full_desc":     {"EN": "Align head, tail, and roll fully to the source bone (bone length and direction follow the source too)",
                                                "ZH": "头部、尾部、扭转全部对齐到来源骨骼 (骨骼长度和方向都会跟随来源)"},

    # ── mhwi_export_mode / mhwi_rank_tab / mhwi_gender EnumProperty items ──────
    "ui.main_panel.mhrs_skel_shadow":      {"EN": "Use Global Skeleton (Legacy)", "ZH": "使用全局骨架（古法）"},
    "ui.main_panel.mhrs_skel_shadow_desc": {
        "EN": "Align the built-in Shadow reference model to the source armature and export it over "
              "mod/{gender}/bone/. Needs no extra plugin, but there is only one such file per gender, "
              "so these proportions apply to every outfit",
        "ZH": "把内置 Shadow 参考模型对齐到体型骨架后覆盖 mod/{gender}/bone/。无需额外插件，"
              "但每个性别只有这一份文件，体型会套用到所有装备"},
    "ui.main_panel.mhrs_skel_lua":         {"EN": "Use Lua Bone (Per-Set Skeleton)", "ZH": "使用Lua bone（独立骨骼）"},
    "ui.main_panel.mhrs_skel_lua_desc": {
        "EN": "Write this set's joint offsets as five json files under reframework/data/LUABoneSystem/custom/. "
              "Proportions apply to this armor set alone, at the cost of players needing the LuaBoneSystem script",
        "ZH": "把本套装备的关节偏移写成五份 json，放在 reframework/data/LUABoneSystem/custom/ 下。"
              "体型只作用于这一套装备，代价是玩家需要安装 LuaBoneSystem 脚本"},

    "ui.main_panel.mhwi_mode_armor":       {"EN": "Armor",  "ZH": "装备"},
    "ui.main_panel.mhwi_mode_armor_desc":  {"EN": "Export character armor (equipment/transmog)", "ZH": "导出人物装备（护甲/幻化）"},
    "ui.main_panel.mhwi_mode_weapon":      {"EN": "Weapon", "ZH": "武器"},
    "ui.main_panel.mhwi_mode_weapon_desc": {"EN": "Export weapon model (blank-model replacement not yet supported)", "ZH": "导出武器模型（暂不支持空模替换）"},
    "ui.main_panel.mhwi_rank_hr":          {"EN": "LR/HR",         "ZH": "上下位"},
    "ui.main_panel.mhwi_rank_hr_desc":     {"EN": "Low Rank / High Rank armor", "ZH": "低位/高位装备"},
    "ui.main_panel.mhwi_rank_mr":          {"EN": "Master Rank",   "ZH": "大师位"},
    "ui.main_panel.mhwi_rank_mr_desc":     {"EN": "Iceborne Master Rank armor", "ZH": "冰原大师位装备"},
    "ui.main_panel.mhwi_rank_sp":          {"EN": "Full Transmog", "ZH": "整套幻化"},
    "ui.main_panel.mhwi_rank_sp_desc":     {"EN": "Standalone transmog set (includes head/hair models)", "ZH": "独立幻化套装（含头部/头发模型）"},
    "ui.main_panel.mhwi_gender_f":         {"EN": "Female", "ZH": "女"},
    "ui.main_panel.mhwi_gender_f_desc":    {"EN": "Export female hunter equipment files only", "ZH": "仅导出女猎装备文件"},
    "ui.main_panel.mhwi_gender_m":         {"EN": "Male",   "ZH": "男"},
    "ui.main_panel.mhwi_gender_m_desc":    {"EN": "Export male hunter equipment files only", "ZH": "仅导出男猎装备文件"},
    "ui.main_panel.mhwi_gender_both":      {"EN": "Both",   "ZH": "双性"},
    "ui.main_panel.mhwi_gender_both_desc": {"EN": "Export both male and female hunter equipment files", "ZH": "同时导出男女猎装备文件"},

    # ── mhws_bs_bind_part EnumProperty items ────────────────────────────────────
    "ui.main_panel.mhws_bind_part_helmet": {"EN": "Helmet", "ZH": "头盔"},
    "ui.main_panel.mhws_bind_part_body":   {"EN": "Body",   "ZH": "身体"},

    # ── bone_view_mode custom toggle buttons (line ~669-674) ────────────────────
    "ui.main_panel.bone_view_all":      {"EN": "Show All",    "ZH": "全显"},
    "ui.main_panel.bone_view_base":     {"EN": "Base Only",   "ZH": "仅基础骨"},
    "ui.main_panel.bone_view_physics":  {"EN": "Physics Only","ZH": "仅物理骨"},

    # ── MHW_OT_GeneralTools: action EnumProperty items + per-action tooltips ───
    # (label keys feed the dynamic items= callback AND the matching toolbar
    # buttons in MHW_PT_MainPanel.draw() that invoke this operator; desc keys
    # feed both the enum item description and the operator's dynamic
    # classmethod description() hook)
    "ui.main_panel.gt_action_roll_zero":         {"EN": "Zero Roll",              "ZH": "扭转归零"},
    "ui.main_panel.gt_desc_roll_zero":           {"EN": "Recursively zero the Roll value of the selected bones and all their children",
                                                   "ZH": "递归将选中骨骼及其所有子骨的 Roll 值归零"},
    "ui.main_panel.gt_action_add_tail":          {"EN": "Add Tail Bone",          "ZH": "添加尾骨"},
    "ui.main_panel.gt_desc_add_tail":            {"EN": "Add a vertical tail bone to the end of each selected bone",
                                                   "ZH": "在每根选中骨骼的末端添加一根垂直向上的尾骨"},
    "ui.main_panel.gt_action_mirror_x":          {"EN": "Mirror Align X",         "ZH": "镜像对齐 X"},
    "ui.main_panel.gt_desc_mirror_x":            {"EN": "Select exactly two bones: mirror the X- side bone's position and roll onto the X+ side bone",
                                                   "ZH": "正好选中两根骨骼：以 X+ 侧那根为基准，镜像覆盖 X- 侧那根的位置与扭转"},
    "ui.main_panel.gt_action_simplify_chain":    {"EN": "Simplify Selected Chains", "ZH": "简化选中骨骼链"},
    "ui.main_panel.gt_desc_simplify_chain":      {"EN": "Pair up bones along each chain, merge their weights, and delete the redundant bones; unweighted tail bones are skipped automatically",
                                                   "ZH": "按链结构将骨骼两两配对合并权重并删除多余骨骼；链末无权重骨（尾骨）自动跳过不参与配对"},
    "ui.main_panel.gt_action_merge_to_active":   {"EN": "Merge Bones into Active Bone", "ZH": "合并骨骼到激活骨"},
    "ui.main_panel.gt_desc_merge_to_active":     {"EN": "Merge the weights of the other selected bones into the active bone (last clicked), then delete the other bones",
                                                   "ZH": "将其余选中骨骼的权重全部并入激活骨（最后点击的那根），然后删除其余骨骼"},
    "ui.main_panel.gt_action_align_pos":         {"EN": "Align (Position)",       "ZH": "对齐 (位置)"},
    "ui.main_panel.gt_desc_align_pos":           {"EN": "Select two armatures: align the active armature's same-named bone head positions to the source armature, without changing bone length/direction",
                                                   "ZH": "选中两个骨架：将激活骨架中同名骨骼的 head 位置对齐到源骨架，不改变骨骼长度与方向"},
    "ui.main_panel.gt_action_align_pos_roll":    {"EN": "Align (Position + Roll)","ZH": "对齐 (位置+扭转)"},
    "ui.main_panel.gt_desc_align_pos_roll":      {"EN": "Select two armatures: align same-named bones' head position and roll, without changing bone length/direction",
                                                   "ZH": "选中两个骨架：对齐同名骨骼的 head 位置和 roll 扭转，不改变骨骼长度与方向"},
    "ui.main_panel.gt_action_align_full":        {"EN": "Align (Full)",           "ZH": "对齐 (完全)"},
    "ui.main_panel.gt_desc_align_full":          {"EN": "Fully align head, tail, and roll between two armatures by bone name (bone length follows the source too)",
                                                   "ZH": "选中两个骨架：按骨骼名完全对齐 head、tail 和 roll（骨骼长度也会跟随源骨架）"},
    "ui.main_panel.gt_action_merge_chains":      {"EN": "Merge Chains into Active Chain", "ZH": "合并链到激活链"},
    "ui.main_panel.gt_desc_merge_chains":        {"EN": "Select the heads of multiple chains: merge the other chains bone-by-bone by position into the active bone's chain; overflow is merged into the chain's last bone",
                                                   "ZH": "选中多条链的链首，将其余链按位置逐骨合并到激活骨所在链；源链超出长度的部分并入链末骨"},

    # ── MHW_OT_GeneralTools.execute() report messages ──────────────────────────
    "ui.main_panel.gt_err_select_armature":      {"EN": "Please select an armature first", "ZH": "请先选中一个骨架"},
    "ui.main_panel.gt_warn_select_bone_edit":    {"EN": "Please select at least one bone in Edit Mode", "ZH": "请在编辑模式下至少选中一根骨骼"},
    "ui.main_panel.gt_info_roll_reset":          {"EN": "Reset Roll on {n} bone(s)", "ZH": "已重置 {n} 根骨骼的 Roll"},
    "ui.main_panel.gt_warn_select_tail_bone":    {"EN": "Please select the bone(s) to add a tail to", "ZH": "请选中需要加尾巴的骨骼"},
    "ui.main_panel.gt_info_tail_added":          {"EN": "Added {n} tail bone(s)", "ZH": "添加了 {n} 根尾骨"},
    "ui.main_panel.gt_err_mirror_need_two":      {"EN": "Please select exactly two bones for mirror align", "ZH": "请正好选中两个骨骼进行镜像对齐"},
    "ui.main_panel.gt_err_need_two_bones":       {"EN": "Please select at least two bones", "ZH": "至少需要选中两个骨骼"},
    "ui.main_panel.gt_warn_no_pairs":            {"EN": "No pairs were generated (not enough bones, or all are tail bones)", "ZH": "未生成任何配对（骨骼数不足或全为尾骨）"},
    "ui.main_panel.gt_info_chain_simplified":    {"EN": "Chain simplification complete: processed {n} bone pair(s)", "ZH": "骨链简化完成: 处理 {n} 对骨骼"},
    "ui.main_panel.gt_err_need_active_bone":     {"EN": "Please make sure there is an active bone (the last one clicked is kept)", "ZH": "请确保有激活骨骼（最后点击的那根为保留目标）"},
    "ui.main_panel.gt_err_need_two_for_merge":   {"EN": "Please select at least two bones (the active bone is kept, the rest are merged in)", "ZH": "请至少选中两根骨骼（激活骨保留，其余骨并入）"},
    "ui.main_panel.gt_info_merged_into":         {"EN": "Merged {n} bone(s) into [{name}]", "ZH": "已将 {n} 根骨骼并入 [{name}]"},
    "ui.main_panel.gt_warn_no_valid_chain_heads":{"EN": "No valid chain head found to merge (select the head bone of another chain)", "ZH": "未找到有效的待合并链首（请选中其他链的链首骨骼）"},
    "ui.main_panel.gt_info_chains_merged":       {"EN": "Merged {chains} chain(s) into [{name}], processed {pairs} bone pair(s) in total", "ZH": "已将 {chains} 条链合并到 [{name}]，共处理 {pairs} 对骨骼"},
    "ui.main_panel.gt_err_need_two_armatures":   {"EN": "Please select two armatures (active one is the target, the other is the source)", "ZH": "请选中两个骨架（激活的为目标，另一个为源）"},
    "ui.main_panel.gt_label_align_pos":          {"EN": "Position Align", "ZH": "位置对齐"},
    "ui.main_panel.gt_info_align_result":        {"EN": "{label}: {n} bone(s)", "ZH": "{label}：{n} 根骨骼"},

    # ── bridge entries: bone_utils.mirror_bone_transform() returns fixed
    # Chinese message templates (that file is out of this migration's scope);
    # keyed by the literal template text itself so T() can translate them
    # without touching core/bone_utils.py ──────────────────────────────────────
    "请选中两个骨骼":        {"EN": "Please select two bones", "ZH": "请选中两个骨骼"},
    "骨骼未找到":            {"EN": "Bone not found",          "ZH": "骨骼未找到"},
    "已将 %s 对齐到 %s":     {"EN": "Aligned %s to %s",        "ZH": "已将 %s 对齐到 %s"},

    # ── MHW_PT_MainPanel.draw() section headers / static labels ────────────────
    "ui.main_panel.label_bone_merge":            {"EN": "Bone & Weight Merge", "ZH": "骨骼&权重合并"},
    "ui.main_panel.label_bone_processing":       {"EN": "Bone Processing",  "ZH": "骨骼处理"},
    "ui.main_panel.label_mesh_processing":       {"EN": "Mesh Processing",  "ZH": "网格处理"},
    "ui.main_panel.label_texture_processing":    {"EN": "Texture Processing", "ZH": "贴图处理"},
    "ui.main_panel.label_skeleton_cleanup":      {"EN": "Non-Physics Workflow", "ZH": "非物理流程工具"},
    "ui.main_panel.label_physics_chain_tools":   {"EN": "Physics Workflow", "ZH": "物理流程工具"},
    "ui.main_panel.label_bone_visibility":       {"EN": "Bone Visibility [X]:", "ZH": "骨骼显示 [X]:"},
    "ui.main_panel.label_mapping_preview_need_preset": {"EN": "Mapping detail preview requires a specific preset (not Auto-Detect)", "ZH": "映射详情预览需要选定具体预设（非自动识别）"},
    "ui.main_panel.label_missing":                {"EN": "Missing", "ZH": "缺失"},
    "ui.main_panel.label_select_armature_preview":{"EN": "Select an armature to preview", "ZH": "请选中骨架以预览"},
    "ui.main_panel.label_simple_tools":           {"EN": "Convert Tools:", "ZH": "转换工具:"},
    "ui.main_panel.label_pose_recorder":          {"EN": "Custom Convert:", "ZH": "自定义转换:"},
    "ui.main_panel.label_fakebone_section":       {"EN": "Fake Head Method (FakeBone)", "ZH": "假头法 (FakeBone)"},
    "ui.main_panel.label_need_mhw_model_editor":  {"EN": "Requires MHW Model Editor!", "ZH": "需要 MHW Model Editor!"},
    "ui.main_panel.label_need_re_chain_editor":   {"EN": "Requires RE Chain Editor!",  "ZH": "需要 RE Chain Editor!"},
    "ui.main_panel.label_need_re_mesh_editor":    {"EN": "Requires RE Mesh Editor!",   "ZH": "需要 RE Mesh Editor!"},

    # ── MHW_PT_MainPanel.draw() operator button labels ──────────────────────────
    "ui.main_panel.btn_sk_to_weights":            {"EN": "Shape Key to Weights",  "ZH": "形态键转权重"},
    "ui.main_panel.btn_merge_renamed_vgroups":    {"EN": "Merge Renamed Vertex Groups", "ZH": "合并重名顶点组"},
    "ui.main_panel.btn_universal_snap":           {"EN": "Align Bones [X+Y, dual armature]", "ZH": "对齐骨骼 [X+Y, 双骨架]"},
    "ui.main_panel.btn_same_kind_snap":           {"EN": "Align Bones [by name, dual armature]", "ZH": "对齐骨骼 [同名骨骼, 双骨架]"},
    "ui.main_panel.same_kind_align_label":        {"EN": "Same-Kind Bone Align", "ZH": "同种类骨骼对齐"},
    "ui.main_panel.same_kind_align_desc":         {"EN": "Both armatures are already the same kind, so bones are matched by name and no preset is needed. Only the align action is shown",
                                                    "ZH": "两个骨架本就是同一种类，按骨骼名直接匹配，不需要预设。勾选后仅显示对齐骨骼功能"},
    "ui.main_panel.btn_direct_convert":           {"EN": "Rename Vertex Groups [X+Y]", "ZH": "重命名顶点组 [X+Y]"},
    "ui.main_panel.btn_merge_physics_weights":    {"EN": "Downgrade Physics Weights [X]", "ZH": "物理权重降级 [X]"},
    "ui.main_panel.btn_remove_non_base_bones":    {"EN": "Remove Non-Base Bones [X]", "ZH": "剔除非基础骨骼 [X]"},
    "ui.main_panel.btn_rename_bones_to_target":   {"EN": "Rename Base Bones [X+Y]", "ZH": "基础骨骼改名 [X+Y]"},
    "ui.main_panel.btn_smart_graft":              {"EN": "Graft Physics Bones [X+Y, dual armature]", "ZH": "移植物理骨骼 [X+Y, 双骨架]"},
    "ui.main_panel.btn_merge_into_parent":        {"EN": "Merge into Parent Bone", "ZH": "合并到父骨"},
    "ui.main_panel.btn_mark_main_continue":       {"EN": "Mark as Main Chain Continuation", "ZH": "标记为主链延伸"},
    "ui.main_panel.btn_clear_chain_role":         {"EN": "Clear Mark", "ZH": "清除标记"},
    "ui.main_panel.btn_refresh_bone_colors":      {"EN": "Refresh Bone Colors", "ZH": "刷新骨骼颜色"},
    "ui.main_panel.btn_mmd_a_to_tpose":           {"EN": "MMD A to T-Pose", "ZH": "MMD A转Tpose"},
    "ui.main_panel.btn_ree_to_tpose":             {"EN": "REE to T-Pose", "ZH": "REE转Tpose"},
    "ui.main_panel.btn_import_reference_model": {
        "EN": "Import Reference Model", "ZH": "导入参考模型"},
    "ui.main_panel.btn_port_mesh_cross_game": {
        "EN": "Port RE Mesh", "ZH": "RE Mesh 移植"},
    "ui.main_panel.btn_convert_chain_cross_game": {
        "EN": "Port RE Chain", "ZH": "RE Chain 移植"},
    "ui.main_panel.btn_port_mdf_material_cross_game": {
        "EN": "Port RE MDF", "ZH": "RE MDF 移植"},
    # The three above are "Port <thing>" and pick their target in a dialog; these name
    # their destination instead, because each is one-way and one-target -- MHWilds is
    # the only game with the reference data to cross engines into.  That distinction
    # is what "to Wilds" carries; the earlier "Rebuild as" wording tried to carry the
    # rebuild-vs-conversion difference too, which is an implementation detail the
    # button does not need to argue (user, 2026-08-16).
    # The destination is no longer in the label: each of the three now picks its
    # target game inside its own dialog (MHWilds or MH Rise), so naming one game on
    # the button would be wrong half the time.  They are named after the *source*
    # format instead, which is what the user is holding when they reach for the
    # button and is the same for every target.
    "ui.main_panel.btn_port_mhwi_to_mhws": {
        "EN": "Port Model (mod3)", "ZH": "移植模型 (mod3)"},
    "ui.main_panel.btn_port_mrl3_to_mdf2": {
        "EN": "Port Material (mrl3)", "ZH": "移植材质 (mrl3)"},
    "ui.main_panel.btn_port_ctc_to_chain2": {
        "EN": "Port Physics (ctc)", "ZH": "移植物理 (ctc)"},
    # Named after what it does to a whole set, not after the three buttons above:
    # it is not "run those three in a loop", it also imports and exports.
    "ui.main_panel.btn_batch_port_mhrs": {
        "EN": "Batch Port Set → MHRS", "ZH": "批量移植整套 → 崛起"},
    "ui.main_panel.btn_record_transform":         {"EN": "Record Transform (select two armatures)", "ZH": "录制变换 (选两个骨架)"},
    "ui.main_panel.btn_apply_forward":            {"EN": "▶ Forward (A→B)", "ZH": "▶ 正向 (A→B)"},
    "ui.main_panel.btn_apply_inverse":            {"EN": "◀ Inverse (B→A)", "ZH": "◀ 逆向 (B→A)"},
    "ui.main_panel.btn_tex_process":              {"EN": "Texture Processing", "ZH": "贴图处理"},
    "ui.main_panel.btn_align_non_physics":        {"EN": "Align Non-Physics Bones", "ZH": "对齐非物理骨骼"},
    "ui.main_panel.btn_split_physics_bones":      {"EN": "Split Physics Bones", "ZH": "拆分物理骨"},
    "ui.main_panel.btn_batch_rename_physics":     {"EN": "One-Click Rename", "ZH": "一键重命名"},
    "ui.main_panel.btn_mrl3_tex_processor":       {"EN": "MRL3 Processor", "ZH": "MRL3 处理器"},
    "ui.main_panel.btn_mrl3_generator":           {"EN": "MRL3 Generator", "ZH": "MRL3 生成器"},
    # ── shared property labels drawn via prop(text=...) ────────────────────
    # Blender shows a property's static name= when prop() has no text=, which
    # bypasses T() entirely. These are the labels that needed routing through it.
    "ui.prop.export_mode": {"EN": "Export Mode", "ZH": "导出模式"},
    "ui.prop.gender": {"EN": "Gender", "ZH": "性别"},
    "ui.prop.rank": {"EN": "Rank", "ZH": "位阶"},
    "ui.prop.cleanup_before_export": {"EN": "Clean Mesh Before Export", "ZH": "导出前清理网格"},
    "ui.prop.triangulate_face": {"EN": "Triangulate Face Mesh", "ZH": "面部网格三角化"},
    "ui.prop.anti_plagiarism": {"EN": "Anti-Plagiarism", "ZH": "防石化"},
    "ui.prop.watermark": {"EN": "Add Watermark Effect", "ZH": "添加水印特效"},
    "ui.prop.use_blank_export": {"EN": "Use Blank Model for Unselected", "ZH": "未选部位使用空模"},
    "ui.prop.ao_image": {"EN": "AO Map", "ZH": "AO 贴图"},
    "ui.prop.use_ao": {"EN": "Add AO", "ZH": "添加 AO"},
    "ui.prop.use_fakebone": {"EN": "Use Fake Head Method", "ZH": "使用假头法"},
    "ui.prop.use_body_armature": {"EN": "Use Body Armature", "ZH": "使用身体骨架"},
    "ui.prop.filter_axis": {"EN": "Axis", "ZH": "轴向"},
    "ui.prop.filter_direction": {"EN": "Direction", "ZH": "方向"},
    "ui.prop.edit_mode": {"EN": "Edit Mode", "ZH": "编辑模式"},

    # ── ui/game_sections.py — per-game tool groups ─────────────────────────
    "ui.game_sections.group_io":       {"EN": "Import & Export",          "ZH": "导入 & 导出"},
    "ui.game_sections.group_rig":      {"EN": "Skeleton & Mesh",          "ZH": "骨架 & 网格处理"},
    "ui.game_sections.group_material": {"EN": "Material & Texture",       "ZH": "材质 & 贴图处理"},
    "ui.game_sections.group_physics":  {"EN": "Physics",                  "ZH": "物理处理"},
    "ui.game_sections.group_port":     {"EN": "Cross-Game Port",          "ZH": "跨游戏移植"},
    "ui.game_sections.btn_batch_export_re4":  {"EN": "RE4 Batch Exporter",  "ZH": "RE4 批量导出"},
    "ui.game_sections.btn_batch_export_mhrs": {"EN": "MHRS Batch Exporter", "ZH": "MHRS 批量导出"},
    "ui.game_sections.btn_batch_export_re9":  {"EN": "RE9 Batch Exporter",  "ZH": "RE9 批量导出"},
    "ui.game_sections.btn_mdf_convert_material": {"EN": "Convert to Another MDF Material", "ZH": "转换为其他MDF材质"},

    "ui.main_panel.btn_convert_packed_shader":    {"EN": "Convert Selected to Packed Shader",
                                                   "ZH": "选中物体转为打包着色器"},
    "ui.main_panel.btn_create_chain":             {"EN": "One-Click Create Chain", "ZH": "一键创建 Chain"},
    "ui.main_panel.btn_mmd_face_weights":         {"EN": "MMD Shape Key to Face Weights", "ZH": "MMD 形态键转表情权重"},
    "ui.main_panel.btn_batch_export":             {"EN": "Batch Export", "ZH": "批量导出"},
    "ui.main_panel.btn_pre_export_check":         {"EN": "Matching Check", "ZH": "匹配检查"},
    "ui.main_panel.btn_batch_import":             {"EN": "Batch Import", "ZH": "批量导入"},
    "ui.main_panel.btn_mhws_preprocess":          {"EN": "One-Click Import & Align Wilds Model", "ZH": "一键导入并对齐荒野模型"},
    "ui.main_panel.btn_mhws_optimize_skeleton":   {"EN": "Optimize Wilds Skeleton", "ZH": "优化荒野骨架"},
    "ui.main_panel.btn_mhws_optimize_aux":        {"EN": "Optimize Auxiliary Bones & Weights", "ZH": "优化辅助骨骼及权重"},
    "ui.main_panel.btn_add_facial_bones":         {"EN": "One-Click Add Facial Bones", "ZH": "一键添加表情骨"},
    "ui.main_panel.btn_mdf_tex_processor":        {"EN": "MDF2 Processor", "ZH": "MDF2 处理器"},
    "ui.main_panel.btn_mdf_generator":            {"EN": "MDF2 Generator", "ZH": "MDF2 生成器"},
    "ui.main_panel.btn_create_re_chain":          {"EN": "One-Click Create RE Chain", "ZH": "一键创建 RE Chain"},
    "ui.main_panel.btn_gen_fakebone":             {"EN": "Generate Fake Bones", "ZH": "生成假骨骼"},
    "ui.main_panel.btn_sync_child_orientation":   {"EN": "Sync Child Orientation & Roll", "ZH": "同步子级朝向及扭转"},

    # ── MHW_OT_ShapeKeyToWeights ─────────────────────────────────────────────────
    "ui.main_panel.sk_sign_pos":                  {"EN": "+ (positive)", "ZH": "+（正向）"},
    "ui.main_panel.sk_sign_neg":                  {"EN": "- (negative)", "ZH": "-（负向）"},
    "ui.main_panel.sk_field_shape_key":           {"EN": "Shape Key",         "ZH": "形态键"},
    "ui.main_panel.sk_field_ignore_threshold":    {"EN": "Ignore Threshold",  "ZH": "忽略阈值"},
    "ui.main_panel.sk_field_weight_strength":     {"EN": "Weight Strength",   "ZH": "权重强度"},
    "ui.main_panel.sk_field_smooth_factor":       {"EN": "Smooth Factor",     "ZH": "平滑扩散率"},
    "ui.main_panel.sk_field_smooth_iters":        {"EN": "Smooth Iterations", "ZH": "平滑迭代次数"},
    "ui.main_panel.sk_field_sync_seams":          {"EN": "Sync Seam Vertices","ZH": "缝合重合顶点"},
    "ui.main_panel.sk_field_direction_filter":    {"EN": "Direction Filter",  "ZH": "方向过滤"},
    "ui.main_panel.sk_err_select_non_basis":      {"EN": "Please select a non-Basis shape key", "ZH": "请选择一个非 Basis 的形态键"},
    "ui.main_panel.sk_warn_no_deformation":       {"EN": "Shape key '{name}' has no detectable deformation; try lowering the ignore threshold",
                                                    "ZH": "形态键 '{name}' 未检测到有效形变，请调低忽略阈值"},
    "ui.main_panel.sk_info_generated":            {"EN": "Generated vertex group '{name}' ({n} valid vertex/vertices)",
                                                    "ZH": "已生成顶点组 '{name}'（{n} 个有效顶点）"},

    # ── MHW_OT_MMDFaceWeights ────────────────────────────────────────────────────
    "ui.main_panel.mmd_face_weights_tip":         {"EN": "Split MMD eyelid/mouth shape keys by direction into target-game facial vertex groups",
                                                    "ZH": "将 MMD 眼皮/嘴型形态键按方向拆分为目标游戏表情顶点组"},
    "ui.main_panel.mmd_target_game_label":        {"EN": "Target Game",        "ZH": "目标游戏"},
    "ui.main_panel.mmd_re4_character_label":      {"EN": "Character",          "ZH": "目标角色"},
    "ui.main_panel.mmd_sync_seams_label":         {"EN": "Sync Seam Vertices", "ZH": "缝合重合顶点"},
    "ui.main_panel.mmd_part_l_upper_eyelid":      {"EN": "L Upper Eyelid",  "ZH": "左眼上眼皮"},
    "ui.main_panel.mmd_part_l_lower_eyelid":      {"EN": "L Lower Eyelid",  "ZH": "左眼下眼皮"},
    "ui.main_panel.mmd_part_r_upper_eyelid":      {"EN": "R Upper Eyelid",  "ZH": "右眼上眼皮"},
    "ui.main_panel.mmd_part_r_lower_eyelid":      {"EN": "R Lower Eyelid",  "ZH": "右眼下眼皮"},
    "ui.main_panel.mmd_part_upper_lip":           {"EN": "Upper Lip",       "ZH": "上嘴唇"},
    "ui.main_panel.mmd_part_lower_lip":           {"EN": "Lower Lip",       "ZH": "下嘴唇"},
    "ui.main_panel.mmd_part_l_mouth_corner":      {"EN": "L Mouth Corner",  "ZH": "左嘴角"},
    "ui.main_panel.mmd_part_r_mouth_corner":      {"EN": "R Mouth Corner",  "ZH": "右嘴角"},
    "ui.main_panel.mmd_warn_no_valid_shapekeys":  {"EN": "No valid shape keys found; check the MMD shape key names", "ZH": "未找到任何有效形态键，请检查 MMD 形态键名称"},
    "ui.main_panel.mmd_info_generated":           {"EN": "Generated {n} facial vertex group(s): {parts}", "ZH": "已生成 {n} 个表情顶点组：{parts}"},
    "ui.main_panel.mmd_info_skipped_suffix":      {"EN": "; skipped: {parts}", "ZH": "；跳过：{parts}"},

    # ── MHW_OT_CylindricalFaceNormals / MHW_OT_ResetFaceNormals ──────────────────
    "ui.main_panel.btn_cylindrical_face_normals": {"EN": "Cylindrical Face Normals (Toon)", "ZH": "面法向柱面化 (三渲二)"},
    "ui.main_panel.btn_reset_face_normals":       {"EN": "Reset Face Normals", "ZH": "重置面法向"},
    "ui.main_panel.fn_cyl_tip":                   {"EN": "Replace the selected faces' custom split normals with a cylindrical field, the way stylised toon-shaded face meshes do it. Unselected faces keep theirs",
                                                    "ZH": "把选中面的自定义法线换成柱面场，与风格化三渲二脸部网格的做法类似。未选中的面保持原样"},
    "ui.main_panel.fn_reset_tip":                 {"EN": "Reshade the selected meshes as one uncut surface. The game forbids welded seams, so a body ships cut into many pieces; this shades across the cuts while leaving the split vertices, sharp edges and material borders exactly as they are",
                                                    "ZH": "把选中的模型当作未切分的整体重算法线。游戏不允许缝合边，所以模型会被切成很多块；此操作让着色跨过这些切口，同时完全不动拆分顶点、锐边和材质边界"},
    "ui.main_panel.fn_field_origin":              {"EN": "Axis Center","ZH": "轴心"},
    "ui.main_panel.fn_origin_object":             {"EN": "Object Origin", "ZH": "物体原点"},
    "ui.main_panel.fn_origin_object_desc":        {"EN": "The axis runs through the object's local origin. This is what the shipped Monster Hunter meshes use",
                                                    "ZH": "轴穿过物体局部原点。怪猎原版资产用的就是这个"},
    "ui.main_panel.fn_origin_cursor":             {"EN": "3D Cursor",  "ZH": "3D 游标"},
    "ui.main_panel.fn_origin_bbox":               {"EN": "Bounding Box Center", "ZH": "包围盒中心"},
    "ui.main_panel.fn_field_only_selected":       {"EN": "Selected Faces Only", "ZH": "仅选中面"},
    "ui.main_panel.fn_desc_only_selected":        {"EN": "Only replace the selected faces' normals. Unselected faces keep theirs and the boundary transitions on its own",
                                                    "ZH": "只替换选中面的法线。未选中的面保持原样，边界会自动过渡"},
    "ui.main_panel.fn_field_smooth_boundary":     {"EN": "Boundary Transition", "ZH": "边界过渡"},
    "ui.main_panel.fn_desc_smooth_boundary":      {"EN": "Boundary vertices take the angle-weighted average of both fields, making the transition exactly one vertex wide. Off gives a hard edge",
                                                    "ZH": "边界顶点取相邻两种面的角度加权平均，过渡宽度恰好一个顶点。关掉则是硬边界"},
    "ui.main_panel.fn_field_strength":            {"EN": "Strength", "ZH": "强度"},
    "ui.main_panel.fn_desc_strength":             {"EN": "1 replaces fully; below 1 falls back toward the original normals",
                                                    "ZH": "1 为完全替换，小于 1 会向原法线方向回退"},
    "ui.main_panel.fn_field_weld_distance":       {"EN": "Distance", "ZH": "距离"},
    "ui.main_panel.fn_desc_weld_distance":        {"EN": "Corners closer together than this count as one position (world units). The cuts a game mesh ships with are exactly coincident, so the default is enough unless the mesh has been edited",
                                                    "ZH": "小于这个距离的角视为同一位置（世界单位）。游戏模型的切口是精确重合的，除非编辑过，默认值就够用"},
    "ui.main_panel.fn_field_weld_angle":          {"EN": "Angle Limit", "ZH": "角度上限"},
    "ui.main_panel.fn_desc_weld_angle":           {"EN": "180 averages every corner at a shared position together, which is what treating the mesh as one whole means. Lower it only if coincident surfaces face opposite ways, such as back-to-back eyelash cards",
                                                    "ZH": "180 表示同一位置上的所有角一起平均，这正是「视为整体」的含义。只有存在朝向相反的重合面（比如背靠背的睫毛卡片）时才调低"},
    "ui.main_panel.fn_field_shade_smooth":        {"EN": "Shade Smooth", "ZH": "平滑着色"},
    "ui.main_panel.fn_desc_shade_smooth":         {"EN": "A flat-shaded face ignores custom normals outright, so without this the result would not show on exactly the faces that need it most. It is a shading flag only — nothing is merged or moved",
                                                    "ZH": "平直着色的面会直接忽略自定义法线，不勾选的话最需要修正的那些面反而看不到效果。它只是个着色标记，不会合并或移动任何东西"},
    "ui.main_panel.fn_field_axis":                {"EN": "Axis", "ZH": "轴向"},
    "ui.main_panel.fn_axis_z":                    {"EN": "Global Z", "ZH": "全局 Z"},
    "ui.main_panel.fn_axis_z_desc":               {"EN": "The cylinder's axis, in world space. Z is upright for a standing character; game meshes are often imported rotated, so a local axis would send the field sideways",
                                                    "ZH": "柱面的轴向，按世界坐标。角色站立时为 Z；游戏网格常带旋转导入，用局部轴会让场歪掉"},
    "ui.main_panel.fn_axis_y":                    {"EN": "Global Y", "ZH": "全局 Y"},
    "ui.main_panel.fn_axis_x":                    {"EN": "Global X", "ZH": "全局 X"},
    "ui.main_panel.fn_err_bad_axis":              {"EN": "The object's transform is degenerate (zero scale?), so the axis cannot be mapped into the mesh",
                                                    "ZH": "物体变换退化（缩放为 0？），无法把轴映射到网格上"},
    "ui.main_panel.fn_err_no_faces":              {"EN": "The mesh has no faces", "ZH": "网格没有面"},
    "ui.main_panel.fn_err_no_selection":          {"EN": "No faces selected. Untick 'Selected Faces Only' to affect everything",
                                                    "ZH": "没有选中的面。取消勾选“仅选中面”可作用于全部"},
    "ui.main_panel.fn_warn_all_selected":         {"EN": "The whole mesh is selected, so nothing was preserved — ears and the back of the head will be flattened too",
                                                    "ZH": "整个网格都被选中了，没有任何区域被保留 —— 耳朵和后脑也会被一起拍平"},
    "ui.main_panel.fn_info_applied":              {"EN": "{faces} face(s), {verts} boundary vertex/vertices",
                                                    "ZH": "{faces} 个面，{verts} 个顶点过渡"},
    "ui.main_panel.fn_info_reset":                {"EN": "Reshaded {objs} mesh(es) as one surface across {n} shared position(s)",
                                                    "ZH": "已把 {objs} 个模型作为整体重算法线，跨过 {n} 处重合位置"},
    "ui.main_panel.fn_warn_opposed":              {"EN": "{n} position(s) hold surfaces facing opposite ways and cancelled out; they kept their own face normal. Lower the angle limit to shade them separately",
                                                    "ZH": "有 {n} 处重合位置的面朝向相反、互相抵消，已保留各自的面法向。调低角度上限可让它们分开着色"},

    # ── MHW_OT_FixShapeKeyNormals ────────────────────────────────────────────────
    "ui.main_panel.btn_fix_shape_key_normals":    {"EN": "Fix Shape Key Normals", "ZH": "修复形态键法向"},
    "ui.main_panel.fsk_tip": {
        "EN": "Re-encode the custom normals against the shape-keyed geometry. Blender stores a custom normal relative to a basis derived from the surrounding geometry, so dialling in shape keys leaves the stored bytes untouched but swings the direction they decode to — a few hundred corners on a face can end up tens of degrees out, which is the blotching around the eyes and mouth. This restores the authored directions without re-baking them, so a stylised field is kept exactly as it is",
        "ZH": "按形态键变形后的几何重新编码自定义法向。Blender 存的是法向在「由周围几何推出的基底」里的编码，所以调形态键时存的字节一个没变，解码出来的方向却歪了 —— 一张脸上会有几百个角点偏出几十度，那就是眼周和嘴部糊掉的斑块。此操作只恢复原本的方向，不重算，所以风格化的法向场分毫不动"},
    "ui.main_panel.fsk_field_reset":              {"EN": "Reset Target To Current Normals", "ZH": "重设目标为当前法向"},
    "ui.main_panel.fsk_err_absolute": {
        "EN": "This mesh uses absolute shape keys, whose mixed positions cannot be derived here. Switch to relative keys",
        "ZH": "这个网格用的是绝对形态键，无法在此推出混合后的坐标。请改用相对形态键"},
    "ui.main_panel.fsk_warn_no_deform": {
        "EN": "Every shape key sits at zero, so there is no deformation to correct for",
        "ZH": "所有形态键的值都是 0，没有需要修正的形变"},
    "ui.main_panel.fsk_done": {
        "EN": "Re-encoded {n} corner(s) against {verts} moved vertex/vertices; residual mean {mean} deg, max {max} deg",
        "ZH": "已按 {verts} 个移动顶点重新编码 {n} 个角点；残差平均 {mean} 度、最大 {max} 度"},
    "ui.main_panel.fsk_note_captured": {
        "EN": "Recorded the current normals as the target, so running this again is a no-op",
        "ZH": "已把当前法向记为目标，所以再运行一次不会有变化"},

    # ── MHW_OT_ApplyModifiersKeepShapeKeys ───────────────────────────────────────
    "ui.main_panel.btn_apply_mods_keep_sk":  {"EN": "Apply Modifiers (Keep Shape Keys)", "ZH": "对有形态键网格应用修改器"},
    "ui.main_panel.amk_tip": {
        "EN": "Apply the viewport-enabled modifiers to a mesh that has shape keys, rebuilding every key on top of the result. The object keeps its identity, and key values/mute/ranges are preserved",
        "ZH": "对带形态键的网格应用视图中启用的修改器，并在结果上重建每一个形态键。物体身份不变，形态键的值/静音/范围都会保留"},
    "ui.main_panel.amk_done": {
        "EN": "Applied {mods} modifier(s), rebuilt {keys} shape key(s) on {verts} vertices",
        "ZH": "已应用 {mods} 个修改器，在 {verts} 个顶点上重建了 {keys} 个形态键"},
    "ui.main_panel.amk_note_slider": {
        "EN": "Shape keys store a linear offset, so slider values other than 0/1 are an interpolation of two modifier results",
        "ZH": "形态键存的是线性偏移，滑块取 0/1 以外的值时是两个修改器结果之间的插值"},

    # ── MHW_OT_SeparateByMaterials ───────────────────────────────────────────────
    "ui.main_panel.btn_separate_by_materials": {"EN": "Separate by Materials", "ZH": "按材质分离网格"},
    "ui.main_panel.sbm_tip": {
        "EN": "Split the selected meshes into one object per material. Blender carries shape keys and vertex groups to every fragment, so the ones that no longer do anything are pruned afterwards",
        "ZH": "把选中网格按材质拆成多个物体。Blender 会把形态键和顶点组原样带给每个碎片，所以之后会剪掉在该碎片上已经失效的那些"},
    "ui.main_panel.sbm_field_rename":       {"EN": "Rename to Material",        "ZH": "按材质名重命名"},
    "ui.main_panel.sbm_field_clean_suffix": {"EN": "Strip Material .001 Suffix","ZH": "去掉材质名的 .001 后缀"},
    "ui.main_panel.sbm_field_prune_keys":   {"EN": "Prune Dead Shape Keys",     "ZH": "剪掉失效的形态键"},
    "ui.main_panel.sbm_field_prune_groups": {"EN": "Prune Empty Vertex Groups", "ZH": "剪掉空的顶点组"},
    "ui.main_panel.sbm_no_mesh": {"EN": "No mesh objects selected", "ZH": "没有选中任何网格物体"},
    "ui.main_panel.sbm_done": {
        "EN": "{n} object(s) after the split; pruned {keys} shape key(s) and {groups} vertex group(s)",
        "ZH": "拆分后共 {n} 个物体；剪掉 {keys} 个形态键、{groups} 个顶点组"},

    # ── MHW_OT_CreateOutline ─────────────────────────────────────────────────────
    "ui.main_panel.btn_create_outline": {"EN": "Create Outline", "ZH": "一键描边"},
    "ui.main_panel.outline_tip": {
        "EN": "Create a brand new '<name>_Outline' shell object for each selected mesh (backface-culled "
              "black material + flipped-normal Solidify on a full duplicate, so vertex groups, shape keys "
              "and any Armature binding carry over) without touching the source mesh itself. The Solidify "
              "is auto-applied (same shape-key-safe path as 'Apply Modifiers (Keep Shape Keys)'), so the "
              "shell ends up as real baked geometry rather than a live modifier. Every run is independent "
              "— there's no tracking back to the source, so running it again just adds another shell "
              "instead of replacing the last one",
        "ZH": "给每个选中网格生成一份全新独立的 “<名字>_Outline” 描边网格（背面剔除黑色材质 + 翻转法线的 "
              "Solidify，整份复制自源网格，顶点组权重/形态键/骨架绑定等都会带过去），源网格本身不会被改动。"
              "Solidify 会自动应用（复用“对有形态键网格应用修改器”同一套形态键安全处理），描边网格最终是"
              "实体几何，不是挂着的活动修改器。每次执行都是独立的——不会记录跟源网格的关联，"
              "所以再执行一次只是多生成一份，不会替换掉上一份"},
    "ui.main_panel.outline_field_vgroup": {"EN": "Thickness Vertex Group", "ZH": "厚度顶点组"},
    "ui.main_panel.outline_field_thickness": {"EN": "Thickness", "ZH": "厚度"},
    "ui.main_panel.outline_field_ignore_collection": {"EN": "Ignore Collection", "ZH": "忽略集合"},
    "ui.main_panel.outline_no_mesh": {"EN": "No mesh objects selected", "ZH": "没有选中任何网格物体"},
    "ui.main_panel.outline_all_ignored": {
        "EN": "All selected meshes are in the ignore collection; nothing changed",
        "ZH": "选中的网格都在忽略集合内，未做任何改动"},
    "ui.main_panel.outline_done": {
        "EN": "Created {added} outline shell(s)",
        "ZH": "已生成 {added} 份描边网格"},
    "ui.main_panel.outline_warn_missing_vgroup_suffix": {
        "EN": "; {n} source(s) have no vertex group by that name, outline thickness is uniform there",
        "ZH": "；其中 {n} 个源网格上没有该名字的顶点组，描边厚度按整网格统一处理"},
    "ui.main_panel.outline_warn_not_baked_suffix": {
        "EN": "; {n} shell(s) couldn't be safely auto-applied and were left as a live Solidify modifier",
        "ZH": "；其中 {n} 份描边网格无法安全自动应用，Solidify 仍以活动修改器的形式保留"},

    # ── MHW_OT_MergeRenamedVGroups ───────────────────────────────────────────────
    "ui.main_panel.merge_vg_done": {"EN": "Merge complete: {merged} vertex group(s) merged, {skipped} skipped (matches a real bone)",
                                     "ZH": "合并完成: {merged} 个顶点组已合并，{skipped} 个已跳过（对应真实骨骼）"},

    # ── MODDER_OT_AutoDetectPreset ───────────────────────────────────────────────
    "ui.main_panel.auto_detect_preset_tip":   {"EN": "Detect the selected armature's bone coverage and auto-match the best-fitting preset",
                                                "ZH": "检测当前选中骨架的骨骼覆盖率，自动匹配最合适的预设"},
    "ui.main_panel.err_select_armature_first":{"EN": "Please select an armature first", "ZH": "请先选中骨架"},
    "ui.main_panel.info_detected":            {"EN": "Detected: {name}", "ZH": "已识别: {name}"},
    "ui.main_panel.warn_no_preset_found":     {"EN": "No preset with >= 95% coverage found; please select manually", "ZH": "未找到覆盖率 >= 95% 的预设，请手动选择"},

    # ── ui/editor_panel.py — MHW_PT_PresetEditor ────────────────────────────────
    "ui.editor_panel.panel_title":          {"EN": "Preset Editor", "ZH": "预设编辑器"},
    "ui.editor_panel.manage_header":        {"EN": "Manage Existing Presets:", "ZH": "管理现有预设 (Manage):"},
    "ui.editor_panel.load_edit":            {"EN": "Load/Edit", "ZH": "读取/编辑"},
    "ui.editor_panel.open_preset_folder":   {"EN": "Open Preset Folder", "ZH": "打开预设文件夹"},
    "ui.editor_panel.convert_to_y":         {"EN": "Copy as Y Preset (X Conversion)", "ZH": "复制为 Y 预设 (X转换)"},
    "ui.editor_panel.convert_to_x":         {"EN": "Copy as X Preset (Y Conversion)", "ZH": "复制为 X 预设 (Y转换)"},
    "ui.editor_panel.workspace_header":     {"EN": "Editor Workspace:", "ZH": "编辑器工作区:"},
    "ui.editor_panel.save_name_label":      {"EN": "Save Name", "ZH": "保存名"},
    "ui.editor_panel.save_btn":             {"EN": "Save", "ZH": "保存"},
    "ui.editor_panel.init_list_btn":        {"EN": "Clear & Initialize List", "ZH": "清空并初始化列表"},
    "ui.editor_panel.list_empty":           {"EN": "List is empty, click Initialize", "ZH": "列表为空，请点击初始化"},
    "ui.editor_panel.unset_label":          {"EN": "[Unset]", "ZH": "[未设置]"},
}
