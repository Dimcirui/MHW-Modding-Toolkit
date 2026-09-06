"""Read an existing material into a MaterialIR.

One reader per source layout.  Adding support for another shader means adding a
reader here — the group builder never learns about it.

  read_flat_slots   the upstream importers' trees, via slot-named Image nodes
  read_principled   Blender's own Principled BSDF
  read_emission     an Emission shader (toon-style materials)
  read_mmd_dev      MMDShaderDev, insofar as it carries anything

``read_material`` dispatches on core.mdf_generator_base.detect_shader_type and
always layers a flat-slot read underneath, because a material imported by RE
Mesh Editor or MHW Model Editor has *both* slot-named Image nodes and a
Principled — and the slot read is the lossless one.

Node traversal reuses mdf_generator_base._collect_tex_images so there is one
implementation of "which images are upstream of here".  The terminal step
differs on purpose: the generator resolves to a *file path* and checks it exists
(it is about to convert it), while these readers resolve to the *datablock* (they
are about to build a node from it).
"""

import bpy

from .shader_ir import (
    MaterialIR, ImageRef,
    SRC_PRINCIPLED, SRC_EMISSION, SRC_MMD_DEV, SRC_FLAT_SLOTS, SRC_EMPTY,
)
from .mdf_generator_base import (
    _collect_tex_images, _find_principled_bsdf, _find_emission_shader,
    _find_mmd_shader_dev, detect_shader_type,
    SHADER_PRINCIPLED, SHADER_EMISSION, SHADER_MMD_DEV,
    PRINCIPLED_INPUT_MAP,
)
from .slot_sources import iter_slot_named_image_nodes

# Separate Color / Separate RGB output socket name -> channel letter
_SEP_CHANNEL = {'Red': 'R', 'R': 'R', 'Green': 'G', 'G': 'G',
                'Blue': 'B', 'B': 'B'}


def _image_from_socket(socket):
    """Resolve ``socket``'s upstream to (ImageRef) or None.

    Mirrors the node shapes mdf_generator_base._analyze_principled_input
    recognises — direct Image Texture, through a Normal Map, through a Separate
    Color, or any single-image chain — but yields the datablock rather than a
    path, and does not distinguish BAKE from failure: a caller that gets None
    records a warning and leaves the socket at its default.
    """
    if socket is None or not socket.is_linked:
        return None

    link = socket.links[0]
    src  = link.from_node

    if src.type == 'TEX_IMAGE':
        if not src.image:
            return None
        return ImageRef(src.image,
                        'A' if link.from_socket.name == 'Alpha' else 'R')

    if src.type == 'NORMAL_MAP':
        colour = src.inputs.get('Color')
        if not colour or not colour.is_linked:
            return None
        return _single_image(colour.links[0].from_node)

    if src.type in ('SEPARATE_COLOR', 'SEPCOLOR', 'SEPRGB'):
        ch = _SEP_CHANNEL.get(link.from_socket.name)
        if ch is None:
            return None
        sep_in = src.inputs.get('Color') or src.inputs.get('Image')
        if not sep_in or not sep_in.is_linked:
            return None
        ref = _single_image(sep_in.links[0].from_node)
        return ImageRef(ref.image, ch) if ref else None

    # Any other chain: accept it only if exactly one image feeds it, which is
    # the same "aggressive penetration" rule the generator applies to normals.
    return _single_image(src)


def _single_image(node):
    found = []
    _collect_tex_images(node, found, set())
    if len(found) != 1 or not found[0].image:
        return None
    return ImageRef(found[0].image, 'R')


# ── Readers ───────────────────────────────────────────────────────────────────

def read_flat_slots(material, slot_types):
    """Read slot-named Image Texture nodes — the upstream importers' contract.

    This is the lossless path: it recovers slots the Principled route cannot
    represent at all (AO, detail maps).  Node names only; see slot_sources for
    why topology is not treated as a contract.
    """
    ir = MaterialIR(source=SRC_FLAT_SLOTS)
    if not material or not material.use_nodes or not material.node_tree:
        return ir

    wanted = set(slot_types)
    for key, node in iter_slot_named_image_nodes(material.node_tree):
        if key not in wanted or key in ir.slots:
            continue
        img = node.image
        # Skip the 1x1 GENERATED placeholders both importers create for a
        # missing texture — they are not real data.
        if img is None or img.source == 'GENERATED':
            continue
        ir.slots[key] = ImageRef(img, 'R')
    return ir


def read_principled(material):
    """Read a Principled BSDF into PBR quantities."""
    ir = MaterialIR(source=SRC_PRINCIPLED)
    node = _find_principled_bsdf(material)
    if node is None:
        return ir

    for pbr_type, socket_name in PRINCIPLED_INPUT_MAP.items():
        socket = node.inputs.get(socket_name)
        if socket is None:
            continue

        if socket.is_linked:
            ref = _image_from_socket(socket)
            if ref is not None:
                ir.pbr[pbr_type] = ref
                if ref.channel not in ('R', 'A'):
                    ir.warn(f"{pbr_type}: taken from channel {ref.channel} of "
                            f"'{ref.name}'; the packed slot's own channel layout "
                            f"decides what that channel means", pbr_type)
            else:
                # A real node chain we cannot fold into a socket. The generator's
                # BAKE path still handles it; the group cannot show it.
                ir.warn(f"{pbr_type}: driven by a node chain that cannot be "
                        f"reduced to one image — left at its default", pbr_type)
            continue

        # Unlinked: carry the constant, exactly as Principled itself would.
        if pbr_type == 'normal':
            # Principled's Normal socket default is a meaningless (0,0,0); the
            # renderer substitutes the geometry normal. Nothing to carry.
            continue
        const = _socket_constant(socket)
        if const is not None:
            ir.pbr[pbr_type] = const

    strength = node.inputs.get('Emission Strength')
    if strength is not None and not strength.is_linked:
        ir.params['Emission Strength'] = float(strength.default_value)

    return ir


def read_emission(material):
    """Read an Emission shader — toon-style materials use these."""
    ir = MaterialIR(source=SRC_EMISSION)
    node = _find_emission_shader(material)
    if node is None:
        return ir

    colour = node.inputs.get('Color')
    if colour is not None:
        ref = _image_from_socket(colour)
        # Emission colour doubles as base colour for toon materials, which is
        # what the generator's use_toon path already assumes.
        value = ref if ref is not None else _socket_constant(colour)
        if value is not None:
            ir.pbr['emissive'] = value
            ir.pbr.setdefault('color', value)

    strength = node.inputs.get('Strength')
    if strength is not None and not strength.is_linked:
        ir.params['Emission Strength'] = float(strength.default_value)
    return ir


def read_mmd_dev(material):
    """Read MMDShaderDev.

    Carries base colour and alpha and nothing else — an MMD material has no
    metallic or roughness concept, so anything further would be invented.  The
    socket names match mdf_generator_base's _MMD_*_SOCKET constants.
    """
    ir = MaterialIR(source=SRC_MMD_DEV)
    node = _find_mmd_shader_dev(material)
    if node is None:
        return ir

    base = node.inputs.get('Base Tex')
    if base is not None:
        ref = _image_from_socket(base)
        if ref is not None:
            ir.pbr['color'] = ref
        elif not base.is_linked:
            const = _socket_constant(base)
            if const is not None:
                ir.pbr['color'] = const

    alpha = node.inputs.get('Base Alpha')
    if alpha is not None:
        ref = _image_from_socket(alpha)
        if ref is not None:
            ir.pbr['alpha'] = ref
        elif not alpha.is_linked:
            const = _socket_constant(alpha)
            if const is not None:
                ir.pbr['alpha'] = const

    ir.warn("MMDShaderDev carries only base colour and alpha; roughness, "
            "metallic and normal were left at their defaults rather than guessed")
    return ir


def read_material(material, slot_types):
    """Read ``material`` into one IR, whatever it is built from.

    Layers a flat-slot read under the shader read: an imported material has both,
    and the slot read is authoritative because it is the lossless one.  Where a
    slot supplies a quantity, apply_ir will leave the matching PBR socket
    neutral — otherwise the two would combine and double-apply.
    """
    kind = detect_shader_type(material)

    if kind == SHADER_PRINCIPLED:
        ir = read_principled(material)
    elif kind == SHADER_EMISSION:
        ir = read_emission(material)
    elif kind == SHADER_MMD_DEV:
        ir = read_mmd_dev(material)
    else:
        ir = MaterialIR(source=SRC_EMPTY)
        ir.warn("no recognised shader connected to Material Output; "
                "only slot-named texture nodes were read")

    flat = read_flat_slots(material, slot_types)
    if flat.slots:
        ir.merge_slots(flat)
        if ir.source == SRC_EMPTY:
            ir.source = SRC_FLAT_SLOTS
    return ir


def _socket_constant(socket):
    """A socket's default_value as a plain float or tuple, or None.

    Returns None rather than raising for anything not numeric.  Real Principled
    sockets are always readable, but a reader may be pointed at a node group
    whose socket is a string, a menu, or something else entirely — losing one
    preview value is not worth failing the whole conversion.
    """
    v = getattr(socket, 'default_value', None)
    if v is None:
        return None
    try:
        return tuple(float(x) for x in v)
    except TypeError:
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
