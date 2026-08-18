"""Coefficient fixups applied to a generated MHWI material after its preset loads.

A preset carries one fixed ``surfaceCoef``/``alphaCoef`` pair, which is right for
the material the preset was captured from and wrong for anything that turned out
transparent: ``Standard.json`` ships ``alphaCoef[2] = 4`` (opaque), so an albedo
with real transparency in its A channel came out of the generator fully solid and
had to be fixed by hand in MHW Model Editor's panel, per material.

The one rule here restores the transparent pair when the generated albedo
actually has non-white alpha.  Deliberately narrow:

* It only fires for the two master materials the values were measured on
  (``PL_Mt`` and ``Npc_Mt``).  ``mmtrName`` is the shader the coefs are
  interpreted by, so a value verified under one says nothing about another.
* It only *sets* the transparent pair -- it never clears it back to opaque.  A
  preset that already names a transparent variant was chosen deliberately.

Free of ``bpy``: the measuring lives in the generator, the decision is a table.

The values are the user's, verified in game (2026-08-18).  Note they do not line
up with ``core/mrl3_port.py``'s reading of ``alphaCoef[2]``, which has 1 = "alpha
follows the albedo map's A channel" and 5 = "follows the mrl3 albedo factor's A":
this rule triggers on the albedo map's A but writes 5.  The in-game result is the
authority; the port's decode table is a separate, weaker inference (it only ever
needed "does this material use alpha at all", and 5 is in its transparent set
either way), so nothing there changes.
"""

#: ``mmtrName`` values the pair below was measured under, lowercased for compare.
TRANSPARENT_MMTRS = frozenset({"pl_mt", "npc_mt"})

#: What a transparent material of those two types wants instead of the preset's.
TRANSPARENT_SURFACE_COEF = (1, 17)
TRANSPARENT_ALPHA_COEF = (128, 112, 5, 0)


def transparent_coefs(mmtr_name, albedo_alpha_is_white):
    """``(surfaceCoef, alphaCoef)`` to write, or None to leave the preset alone.

    *albedo_alpha_is_white* is the generator's measurement of the albedo it just
    wrote; None means it could not be measured (no texture was produced, e.g.
    "Materials Only"), which leaves the preset alone rather than guessing.
    """
    if albedo_alpha_is_white is not False:
        return None
    if (mmtr_name or "").strip().lower() not in TRANSPARENT_MMTRS:
        return None
    return TRANSPARENT_SURFACE_COEF, TRANSPARENT_ALPHA_COEF
