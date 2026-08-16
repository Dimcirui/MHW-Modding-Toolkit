"""MRL3 -> MDF2 port, texture layer: unpack MHWI's packed slots into PBR planes.

``core/mdf_tex_processor_base._compose_channels`` already goes the other way -- PBR
planes into one game's packed slots -- and its ``pbr_arrays`` argument exists for this
caller specifically.  What was missing is the half in front of it: MHWI's textures are
packed too, so a port has to *unpack* them first.  Slot -> PBR -> slot is the whole
pipeline, and this module is the first arrow.

**Decoding is not the encoding table read backwards.**  A channel map's entries are
one of three things -- a ``(pbr_type, index)`` tuple, a constant like ``1.0``, or
``None`` meaning "write zero".  Only the tuples carry information; the other two are
what the *writer* puts in a channel nothing feeds.  Reading them back would invent a
PBR plane out of padding.  So the decode table below lists only the channels that
genuinely hold something, and it is written out rather than derived, because two of
its entries disagree with the encode side on purpose:

* ``RMTMap.B`` is **translucency**.  MHWI's RMT is Roughness / Metallic /
  Translucency, and ``games/mhwi/mrl3_tex_processor.MHWI_SLOT_CHANNEL_MAPS`` has that
  channel as ``None`` -- correct or not for MHWI's own export path, reading it as
  nothing here would silently drop every skin and thin-cloth material's translucency
  on the way to MHWilds.  Left as a deliberate difference rather than changing the
  export map, which is a shipped behaviour and a separate question.
* ``AlbedoMap.A`` is **opacity**, and it must not travel with the colour.  MHWilds'
  ``BaseDielectricMap.A`` is *inverted metallic*, so a slot-to-slot copy of the albedo
  would feed opacity into the metal channel and turn the whole model to chrome.  Here
  it becomes the ``alpha`` plane, which the encoder then routes to
  ``AlphaTranslucentOcclusionSSSMap.R``.

MHWI has no AO channel at all (``RMTMap.B`` is translucency, not occlusion), so no
``ao`` plane is produced.  That is not a gap to fill: ``PBR_DEFAULTS['ao']`` is white,
so leaving it absent gives exactly the white AO the user asked for.

Free of ``bpy``: takes and returns numpy arrays, so the channel routing can be tested
without Blender.
"""

import numpy as np

#: ``{MHWI slot: {channel: (pbr_type, plane index)}}`` -- only channels that carry
#: data.  Channels a slot pads with a constant are absent by design; see the module
#: docstring.
DECODE_MAP = {
    'AlbedoMap': {
        'R': ('color', 0),
        'G': ('color', 1),
        'B': ('color', 2),
        'A': ('alpha', 0),
    },
    'NormalMap': {
        'R': ('normal', 0),
        'G': ('normal', 1),
    },
    'RMTMap': {
        'R': ('roughness', 0),
        'G': ('metallic', 0),
        'B': ('translucency', 0),
    },
    'EmissiveMap': {
        'R': ('emissive', 0),
        'G': ('emissive', 1),
        'B': ('emissive', 2),
        'A': ('emissive', 3),
    },
}

#: Slots that go across as-is rather than through the PBR pivot: MHWilds has a slot
#: that means the same thing, and the contents are a mask whose channels have no PBR
#: reading to decompose into.
DIRECT_SLOTS = {
    'ColorMaskMap': 'ColorLayer_MaskMap',
    'FxMap': 'FxMap',
}

#: MHWI slots with no MHWilds counterpart.  Reported, not silently dropped.
UNPORTABLE_SLOTS = ('FurVelocityMap', 'FurMap')

#: Same values as ``mdf_tex_processor_base.PBR_DEFAULTS``, restated here because that
#: module needs ``bpy``.  ``tests/test_mrl3_port_tex.py`` pins the two in step.
PBR_DEFAULTS = {
    'color':        (0.0, 0.0, 0.0, 1.0),
    'alpha':        (1.0, 1.0, 1.0, 1.0),
    'emissive':     (0.0, 0.0, 0.0, 0.0),
    'normal':       (0.5, 0.5, 1.0, 1.0),
    'roughness':    (1.0, 1.0, 1.0, 1.0),
    'metallic':     (0.0, 0.0, 0.0, 1.0),
    'ao':           (1.0, 1.0, 1.0, 1.0),
    'cavity':       (1.0, 1.0, 1.0, 1.0),
    'translucency': (0.0, 0.0, 0.0, 1.0),
}

_CHANNEL_INDEX = {'R': 0, 'G': 1, 'B': 2, 'A': 3}


def _resize_nearest(arr, height, width):
    """Nearest-neighbour resample.  Returns *arr* untouched when already that size."""
    h, w = arr.shape[:2]
    if (h, w) == (height, width):
        return arr
    rows = (np.arange(height) * h // height).clip(0, h - 1)
    cols = (np.arange(width) * w // width).clip(0, w - 1)
    return arr[rows[:, None], cols[None, :]]


def decompose(slot_arrays, decode_map=None):
    """``({pbr_type: (h, w, 4) float32}, [notes])`` from MHWI's packed slot images.

    *slot_arrays* is ``{slot type: (h, w, 4) float32}``; slots the material does not
    use are simply absent.

    Every plane comes out at one size, the largest input's.  ``_compose_channels``
    now scales mismatched ``pbr_arrays`` entries as well -- it used to drop them, and
    this port is what made that reachable, since MHWI is free to give a 512px RMT to
    a 2048px albedo -- so this is no longer load-bearing.  It is kept because it is
    the layer that can say *which slot* was rescaled: by the time the planes reach
    the encoder they are anonymous quantities, and "roughness was 512px" is a much
    worse report than "RMTMap was".  Resampling is nearest-neighbour, sufficient
    because a material's slots normally already agree.

    A plane is created only when some channel writes to it, and it starts from that
    quantity's neutral default, so a slot that supplies two of four channels does not
    leave the other two at zero.
    """
    decode_map = decode_map or DECODE_MAP
    usable = {s: a for s, a in slot_arrays.items()
              if a is not None and s in decode_map}
    if not usable:
        return {}, []

    height, width = max((a.shape[:2] for a in usable.values()),
                        key=lambda hw: hw[0] * hw[1])
    notes = []

    out = {}
    for slot, arr in sorted(usable.items()):
        if arr.shape[:2] != (height, width):
            notes.append(f"{slot}: {arr.shape[1]}x{arr.shape[0]} -> {width}x{height}")
            arr = _resize_nearest(arr, height, width)
        for channel, (pbr_type, index) in sorted(decode_map[slot].items()):
            plane = out.get(pbr_type)
            if plane is None:
                plane = np.empty((height, width, 4), dtype=np.float32)
                plane[:] = PBR_DEFAULTS[pbr_type]
                out[pbr_type] = plane
            plane[..., index] = arr[..., _CHANNEL_INDEX[channel]]
    return out, notes


def unportable(slot_arrays):
    """Slots the source uses that MHWilds has nowhere to put."""
    return sorted(s for s in slot_arrays
                  if s in UNPORTABLE_SLOTS and slot_arrays[s] is not None)


# ── flat-texture measurement (the MHRS Nuki_Dissolve rule) ──────────────────────
#
# See ``mrl3_port.nuki_dissolve`` for what the answers are used for.  The reading is
# here because it is pixel work, and it is numpy so it stays offline-checkable.

#: How far a channel may wander and still count as flat.  **Not zero, and it cannot
#: be**: MHWI's ``.tex`` are block-compressed, and BC1/BC7 are lossy, so a texture
#: authored as pure white decodes to values a hair under 1.0 that differ per block.
#: One 8-bit step is the smallest tolerance that survives that without admitting a
#: gradient -- a real dissolve mask spans far more than 1/255.
FLAT_TOL = 1.0 / 255.0


def flat_value(arr, index, tol=FLAT_TOL):
    """The channel's value if it is one value across the whole image, else None.

    The midpoint of the observed range rather than any single pixel, so a channel
    that decoded to 0.996..1.000 answers with its centre instead of whichever corner
    happened to be sampled.
    """
    channel = arr[..., index]
    lo, hi = float(channel.min()), float(channel.max())
    if hi - lo > tol:
        return None
    return (lo + hi) / 2.0


def is_flat_rgb(arr, value, tol=FLAT_TOL):
    """Is every RGB pixel *value*?  Alpha is not looked at."""
    rgb = arr[..., :3]
    return bool(float(np.abs(rgb - value).max()) <= tol)


def albedo_alpha_strength(arr, tol=FLAT_TOL):
    """The constant opacity of a white albedo, or None if it is not one.

    "Not one" covers both halves of the test: an albedo with actual colour in it is
    carrying the material's look and must not be reduced to a dissolve number, and an
    albedo whose alpha varies per pixel is a real cutout mask, which a single scalar
    cannot stand in for either.
    """
    if arr is None:
        return None
    if not is_flat_rgb(arr, 1.0, tol):
        return None
    return flat_value(arr, 3, tol)


def is_flat_emissive(arr, tol=FLAT_TOL):
    """Is the emissive map uniformly white or uniformly black?

    Either way it holds no pattern, which is what the rule needs to know; the two are
    not distinguished because the emissive *factor* is what scales them, and a flat
    map of either colour leaves the surface's dissolve unaffected.  Alpha is ignored
    for the same reason it is in ``is_flat_rgb``.
    """
    if arr is None:
        return False
    return is_flat_rgb(arr, 1.0, tol) or is_flat_rgb(arr, 0.0, tol)
