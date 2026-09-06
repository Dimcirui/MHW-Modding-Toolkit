import bpy
import os

from .i18n import T
from .mdf_tex_processor_base import (
    PBR_TYPES, PBR_TYPE_LABELS, PBR_CHANNEL_SELECTABLE,
    BASE_COMMON_SLOT_TYPES, BASE_NULL_TEX_BY_TYPE,
)
from .slot_sources import find_shader_slot_supplies

PROCESSOR_WINDOW_WIDTH = 660

# These two PBR types only exist because a handful of RE4/RE9/MHWS packed-shader
# slots genuinely carry them -- MHWI/MHRS materials, and any material with no
# packed shader at all, have no way to supply either one. Showing the row
# regardless would just offer a manual picker with nothing real behind it, so
# it is gated on whichever game slots the bound material's own packed shader
# (if any) reports supplying -- see core.shader_pack.SLOT_SUPPLIES_KEY.
_CONDITIONAL_PBR_TYPES = {'cavity', 'translucency'}


def _supplied_pbr_types(material_name):
    mat = bpy.data.materials.get(material_name)
    if mat is None:
        return set()
    out = set()
    for pbr_types in find_shader_slot_supplies(mat).values():
        out.update(pbr_types)
    return out


class MdfTexDialogBase(bpy.types.Operator):
    """RE Engine MDF2 + Tex semi-auto texture processor"""
    bl_label   = "MDF2 + Tex Processor"
    bl_options = {'REGISTER'}

    # ── Game-specific class variables (override in subclasses) ─────────────────
    _game_prefix       = ""                    # e.g. "mhws" or "re9"
    _settings_attr     = ""                    # Scene attribute name
    _natives_root_key  = ""                    # Scene custom-property key
    _root_label        = "Mod Root"            # Label on the root picker button
    _path_prefix_label = "natives/STM/Art/"   # Label before the base-path field
    _path_hint         = "例：Author/Character/"
    _common_slot_types = BASE_COMMON_SLOT_TYPES
    _null_tex_by_type  = BASE_NULL_TEX_BY_TYPE

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def invoke(self, context, event):
        cls      = type(self)
        settings = getattr(context.scene, cls._settings_attr)
        col = settings.mdf_collection
        # Always refresh on open, not just when col matches what was loaded
        # last time -- _do_refresh already handles both "same collection
        # again" (preserves the in-memory config) and "switched collections"
        # (saves the old one's state, restores the new one's) safely, so
        # there is no correctness reason to skip it; skipping it just left a
        # stale materials list on screen until the user clicked refresh
        # themselves.
        if col:
            getattr(bpy.ops, cls._game_prefix).mdf_tex_refresh()
        return context.window_manager.invoke_props_dialog(
            self, width=PROCESSOR_WINDOW_WIDTH)

    def execute(self, context):
        getattr(getattr(bpy.ops, type(self)._game_prefix), 'mdf_tex_process')()
        return {'FINISHED'}

    # ── Drawing ────────────────────────────────────────────────────────────────

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        cls      = type(self)
        settings = getattr(scene, cls._settings_attr)
        pfx      = cls._game_prefix

        # Header
        row = layout.row(align=True)
        row.prop(settings, "mdf_collection", text="MDF Collection")
        row.operator(f"{pfx}.mdf_tex_refresh", text="", icon='FILE_REFRESH')

        row = layout.row(align=True)
        row.operator(f"{pfx}.set_natives_root",
                     text=cls._root_label, icon='FILEBROWSER')
        natives_root = scene.get(cls._natives_root_key, "")
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text="Not set", icon='ERROR')

        row = layout.row(align=True)
        row.label(text=cls._path_prefix_label)
        row.prop(settings, "texture_base_path", text="")

        # Global, not per-material: whether a slot's normal is octahedral is a
        # property of how the whole texture set was authored, not of one entry.
        if hasattr(settings, "octahedral_normals"):
            layout.prop(settings, "octahedral_normals",
                        text=T("core.octahedral_normals.label"))
        if not settings.texture_base_path.strip():
            hint = layout.row()
            hint.label(text=f"    {cls._path_hint}", icon='INFO')

        layout.prop(settings, "global_disable_mipmaps",
                    text=T("core.mdf_generator_base.global_disable_mipmaps"))
        grade_row = layout.row(align=True)
        grade_row.label(text=T("core.color_grade.label"))
        grade_row.prop(settings, "global_color_grade", text="")

        if not settings.materials:
            layout.separator()
            layout.label(text="Select MDF collection and click refresh", icon='INFO')
            return

        layout.separator()

        has_clipboard = bool(settings.clipboard_json)

        for mi, mat in enumerate(settings.materials):
            box = layout.box()

            header = box.row(align=False)
            expand_icon = 'TRIA_DOWN' if mat.expanded else 'TRIA_RIGHT'
            header.prop(mat, "expanded", text="", icon=expand_icon, emboss=False)
            header.label(text=mat.material_name, icon='MATERIAL')

            op_copy = header.operator(f"{pfx}.mdf_tex_copy_material",
                                      text="", icon='COPYDOWN')
            op_copy.mat_index = mi

            paste_row = header.row(align=True)
            paste_row.enabled = has_clipboard
            op_paste = paste_row.operator(f"{pfx}.mdf_tex_paste_material",
                                          text="", icon='PASTEDOWN')
            op_paste.mat_index = mi

            if not mat.expanded:
                continue

            # PBR inputs section — indented under material header
            pbr_split = box.split(factor=0.03)
            pbr_split.column()
            pbr_col = pbr_split.column()

            pbr_header = pbr_col.row(align=False)
            pbr_icon = 'TRIA_DOWN' if mat.pbr_expanded else 'TRIA_RIGHT'
            pbr_header.prop(mat, "pbr_expanded", text="", icon=pbr_icon, emboss=False)
            pbr_header.label(text="PBR Input", icon='NODE_COMPOSITING')

            if mat.pbr_expanded:
                pbr_box = pbr_col.box()
                slot_supplies = _supplied_pbr_types(mat.material_name)
                for pt in PBR_TYPES:
                    if pt in _CONDITIONAL_PBR_TYPES and pt not in slot_supplies:
                        continue
                    row = pbr_box.row(align=True)
                    row.label(text=PBR_TYPE_LABELS[pt])
                    cur = getattr(mat.pbr, pt)
                    pick_op = row.operator(
                        f"{pfx}.mdf_tex_pick_pbr",
                        text=os.path.basename(bpy.path.abspath(cur)) if cur else "--",
                        icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
                    )
                    pick_op.mat_index = mi
                    pick_op.pbr_type  = pt
                    if cur:
                        clr_op = row.operator(f"{pfx}.mdf_tex_clear_pbr",
                                              text="", icon='X')
                        clr_op.mat_index = mi
                        clr_op.pbr_type  = pt
                    if pt == 'normal' and cur:
                        row.prop(mat.pbr, "normal_flip_g",
                                 text="GL>DX", icon='LOOP_BACK', toggle=True)
                    if pt in PBR_CHANNEL_SELECTABLE and cur:
                        ch_sub = row.row(align=True)
                        ch_sub.scale_x = 0.35
                        for ch_val in ('R', 'G', 'B', 'A'):
                            ch_sub.prop_enum(mat.pbr, f"{pt}_ch", ch_val)
                        inv_sub = row.row(align=True)
                        inv_sub.scale_x = 0.4
                        inv_sub.prop(mat.pbr, f"{pt}_inv", text="Inv", toggle=True)

            if not mat.slots:
                continue

            # Per-material texture options
            opt_row = box.row(align=True)
            opt_row.prop(mat, "generate_mipmaps",
                        text=T("core.mdf_tex_processor_base.generate_mipmaps_label"))
            if mat.generate_mipmaps:
                opt_row.prop(mat, "mipmap_strategy", text="")
            opt_row.prop(mat, "skip_textures",
                        text=T("core.mdf_tex_processor_base.skip_textures_label"))

            common_slots = [(si, s) for si, s in enumerate(mat.slots)
                            if s.texture_type in cls._common_slot_types]
            other_slots  = [(si, s) for si, s in enumerate(mat.slots)
                            if s.texture_type not in cls._common_slot_types]

            if common_slots:
                box.label(text="Common Textures", icon='RENDERLAYERS')
                self._draw_slots(box, common_slots, mi)

            if other_slots:
                other_header = box.row(align=False)
                other_icon = 'TRIA_DOWN' if mat.other_expanded else 'TRIA_RIGHT'
                other_header.prop(mat, "other_expanded", text="",
                                  icon=other_icon, emboss=False)
                other_header.label(text="Other Textures", icon='RENDERLAYERS')
                if mat.other_expanded:
                    self._draw_slots(box, other_slots, mi)

    def _draw_slots(self, box, indexed_slots, mi):
        cls = type(self)
        pfx = cls._game_prefix
        for si, slot in indexed_slots:
            row = box.row(align=True)
            row.label(text=slot.texture_type, icon='TEXTURE_DATA')
            row.prop(slot, "mode", text="")

            if slot.mode == 'DIRECT':
                cur = slot.direct_image
                pick_op = row.operator(
                    f"{pfx}.mdf_tex_pick_direct",
                    text=os.path.basename(bpy.path.abspath(cur)) if cur else "--",
                    icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
                )
                pick_op.mat_index  = mi
                pick_op.slot_index = si
                if cur:
                    clr_op = row.operator(f"{pfx}.mdf_tex_clear_direct",
                                          text="", icon='X')
                    clr_op.mat_index  = mi
                    clr_op.slot_index = si

            elif slot.mode == 'DEFAULT':
                null_rel = cls._null_tex_by_type.get(slot.texture_type)
                if null_rel:
                    row.label(text=f"-> {null_rel.split('/')[-1]}", icon='LINKED')
                else:
                    row.label(text="(no default null texture)", icon='ERROR')

            elif slot.mode == 'SKIP' and slot.original_path:
                row.label(
                    text=slot.original_path.split('/')[-1],
                    icon='LOOP_BACK',
                )
