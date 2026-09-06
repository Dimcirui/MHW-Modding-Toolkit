import bpy
import json
import os
import re
import shutil
import subprocess
import sys
from .i18n import T
from . import ui_config, bone_mapper
from .bone_mapper import BoneMapManager, STANDARD_BONE_NAMES

# === 初始化/刷新列表 ===
class MODDER_OT_InitEditor(bpy.types.Operator):
    bl_idname = "modder.init_editor"
    bl_label = "Initialize / Refresh List"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.init_editor_desc")

    def execute(self, context):
        settings = context.scene.mhw_preset_editor
        settings.slots.clear()
        # 编辑器恒列全部槽位（含辅助骨）：这里是**编写**预设的地方，能不能填与
        # 运行时勾没勾"忽略辅助骨"无关，把槽位藏起来只会让人以为插件不支持。
        for std_key in bone_mapper.standard_keys(True):
            item = settings.slots.add()
            item.std_name = std_key
            item.ui_name = std_key
        self.report({'INFO'}, T("core.editor_ops.editor_reset"))
        return {'FINISHED'}

# === 拾取骨骼 ===
class MODDER_OT_PickBone(bpy.types.Operator):
    bl_idname = "modder.pick_bone"
    bl_label = "Pick"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.pick_bone_desc")

    slot_index: bpy.props.IntProperty()
    is_aux: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        settings = context.scene.mhw_preset_editor
        slot = settings.slots[self.slot_index]

        selected_names = []
        active_name = ""

        obj = context.active_object
        mode = context.mode

        # --- 路径 1：骨架 Pose / Edit 模式（选中骨骼）---
        if obj and obj.type == 'ARMATURE' and mode == 'POSE':
            selected_names = [b.name for b in (context.selected_pose_bones or [])]
            if context.active_pose_bone:
                active_name = context.active_pose_bone.name

        elif obj and obj.type == 'ARMATURE' and mode in ('EDIT', 'EDIT_ARMATURE'):
            selected_names = [b.name for b in (context.selected_editable_bones or [])]
            if context.active_bone:
                active_name = context.active_bone.name

        # --- 路径 2：Mesh 权重绘制 / 网格编辑模式（激活顶点组 → 对应骨骼）---
        elif obj and obj.type == 'MESH' and mode in ('PAINT_WEIGHT', 'EDIT_MESH', 'EDIT'):
            vg = obj.vertex_groups.active
            if vg is None:
                self.report({'WARNING'}, T("core.editor_ops.no_active_vgroup"))
                return {'CANCELLED'}
            arm_obj = obj.find_armature()
            if arm_obj is None:
                self.report({'WARNING'}, T("core.editor_ops.no_bound_armature"))
                return {'CANCELLED'}
            if vg.name not in arm_obj.data.bones:
                self.report({'WARNING'},
                            T("core.editor_ops.vgroup_no_matching_bone").format(name=vg.name))
                return {'CANCELLED'}
            active_name = vg.name
            selected_names = [vg.name]

        else:
            self.report({'WARNING'}, T("core.editor_ops.enter_pose_or_edit_mode"))
            return {'CANCELLED'}

        if not selected_names and not active_name:
            self.report({'WARNING'}, T("core.editor_ops.no_bones_selected"))
            return {'CANCELLED'}

        if self.is_aux:
            added_count = 0
            for name in selected_names:
                if name == slot.source_bone_name:
                    continue
                if any(aux.name == name for aux in slot.aux_bones):
                    continue
                new_aux = slot.aux_bones.add()
                new_aux.name = name
                added_count += 1
            if added_count > 0:
                slot.is_expanded = True
                self.report({'INFO'}, T("core.editor_ops.batch_added_aux_bones").format(n=added_count))
            else:
                self.report({'WARNING'}, T("core.editor_ops.no_new_bones_added"))
        else:
            if active_name:
                slot.source_bone_name = active_name
                for i, aux in enumerate(slot.aux_bones):
                    if aux.name == active_name:
                        slot.aux_bones.remove(i)
                        break
            else:
                self.report({'WARNING'}, T("core.editor_ops.cannot_determine_active_bone"))
                return {'CANCELLED'}

        return {'FINISHED'}

# === 清除操作 ===
class MODDER_OT_ClearSlot(bpy.types.Operator):
    bl_idname = "modder.clear_slot"
    bl_label = "Clear"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.clear_slot_desc")

    slot_index: bpy.props.IntProperty()
    target: bpy.props.StringProperty()

    def execute(self, context):
        slot = context.scene.mhw_preset_editor.slots[self.slot_index]
        if self.target == 'MAIN':
            slot.source_bone_name = ""
        else:
            idx = -1
            for i, aux in enumerate(slot.aux_bones):
                if aux.name == self.target:
                    idx = i
                    break
            if idx != -1:
                slot.aux_bones.remove(idx)
        return {'FINISHED'}

# === 镜像功能 ===
class MODDER_OT_MirrorMapping(bpy.types.Operator):
    bl_idname = "modder.mirror_mapping"
    bl_label = "Mirror Left -> Right"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.mirror_mapping_desc")

    def execute(self, context):
        slots = context.scene.mhw_preset_editor.slots
        slot_map = {s.std_name: s for s in slots}

        def get_mirrored_name(name):
            if not name: return None
            new_name = name
            # Handle L_/l_ prefix style (RE Engine: L_BoneName, HD2: l_bonename)
            if new_name.startswith("L_"):
                return "R_" + new_name[2:]
            if new_name.startswith("l_"):
                return "r_" + new_name[2:]
            basic_replacements = [
                ("_L_", "_R_"), ("_L.", "_R."), ("_L", "_R"),
                (".L", ".R"), (" L ", " R "),
                ("Left", "Right"), ("left", "right"),
                ("Lf", "Rt"), ("(L)", "(R)")
            ]
            for old, new in basic_replacements:
                if old in new_name:
                    return new_name.replace(old, new)
            new_name = re.sub(r'(^|[\d])L(?=[A-Z])', r'\1R', new_name)
            return new_name if new_name != name else None

        count = 0
        for l_key in slot_map:
            if not l_key.endswith("_L"):
                continue
            r_key = l_key[:-2] + "_R"
            if r_key not in slot_map:
                continue
            l_slot = slot_map[l_key]
            r_slot = slot_map[r_key]
            if l_slot.source_bone_name:
                mirrored = get_mirrored_name(l_slot.source_bone_name)
                if mirrored:
                    r_slot.source_bone_name = mirrored
                    count += 1
            if len(l_slot.aux_bones) > 0:
                r_slot.aux_bones.clear()
                r_slot.is_expanded = l_slot.is_expanded
                for l_aux in l_slot.aux_bones:
                    mirrored_aux = get_mirrored_name(l_aux.name)
                    if mirrored_aux:
                        new_item = r_slot.aux_bones.add()
                        new_item.name = mirrored_aux
                        count += 1

        self.report({'INFO'}, T("core.editor_ops.mirror_done").format(n=count))
        return {'FINISHED'}

# === 工具函数 ===
def _get_addon_dir():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def _get_preset_dir(is_x):
    subdir = os.path.join("presets", "import" if is_x else "bone")
    return os.path.join(_get_addon_dir(), "assets", subdir)

def _get_selected_filename(context, is_x):
    suite = context.scene.mhw_suite_settings
    raw = suite.import_preset_enum if is_x else suite.target_preset_enum
    if not raw or raw in ("NONE", "AUTO"):
        return None
    return os.path.basename(raw)

# === 保存预设 ===
class MODDER_OT_SaveXPreset(bpy.types.Operator):
    bl_idname = "modder.save_x_preset"
    bl_label = "Save Preset"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.save_preset_desc")

    def execute(self, context):
        settings = context.scene.mhw_preset_editor
        is_x = settings.edit_mode == 'X'

        target_dir = _get_preset_dir(is_x)
        filename = settings.new_preset_name + ".json"
        for char in '<>:"/\\|?*':
            filename = filename.replace(char, '')
        filepath = os.path.join(target_dir, filename)

        # 若文件已存在，以它为基础更新，保留编辑器不认识的顶级字段（如 exclude）
        # 以及每个 mapping 条目中 main 列表的多候选
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    final_data = json.load(f)
            except Exception:
                final_data = {}
        else:
            final_data = {}

        # 更新 preset_info（保留原有其他字段）
        preset_type = "X_PRESET" if is_x else "Y_PRESET"
        final_data.setdefault("preset_info", {}).update({
            "name": settings.new_preset_name,
            "type": preset_type,
            "version": "2.0",
        })

        existing_mappings = final_data.get("mappings", {})
        fill_count = 0
        for slot in settings.slots:
            if not slot.source_bone_name and len(slot.aux_bones) == 0:
                continue
            orig = existing_mappings.get(slot.std_name, {})
            orig_main = orig.get("main", [])
            # 保留 main[1:] 多候选，只更新 [0]
            if slot.source_bone_name:
                new_main = [slot.source_bone_name] + orig_main[1:]
            else:
                new_main = orig_main[1:]  # 清空了第一候选，其余保留
            existing_mappings[slot.std_name] = {
                "main": new_main,
                "aux": [aux.name for aux in slot.aux_bones],
            }
            fill_count += 1

        if fill_count == 0:
            self.report({'ERROR'}, T("core.editor_ops.list_empty_not_saved"))
            return {'CANCELLED'}

        final_data["mappings"] = existing_mappings

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            self.report({'INFO'}, T("core.editor_ops.preset_saved").format(
                kind=('X' if is_x else 'Y'), filename=filename))
        except Exception as e:
            self.report({'ERROR'}, T("core.editor_ops.save_failed").format(err=str(e)))
            return {'CANCELLED'}

        return {'FINISHED'}

# === 读取预设 ===
class MODDER_OT_LoadXPreset(bpy.types.Operator):
    bl_idname = "modder.load_x_preset"
    bl_label = "Load Preset"
    bl_options = {'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.load_preset_desc")

    def execute(self, context):
        editor = context.scene.mhw_preset_editor
        is_x = editor.edit_mode == 'X'

        real_filename = _get_selected_filename(context, is_x)
        if not real_filename:
            self.report({'WARNING'}, T("core.editor_ops.no_preset_selected"))
            return {'CANCELLED'}

        mapper = BoneMapManager()
        if not mapper.load_preset(real_filename, is_import_x=is_x):
            self.report({'ERROR'}, T("core.editor_ops.cannot_load_file").format(name=real_filename))
            return {'CANCELLED'}

        bpy.ops.modder.init_editor()
        slot_map = {s.std_name: s for s in editor.slots}

        loaded_count = 0
        for std_key, entry in mapper.mapping_data.items():
            if std_key in slot_map:
                slot = slot_map[std_key]
                mains = entry.get("main", [])
                if mains:
                    slot.source_bone_name = mains[0]
                for aux_name in entry.get("aux", []):
                    new_aux = slot.aux_bones.add()
                    new_aux.name = aux_name
                if mains or entry.get("aux"):
                    loaded_count += 1

        clean_name = real_filename.rsplit('.', 1)[0]
        editor.new_preset_name = clean_name
        display_name = mapper.preset_info.get('name', clean_name)
        self.report({'INFO'}, T("core.editor_ops.preset_loaded").format(
            kind=('X' if is_x else 'Y'), name=display_name, n=loaded_count))
        return {'FINISHED'}

# === 删除预设 ===
class MODDER_OT_DeleteXPreset(bpy.types.Operator):
    bl_idname = "modder.delete_x_preset"
    bl_label = "Delete Preset"
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.delete_preset_desc")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        editor = context.scene.mhw_preset_editor
        is_x = editor.edit_mode == 'X'

        real_filename = _get_selected_filename(context, is_x)
        if not real_filename:
            return {'CANCELLED'}

        filepath = os.path.join(_get_preset_dir(is_x), real_filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                suite = context.scene.mhw_suite_settings
                if is_x:
                    suite.import_preset_enum = "NONE"
                else:
                    suite.target_preset_enum = "NONE"
                self.report({'INFO'}, T("core.editor_ops.deleted").format(name=real_filename))
            except Exception as e:
                self.report({'ERROR'}, T("core.editor_ops.delete_failed").format(err=e))
        else:
            self.report({'ERROR'}, T("core.editor_ops.file_not_exist"))

        return {'FINISHED'}

# === 打开预设文件夹 ===
class MODDER_OT_OpenPresetFolder(bpy.types.Operator):
    bl_idname = "modder.open_preset_folder"
    bl_label = "Open Preset Folder"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.open_folder_desc")

    def execute(self, context):
        editor = context.scene.mhw_preset_editor
        is_x = editor.edit_mode == 'X'
        folder = _get_preset_dir(is_x)

        if not os.path.isdir(folder):
            self.report({'ERROR'}, T("core.editor_ops.folder_not_exist").format(path=folder))
            return {'CANCELLED'}

        if sys.platform == 'win32':
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', folder])
        else:
            subprocess.Popen(['xdg-open', folder])

        return {'FINISHED'}

# === 转换预设（X→Y 或 Y→X，复制方式）===
class MODDER_OT_ConvertPreset(bpy.types.Operator):
    bl_idname = "modder.convert_preset"
    bl_label = "Convert Preset"

    @classmethod
    def description(cls, context, properties):
        return T("core.editor_ops.convert_preset_desc")

    def execute(self, context):
        editor = context.scene.mhw_preset_editor
        is_x = editor.edit_mode == 'X'

        src_filename = _get_selected_filename(context, is_x)
        if not src_filename:
            self.report({'WARNING'}, T("core.editor_ops.no_preset_selected"))
            return {'CANCELLED'}

        src_path = os.path.join(_get_preset_dir(is_x), src_filename)
        if not os.path.exists(src_path):
            self.report({'ERROR'}, T("core.editor_ops.source_file_not_exist").format(name=src_filename))
            return {'CANCELLED'}

        # 生成目标文件名：去掉 .json，加上转换标记，再加 .json
        src_stem = os.path.splitext(src_filename)[0]
        mark = "(X转换)" if is_x else "(Y转换)"
        dst_filename = src_stem + mark + ".json"
        dst_dir = _get_preset_dir(not is_x)  # 目标是另一类型目录
        dst_path = os.path.join(dst_dir, dst_filename)

        if os.path.exists(dst_path):
            self.report({'WARNING'}, T("core.editor_ops.target_file_exists").format(name=dst_filename))
            return {'CANCELLED'}

        try:
            with open(src_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 修改 preset_info
            data['preset_info']['type'] = "Y_PRESET" if is_x else "X_PRESET"
            data['preset_info']['name'] = src_stem + mark

            with open(dst_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            direction = "X → Y" if is_x else "Y → X"
            self.report({'INFO'}, T("core.editor_ops.copied").format(direction=direction, filename=dst_filename))
        except Exception as e:
            self.report({'ERROR'}, T("core.editor_ops.convert_failed").format(err=e))
            return {'CANCELLED'}

        return {'FINISHED'}


classes = [
    MODDER_OT_InitEditor,
    MODDER_OT_PickBone,
    MODDER_OT_ClearSlot,
    MODDER_OT_MirrorMapping,
    MODDER_OT_SaveXPreset,
    MODDER_OT_LoadXPreset,
    MODDER_OT_DeleteXPreset,
    MODDER_OT_OpenPresetFolder,
    MODDER_OT_ConvertPreset,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
