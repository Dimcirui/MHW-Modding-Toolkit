"""RE Mdf port, operator: run mdf_port.plan_material on a real .mdf2 collection.

Mirrors two existing patterns rather than inventing a third:

- ``core/mesh_port_ops.py``'s ``modder.port_mesh_cross_game`` and
  ``core/chain_convert_ops.py``'s ``modder.convert_chain_cross_game`` -- one
  game-agnostic operator, ``source_game`` fixed by which per-game UI section
  calls it, a whole source *collection* picked (not a hand-picked object
  selection), defaulted from the active object's own collection, and enabled
  whenever there is anything to port anywhere in the file rather than gated on
  the current selection. The result lands in a *new* collection next to the
  original rather than mutating it in place.
- ``core/mdf_material_convert_base.py``'s same-game convert -- read the old
  material's bindings, build the new one from a preset, copy the custom textures
  across.  The cross-game difference is everything downstream of "which bindings
  copy": the target's slot vocabulary and channel packing can differ (see
  ``core/mdf_port_tex.py``), so a straight ``old_path`` copy is not enough here.

Params are migrated selectively, not wholesale: the shader's Property List is
game-specific, so which entries mean the same thing on both sides is its own
question -- ``core/mdf_port_params.py`` answers it, and ``migrate_params`` picks
how far to take the answer.
"""

import os
import tempfile
import shutil

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from .i18n import T
from . import mdf_port
from . import mdf_port_params
from . import mdf_port_tex
from .mdf_material_convert_base import (
    _load_vanilla_art_paths, is_custom_tex_path, migrate_property_value)
from .mdf_tex_processor_base import (
    mdf_collection_poll, _import_tex_utils, octahedral_normals_prop)
from .mdf_generator_base import (
    import_read_preset_json, PLACEHOLDER_SLOT_TYPES, _resolve_placeholder_slot)

#: Fallback for the PLACEHOLDER_SLOT_TYPES slots when the port cannot write a
#: real placeholder (textures off, or no destination mod root). Values are the
#: game's own always-present null textures -- see the use site for why the
#: prefab's own path must not survive here. Choices are the user's, 2026-08-15.
_PLACEHOLDER_NULL_TEX = {
    'SkinMap':        'systems/rendering/NullWhite.tex',
    'BlendNormalMap': 'systems/rendering/NullNormalRoughness.tex',
}

_enum_cache = {}


def _cached(key, items):
    cache = _enum_cache.setdefault(key, [])
    cache.clear()
    cache.extend(items)
    return cache


def _target_game_items(self, context):
    items = [(g, g, "") for g in mdf_port.PORTABLE_GAMES if g != self.source_game]
    if not items:
        items = [("NONE", "-", "")]
    return _cached("mdf_port_target_game", items)


def _copy_material_flags(dst_flags, src_flags):
    """Carry the source material's bit flags onto the ported one.

    Only ``flagIntValue``/``flagIntValueB`` are written: every checkbox in the
    Flags panel (BaseTwoSideEnable, SSSProfileUsed, ...) and every small numeric
    in among them (TessFactor, PhongFactor, TransparentPriorityBias) is a bitfield
    *inside* those two int32s, and RE Mesh Editor's own ``update_FlagsFromInt``
    handler expands them back out on assignment.  Setting the expanded fields
    one by one instead would be the same write done twice, through a handler
    that suppresses itself midway.

    ``shaderLODNum`` and ``bakeTextureArraySize`` sit next to them in the panel
    but are their own fields, not part of either int -- and they describe the
    asset's LOD/bake setup rather than its material features, so they stay at
    the target preset's value.
    """
    dst_flags.flagIntValue = src_flags.flagIntValue
    dst_flags.flagIntValueB = src_flags.flagIntValueB


def _migrate_params_items(self, context):
    # BASIC first: it is the default by being first (see the property's comment).
    return _cached("mdf_port_migrate_params", [
        ('BASIC', T("core.mdf_port_ops.params_basic"),
                  T("core.mdf_port_ops.params_basic_desc")),
        ('ALL', T("core.mdf_port_ops.params_all"),
                T("core.mdf_port_ops.params_all_desc")),
    ])


def mdf_material_collections():
    """.mdf2 collections holding at least one RE_MDF_MATERIAL object."""
    return [c for c in bpy.data.collections
            if mdf_collection_poll(None, c)
            and any(o.get("~TYPE") == "RE_MDF_MATERIAL" for o in c.objects)]


def _collection_matches_game(col, game_code):
    """True if at least one material in *col* classifies as one of
    *game_code*'s own prefab archetypes.

    Guards _prefill against a real trap: right after a port, the newly
    created destination collection's materials are the ones left selected
    in the viewport. Porting again with those active would otherwise default
    "MDF Collection" straight back to that *destination* -- its bindings
    already follow the *other* game's convention, so every "find this
    texture under game_code's mod root" lookup would come up empty and the
    op would report source textures missing that were never the problem.
    """
    for obj in col.objects:
        if obj.get("~TYPE") != "RE_MDF_MATERIAL":
            continue
        md = getattr(obj, 're_mdf_material', None)
        if md is None:
            continue
        if mdf_port.classify(game_code, md.mmtrPath) is not None:
            return True
    return False


def _collection_items(self, context):
    items = [(c.name, f"{c.name}  ({sum(1 for o in c.objects if o.get('~TYPE') == 'RE_MDF_MATERIAL')})",
              "", 'OUTLINER_COLLECTION', i) for i, c in enumerate(mdf_material_collections())]
    if not items:
        items = [("NONE", T("core.mdf_port_ops.no_mdf_collection"), "", 'ERROR', 0)]
    return _cached("mdf_port_collection", items)


#: scene attrs already holding a per-game "Base Path" the user has typed for the
#: processor/generator -- the port reuses these instead of asking a third time.
#: Generator checked first: a port is closer in kind to "build a fresh material"
#: than to "reprocess an existing one".
_GENERATOR_SETTINGS_ATTR = {"MHWS": "mhws_mdf_generator", "RE4": "re4_mdf_generator", "RE9": "re9_mdf_generator"}
_PROCESSOR_SETTINGS_ATTR = {"MHWS": "mdf_tex_processor", "RE4": "re4_mdf_tex_processor", "RE9": "re9_mdf_tex_processor"}


def _scene_base_path(context, game_code):
    for attr_map in (_GENERATOR_SETTINGS_ATTR, _PROCESSOR_SETTINGS_ATTR):
        settings = getattr(context.scene, attr_map.get(game_code, ""), None)
        path = getattr(settings, "texture_base_path", "")
        if path:
            return path
    return ""


def _on_target_game_update(self, context):
    # Only fills an empty field -- a target-game change after the user already
    # typed their own path must not clobber it.
    if not self.dest_base_path and self.target_game and self.target_game != 'NONE':
        self.dest_base_path = _scene_base_path(context, self.target_game)


def _stm_prefix_label(dst_cfg):
    """The fixed part of the on-disk path this game's base_path sits under --
    same text the generator/processor panels show next to their own
    texture_base_path field (games/<game>/mdf_generator_ui.py)."""
    if dst_cfg["use_art_prefix"]:
        return "natives/STM/Art/"
    if dst_cfg.get("path_fixed_prefix"):
        return f"natives/STM/{dst_cfg['path_fixed_prefix']}/"
    return "natives/STM/"


def _draw_mod_root_row(layout, context, game_code, cfg, show_hint=False):
    """"Mod Root" button + current path (or a "not set" warning) -- same
    layout the generator/processor panels use for the same scene key.

    *game_code* is folded into the button's own text -- the source and
    destination rows would otherwise be two identical "Mod Root" buttons
    with nothing on screen saying which game each belongs to.

    *show_hint* prepends the one line saying what the directory actually is.
    Off by default because this dialog draws the row twice and the sentence
    only needs saying once; the pre-export check, which draws it once, asks
    for it. Sharing the row is what keeps the two dialogs' wording identical.
    """
    if show_hint:
        layout.label(text=T("core.mdf_port_ops.mod_root_hint"), icon='INFO')
    row = layout.row(align=True)
    row.operator(f"{game_code.lower()}.set_natives_root",
                text=f"{game_code} " + T("core.mdf_port_ops.mod_root_label"), icon='FILEBROWSER')
    natives_root = context.scene.get(cfg["natives_root_key"], "")
    if natives_root:
        parts = natives_root.replace("\\", "/").rstrip("/").split("/")
        short = "/".join(parts[-3:]) if len(parts) > 3 else natives_root
        row.label(text=f".../{short}")
    else:
        row.label(text=T("core.export_prep.not_set"), icon='ERROR')
    return bool(natives_root)


def _scan_source_textures(targets, vanilla_set, src_natives_root, tex_version):
    """``(total, missing)`` over every custom texture binding across *targets*
    -- *missing* holds the full expected disk path for each one that isn't
    there. Runs before any mdf output is touched: a wrong directory or a
    still-.pak-packed mod would otherwise surface as N separate "not found"
    skips deep in the per-material loop instead of one clear signal up front.
    """
    total = 0
    missing = []
    for obj in targets:
        old_data = obj.re_mdf_material
        for b in old_data.textureBindingList_items:
            if not is_custom_tex_path(b.path, vanilla_set):
                continue
            total += 1
            disk_path = mdf_port_tex.resolve_source_disk_path(src_natives_root, b.path, tex_version)
            if not os.path.isfile(disk_path):
                missing.append(disk_path)
    return total, missing


def _new_port_collection(src_col, suffix):
    """A fresh, empty .mdf2 collection beside *src_col* -- same naming/linking
    convention as mesh_port_ops.duplicate_mesh_collection, minus the armature
    duplication that has no equivalent here."""
    stem = src_col.name[:-5] if src_col.name.endswith(".mdf2") else src_col.name
    new_col = bpy.data.collections.new(f"{stem}_{suffix}.mdf2")
    if src_col.get("~TYPE") is not None:
        new_col["~TYPE"] = src_col["~TYPE"]
    new_col.color_tag = src_col.color_tag

    parents = [c for c in bpy.data.collections if src_col.name in c.children]
    if not parents:
        parents = [bpy.context.scene.collection]
    for parent in parents:
        parent.children.link(new_col)
    return new_col


class MODDER_OT_PortMdfMaterialCrossGame(bpy.types.Operator):
    bl_idname = "modder.port_mdf_material_cross_game"
    bl_label = "Port MDF Material to Another Game"
    #: Same reasoning as modder.port_mesh_cross_game: not idempotent (a second
    #: click ports the new collection's own materials) and writes .tex files to
    #: disk, which undo cannot take back either.
    bl_options = {'REGISTER'}

    source_game: StringProperty(options={'HIDDEN'})
    #: A whole .mdf2 collection, not a hand-picked selection of materials -- the
    #: same unit mesh_port_ops/chain_convert_ops operate on. A collection can
    #: hold two dozen material Empties; making the user multi-select them by
    #: hand was the wrong default.
    source_collection: EnumProperty(name="MDF Collection", items=_collection_items)
    target_game: EnumProperty(name="Target Game", items=_target_game_items,
                              update=_on_target_game_update)
    #: Semantically separate from the material port in the dialog (its own
    #: checkbox, its own mod-root rows) but not a second operator -- a material
    #: and its own textures are too tightly bound in practice to split into two
    #: buttons the user has to remember to press in order.
    convert_textures: BoolProperty(
        name="Convert Textures",
        description="Also migrate the source's own custom textures, not just the material itself",
        default=True,
    )
    dest_base_path: StringProperty(
        name="Destination Base Path",
        description="Path under the target game's own natives/STM convention, e.g. Author/Name",
        default="",
    )
    #: Defaults to BASIC rather than ALL: 'all' includes entries that line up by
    #: name but are not the authored look (see mdf_port_params.BASIC_EXCLUDE_*),
    #: and a wrong param value is the kind of bug that renders plausibly.
    #: No `default=`: with a callback items list that would have to be an index,
    #: and the first item is BASIC anyway -- same shape as the same-game convert's
    #: `migrate_mode`.
    migrate_params: EnumProperty(name="Migrate Params", items=_migrate_params_items)
    #: Comma-separated source property names the migration is allowed to read, or
    #: empty for "all of them".  Not shown in the dialog -- it exists for callers
    #: that know the source material is not fully authored.
    #:
    #: ``core/mrl3_port_ops.py``'s relay is the one such caller: the MHWS material
    #: it hands over was itself built from MHWS' ``basic`` prefab minutes earlier
    #: and carries that prefab's defaults everywhere the mrl3 port did not write,
    #: which the migration cannot tell apart from a value the author chose.  Left
    #: unrestricted, MHWS' ``Emissive_Intensity`` of 1.0 lands on MHRS as though it
    #: were authored, overwriting the MHRS prefab's own default -- and the same for
    #: ``Emissive_Color``.  A user porting a real MHWS material sets nothing here
    #: and keeps the old behaviour, which is correct for them: every value in
    #: *their* source is one they could have chosen.
    migrate_only: StringProperty(name="Migrate Only", default="", options={'HIDDEN'})
    #: Same opt-in as the processors and generators carry, and off for the same
    #: reason -- see octahedral_normals_prop.
    octahedral_normals: octahedral_normals_prop()
    #: Off by default, unlike the params above: the target preset's flags are a
    #: deliberate choice by whoever authored it, so overwriting them is opt-in.
    #: Offered here and *not* on the same-game convert for the same reason --
    #: there the preset is the point, here the source material is.
    migrate_flags: BoolProperty(
        name="Migrate Flags",
        description="Carry the source material's bit flags (two-sided, alpha test, SSS profile, ...) "
                    "onto the ported material instead of keeping the target preset's",
        default=False,
    )
    delete_original: BoolProperty(name="Delete Original Material", default=False)

    @classmethod
    def description(cls, context, properties):
        return T("core.mdf_port_ops.desc")

    @classmethod
    def poll(cls, context):
        # Same shape as modder.port_mesh_cross_game/convert_chain_cross_game:
        # enabled whenever there is anything to port anywhere in the file, not
        # gated on the current selection -- _prefill below is what reads the
        # selection, to fill in the common case rather than to gate the button.
        return bool(mdf_material_collections())

    def _prefill(self, context):
        """Default source_collection/dest_base_path off the active object.

        Either the active object's own collection *is* an .mdf2 collection, or
        the active object belongs to one -- both reduce to the same lookup via
        users_collection, so there is no separate "selected the collection
        itself" case to special-case. _collection_matches_game gates it so a
        wrong-game collection (most likely one this same operator just
        produced) is skipped rather than guessed into place.
        """
        obj = context.active_object
        if obj is not None:
            for col in obj.users_collection:
                if mdf_collection_poll(None, col) and _collection_matches_game(col, self.source_game):
                    try:
                        self.source_collection = col.name
                    except (TypeError, ValueError):
                        pass
                    break
        if not self.dest_base_path and self.target_game and self.target_game != 'NONE':
            self.dest_base_path = _scene_base_path(context, self.target_game)

    def invoke(self, context, event):
        self._prefill(context)
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "source_collection", text=T("core.mdf_port_ops.source_collection_label"))
        col.prop(self, "target_game", text=T("core.mdf_port_ops.target_game_label"))

        col.separator()
        col.prop(self, "convert_textures", text=T("core.mdf_port_ops.convert_textures_label"))

        if self.convert_textures:
            box = col.box()

            # source_game has no picker anywhere in this dialog (it's a HIDDEN
            # prop, fixed by which UI section opened this dialog) -- label it
            # here or this row reads as belonging to nothing in particular.
            box.prop(self, "octahedral_normals", text=T("core.octahedral_normals.label"))
            box.label(text=T("core.mdf_port_ops.source_game_label").format(game=self.source_game))
            src_cfg = mdf_port_tex.get_game_tex_config(self.source_game)
            if src_cfg is not None:
                # The hint rides on the source row only: it explains what a mod
                # root *is*, which is the same sentence for both rows below.
                _draw_mod_root_row(box, context, self.source_game, src_cfg, show_hint=True)

            # target_game repeated as a plain label, not a second EnumProperty
            # -- it only ever reflects the choice above, never sets it.
            box.label(text=T("core.mdf_port_ops.target_game_label_plain").format(game=self.target_game))
            dst_cfg = mdf_port_tex.get_game_tex_config(self.target_game)
            if dst_cfg is None:
                box.prop(self, "dest_base_path", text=T("core.mdf_port_ops.dest_base_path_label"))
            else:
                # Same "Mod Root" button + path-prefix hint the generator/
                # processor panels show -- reusing the destination game's own
                # natives-root setter operator and scene key rather than a
                # third, separate mod-root picker just for this dialog.
                _draw_mod_root_row(box, context, self.target_game, dst_cfg)
                row = box.row(align=True)
                row.label(text=_stm_prefix_label(dst_cfg))
                row.prop(self, "dest_base_path", text="")

        col.separator()
        col.prop(self, "migrate_params", text=T("core.mdf_port_ops.migrate_params_label"))
        col.prop(self, "migrate_flags", text=T("core.mdf_port_ops.migrate_flags_label"))

        col.separator()
        col.prop(self, "delete_original", text=T("core.mdf_port_ops.delete_original_label"))

    def execute(self, context):
        src_game = self.source_game
        dst_game = self.target_game
        allow_src = ({n for n in (s.strip() for s in self.migrate_only.split(",")) if n}
                     or None) if self.migrate_only else None
        if not dst_game or dst_game == 'NONE':
            self.report({'ERROR'}, T("core.mdf_port_ops.no_target_selected"))
            return {'CANCELLED'}

        src_cfg = mdf_port_tex.get_game_tex_config(src_game)
        dst_cfg = mdf_port_tex.get_game_tex_config(dst_game)
        if src_cfg is None or dst_cfg is None:
            self.report({'ERROR'}, T("core.mdf_port_ops.missing_tex_config"))
            return {'CANCELLED'}

        mdf_col = bpy.data.collections.get(self.source_collection)
        if mdf_col is None:
            self.report({'ERROR'}, T("core.mdf_port_ops.no_mdf_collection"))
            return {'CANCELLED'}

        targets = [o for o in list(mdf_col.objects)
                   if o.get("~TYPE") == "RE_MDF_MATERIAL" and getattr(o, 're_mdf_material', None)]
        if not targets:
            self.report({'WARNING'}, T("core.mdf_port_ops.no_targets"))
            return {'CANCELLED'}

        readPresetJSON = import_read_preset_json()
        if readPresetJSON is None:
            self.report({'ERROR'}, T("core.mdf_port_ops.cannot_load_preset_tool"))
            return {'CANCELLED'}

        vanilla_set = _load_vanilla_art_paths(src_cfg.get("vanilla_asset_rel", ""))
        src_natives_root = context.scene.get(src_cfg["natives_root_key"], "")
        dst_natives_root = context.scene.get(dst_cfg["natives_root_key"], "")
        # The game's own fixed segment goes on here, once, so every path built
        # below (textures and placeholders alike) agrees with the prefix the
        # dialog showed next to the field.
        dst_base_path = mdf_port_tex.full_base_path(dst_cfg, self.dest_base_path.strip())
        convert_textures = self.convert_textures
        no_source_root = not src_natives_root

        partial_missing = []
        if convert_textures:
            if no_source_root:
                self.report({'WARNING'}, T("core.mdf_port_ops.source_root_missing_warning"))
            if not dst_natives_root:
                self.report({'WARNING'}, T("core.mdf_port_ops.dest_root_missing_warning"))

            # Confirm the source mod actually has something to read before
            # touching any mdf output -- a wrong directory or a still-.pak-
            # packed mod should fail once, up front, not once per texture
            # deep in the per-material loop below.
            if not no_source_root:
                total, missing = _scan_source_textures(
                    targets, vanilla_set, src_natives_root, src_cfg["tex_version"])
                if total > 0 and len(missing) == total:
                    print(f"[MDF Port] no source textures found under natives_root='{src_natives_root}'")
                    for p in missing[:5]:
                        print(f"[MDF Port]   checked: {p}")
                    self.report({'ERROR'}, T("core.mdf_port_ops.no_source_tex_found_error"))
                    return {'CANCELLED'}
                partial_missing = missing

        temp_dir = tempfile.mkdtemp(prefix="mdf_port_")
        new_col = _new_port_collection(mdf_col, dst_game)
        placeholder_cache = {}  # shared across the whole batch, see _resolve_placeholder_slot

        converted = failed = unsupported = 0
        tex_ported = tex_skipped_vanilla = tex_skipped_no_slot = tex_skipped_no_source = 0
        tex_pending_write = tex_placeholder = tex_null_fallback = 0
        params_migrated = params_skipped = 0

        try:
            for obj in targets:
                try:
                    old_data = obj.re_mdf_material
                    old_name = old_data.materialName
                    old_mmtr = old_data.mmtrPath
                    old_bindings = {b.textureType: b.path for b in old_data.textureBindingList_items}

                    plan = mdf_port.plan_material(src_game, dst_game, old_mmtr)
                    if plan["unsupported"]:
                        unsupported += 1
                        print(f"[MDF Port] {old_name}: unsupported material shader "
                              f"'{old_mmtr}', falling back to {plan['target']}")
                    elif not plan["exact"]:
                        print(f"[MDF Port] {old_name}: no exact {dst_game} counterpart "
                              f"for archetype '{plan['archetype']}', using '{plan['target']}'")

                    new_obj = readPresetJSON(plan["path"], new_col)
                    if not new_obj:
                        print(f"[MDF Port] {old_name}: readPresetJSON failed for '{plan['path']}'")
                        failed += 1
                        continue

                    new_data = new_obj.re_mdf_material
                    new_data.materialName = old_name
                    tex_name = old_name.removesuffix('_UseSC')

                    # Read both Property Lists off the live materials, not off the
                    # prefabs: the source may be an unsupported shader with no
                    # prefab at all, and the target's list is what actually has to
                    # accept the write.
                    if self.migrate_flags:
                        _copy_material_flags(new_data.flags, old_data.flags)

                    src_items = {p.prop_name: p for p in old_data.propertyList_items}
                    dst_items = {p.prop_name: p for p in new_data.propertyList_items}
                    if allow_src is not None:
                        src_items = {n: p for n, p in src_items.items() if n in allow_src}
                    for src_name, dst_name in mdf_port_params.migration_pairs(
                            src_game, {n: p.data_type for n, p in src_items.items()},
                            dst_game, {n: p.data_type for n, p in dst_items.items()},
                            self.migrate_params):
                        if migrate_property_value(dst_items[dst_name], src_items[src_name]):
                            params_migrated += 1
                        else:
                            params_skipped += 1

                    dst_binding_types = {b.textureType: b for b in new_data.textureBindingList_items}
                    handled_dst_slots = set()

                    if convert_textures:
                        for tex_type, old_path in old_bindings.items():
                            if not is_custom_tex_path(old_path, vanilla_set):
                                if old_path:
                                    tex_skipped_vanilla += 1
                                continue

                            dst_slot_type = mdf_port_tex.find_dst_slot_type(tex_type, dst_binding_types)
                            if dst_slot_type is None:
                                tex_skipped_no_slot += 1
                                continue
                            dst_binding = dst_binding_types[dst_slot_type]

                            if no_source_root:
                                tex_skipped_no_source += 1
                                continue
                            src_disk_path = mdf_port_tex.resolve_source_disk_path(
                                src_natives_root, old_path, src_cfg["tex_version"])
                            if not os.path.isfile(src_disk_path):
                                print(f"[MDF Port] {old_name}: source texture not found on disk: "
                                      f"{src_disk_path}")
                                tex_skipped_no_source += 1
                                continue

                            if not dst_base_path:
                                tex_pending_write += 1
                                continue

                            ported = mdf_port_tex.repack_slot(
                                src_disk_path, tex_type, dst_slot_type, temp_dir, tex_name,
                                src_channel_maps=src_cfg["channel_maps"],
                                dst_channel_maps=dst_cfg["channel_maps"],
                                octahedral=self.octahedral_normals)
                            mdf_path, written = mdf_port_tex.write_ported_tex(
                                ported, dst_slot_type, dst_cfg, tex_name,
                                dst_natives_root, dst_base_path, temp_dir)
                            dst_binding.path = mdf_path
                            handled_dst_slots.add(dst_slot_type)
                            if written:
                                tex_ported += 1
                            else:
                                tex_pending_write += 1

                        # PLACEHOLDER_SLOT_TYPES (SkinMap/BlendNormalMap so far) have no PBR
                        # recipe and no vanilla default at all (see mdf_generator_base.py's own
                        # comment on that set) -- for any such slot the port left untouched,
                        # write the bundled placeholder rather than shipping the prefab's own
                        # borrowed literal path (some other mod's asset it happened to be
                        # authored against).
                        if dst_base_path and dst_natives_root:
                            for slot_type in PLACEHOLDER_SLOT_TYPES:
                                if slot_type in handled_dst_slots or slot_type not in dst_binding_types:
                                    continue
                                image_to_dds, dds_to_tex = _import_tex_utils()
                                mdf_path = _resolve_placeholder_slot(
                                    slot_type, tex_name, dst_natives_root, dst_base_path, temp_dir,
                                    dst_cfg["abbrev_map"], dst_cfg["tex_version"], dst_cfg["use_art_prefix"],
                                    image_to_dds, dds_to_tex, placeholder_cache)
                                if mdf_path:
                                    dst_binding_types[slot_type].path = mdf_path
                                    handled_dst_slots.add(slot_type)
                                    tex_placeholder += 1

                    # Whatever the branch above did not cover -- textures off, or
                    # on with no mod root set -- must still not ship the prefab's
                    # own literal path for these two. Every other slot the port
                    # leaves alone falls back to a real systems/rendering/Null*
                    # the game ships, but these two have no vanilla default, so
                    # the prefab points at the asset it was authored against
                    # (MK_MODS/Eku/Public/skin.tex): a path that does not exist on
                    # anyone else's machine. A null texture is wrong-looking --
                    # NullWhite makes skin render pallid -- but it is a texture
                    # that resolves, which a dangling path is not.
                    for slot_type, null_path in _PLACEHOLDER_NULL_TEX.items():
                        if slot_type in handled_dst_slots or slot_type not in dst_binding_types:
                            continue
                        dst_binding_types[slot_type].path = null_path
                        tex_null_fallback += 1

                    if self.delete_original:
                        bpy.data.objects.remove(obj, do_unlink=True)

                    converted += 1

                except Exception as e:
                    failed += 1
                    print(f"[MDF Port] convert failed for '{obj.name}': {e}")
                    import traceback
                    traceback.print_exc()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if failed:
            self.report({'WARNING'}, T("core.mdf_port_ops.done_with_fail").format(
                done=converted, failed=failed))
        else:
            self.report({'INFO'}, T("core.mdf_port_ops.done").format(
                done=converted, unsupported=unsupported, tex=tex_ported,
                placeholder=tex_placeholder, pending=tex_pending_write, vskip=tex_skipped_vanilla,
                noslot=tex_skipped_no_slot, nosrc=tex_skipped_no_source)
                + T("core.mdf_port_ops.done_params").format(
                    migrated=params_migrated, skipped=params_skipped))

        # Its own WARNING rather than a count folded into the line above: a
        # pallid-white skin is the kind of result the user would otherwise put
        # down to their own textures being wrong, and the fix (set a mod root,
        # turn texture conversion on) is not something they would guess at.
        if tex_null_fallback:
            self.report({'WARNING'}, T("core.mdf_port_ops.null_fallback_warning").format(
                n=tex_null_fallback))

        # Some (not all -- that case already returned CANCELLED above), so the
        # batch went ahead; call out exactly which ones by full path rather
        # than leaving it to the "nosrc" count above, which doesn't say which.
        if partial_missing:
            shown = partial_missing[:3]
            extra = len(partial_missing) - len(shown)
            listing = "; ".join(shown)
            if extra > 0:
                listing += T("core.mdf_port_ops.and_n_more").format(n=extra)
            self.report({'WARNING'}, T("core.mdf_port_ops.partial_missing_tex_warning").format(paths=listing))
        return {'FINISHED'}


classes = [MODDER_OT_PortMdfMaterialCrossGame]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
