"""Pre-export check, rules layer: what counts as broken, and how to name it.

Three separate questions, deliberately kept apart from the operator that runs
them so each can be checked offline (``tests/test_pre_export_check.py``):

1. **Does a texture binding resolve?**  A path is fine if it is a vanilla game
   asset or if the file is actually on disk under the user's mod root.
   Anything else is a dangling reference the game will fail on.
2. **Do the meshes and the materials line up?**  RE Mesh derives a submesh's
   material name from its object name, so a mesh whose derived name matches no
   material -- or a material no mesh asks for -- is a broken export.
3. **Is a material name legal?**  Separate from (2) because an illegal name can
   match perfectly and still export wrong.

**The legality rules are not RE Mesh Editor's.**  Its exporter does
``name.split("__", 1)[1].split(".")[0]``, which truncates at the *first* dot --
so ``Mat.Body`` silently exports as ``Mat``.  Since people do name materials
that way, following the exporter's parse verbatim would make this check declare
a name fine and then have it export as something else.  This module instead
strips only Blender's own ``.NNN`` de-duplication suffix and judges the rest,
which is what the user actually typed.
"""

import os
import re

#: Blender's own de-duplication suffix -- ``.001``, never anything else.
_DEDUP_SUFFIX = re.compile(r'\.\d{3}$')

#: ``[LOD_n_]Group_x_Sub_y__<material name>``.  The material half is captured
#: raw, illegal characters and all: judging it is the next step's job, and a
#: name has to be *found* before it can be judged.  The index half is captured
#: too, so ``rebuild_mesh_name`` can put a corrected material name back behind
#: the same prefix instead of reconstructing it from parsed integers.
_MESH_NAME = re.compile(r'^(?P<prefix>(?:LOD_\d+_)?Group_\d+_Sub_\d+)__(?P<mat>.+)$')

#: The same shape with one underscore where there should be two -- by far the
#: most common way to get the format wrong, and worth its own message rather
#: than a generic "does not match".
_MESH_NAME_SINGLE = re.compile(
    r'^(?P<prefix>(?:LOD_\d+_)?Group_\d+_Sub_\d+)_(?P<mat>[^_].*)$')

# Reason codes. The operator turns these into translated text; keeping them as
# codes means the rules layer has no opinion about wording or language.
SPACE = 'space'
DOT = 'dot'
LEADING_UNDERSCORE = 'leading_underscore'
EMPTY = 'empty'
SINGLE_UNDERSCORE = 'single_underscore'

#: Texture binding verdicts.
TEX_OK = 'ok'              # a vanilla asset, or found on disk
TEX_MISSING = 'missing'    # neither vanilla nor present under the mod root
TEX_EMPTY = 'empty'        # the binding has no path at all

#: The two halves of ``TEX_OK``.  The report has to tell them apart even though
#: neither is a problem on its own: "no custom texture resolved anywhere" is the
#: signal that the mod root points somewhere wrong, and a mod that is entirely
#: vanilla-textured must not trip it (see ``texture_verdict``).
TEX_VANILLA = 'vanilla'    # a path in the game's own shipped asset list
TEX_FOUND = 'found'        # the user's own asset, present under the mod root

#: Texture *file* verdicts, for the ones that did resolve. Separate from the
#: binding verdicts above because they answer a different question: not "is the
#: file there" but "is the file itself built right".
TEXF_OK = 'ok'
TEXF_NOT_POW2 = 'not_pow2'      # a side that is not a power of two
TEXF_UNREADABLE = 'unreadable'  # no readable .tex header -- often a renamed .png/.dds

#: What the whole texture scan adds up to.
TEXV_OK = 'ok'
TEXV_ROOT_WRONG = 'root_wrong'   # nothing custom resolved -- wrong root, or no textures built
TEXV_MISSING = 'missing'         # some resolved, some did not -- genuinely absent files


def strip_dedup_suffix(name):
    """``Foo.001`` -> ``Foo``.  Only the trailing three-digit suffix Blender
    adds itself; a dot anywhere else is the user's own and is a finding, not
    something to quietly remove."""
    return _DEDUP_SUFFIX.sub('', name or '')


def parse_mesh_name(obj_name):
    """``(material_name, how)`` for a mesh object name.

    *how* is ``'format'`` when the name is the proper
    ``Group_x_Sub_y__Name``, ``'single_underscore'`` when it is that shape with
    one underscore instead of two, and ``'no_format'`` when it is neither -- in
    which case *material_name* is None and the caller falls back to the object's
    Blender material, the same fallback RE Mesh's exporter uses.
    """
    stripped = strip_dedup_suffix(obj_name)
    m = _MESH_NAME.match(stripped)
    if m:
        return m.group('mat'), 'format'
    m = _MESH_NAME_SINGLE.match(stripped)
    if m:
        return m.group('mat'), 'single_underscore'
    return None, 'no_format'


def name_problems(name):
    """Reason codes for a material name, empty list when it is fine.

    Order is stable so a report reads the same way twice.
    """
    out = []
    if not name:
        return [EMPTY]
    if ' ' in name:
        out.append(SPACE)
    if '.' in name:
        out.append(DOT)
    if name.startswith('_'):
        out.append(LEADING_UNDERSCORE)
    return out


def fix_name(name):
    """A legal name: illegal characters become ``_``, except at the very front
    where they become ``0`` (a name may not start with an underscore, so
    replacing with one there would not fix anything).
    """
    if not name:
        return '0'
    chars = []
    for i, ch in enumerate(name):
        illegal = ch in ' .' or (i == 0 and ch == '_')
        if not illegal:
            chars.append(ch)
        else:
            chars.append('0' if i == 0 else '_')
    return ''.join(chars)


def rebuild_mesh_name(obj_name, new_mat):
    """*obj_name* with its material half replaced by *new_mat*, or None when the
    name has no ``Group_x_Sub_y`` prefix to keep.

    Also the one place the single-underscore slip is repaired: the rebuilt name
    always uses ``__``, so fixing a name and fixing the separator are the same
    operation rather than two passes that could disagree.

    Blender's own ``.NNN`` suffix is dropped rather than carried across -- it is
    a de-duplication artifact, and if the new name still collides Blender adds a
    fresh one on assignment.
    """
    stripped = strip_dedup_suffix(obj_name)
    m = _MESH_NAME.match(stripped) or _MESH_NAME_SINGLE.match(stripped)
    if not m:
        return None
    return f"{m.group('prefix')}__{new_mat}"


def plan_name_fixes(material_names, mesh_entries):
    """Every rename one "fix the names" pass should make, in three buckets.

    *mesh_entries* is ``[(object_name, derived_material_name, how)]`` as
    ``parse_mesh_name`` classifies them.  Returns::

        {'materials':  {old_material_name: new},   # mdf Material Name fields
         'objects':    {old_object_name: new},     # mesh object renames
         'datablocks': {old_material_name: new}}   # Blender material datablocks

    **The three have to move together.**  Renaming only the mdf material breaks
    the very match the check exists to protect: the meshes still carry the old
    name in their own object names, so a material that matched before the fix
    dangles after it.  So a corrected name is computed once, per *name*, and
    then applied everywhere that name occurs on either side.

    ``datablocks`` is separate because it is the one bucket with reach beyond
    the collections being checked -- those are meshes whose object name carries
    no ``Group_x_Sub_y__`` at all, so their material comes from the Blender
    material datablock, which other objects anywhere in the file may share. The
    caller is expected to say so in the report rather than rename silently.

    Two bad names can correct to the same good one (``My Mat`` and ``My.Mat``
    both become ``My_Mat``). That is not special-cased: the re-check that runs
    right after a fix reports the result as a duplicate material, which is both
    true and more useful than refusing to fix either.
    """
    renames = {}
    for name in material_names:
        if name_problems(name):
            renames[name] = fix_name(name)
    for _obj_name, mat_name, how in mesh_entries:
        if how != 'no_format' and mat_name and name_problems(mat_name):
            renames.setdefault(mat_name, fix_name(mat_name))

    known_materials = set(material_names)
    materials = {old: new for old, new in renames.items() if old in known_materials}

    objects = {}
    datablocks = {}
    for obj_name, mat_name, how in mesh_entries:
        if how == 'no_format':
            # Nothing to rebuild -- there is no prefix to keep and no indices to
            # invent. Only the datablock the name fell back to can be corrected.
            if mat_name and name_problems(mat_name):
                datablocks[mat_name] = fix_name(mat_name)
            continue
        rebuilt = rebuild_mesh_name(obj_name, renames.get(mat_name, mat_name))
        # Compared against the *stripped* name so a rename is proposed only for
        # a real change, not for dropping a .001 that Blender will re-add.
        if rebuilt and rebuilt != strip_dedup_suffix(obj_name):
            objects[obj_name] = rebuilt

    return {'materials': materials, 'objects': objects, 'datablocks': datablocks}


def classify_tex_binding(path, vanilla_set, exists_fn):
    """``TEX_VANILLA`` / ``TEX_FOUND`` / ``TEX_MISSING`` / ``TEX_EMPTY``.

    *exists_fn* takes the mdf-relative path and answers whether the file is
    present under the mod root -- injected rather than doing the disk walk here
    so the rules stay testable without a mod on disk.
    """
    if not (path or '').strip():
        return TEX_EMPTY
    norm = path.replace('\\', '/').lower()
    if norm in vanilla_set:
        return TEX_VANILLA
    return TEX_FOUND if exists_fn(path) else TEX_MISSING


def is_power_of_two(v):
    return v > 0 and (v & (v - 1)) == 0


def classify_tex_size(size):
    """``TEXF_OK`` / ``TEXF_NOT_POW2`` / ``TEXF_UNREADABLE`` for one resolved
    texture, given ``(width, height)`` or ``None``.

    Both sides have to be a power of two.  The looser rule the block formats
    actually enforce is "a multiple of four", but every non-power-of-two size is
    worth flagging anyway -- mip chains stop halving cleanly -- and one rule
    means one message instead of two tiers the user then has to rank.

    ``None`` (the header would not parse) is a finding rather than a silent
    skip: a file under the mod root that is not a .tex is usually one that was
    renamed instead of converted, and the export will happily point at it.
    """
    if size is None:
        return TEXF_UNREADABLE
    w, h = size
    return TEXF_OK if (is_power_of_two(w) and is_power_of_two(h)) else TEXF_NOT_POW2


def classify_tex_path(path, vanilla_set, exists_fn):
    """``TEX_OK`` / ``TEX_MISSING`` / ``TEX_EMPTY`` for one binding -- the
    coarse view, for callers that only care whether the path resolves."""
    verdict = classify_tex_binding(path, vanilla_set, exists_fn)
    return TEX_OK if verdict in (TEX_VANILLA, TEX_FOUND) else verdict


def texture_verdict(n_found, n_missing):
    """What to *say* about a texture scan, given how many of the user's own
    textures resolved and how many did not.

    The distinction the user asked for: when nothing custom resolved at all, the
    likely cause is a mod root pointing at the wrong directory (or textures that
    were never built), and listing forty paths that are all wrong for the same
    single reason buries that. When some resolved and some did not, the ones
    that did not are genuinely missing files and every one is worth naming.

    Known limit, accepted deliberately: a mod that is almost entirely vanilla
    textures and is missing only its own one or two files lands in
    ``TEXV_ROOT_WRONG`` and gets told to check its mod root. *n_found* counts
    only custom textures, so there is no vanilla count that could separate the
    two cases -- the mod really does have zero resolving custom textures.
    """
    if n_missing == 0:
        return TEXV_OK
    return TEXV_ROOT_WRONG if n_found == 0 else TEXV_MISSING


def match_meshes_to_materials(mesh_entries, material_names):
    """``(unmatched_meshes, unused_materials)``.

    *mesh_entries* is ``[(object_name, derived_material_name)]`` and
    *material_names* the mdf collection's material names.  A mesh may share a
    material with others and a material may serve several meshes, but neither
    side may dangle: a mesh with no material does not export, and a material no
    mesh asks for is dead weight that usually means a rename went half-done.
    """
    available = set(material_names)
    used = set()
    unmatched = []
    for obj_name, mat_name in mesh_entries:
        if mat_name in available:
            used.add(mat_name)
        else:
            unmatched.append((obj_name, mat_name))
    unused = [m for m in material_names if m not in used]
    return unmatched, unused


def duplicate_material_names(material_names):
    """Names appearing more than once in one .mdf2 collection."""
    seen, dupes = set(), []
    for n in material_names:
        if n in seen and n not in dupes:
            dupes.append(n)
        seen.add(n)
    return dupes


def resolve_disk_path(natives_root, mdf_path, tex_version):
    """Where a binding's ``.tex`` should sit under the user's mod root.

    Mirrors ``core/mdf_port_tex.resolve_source_disk_path``; kept as its own
    small function so this module does not pull the port in.
    """
    rel = (mdf_path or '').replace('\\', '/').lstrip('/')
    return os.path.join(natives_root, 'natives', 'STM', *rel.split('/')) + f'.{tex_version}'
