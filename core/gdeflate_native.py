"""GDeflate compression via a bundled GDeflateWrapper DLL (MIT, Windows only).

Needed only for .tex versions that require GDeflate-compressed mip data
(MHWILDS, RE9). Ported from RE-Mesh-Editor's gdeflate/gdeflate.py wrapper.
"""

import ctypes
from ctypes import c_bool, c_uint8, c_uint32, c_uint64, POINTER, byref
import os

# Buffers cross into the DLL by memcpy, never element by element.
#
# ``(c_uint8 * len(data))(*data)`` unpacks the buffer into that many *Python
# arguments* -- 16 million of them for one 4K BC7 mip -- and
# ``bytes(arr[:n])`` builds an intermediate list of ints coming back.  Measured
# on a 16.8 MB mip: the star-unpack alone was 1.59s against 0.006s for
# ``from_buffer_copy``, and it made a .tex write look like GDeflate was slow
# when the actual compression was 0.37s of a 2.31s call.
#
# ``from_buffer_copy`` rather than casting a pointer straight into the bytes
# object: the DLL takes a non-const ``uint8_t*``, and handing it the interior of
# an immutable Python bytes is only safe by inspection of code we do not own.
# The copy costs single-digit milliseconds.

FASTEST = 1      # DSTORAGE_COMPRESSION_FASTEST
DEFAULT = 9       # DSTORAGE_COMPRESSION_DEFAULT
BEST_RATIO = 12   # DSTORAGE_COMPRESSION_BEST_RATIO

_DLL = None


def _bin_dir():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root_dir, "assets", "bin", "gdeflate")


def _load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL

    dll_path = os.path.join(_bin_dir(), "GDeflateWrapper.dll")
    if not os.path.isfile(dll_path):
        raise RuntimeError(f"GDeflate library not found: {dll_path}")
    dll = ctypes.CDLL(dll_path)

    dll.gdeflate_get_compress_bound.argtypes = [c_uint64]
    dll.gdeflate_get_compress_bound.restype = c_uint64

    dll.gdeflate_compress.argtypes = [
        POINTER(c_uint8), POINTER(c_uint64), POINTER(c_uint8), c_uint64, c_uint32, c_uint32,
    ]
    dll.gdeflate_compress.restype = c_bool

    dll.gdeflate_get_uncompressed_size.argtypes = [POINTER(c_uint8), c_uint64, POINTER(c_uint64)]
    dll.gdeflate_get_uncompressed_size.restype = c_bool

    dll.gdeflate_decompress.argtypes = [
        POINTER(c_uint8), c_uint64, POINTER(c_uint8), c_uint64, c_uint32,
    ]
    dll.gdeflate_decompress.restype = c_bool

    _DLL = dll
    return dll


def compress(data, level=DEFAULT, flags=0):
    """Compress bytes with GDeflate. Returns the compressed bytes."""
    dll = _load_dll()
    bound = dll.gdeflate_get_compress_bound(c_uint64(len(data)))
    output_size = c_uint64(bound)
    output_array = (c_uint8 * bound)()
    input_array = (c_uint8 * len(data)).from_buffer_copy(data)

    ok = dll.gdeflate_compress(
        output_array, byref(output_size), input_array, c_uint64(len(data)),
        c_uint32(int(level)), c_uint32(flags),
    )
    if not ok:
        raise RuntimeError("GDeflate compression failed")
    return ctypes.string_at(output_array, output_size.value)


def get_uncompressed_size(compressed_data):
    dll = _load_dll()
    input_array = (c_uint8 * len(compressed_data)).from_buffer_copy(compressed_data)
    uncompressed_size = c_uint64(0)
    ok = dll.gdeflate_get_uncompressed_size(input_array, c_uint64(len(compressed_data)), byref(uncompressed_size))
    if not ok:
        raise RuntimeError("Failed to get GDeflate uncompressed size")
    return uncompressed_size.value


def decompress(compressed_data, num_workers=1):
    dll = _load_dll()
    output_size = get_uncompressed_size(compressed_data)
    input_array = (c_uint8 * len(compressed_data)).from_buffer_copy(compressed_data)
    output_array = (c_uint8 * output_size)()
    ok = dll.gdeflate_decompress(
        output_array, c_uint64(output_size), input_array, c_uint64(len(compressed_data)), c_uint32(num_workers),
    )
    if not ok:
        raise RuntimeError("GDeflate decompression failed")
    return ctypes.string_at(output_array, output_size)
