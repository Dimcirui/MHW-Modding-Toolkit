import bpy
import os

from ...core.i18n import T
from ...core.mdf_tex_processor_base import (
    PBR_TYPES, PBR_TYPE_LABELS, PBR_CHANNEL_SELECTABLE,
)
from .mrl3_tex_processor import MHWI_PBR_SLOT_TYPES, MHWI_NULL_TEX

# MHWI 无独立 AO 槽位，AO 应在 DCC 中预先烘焙到 Albedo
MHWI_PBR_DISPLAY_TYPES = [t for t in PBR_TYPES if t != 'ao']

PROCESSOR_WINDOW_WIDTH = 660


class MHWI_OT_Mrl3TexProcessorDialog(bpy.types.Operator):
    bl_idname  = "mhwi.mrl3_tex_processor_dialog"
    bl_label   = "MRL3 + Tex Processor"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        return T("mhwi.mrl3_tex_processor_ui.dialog_desc")

    def invoke(self, context, event):  # noqa: ARG002
        settings = context.scene.mhwi_mrl3_tex_processor
        col = settings.mrl3_collection
        # Always refresh on open -- see core/mdf_tex_processor_ui_base.py's
        # invoke() for why this must not be conditional on matching the last
        # loaded collection.
        if col:
            bpy.ops.mhwi.mrl3_tex_refresh()
        return context.window_manager.invoke_props_dialog(
            self, width=PROCESSOR_WINDOW_WIDTH)

    def execute(self, context):  # noqa: ARG002
        bpy.ops.mhwi.mrl3_tex_process()
        return {'FINISHED'}

    def draw(self, context):
        layout   = self.layout
        scene    = context.scene
        settings = scene.mhwi_mrl3_tex_processor

        # ── Collection + Refresh ──
        row = layout.row(align=True)
        row.prop(settings, "mrl3_collection", text=T("mhwi.mrl3_tex_processor_ui.mrl3_collection_label"))
        row.operator("mhwi.mrl3_tex_refresh", text="", icon='FILE_REFRESH')

        # ── Mod Root ──
        row = layout.row(align=True)
        row.operator("mhwi.set_natives_root", text="Mod Root", icon='FILEBROWSER')
        natives_root = scene.get("mhwi_natives_root", "")
        if natives_root:
            parts = natives_root.replace("\\", "/").rstrip("/").split("/")
            short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
            row.label(text=f".../{short}")
        else:
            row.label(text=T("mhwi.batch_import_ui.not_set"), icon='ERROR')

        # ── Base Path ──
        row = layout.row(align=True)
        row.label(text="nativePC/")
        row.prop(settings, "texture_base_path", text="")
        if not settings.texture_base_path.strip():
            layout.label(text=f"    {T('mhwi.mrl3_tex_processor_ui.base_path_example')}", icon='INFO')

        layout.prop(settings, "global_disable_mipmaps",
                    text=T("core.mdf_generator_base.global_disable_mipmaps"))
        grade_row = layout.row(align=True)
        grade_row.label(text=T("core.color_grade.label"))
        grade_row.prop(settings, "global_color_grade", text="")

        if not settings.materials:
            layout.separator()
            layout.label(text=T("mhwi.mrl3_tex_processor_ui.select_mrl3_then_refresh"), icon='INFO')
            return

        layout.separator()
        has_clipboard = bool(settings.clipboard_json)

        for mi, mat in enumerate(settings.materials):
            box = layout.box()

            # Material header row
            header = box.row(align=False)
            header.prop(mat, "expanded", text="",
                        icon='TRIA_DOWN' if mat.expanded else 'TRIA_RIGHT',
                        emboss=False)
            header.label(text=mat.material_name, icon='MATERIAL')
            op_copy           = header.operator("mhwi.mrl3_tex_copy_material",
                                                text="", icon='COPYDOWN')
            op_copy.mat_index = mi
            paste_row         = header.row(align=True)
            paste_row.enabled = has_clipboard
            op_paste           = paste_row.operator("mhwi.mrl3_tex_paste_material",
                                                    text="", icon='PASTEDOWN')
            op_paste.mat_index = mi

            if not mat.expanded:
                continue

            # ── PBR inputs ──
            pbr_split = box.split(factor=0.03)
            pbr_split.column()
            pbr_col = pbr_split.column()

            pbr_header = pbr_col.row(align=False)
            pbr_header.prop(mat, "pbr_expanded", text="",
                            icon='TRIA_DOWN' if mat.pbr_expanded else 'TRIA_RIGHT',
                            emboss=False)
            pbr_header.label(text="PBR Input", icon='NODE_COMPOSITING')

            if mat.pbr_expanded:
                pbr_box = pbr_col.box()
                for pt in MHWI_PBR_DISPLAY_TYPES:
                    row     = pbr_box.row(align=True)
                    row.label(text=PBR_TYPE_LABELS[pt])
                    cur     = getattr(mat.pbr, pt)
                    pick_op = row.operator(
                        "mhwi.mrl3_tex_pick_pbr",
                        text=os.path.basename(bpy.path.abspath(cur)) if cur else "--",
                        icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
                    )
                    pick_op.mat_index = mi
                    pick_op.pbr_type  = pt
                    if cur:
                        clr_op            = row.operator("mhwi.mrl3_tex_clear_pbr",
                                                         text="", icon='X')
                        clr_op.mat_index  = mi
                        clr_op.pbr_type   = pt
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
            opt_row.prop(mat, "skip_textures",
                         text=T("core.mdf_tex_processor_base.skip_textures_label"))

            # ── Texture slots ──
            box.label(text="Texture Slots", icon='RENDERLAYERS')
            for si, slot in enumerate(mat.slots):
                is_pbr = slot.texture_type in MHWI_PBR_SLOT_TYPES
                row    = box.row(align=True)
                row.label(text=slot.texture_type, icon='TEXTURE_DATA')
                row.prop(slot, "mode", text="")

                if slot.mode == 'COMPOSE' and not is_pbr:
                    row.label(text=f"→ {T('mhwi.mrl3_tex_processor_ui.use_direct_instead')}", icon='ERROR')

                elif slot.mode == 'DIRECT':
                    cur     = slot.direct_image
                    pick_op = row.operator(
                        "mhwi.mrl3_tex_pick_direct",
                        text=os.path.basename(bpy.path.abspath(cur)) if cur else "--",
                        icon='FILEBROWSER' if not cur else 'IMAGE_DATA',
                    )
                    pick_op.mat_index  = mi
                    pick_op.slot_index = si
                    if cur:
                        clr_op            = row.operator("mhwi.mrl3_tex_clear_direct",
                                                         text="", icon='X')
                        clr_op.mat_index  = mi
                        clr_op.slot_index = si

                elif slot.mode == 'DEFAULT':
                    null_val = MHWI_NULL_TEX.get(slot.texture_type, "")
                    label    = (null_val.replace('\\', '/').split('/')[-1] if null_val
                                else T("mhwi.mrl3_tex_processor_ui.no_default"))
                    row.label(text=f"→ {label}", icon='LINKED')

                elif slot.mode == 'SKIP' and slot.original_path:
                    stem = slot.original_path.replace('\\', '/').split('/')[-1]
                    row.label(text=stem, icon='LOOP_BACK')


classes = [MHWI_OT_Mrl3TexProcessorDialog]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
