"""MRL3 -> MDF2 port, planning layer: what one MHWI material becomes in MHWilds.

**Every material becomes ``basic``, unconditionally** (user's decision, 2026-08-16).
That is not a shortcut, it is the only honest reading of the data.  ``core/mdf_port.py``
classifies an RE material by its own ``.mmtr``, and refuses to guess from the name --
right there, because each RE archetype has its own shader.  MHWI has no such signal:
``PL_Mt`` is a one-for-all material, and measured on a model hand-ported to both games
it backs *skin, hair, eye and cloth alike*.  Face and Iris come out byte-identical on
the MHWI side -- same mmtr, same ``surfaceCoef``, same ``alphaCoef``, same texture set
-- yet the author made one skin and the other eye.  There is nothing to classify on.

MHWilds happens to have its own one-for-all material, ``Base_Equip.mmtr``, which is
what this addon ships as the ``basic`` prefab; ``skin`` and ``hair`` are its
specialisations for those surfaces and ``standard`` is its advanced variant, not a
"default".  So a MHWI material maps to ``basic`` and the user promotes it afterwards
with "Convert to another MDF material", which exists for exactly this.

An earlier version branched to ``standard`` when ``alphaCoef[2]`` said the material
was transparent.  Dropped as too clever: on the reference pair that rule would have
sent 2 of 17 materials to ``standard`` while the author had put 14 there, so it
neither reproduced the hand port nor stayed predictable.  Transparency survives as a
*flag* instead -- see ``decode_flags``.

Free of ``bpy``: a table over the shipped prefab, checkable offline.
"""

#: Where every MHWI material lands.  The stem of ``assets/mdf_presets/mhws/basic.json``,
#: whose ``Master Material Path`` is ``MaterialShader/Variation/Base_Equip.mmtr``.
TARGET_ARCHETYPE = "basic"
TARGET_GAME = "MHWS"


def prefab_path():
    """The shipped prefab every ported material is built from, or None.

    Read through ``mdf_port.load_prefabs`` rather than by joining a path, so the two
    ports cannot disagree about where the prefabs live or what an archetype is named.
    """
    from . import mdf_port

    info = mdf_port.load_prefabs(TARGET_GAME).get(TARGET_ARCHETYPE)
    return info["path"] if info else None


# ── flags ───────────────────────────────────────────────────────────────────────

#: ``surfaceCoef[1]`` values that mean the surface is drawn from both sides.
#: 17 is single-sided, 225 double (user, measured).  Anything else is unknown and
#: falls back to single, which is the safer error: a surface wrongly drawn one-sided
#: shows a hole the user will notice, while one wrongly drawn two-sided hides
#: backface artefacts until they show up in motion.
_TWO_SIDE_VALUE = 225

#: ``alphaCoef[2]`` values that mean the material uses its alpha.  4 is opaque; 1 and
#: 5 are the two transparent variants (1 = alpha follows the albedo map's A channel,
#: 5 = it follows the mrl3 albedo factor's A).
_ALPHA_VALUES = frozenset({1, 5})


def decode_flags(surface_coef, alpha_coef):
    """``{"two_side": bool, "alpha_test": bool}`` from an mrl3 material's two coefs.

    Validated against a model hand-ported to both games (17 materials).  The two rules
    are not equally strong and the difference matters when reading a mismatch report:

    * ``two_side`` reproduced the author's ``BaseTwoSideEnable`` on 13 of 17.  The four
      misses are all authoring choices rather than rule failures -- the eyes were made
      single-sided in MHWilds though MHWI had them double, and two cloth pieces went
      the other way.
    * ``alpha_test`` is **sufficient, not necessary**: every material the rule flags
      does have ``BaseAlphaTestEnable`` set (2 of 2), but the author also set it on ten
      more that the coefs call opaque.  So this turns the flag *on* where MHWI says it
      must be on, and leaves the rest to the target prefab's own default rather than
      forcing them off.
    """
    two_side = len(surface_coef) > 1 and surface_coef[1] == _TWO_SIDE_VALUE
    alpha = len(alpha_coef) > 2 and alpha_coef[2] in _ALPHA_VALUES
    return {"two_side": bool(two_side), "alpha_test": bool(alpha)}


# ── parameters ──────────────────────────────────────────────────────────────────

#: How an mrl3 constant-buffer field's type is written into an MDF Property List.
#:
#: This layer is why a plain name/type intersection finds nothing between the two
#: games: mrl3 spells its types ``float[4]`` / ``bbool`` / ``uint`` and MDF spells
#: them ``COLOR`` / ``BOOL`` / ``FLOAT``, so every row would be rejected on type
#: before its name was ever compared.
#:
#: ``color3`` is the one that is not a relabel: mrl3 stores an RGB triple where MDF
#: wants RGBA, so alpha is filled with 1.0.
CONVERTERS = ("scalar", "color4", "color3", "bool", "bool_as_float", "uint_as_float")

#: Migrated in **both** tiers.  Deliberately only three (user's decision, 2026-08-16):
#: these are the PBR quantities whose meaning and 0..1 scale are the same in both
#: engines, so carrying them across is a copy rather than a reinterpretation.
BASIC_PARAMS = (
    ("fMetalic__uiUNorm", "MetalParam", "scalar"),
    ("fRoughness__uiUNorm", "RoughnessParam", "scalar"),
    ("fTranslucency__uiUNorm", "TranslucentParam", "scalar"),
)

#: Migrated only under "all".  Every target exists in the ``basic`` prefab (checked
#: against the shipped JSON); hair's ``PrimalySpecularColor`` and the rest of the
#: specialised shaders' knobs are deliberately absent, because the destination is
#: always ``basic``.
ALL_PARAMS = (
    ("fBaseMapFactor__uiColor", "ColorParam", "color4"),
    ("fSubSurfaceBlend__uiUNorm", "SSSParam", "scalar"),
    # mrl3 stores the profile as an integer index, MDF as a float.  Both are opaque
    # per-game enums, so the number is carried, not the appearance -- worth a note in
    # the report rather than silent trust.
    ("iSubSurfaceProfile", "SSSProfile", "uint_as_float"),
    ("bBaseColorEmissive", "Use_Basecolor_to_Emissive", "bool"),
    ("bBackFaceNormalFilp", "BackFaceFlipNormal", "bool_as_float"),
    ("fAnimEmitMin", "AnimEmit_Min", "scalar"),
    ("fAnimEmitSpeed", "AnimEmit_Speed", "scalar"),
    ("fAnimEmitWave", "AnimEmitWave", "scalar"),
    ("bUseWaveEmit", "UseWaveEmit", "bool"),
    ("fFilmThickness__uiUNorm", "Film_Thickness", "scalar"),
    ("fFilmBlend__uiUNorm", "Film_Blend", "scalar"),
    ("fFilmIOR__uiUNorm", "Film_IOR", "scalar"),
    ("fRefractBlend__uiUNorm", "FakeRefraction_Blend", "scalar"),
    ("fRefraction__uiSNorm", "Refraction_Index", "scalar"),
    # MHWI's colour-mask dyeing system and MHWilds' ColorLayer are the same idea: one
    # mask texture keyed to four colours.  The A/B/C/D -> R/G/B/A pairing is
    # positional and **unverified in game** -- the data only shows both are four
    # colours indexed by a mask's four channels.
    ("fAddColorA__uiColor", "ColorLayer_R", "color4"),
    ("fAddColorB__uiColor", "ColorLayer_G", "color4"),
    ("fAddColorC__uiColor", "ColorLayer_B", "color4"),
    ("fAddColorD__uiColor", "ColorLayer_A", "color4"),
)

#: Never migrated, in either tier: runtime state and pipeline constants rather than
#: the material's authored look.  Mirrors ``mdf_port_params.BASIC_EXCLUDE_*``.
#:
#: The snow family is MHWilds-irrelevant twice over -- it is World's dynamic snow
#: cover, driven by the game, and Wilds' equivalent is sand.
EXCLUDED_PREFIXES = ("fSnow", "fMaterialSnow", "align")
EXCLUDED_NAMES = frozenset({
    "fFakeLight__uiDirection",       # shader lighting constant; MDF's LightDirection
                                     # is excluded for the same reason
    "bBypass", "bDecalMask", "bEmissive", "iGBufferId", "iOutlineId",  # CBMaterialCommon
})

#: The emissive factor is one source and two destinations, so it cannot live in the
#: tables above.  See ``split_emissive``.
EMISSIVE_SOURCE = "fEmissiveMapFactor__uiColor"
EMISSIVE_TARGETS = ("Emissive_Color", "Emissive_Power")


def split_emissive(factor):
    """``(rgba, power)`` for MDF, from mrl3's emissive factor.

    mrl3 lets the factor exceed 1, and uses the excess as *brightness*: a value of
    ``(7, 7, 7)`` reads as white at seven times the intensity, not as some brighter
    white -- on screen it is indistinguishable from ``(1, 1, 1)`` until you notice the
    bloom.  MDF splits those two ideas into a colour and a power, so the magnitude has
    to be lifted out here or a 7x emissive lands as plain white and the glow is gone.

    The scales are not the same between the engines and there is no way to calibrate
    them offline, so the number is carried across as-is.  That inexactness is why the
    pair sits in the "all" tier rather than the basic one: the prefab's own
    colour/power pairing is already the sensible default, and anyone who wants the
    glow tuned should be tuning it deliberately.
    """
    rgb = list(factor)[:3]
    while len(rgb) < 3:
        rgb.append(0.0)
    peak = max(rgb)
    if peak > 1.0:
        rgb = [c / peak for c in rgb]
        power = peak
    else:
        power = 1.0
    return (rgb + [1.0]), power


def is_excluded(field_name):
    return (field_name in EXCLUDED_NAMES
            or field_name.startswith(EXCLUDED_PREFIXES))


def param_pairs(mode):
    """``[(mrl3 field, MDF property, converter)]`` for ``'BASIC'`` or ``'ALL'``."""
    pairs = list(BASIC_PARAMS)
    if mode == "ALL":
        pairs += [p for p in ALL_PARAMS if not is_excluded(p[0])]
    return pairs


def written_props(mode):
    """The MDF property names this port can actually write, for *mode*.

    Everything else in the material it produces is the ``basic`` prefab's own
    default, untouched -- which matters to the relay: the MHWS -> MHRS hop cannot
    tell a prefab default from an authored value, so without this list it carries
    MHWS' defaults into MHRS and overwrites MHRS' own.  ``Emissive_Intensity`` is
    the visible case (1.0 over MHRS' 0.3), ``Emissive_Color`` the quiet one.

    Derived from the pair tables rather than hand-listed, so a param added there
    is carried by the relay automatically instead of being silently dropped.
    """
    names = {dst for _src, dst, _conv in param_pairs(mode)}
    if mode == "ALL":
        names.update(EMISSIVE_TARGETS)
    return names


# ── relay support ───────────────────────────────────────────────────────────────
# Used when the port is asked for MHRS: the material half goes through the ordinary
# MHWS -> MHRS port, which skips its whole texture-binding loop when it is told not
# to convert textures -- and it is told not to, because ``mrl3_port_ops`` has
# already written them in MHRS's own container.  So the bindings are carried over
# by slot type instead.
#
# A plain name-keyed copy is enough because MHWilds and MHRS name all 15 slot types
# identically and pack them identically (measured against the registered tex
# configs); it is the same fact that lets ``mdf_port_tex.repack_slot`` rewrite the
# container without touching pixels.
#
# Duck-typed rather than bpy-typed, so it lives here with the rest of the offline-
# checkable half rather than in the ops module.

def _materials_by_name(col):
    out = {}
    for obj in col.objects:
        if obj.get("~TYPE") != "RE_MDF_MATERIAL":
            continue
        data = getattr(obj, "re_mdf_material", None)
        if data is not None:
            out[data.materialName or obj.name] = data
    return out


def carry_texture_bindings(src_col, dst_col, is_custom=None):
    """Copy texture paths from *src_col*'s materials onto *dst_col*'s, by slot type.

    Only onto slots the destination actually has, and only from source slots that
    hold *the author's own* texture.  *is_custom* is a one-argument predicate --
    in practice ``is_custom_tex_path`` bound to the source game's vanilla list.

    Skipping the non-custom ones is not an optimisation, it is the point.  Every
    prefab fills every slot, so "source path is non-empty" is true of all of them,
    and a stock path is **per game**: MHWilds' basic prefab puts
    ``MasterMaterial/Textures/NullBlack_Alpha_MSK4.tex`` in EmissiveMap and FxMap
    where MHRS's PL_Default puts ``systems/rendering/NullBlack.tex``.  Carrying
    those across replaces the destination's own correct placeholder with one that
    does not exist in the destination game -- 46064 entries in MHWilds' vanilla
    list against 26473 in MHRS's, and that path is in the first and not the
    second, so the game cannot load it and the pre-export check flags every one.

    Without a predicate every non-empty path is carried, which is the old
    behaviour and is only right when both sides share a vanilla set.
    """
    src_mats = _materials_by_name(src_col)
    carried = 0
    for name, dst_data in _materials_by_name(dst_col).items():
        src_data = src_mats.get(name)
        if src_data is None:
            continue
        src_paths = {b.textureType: b.path for b in src_data.textureBindingList_items}
        for binding in dst_data.textureBindingList_items:
            path = src_paths.get(binding.textureType)
            if not path or (is_custom is not None and not is_custom(path)):
                continue
            if binding.path != path:
                binding.path = path
                carried += 1
    return carried
