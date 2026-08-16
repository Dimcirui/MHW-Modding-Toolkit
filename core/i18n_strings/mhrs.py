"""Strings for games/mhrs/. Filled in incrementally as the module is migrated.

Key naming convention: "mhrs.<file_without_.py>.<short_purpose>".
"""

STRINGS = {

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/operators.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.operators.auto_create_chains_desc": {
        "EN": "Create RE Chain in one click (MHRS uses the .chain format)",
        "ZH": "一键创建 RE Chain（MHRS 使用 .chain 格式）"},
    # NOTE: chain_collection's description= is a per-property tooltip (operator property, same
    # gap as pattern 6 — no per-draw dynamic-tooltip hook), left as a plain English literal in
    # operators.py rather than routed through T().

    "mhrs.operators.settings_mode_separate_desc": {
        "EN": "Each chain gets its own independent Chain Settings", "ZH": "每条链拥有独立的 Chain Settings"},
    "mhrs.operators.settings_mode_guess": {"EN": "Guess Groups", "ZH": "猜测分组"},
    "mhrs.operators.settings_mode_guess_desc": {
        "EN": "Auto-classify by bone name; same-type bones share one Chain Settings with guessed physics "
              "parameters written in, unrecognized bones fall into the first group",
        "ZH": "根据骨骼名自动分类，同类型共享一组 Chain Settings 并写入推测物理参数；无法识别的归入第一组"},

    "mhrs.operators.auto_create_collection_label": {"EN": "Auto-create Collection", "ZH": "自动创建集合"},

    "mhrs.operators.chain_format_chain_desc": {
        "EN": "Legacy format, used by MHRS / RE4 etc.", "ZH": "旧格式，用于 MHRS / RE4 等游戏"},

    "mhrs.operators.straighten_orientation_label": {"EN": "Bone Direction Preprocess", "ZH": "骨骼方向预处理"},
    # NOTE: straighten_orientation/auto_refresh/apply_angle_ramp description= are per-property
    # operator tooltips (same pattern-6 gap), left as plain English literals in operators.py.

    "mhrs.operators.auto_refresh_label": {
        "EN": "Create Directly (Auto-refresh Bone Colors)", "ZH": "直接创建（自动刷新骨骼颜色）"},

    "mhrs.operators.apply_angle_ramp_label": {"EN": "Auto-apply Angle Ramp", "ZH": "自动应用角度坡度"},

    "mhrs.operators.no_markers_warning": {"EN": "The current armature has no markers!", "ZH": "当前骨架没有任何标记！"},
    "mhrs.operators.no_markers_hint": {
        "EN": "It's recommended to manually mark chains with the Physics Chain Tools first before using this feature.",
        "ZH": "建议先使用物理链工具手动标记后再使用此功能。"},
    "mhrs.operators.create_failed": {"EN": "Failed to create RE Chain", "ZH": "创建 RE Chain 失败"},
    "mhrs.operators.create_done": {"EN": "RE Chain creation complete", "ZH": "RE Chain 创建完成"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/batch_export.py
    # ══════════════════════════════════════════════════════════════════════

    # ── MHRS_PART_LABEL_KEYS (part_id -> bilingual display label) ──────────
    "mhrs.batch_export.part_arm":  {"EN": "Arm",   "ZH": "护腕"},
    "mhrs.batch_export.part_body": {"EN": "Body",  "ZH": "躯干"},
    "mhrs.batch_export.part_wst":  {"EN": "Waist", "ZH": "腰带"},
    "mhrs.batch_export.part_helm": {"EN": "Helm",  "ZH": "头盔"},
    "mhrs.batch_export.part_leg":  {"EN": "Leg",   "ZH": "腿部"},

    "mhrs.batch_export.gender_f": {"EN": "Female", "ZH": "女"},
    "mhrs.batch_export.gender_m": {"EN": "Male",   "ZH": "男"},

    # ── get_mhrs_schemes_callback / get_mhrs_armor_callback fallback items ─

    # ── MHRS_OT_BatchExport / MHRS_OT_SetNativesRoot ────────────────────────
    "mhrs.batch_export.batch_export_desc": {"EN": "Batch-export MHRS armor", "ZH": "MHRS 装备批量导出"},
    "mhrs.batch_export.set_natives_root_desc": {
        "EN": "Select the MHRS mod root folder (the parent of natives). If the selected folder is itself "
              "named natives, its parent is used automatically",
        "ZH": "选择 MHRS Mod 根目录（natives 的上级）。若选中的文件夹本身名为 natives，自动取其上级"},

    "mhrs.batch_export.remesh_not_installed": {
        "EN": "RE Mesh Editor not installed, skipping pre-export cleanup", "ZH": "RE Mesh Editor 未安装，跳过导出前清理"},
    "mhrs.batch_export.load_scheme_failed": {"EN": "Could not load the armor pack", "ZH": "无法加载装备包"},
    "mhrs.batch_export.armor_not_found_in_scheme": {
        "EN": "Not found in armor pack: {id}", "ZH": "在装备包中未找到: {id}"},

    "mhrs.batch_export.shadow_need_importer": {
        "EN": "Shadow export: requires RE Mesh Editor's mesh importer", "ZH": "Shadow 导出: 需要 RE Mesh Editor 的网格导入器"},
    "mhrs.batch_export.shadow_need_align_arm": {
        "EN": "Shadow export: please select an armature to align to", "ZH": "Shadow 导出: 请选择一个用于对齐的骨架"},
    "mhrs.batch_export.shadow_missing_asset": {
        "EN": "Shadow export: missing built-in reference model {name} (place it under assets/mhrs/shadow/)",
        "ZH": "Shadow 导出: 缺少内置参考模型 {name}（需放入 assets/mhrs/shadow/）"},
    "mhrs.batch_export.shadow_import_failed": {
        "EN": "Failed to import reference model: {path}", "ZH": "导入参考模型失败: {path}"},
    "mhrs.batch_export.shadow_no_unique_armature": {
        "EN": "No unique armature found in the reference model collection", "ZH": "参考模型集合中未找到唯一骨架"},
    "mhrs.batch_export.shadow_export_done": {"EN": "Shadow export complete: {name}", "ZH": "Shadow 导出完成: {name}"},
    "mhrs.batch_export.shadow_export_failed": {"EN": "Shadow export failed: {err}", "ZH": "Shadow 导出失败: {err}"},
    "mhrs.batch_export.lua_bone_export_done": {
        "EN": "LuaBoneSystem: wrote {count} json to {dir}/ ({missing} joint(s) not on this rig, written as 0)",
        "ZH": "LuaBoneSystem: 已写入 {count} 份 json 到 {dir}/（{missing} 根骨骼不在该骨架上，按 0 写出）"},
    "mhrs.batch_export.lua_bone_export_failed": {
        "EN": "LuaBoneSystem export failed: {err}", "ZH": "LuaBoneSystem 导出失败: {err}"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/batch_export_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.batch_export_ui.pick_armor_desc": {
        "EN": "Search and pick an armor set (avoids the dropdown overflowing the screen when there are many)",
        "ZH": "搜索并选择装备（避免装备过多时下拉表溢出屏幕）"},
    "mhrs.batch_export_ui.batch_export_dialog_desc": {
        "EN": "MHRS armor batch-export dialog", "ZH": "MHRS 装备批量导出对话框"},

    "mhrs.batch_export_ui.select_armor_placeholder": {"EN": "Select Armor...", "ZH": "选择装备..."},
    "mhrs.batch_export_ui.select_armor_to_configure": {
        "EN": "Select an armor set to configure bindings", "ZH": "请选择装备以配置绑定"},

    "mhrs.batch_export_ui.skeleton_mode_label":    {"EN": "Skeleton Scheme", "ZH": "骨骼方案"},
    "mhrs.batch_export_ui.lua_bone_hint": {
        "EN": "Writes reframework/data/LUABoneSystem/custom/ next to natives. Players need the LuaBoneSystem script",
        "ZH": "写入与 natives 并列的 reframework/data/LUABoneSystem/custom/，玩家需安装 LuaBoneSystem 脚本"},
    "mhrs.batch_export_ui.align_armature_label":   {"EN": "Source Armature", "ZH": "来源骨架"},
    "mhrs.batch_export_ui.shadow_auto_use_hint":   {
        "EN": "Will auto-use when unselected: {name}", "ZH": "未选择时将自动使用: {name}"},
    "mhrs.batch_export_ui.shadow_no_align_arm_error": {
        "EN": "No align armature selected, and it cannot be auto-determined (requires exactly 1 bound Mesh collection)",
        "ZH": "未选择对齐骨架，且无法自动判定（需恰好绑定 1 个 Mesh 集合）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/mdf_generator.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.mdf_generator.use_toon_label": {"EN": "Toon Shading", "ZH": "使用三渲二"},
    "mhrs.mdf_generator.skip_textures_label": {"EN": "Material Only", "ZH": "仅生成材质"},
    "mhrs.mdf_generator.flip_normal_g_label": {"EN": "Normal OpenGL -> DirectX", "ZH": "法线 OpenGL → DirectX"},
    # NOTE: use_toon/skip_textures/use_ao/ao_image/flip_normal_g description= are PropertyGroup
    # property tooltips (pattern 6 — no per-draw dynamic-tooltip hook for regular properties),
    # left as plain English literals in mdf_generator.py.

    "mhrs.mdf_generator.select_same_material_desc": {
        "EN": "Select all mesh objects in the Mesh Collection that use the active material (stage 2: smart filter)",
        "ZH": "选中 Mesh Collection 中所有使用当前材质的网格物体（阶段二：智能筛选）"},
    "mhrs.mdf_generator.select_mesh_collection_first": {
        "EN": "Please select a Mesh Collection first", "ZH": "请先选择 Mesh Collection"},
    "mhrs.mdf_generator.select_same_material_done": {
        "EN": "Selected {n} mesh(es) using '{name}' (including itself: {total} total)",
        "ZH": "已选中 {n} 个使用 '{name}' 的网格（含自身共 {total} 个）"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/mdf_generator_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.mdf_generator_ui.dialog_desc": {
        "EN": "MHRS MDF2 Generator — creates MDF2 + textures from Blender mesh materials. Requires an existing "
              "mesh collection with a Principled BSDF wired up in the material",
        "ZH": "MHRS MDF2 Generator — 从 Blender 网格材质创建 MDF2 + 贴图。需要有现成的 mesh 集合，并在材质里连好 Principled BSDF"},

    "mhrs.mdf_generator_ui.auto_name_hint": {"EN": "    Auto: {name}", "ZH": "    自动: {name}"},
    "mhrs.mdf_generator_ui.base_path_hint": {"EN": "    e.g. player/mod/f/pl279", "ZH": "    例如 player/mod/f/pl279"},
    "mhrs.mdf_generator_ui.preset_dir_not_found": {
        "EN": "RE Mesh Editor MHRS preset directory not found", "ZH": "未找到 RE Mesh Editor MHRS 预设目录"},
    "mhrs.mdf_generator_ui.select_collection_hint": {
        "EN": "Select a mesh collection, then click refresh", "ZH": "选择网格集合后点击刷新"},
    "mhrs.mdf_generator_ui.strat_analysis_header": {
        "EN": "Node Tree Analysis (Texture Source Strategy)", "ZH": "节点树分析 (贴图来源策略)"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/mdf_tex_processor_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.mdf_tex_processor_ui.dialog_desc": {
        "EN": "MDF2 Processor — processes textures on top of existing MDF2 materials. Requires an existing, "
              "already-named MDF2 collection",
        "ZH": "MDF2 处理器 — 在已有 MDF2 材质的基础上处理贴图。需要有现成的已起好名字的 MDF2 集合"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/shader_defs.py — packed shader sockets
    #
    # These become node group socket descriptions (tooltips), baked into the
    # datablock when the group is first built. Switching language does not
    # retranslate an already-built group; it only affects groups created
    # afterwards.
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.shader_defs.nrmr": {
        "EN": "NRMR_NRRTMap — R/G plain tangent-space normal, B unused, A roughness",
        "ZH": "NRMR_NRRTMap — R/G 普通切线空间法线, B 未使用, A 粗糙度"},

    "mhrs.shader_defs.alphamap": {
        "EN": "AlphaMap — alpha-test cutout mask. No PBR composition recipe "
              "exists for this slot, so it is carried through for export only, "
              "not used by the preview",
        "ZH": "AlphaMap — 抠图测试遮罩。这个槽位没有 PBR 合成方案，仅为导出保留，"
              "预览不使用"},
    "mhrs.shader_defs.usercolorchangemap": {
        "EN": "UserColorchangeMap — drives the S_col_R/S_col_G two-tone "
              "colourisation; carried for export, not used by the preview",
        "ZH": "UserColorchangeMap — 驱动 S_col_R/S_col_G 双色染色；仅为导出保留，"
              "预览不使用"},
    "mhrs.shader_defs.furvelocitymap": {
        "EN": "FurVelocityMap — fur simulation velocity map; carried for "
              "export, not used by the preview",
        "ZH": "FurVelocityMap — 毛发模拟速度贴图；仅为导出保留，预览不使用"},
    "mhrs.shader_defs.furtex": {
        "EN": "FurTex — fur base texture; carried for export, not used by the "
              "preview",
        "ZH": "FurTex — 毛发基础贴图；仅为导出保留，预览不使用"},

    "mhrs.shader_defs.pbr_base_color": {
        "EN": "Base colour. Multiplied with BaseDielectricMap",
        "ZH": "基础色。与 BaseDielectricMap 相乘"},
    "mhrs.shader_defs.pbr_alpha": {
        "EN": "Alpha. No slot carries real opacity for MHRS -- AlphaMap has no "
              "PBR recipe -- so this panel value is the only source",
        "ZH": "透明度。MHRS 没有携带真实不透明度的槽位——AlphaMap 没有 PBR 合成"
              "方案——此项是唯一来源"},
    "mhrs.shader_defs.pbr_roughness": {
        "EN": "Roughness. Multiplied with NRMR_NRRTMap.A",
        "ZH": "粗糙度。与 NRMR_NRRTMap.A 相乘"},
    "mhrs.shader_defs.pbr_metallic": {
        "EN": "Metallic. Added to BaseDielectricMap's inverted alpha (1 - alpha)",
        "ZH": "金属度。与 BaseDielectricMap 反转后的 Alpha (1 - alpha) 相加"},
    "mhrs.shader_defs.pbr_ao": {
        "EN": "Ambient occlusion, multiplied into base colour. Preview-only: "
              "this preset has no AO-carrying slot to write it back to",
        "ZH": "环境光遮蔽，正片叠底到基础色上。仅预览用——这个材质没有携带 AO 的"
              "槽位可以写回"},
    "mhrs.shader_defs.pbr_emission": {
        "EN": "Emission colour. Added to EmissiveMap",
        "ZH": "自发光颜色。与 EmissiveMap 相加"},
    "mhrs.shader_defs.pbr_normal": {
        "EN": "Normal map texture — plug the image in directly, no Normal Map "
              "node needed. Its deviation from flat is added to "
              "NRMR_NRRTMap's decoded normal",
        "ZH": "法线贴图 —— 直接连图片即可，不需要 Normal Map 节点。"
              "其相对平面的偏移量会和 NRMR_NRRTMap 解码出的法线相加"},
    "mhrs.shader_defs.fxmap": {
        "EN": "FxMap — secondary effect mask; carried for export, not used by "
              "the preview",
        "ZH": "FxMap — 附加特效遮罩；仅为导出保留，预览不使用"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/batch_import.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.batch_import.scan_desc": {
        "EN": "Scan the armor pack against the Mod Root and list files found on disk",
        "ZH": "按装备包在 Mod Root 中扫描，列出磁盘上实际存在的文件"},
    "mhrs.batch_import.no_files_found": {"EN": "No files found", "ZH": "未找到任何文件"},
    "mhrs.batch_import.scan_done": {"EN": "Found {n} file(s)", "ZH": "已找到 {n} 个文件"},
    "mhrs.batch_import.toggle_group_desc": {
        "EN": "Expand/collapse this armor set", "ZH": "展开/折叠该装备"},
    "mhrs.batch_import.select_group_desc": {
        "EN": "Select/deselect all files in this armor set", "ZH": "选中/取消选中该装备的所有文件"},
    "mhrs.batch_import.select_all_desc": {
        "EN": "Select/deselect all files", "ZH": "选中/取消选中全部文件"},
    "mhrs.batch_import.mesh_editor_missing": {
        "EN": "RE Mesh Editor not installed, cannot import", "ZH": "未安装 RE Mesh Editor，无法导入"},
    "mhrs.batch_import.no_items_selected": {"EN": "No files selected", "ZH": "未选中任何文件"},
    "mhrs.batch_import.batch_import_desc": {
        "EN": "MHRS armor batch import", "ZH": "MHRS 装备批量导入"},
    "mhrs.batch_import.done": {
        "EN": "Done: imported {ok}, skipped {skip}", "ZH": "完成: 导入 {ok}, 跳过 {skip}"},
    "mhrs.batch_import.done_with_fail": {
        "EN": "Done: imported {ok}, failed {fail}, skipped {skip}",
        "ZH": "完成: 导入 {ok}, 失败 {fail}, 跳过 {skip}"},

    # ══════════════════════════════════════════════════════════════════════
    # games/mhrs/batch_import_ui.py
    # ══════════════════════════════════════════════════════════════════════

    "mhrs.batch_import_ui.dialog_desc": {
        "EN": "MHRS armor batch import dialog", "ZH": "MHRS 装备批量导入对话框"},
    "mhrs.batch_import_ui.scan_btn": {"EN": "Scan", "ZH": "扫描"},
    "mhrs.batch_import_ui.click_scan_hint": {
        "EN": "Click Scan to look for importable files", "ZH": "点击扫描以查找可导入的文件"},
    "mhrs.batch_import_ui.set_mod_root_hint": {
        "EN": "Please set Mod Root first, then click Scan", "ZH": "请先设置 Mod Root，再点击扫描"},
    "mhrs.batch_import_ui.deselect_all": {"EN": "Deselect All", "ZH": "取消全选"},
    "mhrs.batch_import_ui.selected_count": {
        "EN": "{enabled}/{total} selected", "ZH": "已选 {enabled}/{total}"},
}
