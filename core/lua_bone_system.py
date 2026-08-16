"""LuaBoneSystem custom-offset JSON, written from a Blender rig.

MHRS has one skeleton per character, so the usual way to give an armour set its
own proportions -- exporting a reshaped ``{gender}_shadow.mesh`` over
``mod/{gender}/bone/`` -- reshapes *every* outfit at once.  LuaBoneSystem is the
way around that: a REFramework script that, each frame, moves the player's joints
by a per-equipment offset table read from
``reframework/data/LUABoneSystem/custom/<part file name>.json``.

The table the script writes when the user presses its own "Bind" button is

    offset[joint] = LocalPosition(equipped rig)[joint] - LocalPosition(base rig)[joint]

which is a **parent-relative rest translation difference, in the game's own
coordinates** -- and that is a thing Blender already has, so the round trip
through the game is not necessary.  ``bone.matrix_local`` relative to the parent's
reproduces the game's ``LocalPosition`` exactly: three independently recorded
tables (two armour sets from a mod pack, one from a live MHRise install) each
round-trip to their rig with a maximum error of 1.6e-7 m, which is float32
round-off, not a discrepancy.

Two things the recorded tables show that a naive subtraction would get wrong:

* **Seven joints are always zero.**  ``Root``, ``Cog``, ``Face_Parts``,
  ``LookAt``, ``PL_Cam`` and the two ``*_Foot_IK`` are control joints, not deform
  joints; the script's own base table omits them entirely and its ``nil`` branch
  writes zeros.  Writing a computed offset for them instead would move things the
  game never intends the mesh to move.
* **The five files are identical.**  The script scans the equipped parts and uses
  the *first* json it manages to load for the whole player (``player_joint`` is one
  name, not five), so five different tables would mean an arbitrary winner.  Every
  reference set ships five byte-identical files, and this writes them the same way
  -- one rig in, five copies out.  ``f_body279.json`` measured against an
  ``f_arm279`` rig matches 72/72, which is the same fact from the other side.
"""

import json
import os

#: Control joints the game never takes from the mesh -- always written as zero.
#: See the module docstring; this is the explicit form of the script's ``nil``
#: branch, which cannot be inferred from the reference rig because the reference
#: rig *does* carry all seven.
ZERO_JOINTS = frozenset((
    "Root", "Cog", "Face_Parts", "LookAt", "PL_Cam", "L_Foot_IK", "R_Foot_IK",
))

#: Below the mod root, next to ``natives``.  REFramework reads it from the game
#: folder, so a mod ships it at the same level as the files it overrides.
CUSTOM_DIR = ("reframework", "data", "LUABoneSystem", "custom")

#: The five armour parts, using MHRS' own part codes -- the json file name is the
#: part's mesh file name, so these have to be spelled the way the game spells them.
PART_CODES = ("body", "helm", "arm", "wst", "leg")


def local_rest_positions(armature_obj):
    """``{bone name: (x, y, z)}`` -- each bone's rest head relative to its parent.

    The game's ``get_BaseLocalPosition`` in Blender's terms.  Read off
    ``matrix_local`` rather than ``head_local``: the parent's rest *orientation*
    is part of the frame the child's position is expressed in, and a rig whose
    bones roll (every ported one does) would otherwise come out rotated.

    No axis conversion, because there is none to do -- RE Mesh Editor imports the
    rig in the game's own Y-up frame and leaves the armature object unrotated.
    """
    out = {}
    for bone in armature_obj.data.bones:
        if bone.parent is not None:
            mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
        else:
            mat = bone.matrix_local
        t = mat.to_translation()
        out[bone.name] = (t.x, t.y, t.z)
    return out


def build_offsets(target, base):
    """The offset table for a rig, given *target* and *base* rest positions.

    Keyed on *base*, not on *target*: the joint set the game moves is the base
    skeleton's, so an armour's own bones (``Wing_153`` and friends) are dropped
    and a joint the part's rig happens to lack -- ``f_arm279`` carries no
    ``Root`` -- is still written, as zero.  A recorded table has exactly the base
    skeleton's 79 keys whatever the armour is, and this reproduces that.
    """
    out = {}
    for name, b in base.items():
        t = None if name in ZERO_JOINTS else target.get(name)
        if t is None:
            out[name] = {"x": 0.0, "y": 0.0, "z": 0.0}
        else:
            out[name] = {"x": t[0] - b[0], "y": t[1] - b[1], "z": t[2] - b[2]}
    return out


def custom_dir(mod_root):
    return os.path.join(mod_root, *CUSTOM_DIR)


def file_names(gender, armor_id):
    """The five file names for one armour set, e.g. ``f_body279.json``.

    Built the same way ``games/mhrs/batch_export._make_filepath`` builds the mesh
    name, because it *is* that name with a different extension -- the script keys
    its lookup on the part GameObject's name, which the game takes from the file.
    """
    return [f"{gender}_{part}{armor_id}.json" for part in PART_CODES]


def write(mod_root, gender, armor_id, offsets):
    """Write the five identical json files.  Returns the paths written."""
    out_dir = custom_dir(mod_root)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name in file_names(gender, armor_id):
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(offsets, fh, indent=4, sort_keys=True)
        written.append(path)
    return written
