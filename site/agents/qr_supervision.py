"""
qr_supervision.py — thin adapter that re-exports the canonical ae.supervision.

The canonical module lives at aeqr/ae/supervision.py. This shim exists so that
existing `from ae import supervision as qs` calls in the fleet agents continue to work
without modification. New code should import from ae directly:

    from ae import supervision as qs
"""
import sys, pathlib
_AEQR = pathlib.Path(r"C:/æ/aeqr")
if str(_AEQR) not in sys.path:
    sys.path.insert(0, str(_AEQR))

from ae.supervision import *  # noqa: F401,F403
from ae.supervision import produce, supervise, selftest, render_verified  # noqa: F401
from ae.supervision import _render, _estimate_modules_side, _verify_links  # noqa: F401
from ae.supervision import chain_verify, chain_prev, chain_append  # noqa: F401
from ae.supervision import decoders_available, require_armed, GateUnarmed  # noqa: F401
