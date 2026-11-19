"""Compatibility shim — the rasteriser now lives in tinyCUDA.

tinyGPU used to carry its own copy of the CUDA kernels. Two copies drift, so
the primitive was extracted: `tinycuda.py` is the rasteriser, and this module
re-exports it under the names existing callers use.

    from rtx_raster import RtxRenderer, persp, look_at   # still works
    from tinycuda import Raster                          # the real name
"""
from tinycuda import Raster as RtxRenderer, persp, look_at, load_stl, fit_camera

__all__ = ['RtxRenderer', 'persp', 'look_at', 'load_stl', 'fit_camera']
