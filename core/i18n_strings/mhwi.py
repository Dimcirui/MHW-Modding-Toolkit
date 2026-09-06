"""
core/i18n_strings/mhwi.py — bilingual STRINGS table for games/mhwi/*.py.

Key naming convention: "mhwi.<module_name_without_.py>.<short_purpose>".
"""

STRINGS = {
    # ── MHWI_OT_EndfieldFaceRename ──────────────────────────────────────────
    "mhwi.operators.endfield_face_rename_desc": {
        "EN": "Batch-convert Endfield facial vertex group names to MHWorld format",
        "ZH": "将 Endfield 面部顶点组名称批量转换为 MHWorld 格式"},
    "mhwi.operators.endfield_face_rename_label": {
        "EN": "Endfield Face Rename", "ZH": "Endfield 面部改名"},
    "mhwi.operators.endfield_processed": {
        "EN": "Renamed / merged {n} vertex group(s)",
        "ZH": "已改名 / 合并 {n} 个顶点组"},
    "mhwi.operators.endfield_map_missing": {
        "EN": "assets/facial_maps/endfield_to_mhwi.json is missing or unreadable",
        "ZH": "读不到 assets/facial_maps/endfield_to_mhwi.json"},


    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/operators.py
    # ══════════════════════════════════════════════════════════════════════

    # ── MHWI_OT_AlignNonPhysics ─────────────────────────────────────────────
    "mhwi.operators.align_non_physics_desc": {
        "EN": "Align MHWI bones (skip physics bones numbered 150-245)",
        "ZH": "对齐 MHWI 骨骼 (跳过 150-245 物理骨)"},
    "mhwi.operators.select_two_armatures": {
        "EN": "Please select two armatures (source -> target)",
        "ZH": "请选择两个骨架 (源 -> 目标)"},
    "mhwi.operators.align_done": {
        "EN": "Aligned: {aligned}, skipped physics bones: {skip}",
        "ZH": "对齐: {aligned}, 跳过物理骨: {skip}"},

    # ── MHWI_OT_AutoCreateChains ─────────────────────────────────────────────
    "mhwi.operators.auto_create_chains_desc": {
        "EN": "In Pose Mode, automatically create a CTC Chain for each linear chain based on "
              "the chain_role property of physics bones.\n"
              "Chains with branches are skipped and reported; resolve branches manually, then run again.\n"
              "Requires the MHW Model Editor add-on.",
        "ZH": "在姿态模式下，根据物理骨骼的 chain_role 属性自动为每条线性链创建 CTC Chain。\n"
              "存在分叉的链会被跳过并报告，需用户手动处理分叉后再次运行。\n"
              "需要 MHW Model Editor 插件。"},
    "mhwi.operators.auto_refresh_name": {
        "EN": "Create Directly (auto-refresh bone colors)", "ZH": "直接创建（自动刷新骨骼颜色）"},
    "mhwi.operators.ctc_collection_desc": {
        "EN": "Select the CTC Collection to write into", "ZH": "选择要写入的 CTC Collection"},
    "mhwi.operators.auto_create_collection_name": {
        "EN": "Auto-create Collection", "ZH": "自动创建集合"},
    "mhwi.operators.straighten_orientation_name": {
        "EN": "Bone Orientation Preprocessing", "ZH": "骨骼方向预处理"},
    "mhwi.operators.no_markers_warning": {
        "EN": "This armature has no markers yet!", "ZH": "当前骨架没有任何标记！"},
    "mhwi.operators.no_markers_hint": {
        "EN": "It's recommended to mark chains manually with the physics chain tools first.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。"},
    "mhwi.operators.branch_detected": {
        "EN": "{n} chain(s) have branches ({names}); CTC doesn't support branching chains. "
              "Mark the branch direction with \"Mark as Main Chain Continue\" and try again",
        "ZH": "检测到 {n} 条链存在分叉（{names}），CTC 不支持分叉链，"
              "请使用【标记为主链延伸】标记分叉方向后重试"},
    "mhwi.operators.auto_create_ctc_failed": {
        "EN": "Failed to auto-create CTC Collection", "ZH": "自动创建 CTC Collection 失败"},
    "mhwi.operators.collection_not_found": {
        "EN": "Collection not found: {name}", "ZH": "找不到集合: {name}"},
    "mhwi.operators.ctc_toolpanel_missing": {
        "EN": "MHW CTC scene properties not found; please confirm MHW Model Editor is loaded correctly",
        "ZH": "未找到 MHW CTC 场景属性，请确认 MHW Model Editor 已正确加载"},
    "mhwi.operators.no_chain_heads": {
        "EN": "No chain head bones found (chain_role=head/branch_head); please refresh bone colors first",
        "ZH": "未找到链首骨骼（chain_role=head/branch_head），请先刷新骨骼颜色"},
    "mhwi.operators.chains_created": {
        "EN": "{n} chain(s) created", "ZH": "已创建 {n} 条链"},
    "mhwi.operators.chains_skipped_existing": {
        "EN": "{n} already existed, skipped", "ZH": "已存在跳过 {n} 条"},
    "mhwi.operators.chains_skipped_branch": {
        "EN": "{n} skipped due to branching: {names}", "ZH": "因分叉跳过 {n} 条: {names}"},
    "mhwi.operators.list_sep": {"EN": ", ", "ZH": "，"},

    # ── MHWI_OT_SplitPhysicsBones ────────────────────────────────────────────
    "mhwi.operators.split_physics_bones_desc": {
        "EN": "Split physics bones into separate armatures by body region (bones are not renamed).\n"
              "Armature object names get a region suffix (_body/_arm/_wst/_leg).\n"
              "When total bone count is <=255, direct rename or split are both available; >255 requires splitting.",
        "ZH": "将物理骨骼按部位拆分到不同骨架（不重命名骨骼）。\n"
              "骨架对象名会加上部位后缀（_body/_arm/_wst/_leg）。\n"
              "骨架总数 ≤255 时可选直接重命名或拆分；>255 时必须拆分。"},
    "mhwi.operators.fast_mode_direct": {"EN": "Direct Rename", "ZH": "直接重命名"},
    "mhwi.operators.fast_mode_direct_desc": {
        "EN": "One step: rename all physics bones directly into the 300-512 range",
        "ZH": "一步到位，全部物理骨命名到 300~512"},
    "mhwi.operators.fast_mode_split": {"EN": "Split into Multiple Regions", "ZH": "拆分为多个部位"},
    "mhwi.operators.fast_mode_split_desc": {
        "EN": "Split the armature by region, then process with \"Batch Rename\" afterward",
        "ZH": "按部位拆分骨架，后续用「一键重命名」处理"},
    "mhwi.operators.region_head": {"EN": "Head", "ZH": "头部"},
    "mhwi.operators.region_arms": {"EN": "Arms", "ZH": "双臂"},
    "mhwi.operators.region_torso": {"EN": "Torso", "ZH": "躯干"},
    "mhwi.operators.region_legs": {"EN": "Legs", "ZH": "双腿"},
    "mhwi.operators.col_region": {"EN": "Region", "ZH": "区域"},
    "mhwi.operators.col_bone_count": {"EN": "Physics Bones", "ZH": "物理骨数"},
    "mhwi.operators.col_target_slot": {"EN": "Target Slot", "ZH": "目标部位"},
    "mhwi.operators.capacity_status": {"EN": "Capacity status:", "ZH": "容量状态："},
    "mhwi.operators.capacity_exceeded": {
        "EN": "Warning: {slot} exceeds capacity limit, please adjust allocation",
        "ZH": "警告：{slot} 超出容量限制，请调整分配"},
    "mhwi.operators.cannot_load_world_preset": {
        "EN": "Cannot load the Monster Hunter World preset", "ZH": "无法加载怪猎世界预设"},
    "mhwi.operators.no_physics_bones_found": {
        "EN": "No physics bones found to process", "ZH": "未找到需要处理的物理骨骼"},
    "mhwi.operators.isolated_physics_bones": {
        "EN": "All physics bones are isolated bones, cannot auto-assign regions",
        "ZH": "物理骨骼均为孤立骨骼，无法自动分配区域"},
    "mhwi.operators.fast_path_prompt": {
        "EN": "Physics bone count is within the body limit — how to proceed?",
        "ZH": "物理骨数未超出 body 限制范围，如何处理？"},
    "mhwi.operators.confirm_region_targets": {
        "EN": "Please confirm the target slot for each region:", "ZH": "请确认各区域的目标部位："},
    "mhwi.operators.over_255_prompt": {
        "EN": "Total bone count exceeds 255; please assign a target slot for each region:",
        "ZH": "总骨骼数超过 255，请分配各区域的目标部位："},
    "mhwi.operators.exceeds_bone_count": {
        "EN": "Currently over by {n} bone(s) (ID range insufficient); please use split mode instead",
        "ZH": "当前超出了 {n} 个骨骼（ID 范围不足），请改用拆分模式"},
    "mhwi.operators.rename_done": {
        "EN": "Rename complete: {success} succeeded, {fail} failed",
        "ZH": "重命名完成：成功 {success} 根，失败 {fail} 根"},
    "mhwi.operators.slot_capacity_exceeded": {
        "EN": "{slot} exceeds capacity limit ({count}/{cap}); please adjust allocation first",
        "ZH": "{slot} 超出容量限制（{count}/{cap}），请先调整分配"},
    "mhwi.operators.split_done": {
        "EN": "Split complete: {n} armature(s) generated ({names})",
        "ZH": "拆分完成：已生成 {n} 个骨架（{names}）"},

    # ── MHWI_OT_BatchRenamePhysicsBones ──────────────────────────────────────
    "mhwi.operators.batch_rename_desc": {
        "EN": "Batch-rename physics bones on all selected armatures to the MhBone_xxx format.\n"
              "Armatures with names containing _body use the 300-512 range; others use 150-200 "
              "(non-tail) + 201-245 (tail).\n"
              "Run \"Split Physics Bones\" first to split armatures, then run this operation.",
        "ZH": "对选中的所有骨架批量重命名物理骨骼为 MhBone_xxx 格式。\n"
              "名称含 _body 的骨架使用 300~512 范围；其他骨架使用 150~200（非尾骨）+ 201~245（尾骨）范围。\n"
              "请先用「拆分物理骨」完成骨架拆分，再运行此操作。"},
    "mhwi.operators.warning_label": {"EN": "Warning", "ZH": "警告"},
    "mhwi.operators.batch_rename_over_limit": {
        "EN": "Currently over by {n} bone(s); recommend simplifying bones before renaming.",
        "ZH": "当前超出了 {n} 个骨骼，建议先简化骨骼后再进行命名。"},
    "mhwi.operators.confirm_rename_anyway": {
        "EN": "Proceed with renaming anyway?", "ZH": "确定仍然进行重命名？"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_import.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_import.part_arm":  {"EN": "Arms", "ZH": "手臂"},
    "mhwi.batch_import.part_leg":  {"EN": "Legs", "ZH": "腿部"},
    "mhwi.batch_import.part_body": {"EN": "Chest", "ZH": "身体"},
    "mhwi.batch_import.part_helm": {"EN": "Head", "ZH": "头盔"},
    "mhwi.batch_import.part_wst":  {"EN": "Waist", "ZH": "腰部"},
    "mhwi.batch_import.gender_f":  {"EN": "Female", "ZH": "女"},
    "mhwi.batch_import.gender_m":  {"EN": "Male", "ZH": "男"},

    "mhwi.batch_import.scan_desc": {
        "EN": "Scan the current Mod Root folder and list importable equipment files",
        "ZH": "扫描当前 Mod Root 目录，列出可导入的装备文件"},
    "mhwi.batch_import.set_mod_root_first": {
        "EN": "Please set the Mod Root folder first (the parent folder of nativePC)",
        "ZH": "请先设置 Mod Root 目录（nativePC 的上级文件夹）"},
    "mhwi.batch_import.no_files_found": {
        "EN": "No importable equipment files found; please confirm the folder structure is correct",
        "ZH": "未找到任何可导入的装备文件，请确认目录结构正确"},
    "mhwi.batch_import.scan_done": {
        "EN": "Scan complete, found {n} file(s)", "ZH": "解析完成，找到 {n} 个文件"},
    "mhwi.batch_import.toggle_group_desc": {
        "EN": "Expand/collapse one equipment set", "ZH": "展开/折叠一套装备"},
    "mhwi.batch_import.select_group_desc": {
        "EN": "Batch select/deselect all files in one equipment set", "ZH": "批量选中/取消选中一套装备的所有文件"},
    "mhwi.batch_import.select_all_desc": {
        "EN": "Select/deselect all pending import files", "ZH": "全选/全不选所有待导入文件"},
    "mhwi.batch_import.batch_import_desc": {
        "EN": "MHWI equipment batch import", "ZH": "MHWI 装备批量导入"},
    "mhwi.batch_import.model_editor_missing": {
        "EN": "MHW Model Editor is not installed", "ZH": "MHW Model Editor 未安装"},
    "mhwi.batch_import.no_items_selected": {
        "EN": "No items selected", "ZH": "没有选中任何项目"},
    "mhwi.batch_import.import_done_with_fail": {
        "EN": "Done: imported {ok}, failed {fail}", "ZH": "完成: 导入 {ok}, 失败 {fail}"},
    "mhwi.batch_import.import_done": {
        "EN": "Done: imported {ok} file(s)", "ZH": "完成: 导入 {ok} 个文件"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_import_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_import_ui.dialog_desc": {
        "EN": "MHWI equipment batch import dialog", "ZH": "MHWI 装备批量导入对话框"},
    "mhwi.batch_import_ui.not_set": {"EN": "Not set", "ZH": "未设置"},
    "mhwi.batch_import_ui.scan_btn": {"EN": "Scan", "ZH": "解析"},
    "mhwi.batch_import_ui.click_scan_hint": {
        "EN": "Click \"Scan\" to scan for equipment files", "ZH": "点击「解析」扫描装备文件"},
    "mhwi.batch_import_ui.set_mod_root_hint": {
        "EN": "Please set Mod Root first", "ZH": "请先设置 Mod Root"},
    "mhwi.batch_import_ui.deselect_all": {"EN": "Deselect All", "ZH": "全不选"},
    "mhwi.batch_import_ui.selected_count": {
        "EN": "{enabled} / {total} selected", "ZH": "{enabled} / {total} 已选"},
    "mhwi.batch_import_ui.main_model": {"EN": "Main Model", "ZH": "主模型"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/weapon_data.py
    # ══════════════════════════════════════════════════════════════════════
    # (weapon type display names in WEAPON_TYPES are static English fallbacks
    # since that list is a module-level constant evaluated once at import time,
    # before the addon's language preference is loaded; only the secondary-part
    # labels below are re-looked-up dynamically via get_weapon_parts())

    "mhwi.weapon_data.type_two":  {"EN": "Greatsword",     "ZH": "大剑"},
    "mhwi.weapon_data.type_one":  {"EN": "Sword & Shield", "ZH": "片手剑"},
    "mhwi.weapon_data.type_sou":  {"EN": "Dual Blades",    "ZH": "双剑"},
    "mhwi.weapon_data.type_swo":  {"EN": "Long Sword",     "ZH": "太刀"},
    "mhwi.weapon_data.type_ham":  {"EN": "Hammer",         "ZH": "大锤"},
    "mhwi.weapon_data.type_hue":  {"EN": "Hunting Horn",   "ZH": "狩猎笛"},
    "mhwi.weapon_data.type_lan":  {"EN": "Lance",          "ZH": "长枪"},
    "mhwi.weapon_data.type_gun":  {"EN": "Gunlance",       "ZH": "铳枪"},
    "mhwi.weapon_data.type_saxe": {"EN": "Switch Axe",     "ZH": "斩斧"},
    "mhwi.weapon_data.type_caxe": {"EN": "Charge Blade",   "ZH": "盾斧"},
    "mhwi.weapon_data.type_rod":  {"EN": "Insect Glaive",  "ZH": "操虫棍"},
    "mhwi.weapon_data.type_bow":  {"EN": "Bow",            "ZH": "弓"},
    "mhwi.weapon_data.type_hbg":  {"EN": "Heavy Bowgun",   "ZH": "重弩炮"},
    "mhwi.weapon_data.type_lbg":  {"EN": "Light Bowgun",   "ZH": "轻弩炮"},

    "mhwi.weapon_data.part_main":   {"EN": "Main Model", "ZH": "主模型"},
    "mhwi.weapon_data.part_sld":    {"EN": "Shield", "ZH": "盾"},
    "mhwi.weapon_data.part_saya":   {"EN": "Sheath", "ZH": "刀鞘"},
    "mhwi.weapon_data.part_sou_r":  {"EN": "Right Blade", "ZH": "右手剑"},
    "mhwi.weapon_data.part_saya_r": {"EN": "Right Sheath", "ZH": "右手鞘"},
    "mhwi.weapon_data.no_weapon_sets": {"EN": "No weapon preset groups", "ZH": "无武器预设组"},
    "mhwi.weapon_data.no_weapons":     {"EN": "No weapons", "ZH": "无武器"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_export.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_export.no_armor_sets": {"EN": "No armor preset packs", "ZH": "无装备包"},
    "mhwi.batch_export.batch_export_desc": {"EN": "MHWI equipment batch export", "ZH": "MHWI 装备批量导出"},
    "mhwi.batch_export.select_weapon_first": {"EN": "Please select a weapon first", "ZH": "请先选择一件武器"},
    "mhwi.batch_export.weapon_not_found": {
        "EN": "Not found in weapon preset group: {id}", "ZH": "武器预设组中未找到: {id}"},
    "mhwi.batch_export.armor_not_found": {
        "EN": "Not found in armor pack: {id}", "ZH": "装备包中未找到: {id}"},
    "mhwi.batch_export.set_natives_root_desc": {
        "EN": "Select the MHWI Mod root folder (the parent folder of nativePC)",
        "ZH": "选择 MHWI Mod 根目录（nativePC 的上级文件夹）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/batch_export_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.batch_export_ui.no_matching_collections": {"EN": "No matching collections", "ZH": "无匹配集合"},
    "mhwi.batch_export_ui.toggle_blank_desc": {
        "EN": "Toggle whether this part uses a blank model", "ZH": "切换该部位是否使用空模"},
    "mhwi.batch_export_ui.toggle_ccl_desc": {
        "EN": "Toggle whether this part's CTC also exports CCL", "ZH": "切换该部位 CTC 是否顺带导出 CCL"},
    "mhwi.batch_export_ui.pick_armor_desc": {
        "EN": "Search and select an armor set (avoids overflowing the screen when there are too many)",
        "ZH": "搜索并选择装备（避免装备过多时下拉表溢出屏幕）"},
    "mhwi.batch_export_ui.pick_weapon_desc": {
        "EN": "Search and select a weapon (avoids overflowing the screen when there are too many)",
        "ZH": "搜索并选择武器（避免武器过多时下拉表溢出屏幕）"},
    "mhwi.batch_export_ui.dialog_desc": {
        "EN": "MHWI equipment batch export dialog", "ZH": "MHWI 装备批量导出对话框"},
    "mhwi.batch_export_ui.watermark_toggle_desc": {
        "EN": "Anti-reselling: adds a watermark effect that is almost only visible when changing equipment",
        "ZH": "防倒狗用，添加一个几乎只在换装时可见的水印"},
    "mhwi.batch_export_ui.watermark_dialog_body": {
        "EN": "This feature is intended only for freely distributed mods.\n"
              "When enabled, wearing this outfit will display:\n"
              "\"This is a free mod — refuse resellers, beware scams!\"\n"
              "If your mod has no free distribution channel,\n"
              "it's best not to use this feature!",
        "ZH": "此功能仅为免费公开MOD使用，\n"
              "选中后会在穿着此套服装时显示：\n"
              "「此为免费MOD，拒绝倒狗 谨防受骗！」\n"
              "如果你的mod不设任何免费获取渠道，\n"
              "最好不要使用此功能！"},
    "mhwi.batch_export_ui.preset_group": {"EN": "Preset Group", "ZH": "预设组"},
    "mhwi.batch_export_ui.weapon_type": {"EN": "Weapon Type", "ZH": "武器类型"},
    "mhwi.batch_export_ui.select_armor_hint": {
        "EN": "Please select an armor set to configure bindings", "ZH": "请选择装备以配置绑定"},
    "mhwi.batch_export_ui.armor_not_in_pack": {
        "EN": "This armor was not found in the pack", "ZH": "装备包中未找到该装备"},
    "mhwi.batch_export_ui.pick_weapon_placeholder": {"EN": "Select weapon...", "ZH": "选择武器..."},
    "mhwi.batch_export_ui.select_weapon_hint": {
        "EN": "Please select a weapon to configure bindings", "ZH": "请选择武器以配置绑定"},
    "mhwi.batch_export_ui.patch_model_warning": {
        "EN": "This weapon has a patch model — replacing it is not recommended!",
        "ZH": "该武器拥有贴片模型，不建议替换！"},
    "mhwi.batch_export_ui.blank_model": {"EN": "Blank", "ZH": "空模"},
    "mhwi.batch_export_ui.blank_model_evhl": {"EN": "Blank+evhl", "ZH": "空模+evhl"},
    "mhwi.batch_export_ui.physics_not_supported": {"EN": "Physics Not Supported", "ZH": "不支持物理"},
    "mhwi.batch_export_ui.standalone_face": {"EN": "Standalone Face", "ZH": "独立头部"},
    "mhwi.batch_export_ui.face_label": {"EN": "Face", "ZH": "头部"},
    "mhwi.batch_export_ui.standalone_hair": {"EN": "Standalone Hair", "ZH": "独立头发"},
    "mhwi.batch_export_ui.hair_label": {"EN": "Hair", "ZH": "头发"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_generator.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_generator.refresh_desc": {"EN": "Refresh the material list", "ZH": "刷新材质列表"},
    "mhwi.mrl3_generator.process_desc": {
        "EN": "Generate MRL3 + textures from Blender materials", "ZH": "从 Blender 材质生成 MRL3 + 贴图"},
    "mhwi.mrl3_generator.set_mod_root_first": {"EN": "Please set the Mod Root folder first", "ZH": "请先设置 Mod Root 目录"},
    "mhwi.mrl3_generator.select_mod3_collection_first": {
        "EN": "Please select a MOD3 collection first", "ZH": "请先选择 MOD3 集合"},
    "mhwi.mrl3_generator.fill_base_path": {
        "EN": "Please fill in the Base Path (texture directory under nativePC/)",
        "ZH": "请填写 Base Path（nativePC/ 下的贴图目录）"},
    "mhwi.mrl3_generator.click_refresh_first": {
        "EN": "Please click Refresh to load materials first", "ZH": "请先点击 Refresh 加载材质"},
    "mhwi.mrl3_generator.cannot_load_tex_convert": {
        "EN": "Cannot load the MHW Model Editor texture conversion function; "
              "please confirm it's installed and enabled",
        "ZH": "无法加载 MHW Model Editor 贴图转换函数，请确认已安装并启用"},
    "mhwi.mrl3_generator.cannot_load_tex_utils": {
        "EN": "Cannot load the RE Mesh Editor texture tools; please confirm it's installed and enabled",
        "ZH": "无法加载 RE Mesh Editor 贴图工具，请确认已安装并启用"},
    "mhwi.mrl3_generator.process_done_with_fail": {
        "EN": "Done: {success} succeeded, {fail} failed", "ZH": "完成: 成功 {success}, 失败 {fail}"},
    "mhwi.mrl3_generator.process_done": {
        "EN": "Done: successfully generated MRL3 + textures for {n} material(s)",
        "ZH": "完成: 成功生成 {n} 个材质的 MRL3 + 贴图"},
    "mhwi.mrl3_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the MOD3 collection using the current material (stage 2: smart filter)",
        "ZH": "选中 MOD3 集合中所有使用当前材质的网格物体（阶段二：智能筛选）"},
    "mhwi.mrl3_generator.selected_matching_meshes": {
        "EN": "Selected {n} mesh(es) using '{name}' (including self, {total} total)",
        "ZH": "已选中 {n} 个使用 '{name}' 的网格（含自身共 {total} 个）"},

    "mhwi.mrl3_generator.use_toon_name": {"EN": "Toon Shading", "ZH": "使用三渲二"},
    "mhwi.mrl3_generator.skip_textures_name": {"EN": "Materials Only", "ZH": "仅生成材质"},
    "mhwi.mrl3_generator.ao_strength_name": {
        "EN": "AO Strength", "ZH": "AO 强度"},
    "mhwi.mrl3_generator.hide_snow_overlay_name": {
        "EN": "Hide Snow Overlay (fixes black legs in snow)", "ZH": "隐藏覆雪效果（解决雪地腿部发黑）"},
    "mhwi.mrl3_generator.flip_normal_g_name": {"EN": "Normal Map OpenGL -> DirectX", "ZH": "法线 OpenGL → DirectX"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_generator_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_generator_ui.dialog_desc": {
        "EN": "MRL3 Generator - create MRL3 + textures from Blender mesh materials. "
              "Requires an existing MOD3 collection with a Principled BSDF wired up in the material",
        "ZH": "MRL3 Generator — 从 Blender 网格材质创建 MRL3 + 贴图。需要有现成的 MOD3 集合，并在材质里连好 Principled BSDF"},
    "mhwi.mrl3_generator_ui.auto_prefix": {"EN": "Auto", "ZH": "自动"},
    "mhwi.mrl3_generator_ui.preset_dir_not_found": {
        "EN": "MHW Model Editor MaterialPresets folder not found", "ZH": "未找到 MHW Model Editor MaterialPresets 目录"},
    "mhwi.mrl3_generator_ui.select_mod3_then_refresh": {
        "EN": "Select a MOD3 collection, then click Refresh", "ZH": "选择 MOD3 集合后点击刷新"},
    "mhwi.mrl3_generator_ui.node_tree_analysis": {
        "EN": "Node Tree Analysis (texture source strategy)", "ZH": "节点树分析 (贴图来源策略)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_tex_processor.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_tex_processor.select_mrl3_collection_first": {
        "EN": "Please select an MRL3 collection first", "ZH": "请先选择 MRL3 集合"},
    "mhwi.mrl3_tex_processor.materials_loaded": {
        "EN": "Loaded {n} material(s)", "ZH": "已加载 {n} 个材质"},
    "mhwi.mrl3_tex_processor.process_desc": {
        "EN": "Compose PBR texture channels, convert DDS to TEX, and update MRL3 binding paths",
        "ZH": "合成 PBR 贴图通道、转换 DDS→TEX 并更新 MRL3 绑定路径"},
    "mhwi.mrl3_tex_processor.process_done_with_fail": {
        "EN": "Done: generated {n}, failed {fail}, skipped {skip}",
        "ZH": "完成: 生成 {n}, 失败 {fail}, 跳过 {skip}"},
    "mhwi.mrl3_tex_processor.process_done": {
        "EN": "Done: generated {n}, skipped {skip}", "ZH": "完成: 生成 {n}, 跳过 {skip}"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/mrl3_tex_processor_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.mrl3_tex_processor_ui.dialog_desc": {
        "EN": "MHWI MRL3 + Tex Processor", "ZH": "MHWI MRL3 + Tex 处理器"},
    "mhwi.mrl3_tex_processor_ui.mrl3_collection_label": {"EN": "MRL3 Collection", "ZH": "MRL3 集合"},
    "mhwi.mrl3_tex_processor_ui.base_path_example": {
        "EN": "e.g. pl/f_equip/pl042_0500/helm/tex", "ZH": "例：pl/f_equip/pl042_0500/helm/tex"},
    "mhwi.mrl3_tex_processor_ui.select_mrl3_then_refresh": {
        "EN": "Select an MRL3 collection and click Refresh", "ZH": "选择 MRL3 集合并点击 Refresh"},
    "mhwi.mrl3_tex_processor_ui.use_direct_instead": {"EN": "Use DIRECT instead", "ZH": "请改用 DIRECT"},
    "mhwi.mrl3_tex_processor_ui.no_default": {"EN": "(no default)", "ZH": "(无默认)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhwi/shader_defs.py — packed shader sockets
    #
    # These become node group socket descriptions (tooltips), which are baked
    # into the datablock when the group is first built. Switching language
    # therefore does not retranslate an already-built group; it only affects
    # groups created afterwards.
    # ══════════════════════════════════════════════════════════════════════

    "mhwi.shader_defs.albedo": {
        "EN": "AlbedoMap — RGB base colour, A alpha",
        "ZH": "AlbedoMap — RGB 基础色, A 透明度"},
    "mhwi.shader_defs.normal": {
        "EN": "NormalMap — RG tangent normal (B unused, BC5)",
        "ZH": "NormalMap — RG 切线法线 (B 未使用, BC5)"},
    "mhwi.shader_defs.rmt": {
        "EN": "RMTMap — R roughness, G metallic, B translucency",
        "ZH": "RMTMap — R 粗糙度, G 金属度, B 透光"},
    "mhwi.shader_defs.colormask": {
        "EN": "ColorMaskMap — colour-change mask. Carried for export; not previewed",
        "ZH": "ColorMaskMap — 换色遮罩。仅用于导出, 不参与预览"},
    "mhwi.shader_defs.fx": {
        "EN": "FxMap — carried for export; not previewed",
        "ZH": "FxMap — 仅用于导出, 不参与预览"},
    "mhwi.shader_defs.furvelocity": {
        "EN": "FurVelocityMap — carried for export; not previewed",
        "ZH": "FurVelocityMap — 仅用于导出, 不参与预览"},

    "mhwi.shader_defs.pbr_base_color": {
        "EN": "Base colour. Multiplied with AlbedoMap",
        "ZH": "基础色。与 AlbedoMap 相乘"},
    "mhwi.shader_defs.pbr_alpha": {
        "EN": "Alpha. Multiplied with AlbedoMap's alpha",
        "ZH": "透明度。与 AlbedoMap 的 Alpha 相乘"},
    "mhwi.shader_defs.pbr_roughness": {
        "EN": "Roughness. Multiplied with RMTMap.R, as MRL3 does with fRoughness",
        "ZH": "粗糙度。与 RMTMap.R 相乘 (与 MRL3 的 fRoughness 一致)"},
    "mhwi.shader_defs.pbr_metallic": {
        "EN": "Metallic. Added to RMTMap.G",
        "ZH": "金属度。与 RMTMap.G 相加"},
    "mhwi.shader_defs.pbr_ao": {
        "EN": "Ambient occlusion, multiplied into base colour. MHWI has no AO slot, "
              "so this gets baked into AlbedoMap on export instead of its own texture",
        "ZH": "环境光遮蔽，正片叠底到基础色上。MHWI 没有独立的 AO 槽位，导出时会直接烤进 AlbedoMap，而不是单独出图"},
    "mhwi.shader_defs.pbr_emission": {
        "EN": "Emission colour. Added to EmissiveMap",
        "ZH": "自发光颜色。与 EmissiveMap 相加"},
    "mhwi.shader_defs.pbr_normal": {
        "EN": "Normal map texture — plug the image in directly, no Normal Map "
              "node needed. Its deviation from flat is added to NormalMap's",
        "ZH": "法线贴图 —— 直接连图片即可，不需要 Normal Map 节点。"
              "其相对平面的偏移量与 NormalMap 相加"},

    # ── MHWI_OT_SetMeshDisplayCondition ──────────────────────────────────
    "mhwi.operators.btn_set_display_condition": {"EN": "Set Mesh Display Condition", "ZH": "设置网格显示条件"},
    "mhwi.operators.set_display_condition_desc": {
        "EN": "Set when the selected meshes are visible in game. mod3 encodes this in the Group_<N> part of the object name, so this is a rename. Meshes not already in mod3 naming format are renamed first",
        "ZH": "设置选中网格在游戏里的显示时机。mod3 把它编码在物体名的 Group_<N> 里，所以本质是改名。名字不符合 mod3 格式的网格会先被重命名"},
    "mhwi.operators.disp_field_preset":   {"EN": "Preset",   "ZH": "预设"},
    "mhwi.operators.disp_field_group_id": {"EN": "Group ID", "ZH": "Group ID"},
    "mhwi.operators.disp_cond_0":  {"EN": "0 - Always visible",                      "ZH": "0 - 始终显示"},
    "mhwi.operators.disp_cond_1":  {"EN": "1 - Weapon drawn (weapons only)",         "ZH": "1 - 持刀显示（仅武器）"},
    "mhwi.operators.disp_cond_2":  {"EN": "2 - Weapon sheathed (weapons only)",      "ZH": "2 - 收刀显示（仅武器）"},
    "mhwi.operators.disp_cond_30": {"EN": "30 - Sheathed (needs transform plugin)",  "ZH": "30 - 收刀显示（需要变身插件）"},
    "mhwi.operators.disp_cond_31": {"EN": "31 - Drawn (needs transform plugin)",     "ZH": "31 - 拔刀显示（需要变身插件）"},
    "mhwi.operators.disp_cond_32": {"EN": "32 - Glaive no light / Long Sword no aura (needs transform plugin)",
                                     "ZH": "32 - 虫棍无灯 / 太刀无刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_33": {"EN": "33 - Glaive 1 light / Long Sword white (needs transform plugin)",
                                     "ZH": "33 - 虫棍一灯 / 太刀白刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_34": {"EN": "34 - Glaive 2 lights / Long Sword yellow (needs transform plugin)",
                                     "ZH": "34 - 虫棍二灯 / 太刀黄刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_35": {"EN": "35 - Glaive 3 lights / Long Sword red (needs transform plugin)",
                                     "ZH": "35 - 虫棍三灯 / 太刀红刃显示（需要变身插件）"},
    "mhwi.operators.disp_cond_custom": {"EN": "Other - enter an ID manually", "ZH": "其他 - 手动填写 ID"},
    "mhwi.operators.disp_no_mesh": {"EN": "No mesh objects selected", "ZH": "没有选中任何网格物体"},
    "mhwi.operators.disp_done": {"EN": "Set display condition {gid} on {n} mesh(es)",
                                  "ZH": "已将 {n} 个网格的显示条件设为 {gid}"},
    "mhwi.operators.disp_renamed_suffix": {"EN": "; {n} renamed to mod3 format first",
                                            "ZH": "；其中 {n} 个先重命名为 mod3 格式"},
}
