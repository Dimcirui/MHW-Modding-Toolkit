import bpy
import os
import re
from ..core.i18n import T, draw_language_toggle, get_lang
from ..core import bone_utils, ui_config
from . import game_sections
from ..core.mdf_generator_base import MHW_OT_SetChannelSize, MHW_OT_SetShaderSource
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.pose_ops import get_pose_presets_callback
from ..games.re9.batch_export import get_schemes_callback
from ..games.re4.batch_export import get_schemes_callback as get_re4_schemes_callback
from ..games.mhws.batch_export import get_mhws_schemes_callback, get_mhws_armor_callback, get_mhws_variants
from ..games.mhrs.batch_export import get_mhrs_schemes_callback, get_mhrs_armor_callback, get_mhrs_genders
from ..games.mhwi.batch_export import (
    get_mhwi_armor_sets_callback,
    get_mhwi_hr_armor_callback,
    get_mhwi_mr_armor_callback,
    get_mhwi_sp_armor_callback,
)
from ..games.mhwi.weapon_data import get_mhwi_weapon_sets_callback, get_weapon_type_items
from ..core.bone_mapper import BoneMapManager

# Mapping detail preview cache: {(x_preset, y_preset): (mapper_x, mapper_y)}
_mapping_detail_cache = {}


def _align_mode_items(self, context):
    return [
        ('POS_ONLY', T("ui.main_panel.align_mode_pos_only"), T("ui.main_panel.align_mode_pos_only_desc")),
        ('POS_ROLL', T("ui.main_panel.align_mode_pos_roll"), T("ui.main_panel.align_mode_pos_roll_desc")),
        ('FULL',     T("ui.main_panel.align_mode_full"),     T("ui.main_panel.align_mode_full_desc")),
    ]


#: Persistent backing for the enum below -- the trap every dynamic enum in this
#: addon documents: Blender's C side keeps the pointers, so a list built fresh
#: inside the callback is freed the moment Python drops it.
_skeleton_mode_item_cache = []


def _mhrs_skeleton_mode_items(self, context):
    # Four-tuples: an ENUM_FLAG enum needs an explicit power-of-two value per item.
    _skeleton_mode_item_cache.clear()
    _skeleton_mode_item_cache.extend([
        ('SHADOW', T("ui.main_panel.mhrs_skel_shadow"), T("ui.main_panel.mhrs_skel_shadow_desc"), 1),
        ('LUA',    T("ui.main_panel.mhrs_skel_lua"),    T("ui.main_panel.mhrs_skel_lua_desc"),    2),
    ])
    return _skeleton_mode_item_cache


#: Where the previous selection is remembered, so the update below can tell which
#: of two lit buttons was the one just clicked.
_SKEL_PREV_KEY = "_mhrs_skeleton_mode_prev"


def _mhrs_skeleton_mode_exclusive(self, context):
    """Keep at most one scheme lit.

    A plain EnumProperty cannot express "neither" -- it always holds a value --
    so this is an ENUM_FLAG (a set, which may be empty) narrowed back down to a
    radio button by hand.  That buys the two things a plain enum could not have
    together: nothing selected by default, and clicking the lit button again to
    turn it back off.

    Re-assigning inside an update callback re-enters this function once; the
    second pass sees a single item and only records it, so it terminates.
    """
    current = set(self.mhrs_skeleton_mode)
    if len(current) > 1:
        just_clicked = current - set(self.get(_SKEL_PREV_KEY, []))
        self.mhrs_skeleton_mode = just_clicked or {next(iter(current))}
        return
    self[_SKEL_PREV_KEY] = list(current)


def _mhwi_export_mode_items(self, context):
    return [
        ('ARMOR',  T("ui.main_panel.mhwi_mode_armor"),  T("ui.main_panel.mhwi_mode_armor_desc")),
        ('WEAPON', T("ui.main_panel.mhwi_mode_weapon"), T("ui.main_panel.mhwi_mode_weapon_desc")),
    ]


def _mhwi_rank_tab_items(self, context):
    return [
        ('HR', T("ui.main_panel.mhwi_rank_hr"), T("ui.main_panel.mhwi_rank_hr_desc")),
        ('MR', T("ui.main_panel.mhwi_rank_mr"), T("ui.main_panel.mhwi_rank_mr_desc")),
        ('SP', T("ui.main_panel.mhwi_rank_sp"), T("ui.main_panel.mhwi_rank_sp_desc")),
    ]


def _mhwi_gender_items(self, context):
    return [
        ('F',    T("ui.main_panel.mhwi_gender_f"),    T("ui.main_panel.mhwi_gender_f_desc")),
        ('M',    T("ui.main_panel.mhwi_gender_m"),    T("ui.main_panel.mhwi_gender_m_desc")),
        ('BOTH', T("ui.main_panel.mhwi_gender_both"), T("ui.main_panel.mhwi_gender_both_desc")),
    ]


def _mhws_bs_bind_part_items(self, context):
    return [
        ("1", T("ui.main_panel.mhws_bind_part_helmet"), ""),
        ("2", T("ui.main_panel.mhws_bind_part_body"), ""),
    ]


# align_mode_override reused as the mode picker for same-kind (name-matched)
# alignment, which routes to MHW_OT_GeneralTools instead of the preset pipeline
_SAME_KIND_ALIGN_ACTION = {
    'POS_ONLY': 'ALIGN_POS',
    'POS_ROLL': 'ALIGN_POS_ROLL',
    'FULL':     'ALIGN_FULL',
}


class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # Top toggle row
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=False)
    show_mhws: bpy.props.BoolProperty(name="MHWS", default=False)
    show_mhrs: bpy.props.BoolProperty(name="MHRS", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)
    show_re9: bpy.props.BoolProperty(name="RE9", default=False)

    # Basic tools toggle
    show_basic_tools: bpy.props.BoolProperty(name="Basic Tools", default=True)

    # Universal converter toggle
    show_std_converter: bpy.props.BoolProperty(name="Universal Skeleton Conversion", default=True)
    show_skeleton_cleanup: bpy.props.BoolProperty(name="Skeleton Cleanup", default=False)
    show_physics_chain_tools: bpy.props.BoolProperty(name="Physics Chain Tools", default=False)

    # Collapses the converter down to a plain name-matched armature align
    same_kind_align: bpy.props.BoolProperty(
        name="Same-Kind Bone Align",
        description="Both armatures are already the same kind, so bones are matched by name and no preset is needed",
        default=False,
    )

    # Preset selection (X/Y) - used by the standard converter
    import_preset_enum: bpy.props.EnumProperty(
        name="Source Preset (X)",
        description="Select the skeleton structure of the imported model",
        items=get_import_presets_callback,
    )

    target_preset_enum: bpy.props.EnumProperty(
        name="Target Game (Y)",
        description="Select the target game to export to",
        items=get_target_presets_callback,
        update=lambda self, context: setattr(
            self, "align_mode_override", bone_utils.get_default_align_mode(self.target_preset_enum)
        ),
    )

    align_mode_override: bpy.props.EnumProperty(
        name="Align Mode",
        description="Bone alignment (Snap) mode; automatically syncs to the preset's default when the target game (Y) changes",
        items=_align_mode_items,
        default=0,
    )

    show_mapping_details: bpy.props.BoolProperty(name="Show Mapping Details", default=False)

    bone_view_mode: bpy.props.EnumProperty(
        items=[
            ('ALL',     '全显',    '显示所有骨骼'),
            ('BASE',    '仅基础骨', '隐藏物理骨，只显示预设基础骨'),
            ('PHYSICS', '仅物理骨', '隐藏基础骨，只显示物理骨'),
        ],
        default='ALL'
    )

    # Pose convert section
    show_pose_convert: bpy.props.BoolProperty(name="Pose Convert", default=False)

    # Pose-convert-only preset (independent of the standard converter's X/Y presets)
    pose_import_preset_enum: bpy.props.EnumProperty(
        name="Skeleton Preset",
        description="Preset used to recognize bone names",
        items=get_import_presets_callback,
    )

    # Saved pose record selection
    pose_preset_enum: bpy.props.EnumProperty(
        name="Pose Record",
        description="Select a saved pose matrix record",
        items=get_pose_presets_callback
    )

    # RE9 batch export scheme
    re9_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE9",
        items=get_schemes_callback
    )

    # MHWI batch export
    mhwi_export_mode: bpy.props.EnumProperty(
        name="Export Mode",
        items=_mhwi_export_mode_items,
        default=0,
    )
    mhwi_armor_sets_file: bpy.props.EnumProperty(
        name="Preset Group",
        description="Select an MHWI armor preset group JSON",
        items=get_mhwi_armor_sets_callback,
    )
    mhwi_weapon_sets_file: bpy.props.EnumProperty(
        name="Preset Group",
        description="Select an MHWI weapon preset group JSON",
        items=get_mhwi_weapon_sets_callback,
    )
    mhwi_weapon_type_tab: bpy.props.EnumProperty(
        name="Weapon Type",
        items=get_weapon_type_items,
    )
    mhwi_rank_tab: bpy.props.EnumProperty(
        name="Rank",
        items=_mhwi_rank_tab_items,
        default=0,
    )
    mhwi_gender: bpy.props.EnumProperty(
        name="Gender",
        items=_mhwi_gender_items,
        default=0,
    )
    mhwi_selected_hr_armor: bpy.props.EnumProperty(
        name="LR/HR Armor",
        description="Select the LR/HR armor to export",
        items=get_mhwi_hr_armor_callback,
    )
    mhwi_selected_mr_armor: bpy.props.EnumProperty(
        name="MR Armor",
        description="Select the MR armor to export",
        items=get_mhwi_mr_armor_callback,
    )
    mhwi_selected_sp_armor: bpy.props.EnumProperty(
        name="Full Transmog Set",
        description="Select the full transmog set to export",
        items=get_mhwi_sp_armor_callback,
    )
    mhwi_cleanup_before_export: bpy.props.BoolProperty(
        name="Clean Mesh Before Export",
        description="Before export, run on all bound mod3 collections: remove loose geometry, fix duplicate UVs, "
                     "clear zero-weight vertex groups, limit and normalize weights "
                     "(requires RE Mesh Editor; silently skipped if not installed)",
        default=True,
    )
    mhwi_confuse_before_export: bpy.props.BoolProperty(
        name="Anti-Plagiarism",
        description="Adds confusion content to mod3/mrl3 that doesn't affect normal use, but helps deter people "
                     "who repackage others' mods as their own",
        default=False,
    )
    mhwi_watermark_before_export: bpy.props.BoolProperty(
        name="Add Watermark Effect",
        description="Anti-reselling: adds a watermark effect that is almost only visible when changing equipment",
        default=False,
    )

    # MHWs batch export
    mhws_armor_scheme: bpy.props.EnumProperty(
        name="Armor Pack",
        description="Select an MHWs armor pack JSON",
        items=get_mhws_schemes_callback
    )
    mhws_armor_variant: bpy.props.EnumProperty(
        name="Set Variant",
        description="Select the set variant (male/female hunter x male/female set)",
        items=get_mhws_variants,
    )
    mhws_selected_armor: bpy.props.EnumProperty(
        name="Armor",
        description="Select the armor to export",
        items=get_mhws_armor_callback
    )

    # MHWs Bonesystem
    mhws_use_bonesystem: bpy.props.BoolProperty(
        name="Use Bonesystem",
        description="Also generate fbxskel.7 and BoneSystem JSON on export (requires the Bonesystem framework)",
        default=False,
    )
    mhws_fbxskel_name: bpy.props.StringProperty(
        name="FBXSkel Definition Name",
        description="Written to the JSON's FbxPath field, also used as the .fbxskel.7 filename (e.g. ch03_000_9000)",
    )
    mhws_bs_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="Armature",
        description="MHWs character armature used to generate the fbxskel",
    )
    mhws_bs_hide_face: bpy.props.BoolProperty(
        name="Hide Face",    default=True)
    mhws_bs_hide_hair: bpy.props.BoolProperty(
        name="Hide Hair",    default=True)
    mhws_bs_hide_slinger: bpy.props.BoolProperty(
        name="Hide Slinger",  default=True)
    mhws_bs_bind_face: bpy.props.BoolProperty(
        name="Bind Face",    default=True)
    mhws_bs_bind_part: bpy.props.EnumProperty(
        name="Bind Part",
        items=_mhws_bs_bind_part_items,
        default=0,
    )
    mhws_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=False,
    )
    mhws_triangulate_face: bpy.props.BoolProperty(
        name="Triangulate Face Mesh",
        description="Before export, temporarily add a Triangulate modifier to meshes weighted to the head bone. "
                     "RE Mesh Editor's exporter otherwise breaks face shading. The mesh data itself is not modified",
        default=False,
    )
    mhws_cleanup_before_export: bpy.props.BoolProperty(
        name="Clean Mesh Before Export",
        description="Before export, run on all bound mesh collections: remove loose geometry, fix duplicate UVs, "
                     "clear zero-weight vertex groups, limit and normalize weights (requires RE Mesh Editor)",
        default=True,
    )
    re9_triangulate_face: bpy.props.BoolProperty(
        name="Triangulate Face Mesh",
        description="Before export, temporarily add a Triangulate modifier to meshes weighted to the head bone. "
                     "RE Mesh Editor's exporter otherwise breaks face shading. The mesh data itself is not modified",
        default=False,
    )
    re9_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=True,
    )

    # MHRS batch export
    mhrs_armor_scheme: bpy.props.EnumProperty(
        name="Armor Pack",
        description="Select an MHRS armor pack JSON",
        items=get_mhrs_schemes_callback
    )
    mhrs_gender: bpy.props.EnumProperty(
        name="Gender",
        description="Select hunter gender",
        items=get_mhrs_genders,
    )
    mhrs_selected_armor: bpy.props.EnumProperty(
        name="Armor",
        description="Select the armor to export",
        items=get_mhrs_armor_callback
    )
    mhrs_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=False,
    )
    mhrs_triangulate_face: bpy.props.BoolProperty(
        name="Triangulate Face Mesh",
        description="Before export, temporarily add a Triangulate modifier to meshes weighted to the head bone. "
                     "RE Mesh Editor's exporter otherwise breaks face shading. The mesh data itself is not modified",
        default=False,
    )
    mhrs_cleanup_before_export: bpy.props.BoolProperty(
        name="Clean Mesh Before Export",
        description="Before export, run on all bound mesh collections: remove loose geometry, fix duplicate UVs, "
                     "clear zero-weight vertex groups, limit and normalize weights (requires RE Mesh Editor)",
        default=True,
    )
    #: How the armour's proportions reach the game.  One enum rather than two
    #: checkboxes because the two are mutually exclusive in the game, not merely
    #: by convention: both move the same joints, so enabling both applies the
    #: same offset twice.
    mhrs_skeleton_mode: bpy.props.EnumProperty(
        name="Skeleton Scheme",
        description="How this armor set's skeleton reaches the game",
        items=_mhrs_skeleton_mode_items,
        options={'ENUM_FLAG'},
        # No default=.  Blender rejects a set default when items is a callback
        # ("'default' can only be an integer when 'items' is a function"), and an
        # ENUM_FLAG with no default already starts as the empty set, which is
        # exactly "neither scheme chosen".
        update=_mhrs_skeleton_mode_exclusive,
    )
    mhrs_shadow_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        name="Source Armature",
        description="Armature this set's skeleton is read from; if left empty and only "
                     "one Mesh collection is bound this run, that collection's armature is used automatically",
    )

    # RE4 batch export
    re4_export_scheme: bpy.props.EnumProperty(
        name="Export Scheme",
        description="Select character export scheme for RE4",
        items=get_re4_schemes_callback
    )
    re4_triangulate_face: bpy.props.BoolProperty(
        name="Triangulate Face Mesh",
        description="Before export, temporarily add a Triangulate modifier to meshes weighted to the head bone. "
                     "RE Mesh Editor's exporter otherwise breaks face shading. The mesh data itself is not modified",
        default=False,
    )
    re4_use_blank_export: bpy.props.BoolProperty(
        name="Use Blank Model for Unselected",
        description="For slots with no collection selected, copy in the built-in blank file instead of skipping",
        default=True,
    )
    re4_use_fakebone: bpy.props.BoolProperty(
        name="Use Fake Head Method",
        description="Before exporting fbxskel, auto-generate body+finger End bones "
                     "(the native skeleton is specified by the preset's native_skeleton field)",
        default=False,
    )
    re4_use_body_arm: bpy.props.BoolProperty(
        name="Use Body Armature",
        description="Automatically get the armature from the body Mesh collection and align it to the native "
                     "skeleton, skipping manual fbxskel armature binding",
        default=False,
    )


class MHW_PT_MainPanel(bpy.types.Panel):
    bl_label = "MOD Toolkit"
    bl_idname = "MHW_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object

        draw_language_toggle(layout)
        layout.separator()

        # =========================================
        # 1. Top toggle row
        # =========================================
        row = layout.row(align=True)
        row.prop(settings, "show_mhwi", toggle=True, text="MHWI")
        row.prop(settings, "show_mhws", toggle=True, text="MHWS")
        row.prop(settings, "show_mhrs", toggle=True, text="MHRS")
        row.prop(settings, "show_re4", toggle=True, text="RE4")
        row.prop(settings, "show_re9", toggle=True, text="RE9")
        
        layout.separator()

        # =========================================
        # 2. Basic tools
        # =========================================
        basic_box = layout.box()
        row = basic_box.row()
        row.prop(settings, "show_basic_tools",
                 icon="TRIA_DOWN" if settings.show_basic_tools else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text=T("ui.main_panel.basic_tools_header"), icon='TOOL_SETTINGS')

        if settings.show_basic_tools:
            col = basic_box.column(align=True)

            # Bone-level merge on its own row; the two chain-level actions pair up below
            col.label(text=T("ui.main_panel.label_bone_merge"), icon='AUTOMERGE_ON')
            # Merging into the parent is the same kind of operation as merging into
            # the active bone, and needs no preset: the merge itself is preset-free,
            # and the chain_role refresh it does afterwards is already guarded.
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_merge_to_active")).action = 'MERGE_TO_ACTIVE'
            row.operator("modder.merge_into_parent", text=T("ui.main_panel.btn_merge_into_parent"), icon='SNAP_MIDPOINT')
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_simplify_chain")).action = 'SIMPLIFY_CHAIN'
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_merge_chains")).action = 'MERGE_CHAINS'

            col.separator(factor=0.8)
            col.label(text=T("ui.main_panel.label_bone_processing"), icon='BONE_DATA')
            row = col.row(align=True)
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_roll_zero")).action = 'ROLL_ZERO'
            row.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_mirror_x")).action = 'MIRROR_X'

            # NOTE: the armature-align group used to live here. It overlapped with
            # the standard converter's align action, so it now sits behind that
            # section's "Same-Kind Bone Align" toggle.

            col.separator(factor=0.8)
            col.label(text=T("ui.main_panel.label_mesh_processing"), icon='GROUP_VERTEX')
            row = col.row(align=True)
            row.operator("mhw.sk_to_weights", text=T("ui.main_panel.btn_sk_to_weights"), icon='SHAPEKEY_DATA')
            row.operator("mhw.merge_renamed_vgroups", text=T("ui.main_panel.btn_merge_renamed_vgroups"), icon='AUTOMERGE_ON')
            row = col.row(align=True)
            row.operator("mhw.cylindrical_face_normals", text=T("ui.main_panel.btn_cylindrical_face_normals"), icon='NORMALS_FACE')
            row.operator("mhw.reset_face_normals", text=T("ui.main_panel.btn_reset_face_normals"), icon='FILE_REFRESH')
            col.operator("mhw.apply_modifiers_keep_shape_keys",
                         text=T("ui.main_panel.btn_apply_mods_keep_sk"), icon='MODIFIER')
            col.operator("mhw.separate_by_materials",
                         text=T("ui.main_panel.btn_separate_by_materials"), icon='MOD_EXPLODE')
            col.operator("mhw.create_outline",
                         text=T("ui.main_panel.btn_create_outline"), icon='MOD_SOLIDIFY')

            col.separator(factor=0.8)
            col.label(text=T("ui.main_panel.label_texture_processing"), icon='TEXTURE')
            col.operator("mt.tex_convert_dialog",
                         text=T("ui.main_panel.btn_tex_process"), icon='TEXTURE')

        layout.separator()

        # =========================================
        # 3. Universal skeleton conversion system
        # =========================================
        main_box = layout.box()
        row = main_box.row()
        row.prop(settings, "show_std_converter",
                 icon="TRIA_DOWN" if settings.show_std_converter else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text=T("ui.main_panel.std_converter_header"), icon='ARMATURE_DATA')

        if settings.show_std_converter:
            col = main_box.column(align=True)
            col.prop(settings, "same_kind_align", text=T("ui.main_panel.same_kind_align_label"))
            col.separator()

            # Same-kind armatures match by bone name, so the preset pipeline and
            # everything hanging off it is irrelevant here — show only the align row.
            if settings.same_kind_align:
                row = col.row(align=True)
                row.scale_y = 1.2
                row.prop(settings, "align_mode_override", text="")
                row.operator("mhw.general_tools",
                             text=T("ui.main_panel.btn_same_kind_snap"),
                             icon='SNAP_ON').action = _SAME_KIND_ALIGN_ACTION[settings.align_mode_override]

            else:
                row = col.row(align=True)
                row.prop(settings, "import_preset_enum", text=T("ui.main_panel.import_preset_label"), icon='IMPORT')
                op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
                op.attr_name = 'import_preset_enum'
                op.is_import_x = True
                row = col.row(align=True)
                row.prop(settings, "target_preset_enum", text=T("ui.main_panel.target_preset_label"), icon='EXPORT')
                op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
                op.attr_name = 'target_preset_enum'
                op.is_import_x = False

                col.separator()

                # Core actions (with preset-dependency hints)
                row = col.row(align=True)
                row.scale_y = 1.2
                row.prop(settings, "align_mode_override", text="")
                row.operator("modder.universal_snap", text=T("ui.main_panel.btn_universal_snap"), icon='SNAP_ON')

                row = col.row(align=True)
                row.scale_y = 1.2
                row.operator("modder.direct_convert", text=T("ui.main_panel.btn_direct_convert"), icon='MOD_VERTEX_WEIGHT')

                # Skeleton cleanup (collapsible, closed by default)
                col.separator()
                row = col.row()
                row.prop(settings, "show_skeleton_cleanup",
                         icon="TRIA_DOWN" if settings.show_skeleton_cleanup else "TRIA_RIGHT",
                         icon_only=True, emboss=False)
                row.label(text=T("ui.main_panel.label_skeleton_cleanup"), icon='TOOL_SETTINGS')

                if settings.show_skeleton_cleanup:
                    sc_col = col.column(align=True)
                    sc_col.operator("modder.merge_physics_weights", text=T("ui.main_panel.btn_merge_physics_weights"), icon='TRASH')
                    sc_col.operator("modder.remove_non_base_bones", text=T("ui.main_panel.btn_remove_non_base_bones"), icon='X')
                    sc_col.operator("modder.rename_bones_to_target", text=T("ui.main_panel.btn_rename_bones_to_target"), icon='SORTALPHA')

                # Physics chain tools (collapsible, closed by default) — bone
                # visibility lives here because the three modes filter by
                # physics vs base bones
                col.separator()
                row = col.row()
                row.prop(settings, "show_physics_chain_tools",
                         icon="TRIA_DOWN" if settings.show_physics_chain_tools else "TRIA_RIGHT",
                         icon_only=True, emboss=False)
                row.label(text=T("ui.main_panel.label_physics_chain_tools"), icon='BONE_DATA')

                if settings.show_physics_chain_tools:
                    pc_col = col.column(align=True)
                    pc_col.operator("modder.smart_graft", text=T("ui.main_panel.btn_smart_graft"), icon='BONE_DATA')
                    pc_col.operator("mhw.general_tools", text=T("ui.main_panel.gt_action_add_tail"), icon='RIGID_BODY').action = 'ADD_TAIL'
                    row = pc_col.row(align=True)
                    row.operator("modder.mark_as_main_continue", text=T("ui.main_panel.btn_mark_main_continue"), icon='HANDLE_ALIGNED')
                    row.operator("modder.clear_chain_role", text=T("ui.main_panel.btn_clear_chain_role"), icon='X')
                    pc_col.operator("modder.refresh_physics_bone_colors", text=T("ui.main_panel.btn_refresh_bone_colors"), icon='COLOR')
                    pc_col.separator()
                    row = pc_col.row(align=True)
                    row.label(text=T("ui.main_panel.label_bone_visibility"), icon='HIDE_OFF')
                    row = pc_col.row(align=True)
                    row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_all"),
                                 depress=(settings.bone_view_mode == 'ALL')).mode = 'ALL'
                    row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_base"),
                                 depress=(settings.bone_view_mode == 'BASE')).mode = 'BASE'
                    row.operator("modder.set_bone_visibility", text=T("ui.main_panel.bone_view_physics"),
                                 depress=(settings.bone_view_mode == 'PHYSICS')).mode = 'PHYSICS'

                # Mapping detail preview
                col.separator()
                row = col.row()
                row.prop(settings, "show_mapping_details", text=T("ui.main_panel.show_mapping_details_label"),
                         icon='TRIA_DOWN' if settings.show_mapping_details else 'TRIA_RIGHT',
                         emboss=False)

                if settings.show_mapping_details:
                    if arm_obj and arm_obj.type == 'ARMATURE':
                        if 'AUTO' in (settings.import_preset_enum, settings.target_preset_enum):
                            col.label(text=T("ui.main_panel.label_mapping_preview_need_preset"), icon='INFO')
                        else:
                            cache_key = (settings.import_preset_enum, settings.target_preset_enum)
                            if cache_key not in _mapping_detail_cache:
                                m_x = BoneMapManager()
                                m_y = BoneMapManager()
                                m_x.load_preset(settings.import_preset_enum, is_import_x=True)
                                m_y.load_preset(settings.target_preset_enum, is_import_x=False)
                                _mapping_detail_cache.clear()
                                _mapping_detail_cache[cache_key] = (m_x, m_y)
                            mapper, mapper_y = _mapping_detail_cache[cache_key]

                            preview_box = col.box()
                            for group_name, group_data in ui_config.UI_HIERARCHY.items():
                                g_box = preview_box.box()
                                g_box.label(text=group_name, icon=group_data['icon'])

                                for sub_name, bones in group_data['subsections'].items():
                                    sub_col = g_box.column(align=True)
                                    sub_col.label(text=sub_name)

                                    for std_key in bones:
                                        if std_key in ui_config.OPTIONAL_BONES:
                                            if std_key not in mapper_y.mapping_data:
                                                continue

                                        main_bone, aux_list = mapper.get_matches_for_standard(arm_obj, std_key)
                                        m_row = sub_col.row(align=True)
                                        m_row.label(text=f"  {ui_config.get_display_name(std_key)}")

                                        if main_bone:
                                            status = f"{main_bone}"
                                            if aux_list: status += f" (+{len(aux_list)})"
                                            m_row.label(text=status, icon='CHECKMARK')
                                        else:
                                            m_row.label(text=T("ui.main_panel.label_missing"), icon='CANCEL')
                    else:
                        col.label(text=T("ui.main_panel.label_select_armature_preview"), icon='INFO')

        layout.separator()

        # =========================================
        # 4. Pose convert (standalone section)
        # =========================================
        pose_box = layout.box()
        row = pose_box.row()
        row.prop(settings, "show_pose_convert",
                 icon="TRIA_DOWN" if settings.show_pose_convert else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text=T("ui.main_panel.pose_convert_header"), icon='OUTLINER_OB_ARMATURE')

        if settings.show_pose_convert:
            col = pose_box.column(align=True)

            # Both fixed-purpose tools below are self-contained: MMD A->T always matches
            # against the MMD preset internally, REE->T auto-detects the game from its own
            # private bone list. Neither needs the generic preset selector any more; that
            # selector now only feeds the Pose Recorder's optional name bridge below
            # (same-name matching is still the fallback there).
            col.label(text=T("ui.main_panel.label_simple_tools"))
            col.operator("modder.mmd_a_to_tpose", text=T("ui.main_panel.btn_mmd_a_to_tpose"), icon='EMPTY_SINGLE_ARROW')
            col.operator("modder.ree_to_tpose", text=T("ui.main_panel.btn_ree_to_tpose"), icon='MESH_GRID')

            col.separator()
            col.label(text=T("ui.main_panel.label_pose_recorder"))

            row = col.row(align=True)
            row.prop(settings, "pose_import_preset_enum", text=T("ui.main_panel.pose_preset_field_label"), icon='IMPORT')
            op = row.operator("modder.auto_detect_preset", text="", icon='VIEWZOOM')
            op.attr_name = 'pose_import_preset_enum'
            op.is_import_x = True

            row = col.row(align=True)
            row.prop(settings, "pose_preset_enum", text="")
            row.operator("modder.delete_pose_preset", text="", icon='TRASH')

            col.operator("modder.record_transform", text=T("ui.main_panel.btn_record_transform"), icon='REC')

            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator("modder.apply_transform_forward", text=T("ui.main_panel.btn_apply_forward"), icon='PLAY')
            row.operator("modder.apply_transform_inverse", text=T("ui.main_panel.btn_apply_inverse"), icon='LOOP_BACK')

        layout.separator()

        # =========================================
        # 5. Game-specific toolbars
        # =========================================
        
        # One data-driven pass per game -- see ui/game_sections.py. These five
        # sections used to be five hand-written blocks that had drifted apart.
        for _key, _shown in (("mhwi", settings.show_mhwi),
                             ("mhws", settings.show_mhws),
                             ("re4",  settings.show_re4),
                             ("mhrs", settings.show_mhrs),
                             ("re9",  settings.show_re9)):
            if _shown:
                game_sections.draw_section(layout, _key)
# Known Blender dynamic-enum limitation: if the list returned by an items=
# callback is a local variable, Python's GC can free the strings while the C
# side still holds a pointer to them, corrupting non-ASCII (CJK, etc.) text.
# Fix: stash the list in a module-level variable so GC can't collect it.
_sk_enum_cache: list = []


# ==========================================
# register / unregister
# ==========================================
classes = [
    MHW_PT_SuiteSettings,
    MHW_OT_SetChannelSize,
    MHW_OT_SetShaderSource,
    MHW_PT_MainPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhw_suite_settings = bpy.props.PointerProperty(type=MHW_PT_SuiteSettings)

def unregister():
    del bpy.types.Scene.mhw_suite_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)