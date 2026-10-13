"""
qr_envelope.py — thin adapter that re-exports the canonical ae.envelope.

The canonical module lives at aeqr/ae/envelope.py. This shim exists so that
existing `from ae import envelope as qe` calls in the fleet agents continue to work
without modification. New code should import from ae directly:

    from ae import envelope as qe
"""
import sys, pathlib
_AEQR = pathlib.Path(r"C:/æ/aeqr")
if str(_AEQR) not in sys.path:
    sys.path.insert(0, str(_AEQR))

from ae.envelope import *  # noqa: F401,F403
from ae.envelope import encode, decode, TYPES, MAGIC, VERSION, LEGACY_PREFIX  # noqa: F401
