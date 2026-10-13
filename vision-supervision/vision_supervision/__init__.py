"""
vision_supervision — compatibility shim (unified toolchain).

The canonical computer-vision engine now lives in ONE place:

    C:/æ/supervisionvidaeo/supervisionvidaeo/vision/

This package re-exports it under the historical name `vision_supervision`, so
every existing import keeps working while there is a single source of truth —
no more 9/10-identical vendored copies silently drifting apart.

    vision_supervision.X is supervisionvidaeo.vision.X     # the same object

Deep imports (`vision_supervision.qr_coder`, ...) resolve through the
sys.modules aliases registered below, so `from vision_supervision.<mod> import
X` finds the canonical module without a physical file.
"""
from __future__ import annotations

import importlib
import pathlib
import sys

# Locate the canonical package from this monorepo checkout and make it
# importable, so the shim is self-contained (no install step required).
_here = pathlib.Path(__file__).resolve().parent           # .../vision-supervision/vision_supervision
_canon = _here.parent.parent / "supervisionvidaeo"         # C:/æ/supervisionvidaeo
if _canon.is_dir() and str(_canon) not in sys.path:
    sys.path.insert(0, str(_canon))

from supervisionvidaeo import vision as _vision  # noqa: E402

# Alias every submodule so `from vision_supervision.<mod> import X` resolves to
# the canonical module. The import system checks sys.modules before it ever
# looks for a file, so these aliases win over any stale on-disk copy.
_SUBMODULES = (
    "deteccion", "anotador", "rastreador", "procesador", "metricas",
    "detectores", "qr_vision", "qr_coder", "video_supervision",
)
for _name in _SUBMODULES:
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(
        f"supervisionvidaeo.vision.{_name}"
    )

# Re-export the full public surface under the historical name.
from supervisionvidaeo.vision import *  # noqa: E402,F401,F403
from supervisionvidaeo.vision import __version__  # noqa: E402,F401
__all__ = [
    "Deteccion",
    "LoteDetecciones",
    "Anotador",
    "RastreadorIOU",
    "ProcesadorVideo",
    "Metricas",
    "DetectorColor",
    "DetectorMovimiento",
    "QRDeteccion",
    "LoteQRs",
    "DetectorQR",
    "ProcesadorQRVideo",
    "QRCode",
    "QRLote",
    "QRCoder",
    "QRBatchCoder",
    "FrameAnalysis",
    "VideoReport",
    "SupervisorVideo",
    "supervisar_video",
]
