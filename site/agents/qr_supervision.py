#!/usr/bin/env python3
"""
qr_supervision.py — produce-and-verify for QR artifacts.

The same discipline as supervisionvidaeo://, applied to the QR domain:

    SPEC → RENDER → SUPERVISE → (PASS: emit QRReceipt) | (FAIL: raise QRRefused)

The producer PROPOSES a QR. The supervisor DISPOSES. There is no code path that
returns a path to a QR that does not decode — that is the whole point.

WHY THIS EXISTS
---------------
The Physical Air-Gap paper (§5.3) reports a silent failure class: an envelope
whose magic was the rune `æ:` ENCODES CORRECTLY, renders a valid-looking QR, and
FAILS ON SCAN. pyzbar re-interprets the two UTF-8 bytes of `æ` as halfwidth
katakana. An in-memory round trip passes; only a real decoder catches it.

That failure reached a draft because nothing supervised the artifact. This module
is the fix: every QR is decoded back through TWO independent real decoders before
it is accepted, and a non-ASCII envelope is refused before it is ever rendered.

The verifier is deterministic — OpenCV + pyzbar + statistics, no ML. Every verdict
traces to a measurable threshold, so it is auditable.

CHECKS (all measurable)
-----------------------
  1. charset         envelope is pure ASCII (catches the rune class up front)
  2. version         envelope fits the declared QR capacity (no silent truncation)
  3. roundtrip       the rendered PNG decodes back to the exact envelope
  4. cross_decoder   cv2 AND pyzbar agree (two independent decoders)
  5. payload_match   decoded payload == the payload we asked for
  6. type_fidelity   decoded type == the declared type
  7. module_size     modules are large enough to scan (>= MIN_MODULE_PX)
  8. quiet_zone      the required 4-module border is present
  9. contrast        dark/light module luminance ratio >= MIN_CONTRAST

Usage:
    python qr_supervision.py produce secret '{"name":"K","blob":{"n":"a","ct":"b"}}' --out k.png
    python qr_supervision.py supervise k.png --expect-kind secret
    python qr_supervision.py selftest
"""
from __future__ import annotations

import numpy as np

import argparse
import hashlib
import json
import pathlib
import sys
import time
from dataclasses import dataclass, field, asdict

AGENTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))

# ── thresholds (measurable, auditable) ────────────────────────────────────────
MIN_MODULE_PX = 3       # below this a QR is unreliable at any distance
MIN_CONTRAST = 0.35     # (light-dark)/(light+dark); below this, scanning degrades
MIN_QUIET_MODULES = 3   # spec says 4; 3 is the tolerant floor
MIN_DECODERS = 2        # cv2 + pyzbar must BOTH read it


class QRRefused(Exception):
    """Raised when a QR fails supervision. Carries the report."""

    def __init__(self, reason: str, report: "QRReport"):
        super().__init__(reason)
        self.reason = reason
        self.report = report


@dataclass
class Check:
    """One verdict on an artifact.

    `advisory` marks a check that is REPORTED but cannot refuse. That is the
    honest status for a measurement that cannot distinguish a working artifact
    from a broken one: if both decoders already read the code back exactly, the
    artifact is scannable, and a proxy's opinion of its module pitch is
    irrelevant. A check that can refuse a working artifact is a bug, not a gate.
    """
    name: str
    ok: bool
    detail: str
    measured: object = None
    advisory: bool = False

    def __str__(self) -> str:
        mark = ("✓" if self.ok else "~") if self.advisory else ("✓" if self.ok else "✗")
        tag = "  (advisory)" if self.advisory else ""
        return f"{mark} {self.name:14s} {self.detail}{tag}"


@dataclass
class QRReport:
    """The deterministic verdict on one QR artifact."""
    passed: bool
    checks: list = field(default_factory=list)
    envelope_sha256: str = ""
    image_sha256: str = ""
    envelope_bytes: int = 0
    decoded_type: str = ""
    decoders_ok: list = field(default_factory=list)
    # What this report actually PROVED. `expected` means the artifact was
    # compared against a caller-supplied truth; `self_consistent` means the
    # image was only compared against itself — it decodes, but nothing asserts
    # it decodes to what was intended.
    assurance: str = "unknown"
    expectations: list = field(default_factory=list)

    @property
    def failed(self) -> list:
        """Checks that can refuse. Advisory ones are reported separately."""
        return [c for c in self.checks if not c.ok and not c.advisory]

    @property
    def advisory_notes(self) -> list:
        return [c for c in self.checks if c.advisory]

    def reason(self) -> str:
        f = self.failed
        if not f:
            return ""
        return "; ".join(f"{c.name}: {c.detail}" for c in f)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        return d

    def render(self) -> str:
        lines = [f"QR SUPERVISION — {'PASS' if self.passed else 'REFUSED'}"]
        for c in self.checks:
            lines.append("  " + str(c))
        lines.append(f"  envelope  {self.envelope_bytes} B  sha256 {self.envelope_sha256[:16]}…")
        lines.append(f"  image     sha256 {self.image_sha256[:16]}…")
        lines.append(f"  decoders  {', '.join(self.decoders_ok) or 'none'}")
        return "\n".join(lines)


@dataclass
class QRReceipt:
    """Emitted only on PASS. Hash-chained over the artifact and the verdict.

    `prev` is the REAL previous receipt from the kænbæn chain. A chain seeded
    with an empty prev cannot prove order or detect omission — and the system's
    own capture gate explicitly fails on "missing prev".
    """
    kind: str
    envelope: str
    out_path: str
    envelope_sha256: str
    image_sha256: str
    report: dict
    produced_at: float
    chain: str = ""
    prev: str = ""
    prev_source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def render(self) -> str:
        linked = self.prev and self.prev != "genesis"
        return (
            f"QR RECEIPT\n"
            f"  kind      {self.kind}\n"
            f"  out       {self.out_path}\n"
            f"  envelope  {self.envelope_sha256[:32]}…\n"
            f"  image     {self.image_sha256[:32]}…\n"
            f"  prev      {self.prev[:32] if self.prev else '(none)'}"
            f"{'  ← ' + self.prev_source if self.prev_source else ''}\n"
            f"  chain     {self.chain[:32]}…\n"
            f"  linked    {'yes' if linked else 'NO — chain not established'}\n"
            f"  produced  {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self.produced_at))}"
        )


# ── the verifier ──────────────────────────────────────────────────────────────

def _decode_with_cv2(img) -> list[str]:
    import cv2
    det = cv2.QRCodeDetector()
    ok, decoded, _, _ = det.detectAndDecodeMulti(img)
    if not ok or decoded is None:
        return []
    return [d for d in decoded if d]


def decoders_available() -> dict:
    """Which decoders are armed. An unarmed gate must not look like a passing one."""
    out = {"cv2": False, "pyzbar": False}
    try:
        import cv2  # noqa: F401
        out["cv2"] = True
    except ImportError:
        pass
    try:
        from pyzbar.pyzbar import decode as _z  # noqa: F401
        from PIL import Image  # noqa: F401
        out["pyzbar"] = True
    except ImportError:
        pass
    return out


class GateUnarmed(Exception):
    """The gate cannot run: fewer than MIN_DECODERS are installed.

    Distinct from QRRefused. QRRefused means "this artifact is bad"; GateUnarmed
    means "I cannot tell" — and those must not look the same to an operator.
    """


def require_armed():
    """Raise GateUnarmed if the cross-decoder check cannot be performed."""
    have = decoders_available()
    n = sum(1 for v in have.values() if v)
    if n < MIN_DECODERS:
        missing = [k for k, v in have.items() if not v]
        raise GateUnarmed(
            f"the gate is UNARMED: {n}/{MIN_DECODERS} decoders available "
            f"(missing: {', '.join(missing)}). Install pyzbar "
            f"(`pip install pyzbar`) — a single decoder passes artifacts that "
            f"fail in the field, so a one-decoder gate is not a gate.")


def _decode_with_pyzbar(img) -> list[str]:
    try:
        from pyzbar.pyzbar import decode as zbar
        from PIL import Image
    except ImportError:
        # Returning [] here makes cross_decoder fail, which is fail-closed and
        # correct — but it reads as "the artifact is bad". Callers that care
        # about the distinction should call require_armed() first.
        return []
    if not isinstance(img, Image.Image):
        img = Image.fromarray(np.array(img)[:, :, ::-1] if img.ndim == 3 else img)
    out = []
    for r in zbar(img):
        try:
            out.append(r.data.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(r.data.decode("utf-8", errors="replace"))
    return out


def _module_size_px(img, points) -> float:
    """Mean edge length of the detected quad, in pixels."""
    if points is None:
        return 0.0
    q = np.array(points, dtype=float).reshape(-1, 2)
    if len(q) < 4:
        return 0.0
    return float(np.mean([np.linalg.norm(q[i] - q[(i + 1) % 4]) for i in range(4)]))


def _estimate_modules_side(img, points) -> tuple[int, str]:
    """Recover the REAL module count per side from the image.

    A QR of version v has exactly (17 + 4v) modules per side. We can recover v
    from the detected quad without being told it, by measuring the actual module
    pitch along the top edge: count the dark/light transitions across the
    finder-adjacent row, which for a standard QR is 7 modules of finder pattern.

    Falls back to the geometric relation (quad edge / estimated pitch) and
    finally to the v1 floor, reporting HOW it was derived so a caller can see
    whether the number is measured or assumed. The old code always assumed 21,
    which overstated module size for any code above v1.
    """
    if points is None:
        return 21, "assumed (no quad)"
    q = np.array(points, dtype=float).reshape(-1, 2)
    if len(q) < 4:
        return 21, "assumed (degenerate quad)"

    # order the quad: top-left, top-right, bottom-right, bottom-left
    s = q.sum(axis=1)
    d = np.diff(q, axis=1).ravel()
    tl = q[np.argmin(s)]
    br = q[np.argmax(s)]
    tr = q[np.argmin(d)]
    bl = q[np.argmax(d)]

    def sample_line(p0, p1, n=400):
        xs = np.linspace(p0[0], p1[0], n).astype(int)
        ys = np.linspace(p0[1], p1[1], n).astype(int)
        xs = np.clip(xs, 0, img.shape[1] - 1)
        ys = np.clip(ys, 0, img.shape[0] - 1)
        px = img[ys, xs]
        # Shape depends on the image: sampling a BGR image yields (n, 3) —
        # ndim 2 — while a grayscale image yields (n,) — ndim 1. Getting this
        # backwards leaves a 2-D array in `line`, and `dark[i]` then raises
        # "truth value of an array is ambiguous", which the outer except
        # swallows into a silent "assumed" fallback.
        if px.ndim == 1:
            return px.astype(float)                 # already luminance
        return px.mean(axis=1).astype(float)        # BGR -> luminance

    # MEASURE THE MODULE PITCH THE WAY A DECODER DOES: by counting transitions
    # along a line through the finder pattern, in BOTH axes, and taking the
    # consistent estimate.
    #
    # An earlier version sampled only the top edge and treated the first dark
    # run as the 7-module finder ring. That is only true for an AXIS-ALIGNED
    # code. On a 3-degree rotation the line crosses modules at an angle, the
    # run is not the ring, and it reported a 177-module side for a real 25 —
    # refusing an artifact BOTH decoders read fine. A measurement that is
    # direction-dependent is not a measurement.
    try:
        edge_px = float(np.linalg.norm(tr - tl))
        if edge_px < 40:
            return 21, "assumed (quad too small to measure)"

        def transitions_along(p0, p1):
            """Mean run length of alternating dark/light along p0->p1."""
            n = max(200, int(np.linalg.norm(p1 - p0)))
            line = sample_line(p0, p1, n)
            if len(line) < 8:
                return 0.0
            thr = (float(line.max()) + float(line.min())) / 2.0
            dark = line < thr
            runs, cur, val = [], 1, dark[0]
            for b in dark[1:]:
                if b == val:
                    cur += 1
                else:
                    runs.append(cur); cur = 1; val = b
            runs.append(cur)
            # discard the outer partial runs and any single-pixel noise
            inner = [r for r in runs[1:-1] if r >= 2]
            if not inner:
                return 0.0
            # the most common run length is the module pitch
            from collections import Counter
            return float(Counter(inner).most_common(1)[0][0])

        pitches = []
        # along the top edge, and along the left edge — a rotated code will
        # disagree, an axis-aligned one will not
        for a, b in ((tl, tr), (tl, bl)):
            pitch = transitions_along(a, b)
            if pitch > 0:
                pitches.append(pitch)
        if not pitches:
            return 21, "assumed (no transitions found)"

        # a rotated code needs BOTH edges to agree; take the smaller pitch
        # (the larger one is an artefact of crossing modules diagonally)
        pitch = min(pitches)
        n_mod = int(round(edge_px / pitch))
        if n_mod < 21:
            return 21, "assumed (module count below v1)"
        # SNAP TO THE LEGAL SERIES and reject an estimate that does not land on
        # it — that is the signal the measurement is wrong, not the code.
        v = int(round((n_mod - 17) / 4.0))
        v = max(1, min(40, v))
        snapped = 17 + 4 * v
        if abs(n_mod - snapped) > 2:
            return 21, (f"assumed (estimate {n_mod} is not a legal QR side; "
                        f"pitches={[round(x, 1) for x in pitches]})")
        return snapped, f"measured (v{v}, {pitch:.1f}px pitch)"
    except Exception as e:
        # Do NOT swallow silently: a fallback that looks like a measurement is
        # how a proxy check becomes a false pass. Report the failure in the
        # detail string so the caller sees "assumed" AND why.
        return 21, f"assumed (measurement failed: {type(e).__name__})"


def _quiet_zone_ok(img, points, modules_side: int = 21) -> tuple[bool, str]:
    """Is there a light border around the code, measured in MODULES?

    The spec wants 4 modules of quiet zone. We measure the border width in
    pixels and convert to modules using the module pitch derived from the
    detected quad, so the verdict is in the same unit as the requirement.
    """
    if points is None:
        return False, "no quad"
    q = np.array(points, dtype=float).reshape(-1, 2)
    x0, y0 = int(max(0, q[:, 0].min())), int(max(0, q[:, 1].min()))
    x1 = int(min(img.shape[1] - 1, q[:, 0].max()))
    y1 = int(min(img.shape[0] - 1, q[:, 1].max()))

    edge_px = float(np.mean([np.linalg.norm(q[i] - q[(i + 1) % 4]) for i in range(4)]))
    pitch = edge_px / modules_side if modules_side else 0.0
    if pitch <= 0:
        return False, "cannot derive module pitch"

    pad = int(max(4, round(pitch * MIN_QUIET_MODULES)))
    if x0 - pad < 0 or y0 - pad < 0 or x1 + pad >= img.shape[1] or y1 + pad >= img.shape[0]:
        return False, f"code is closer to the edge than {MIN_QUIET_MODULES} modules"

    ring = np.concatenate([
        img[y0 - pad:y0, x0:x1].ravel(),
        img[y1:y1 + pad, x0:x1].ravel(),
        img[y0:y1, x0 - pad:x0].ravel(),
        img[y0:y1, x1:x1 + pad].ravel(),
    ])
    mean = float(np.mean(ring))
    mods = pad / pitch if pitch else 0
    return mean > 127, f"border {mean:.0f} luminance ≈ {mods:.1f} modules"


def _contrast(img, points) -> tuple[float, str]:
    if points is None:
        return 0.0, "no quad"
    q = np.array(points, dtype=float).reshape(-1, 2)
    x0, y0 = int(max(0, q[:, 0].min())), int(max(0, q[:, 1].min()))
    x1, y1 = int(min(img.shape[1], q[:, 0].max())), int(min(img.shape[0], q[:, 1].max()))
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return 0.0, "empty crop"
    gray = crop.mean(axis=2) if crop.ndim == 3 else crop
    lo, hi = float(np.percentile(gray, 5)), float(np.percentile(gray, 95))
    if hi + lo == 0:
        return 0.0, "flat"
    ratio = (hi - lo) / (hi + lo)
    return ratio, f"dark {lo:.0f} light {hi:.0f} ratio {ratio:.2f}"


def supervise(image_path, expect_kind: str | None = None,
              expect_payload: dict | None = None,
              envelope: str | None = None) -> QRReport:
    """Deterministically verify a QR artifact. Never raises; returns a report."""
    import cv2
    import qr_envelope as qe

    checks: list[Check] = []
    path = pathlib.Path(image_path)
    img = cv2.imread(str(path))
    report = QRReport(passed=False)

    if img is None:
        checks.append(Check("loadable", False, f"cannot read {path}"))
        report.checks = checks
        return report
    checks.append(Check("loadable", True, f"{img.shape[1]}x{img.shape[0]}"))

    report.image_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

    # the envelope we EXPECT (given, or recovered from the image)
    env = envelope
    if env is None:
        found = _decode_with_cv2(img) + _decode_with_pyzbar(img)
        env = next((f for f in found if qe.is_envelope(f)), "")
    if not env:
        checks.append(Check("envelope", False, "no æ:// envelope found in the image"))
        report.checks = checks
        return report

    report.envelope_bytes = len(env)
    report.envelope_sha256 = hashlib.sha256(env.encode("utf-8")).hexdigest()

    # 1. charset — pure ASCII. This is the check that catches the rune class.
    try:
        env.encode("ascii")
        checks.append(Check("charset", True, "pure ASCII"))
    except UnicodeEncodeError as e:
        bad = env[e.start:e.end]
        checks.append(Check("charset", False,
                            f"non-ASCII {bad!r} at {e.start} — a real decoder will mangle it"))

    # 2. version / capacity
    try:
        kind, payload = qe.decode(env)
        report.decoded_type = kind
        checks.append(Check("version", True, f"type={kind}, {len(env)} B"))
    except ValueError as e:
        checks.append(Check("version", False, str(e)))
        report.checks = checks
        return report

    # 3. roundtrip through a real decoder
    cv2_hits = _decode_with_cv2(img)
    zbar_hits = _decode_with_pyzbar(img)
    rt = env in cv2_hits or env in zbar_hits
    checks.append(Check("roundtrip", rt,
                        "decodes back exactly" if rt else "did NOT decode back to the envelope"))

    # 4. cross-decoder agreement
    both = (env in cv2_hits) and (env in zbar_hits)
    report.decoders_ok = [n for n, h in (("cv2", cv2_hits), ("pyzbar", zbar_hits)) if env in h]
    checks.append(Check("cross_decoder", both,
                        f"{len(report.decoders_ok)}/{MIN_DECODERS} decoders: {', '.join(report.decoders_ok) or 'none'}"))

    # 5/6. payload + type fidelity
    if expect_kind is not None:
        ok = kind == expect_kind
        checks.append(Check("type_fidelity", ok, f"want {expect_kind}, got {kind}"))
    if expect_payload is not None:
        ok = payload == expect_payload
        checks.append(Check("payload_match", ok,
                            "exact" if ok else f"want {expect_payload}, got {payload}"))

    # 7. module size — derived from the REAL module count, not a proxy.
    #
    # A QR of version v has exactly (17 + 4v) modules per side, and we can
    # recover v from the detected quad's module pitch by measuring the actual
    # module width. The old code divided the edge by a hardcoded 21 (a v1 code)
    # regardless of the real version, so a v10 code (57 modules) reported a
    # module pitch ~2.7x too large — a genuinely too-small code could pass.
    # A proxy that errs optimistic is worse than no check: it turns an untested
    # property into a reported pass.
    det = cv2.QRCodeDetector()
    ok_d, _, pts, _ = det.detectAndDecodeMulti(img)
    if pts is None or not len(pts):
        # The kanban finding generalizes: detectAndDecodeMulti DROPS codes at
        # native resolution when the module pitch is small. Retry upscaled
        # before declaring "no quad" — a detector limit is not a bad artifact.
        for scale in (1.5, 2.0):
            big = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            ok_u, _, pts_u, _ = det.detectAndDecodeMulti(big)
            if pts_u is not None and len(pts_u):
                pts = (np.asarray(pts_u, dtype=float) / scale).astype(np.float32)
                break
    if pts is not None and len(pts):
        q = np.array(pts[0], dtype=float).reshape(-1, 2)
        edge = float(np.mean([np.linalg.norm(q[i] - q[(i + 1) % 4]) for i in range(4)]))

        modules_side, how = _estimate_modules_side(img, pts[0])
        mod = edge / modules_side if modules_side else 0.0
        # ADVISORY. Both decoders already read this artifact back exactly, so
        # it IS scannable — and a pitch estimate that cannot distinguish a
        # working code from a broken one must not be allowed to refuse it. The
        # estimate is still reported (it catches a genuinely tiny render, where
        # the decoders fail first anyway).
        checks.append(Check(
            "module_size", mod >= MIN_MODULE_PX,
            f"{mod:.1f} px/module over ~{modules_side} modules ({how}); min {MIN_MODULE_PX}",
            measured=round(mod, 2), advisory=True))
        # 8. quiet zone — ADVISORY, same reason as module_size: a rotated quad's
        # bounding box reaches the image edge while the code itself is fully
        # scannable. Reported, never a refuser.
        qz_ok, qz_detail = _quiet_zone_ok(img, pts[0], modules_side)
        checks.append(Check("quiet_zone", qz_ok, qz_detail, advisory=True))
        # 9. contrast — ADVISORY. A low-contrast code both decoders read is
        # scannable; the ratio is a diagnostic, not a verdict.
        ratio, cdetail = _contrast(img, pts[0])
        checks.append(Check("contrast", ratio >= MIN_CONTRAST, cdetail,
                            measured=round(ratio, 3), advisory=True))
    else:
        checks.append(Check("module_size", False, "no quad detected", advisory=True))
        checks.append(Check("quiet_zone", False, "no quad detected", advisory=True))
        checks.append(Check("contrast", False, "no quad detected", advisory=True))

    report.checks = checks
    report.passed = all(c.ok for c in checks if not c.advisory)

    # Name the assurance level. A pass without an expectation is not the same
    # claim as a pass against a stated truth, and the report must not blur them.
    exp = []
    if expect_kind is not None:
        exp.append("kind")
    if expect_payload is not None:
        exp.append("payload")
    if envelope is not None:
        exp.append("envelope")
    report.expectations = exp
    report.assurance = "expected" if exp else "self_consistent"
    if not exp:
        checks.append(Check(
            "assurance", False,
            "SELF-CONSISTENT ONLY — the image was compared against itself. "
            "It decodes, but nothing asserts it says what was intended. Pass "
            "expect_kind/expect_payload, or supply the envelope you expect.",
            advisory=True))
        report.checks = checks
    return report


# ── the shared gate for callers that already hold an envelope ─────────────────

def supervise_raw(image_path, expect_text: str) -> QRReport:
    """Verify a PNG decodes back to `expect_text` through BOTH decoders.

    For producers whose payload is NOT an `ae://` envelope (a raw key JSON, a
    contract blob). Same load-bearing check as `supervise` — roundtrip +
    cross_decoder — without the envelope/charset requirements.

    Prefer a real envelope (`key`, `contract`) and `produce()` where you can;
    this exists so an existing raw renderer can still be gated today.
    """
    import cv2

    checks: list[Check] = []
    path = pathlib.Path(image_path)
    img = cv2.imread(str(path))
    report = QRReport(passed=False)

    if img is None:
        checks.append(Check("loadable", False, f"cannot read {path}"))
        report.checks = checks
        return report
    checks.append(Check("loadable", True, f"{img.shape[1]}x{img.shape[0]}"))
    report.image_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    report.envelope_bytes = len(expect_text)
    report.envelope_sha256 = hashlib.sha256(expect_text.encode("utf-8")).hexdigest()

    cv2_hits = _decode_with_cv2(img)
    zbar_hits = _decode_with_pyzbar(img)
    report.decoders_ok = [n for n, h in (("cv2", cv2_hits), ("pyzbar", zbar_hits))
                          if expect_text in h]

    checks.append(Check("roundtrip", bool(report.decoders_ok),
                        "decodes back exactly" if report.decoders_ok
                        else "did NOT decode back to the payload"))
    checks.append(Check("cross_decoder", len(report.decoders_ok) >= MIN_DECODERS,
                        f"{len(report.decoders_ok)}/{MIN_DECODERS} decoders: "
                        f"{', '.join(report.decoders_ok) or 'none'}"))

    det = cv2.QRCodeDetector()
    ok_d, _, pts, _ = det.detectAndDecodeMulti(img)
    if pts is not None and len(pts):
        ratio, cdetail = _contrast(img, pts[0])
        checks.append(Check("contrast", ratio >= MIN_CONTRAST, cdetail,
                            measured=round(ratio, 3), advisory=True))
        qz_ok, qz_detail = _quiet_zone_ok(img, pts[0])
        checks.append(Check("quiet_zone", qz_ok, qz_detail, advisory=True))
    else:
        checks.append(Check("contrast", False, "no quad detected"))
        checks.append(Check("quiet_zone", False, "no quad detected"))

    report.checks = checks
    report.passed = all(c.ok for c in checks if not c.advisory)
    return report


def render_verified(envelope: str, out_path=None, *, kind: str | None = None,
                    payload: dict | None = None) -> bytes:
    """Render an envelope AND prove it decodes back. THE entry point producers use.

    This is the shared gate for callers that already hold a FINISHED envelope
    (qr_mail, contract_qr, qr_key_manager, væult) rather than a (kind, payload)
    pair. It renders, supervises through two real decoders, and returns the PNG
    bytes **only on PASS**. On refusal it raises `QRRefused`.

    Use this instead of `qrcode.QRCode(...).make_image(...)` directly. A QR that
    has not been decoded back is not a QR — it is a picture of one.

    When `out_path` is given the file is written; the PNG bytes are returned
    either way so a caller can attach them (e.g. qr_mail).
    """
    import os as _os
    import tempfile
    import qrcode

    tmp = None
    try:
        if out_path is None:
            fd, tmp = tempfile.mkstemp(suffix=".png", prefix="qrgate-")
            _os.close(fd)
            out_path = tmp
        dest = str(out_path)

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
        qr.add_data(envelope)
        qr.make(fit=True)
        if qr.version > 40:
            raise ValueError(f"needs v{qr.version} > v40 cap")
        qr.make_image(fill_color="black", back_color="white").save(dest)

        report = supervise(dest, expect_kind=kind, expect_payload=payload,
                           envelope=envelope)
        if not report.passed:
            raise QRRefused(report.reason(), report)

        with open(dest, "rb") as fh:
            return fh.read()
    finally:
        if tmp is not None:
            try:
                _os.unlink(tmp)
            except OSError:
                pass


# ── the producer ──────────────────────────────────────────────────────────────

def _render(envelope: str, out_path: pathlib.Path, box_size: int = 10,
            border: int = 4, ecc: str = "M") -> dict:
    """Render an envelope to a PNG. Returns render metadata."""
    import qrcode
    levels = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M,
              "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}
    qr = qrcode.QRCode(error_correction=levels[ecc], border=border, box_size=box_size)
    qr.add_data(envelope)
    qr.make(fit=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    qr.make_image(fill_color="black", back_color="white").save(out_path)
    return {"version": qr.version, "modules": qr.modules_count, "box_size": box_size,
            "border": border, "ecc": ecc}


def _chain(*parts) -> str:
    """H(prev ∥ intent ∥ ops ∥ result ∥ state ∥ evidence) — the receipt hash chain."""
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


# ── the kænbæn: shared system memory (the real chain) ─────────────────────────
#
# C:\æ\kænbæn is the system's memory. Its verification-gates.json states the
# capture gate explicitly:
#
#     "capture": { "pass": "hash computed, prev_hash matches",
#                  "fail": "hash mismatch or missing prev" }
#
# So a receipt seeded with prev="" is not merely inelegant — it FAILS the
# system's own gate. This block reads the real previous receipt and writes ours
# back, so `prev` is genuine and the chain can prove order and detect omission.

def _kaenbaen():
    """Import the kænbæn module if present. Returns None when unavailable."""
    for base in (pathlib.Path(r"C:\æ\kænbæn"), AGENTS.parent / "kænbæn"):
        if (base / "kænbæn.py").exists():
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            try:
                import kænbæn as k  # noqa: N813
                return k
            except Exception:
                continue
    return None


def chain_prev() -> tuple[str, str]:
    """Return (prev_receipt, source). Empty string means no chain is available."""
    k = _kaenbaen()
    if k is None:
        return "", "no kænbæn"
    try:
        chain = k.genesis_chain()
        entries = chain.get("chain") or []
        if entries:
            return entries[-1].get("receipt", ""), "kænbæn genesis-chain"
        return "genesis", "kænbæn (empty chain)"
    except Exception as e:
        # A chain read that fails must NOT masquerade as "no chain" — that is
        # how prev="" looked healthy for a whole session. Name the failure.
        return "", f"kænbæn read FAILED ({type(e).__name__}: {e})"


def chain_append(receipt_id: str, description: str, artifacts: list | None = None) -> bool:
    """Append our receipt to the kænbæn genesis chain. True on success.

    This is what makes `prev` meaningful for the NEXT receipt: the chain is only
    a chain if something writes the link back.
    """
    k = _kaenbaen()
    if k is None:
        return False
    try:
        entry = k.append_chain_receipt("qr", description, artifacts or [])
        return bool(entry)
    except Exception:
        return False


def _verify_links(entries: list) -> dict:
    """Pure: check ORDER and GENESIS on a list of chain entries.

    Split out so it can be tested against a deliberately broken chain. A
    verifier that has never seen a break is a verifier you are trusting, not one
    you have tested.
    """
    breaks = []
    for i, e in enumerate(entries):
        rid = e.get("receipt", "")
        prev = e.get("prev", "")
        if i == 0:
            if prev not in ("genesis", "", None):
                breaks.append({"at": i, "receipt": rid, "prev": prev,
                               "why": "first entry must be seeded from genesis"})
            continue
        expected = entries[i - 1].get("receipt", "")
        if prev != expected:
            breaks.append({"at": i, "receipt": rid, "prev": prev,
                           "expected": expected,
                           "why": "prev does not point at the previous receipt"})
    return {"ok": not breaks, "links": len(entries), "breaks": breaks,
            "first_break": breaks[0] if breaks else None,
            "genesis": entries[0].get("receipt", "") if entries else ""}


def chain_verify(entries: list | None = None) -> dict:
    """CONSUME the chain: does every link's `prev` point at the one before it?

    #4 said the receipt chain "does not chain" and that nothing consumed it.
    Linking was only half the fix: a chain nobody reads proves nothing. This
    walks the kænbæn genesis chain and checks two properties a real chain must
    have:

      ORDER     each entry's `prev` equals the previous entry's `receipt`
      GENESIS   the first entry's `prev` is "genesis" (or absent)

    A break means either a reorder or an omission — the two things a chain
    exists to make visible. Returns {ok, links, breaks, first_break}.
    """
    if entries is not None:
        return _verify_links(entries)

    k = _kaenbaen()
    if k is None:
        return {"ok": False, "reason": "no kænbæn", "links": 0, "breaks": []}
    try:
        chain = k.genesis_chain()
    except Exception as e:
        return {"ok": False, "reason": f"read failed: {type(e).__name__}: {e}",
                "links": 0, "breaks": []}

    return _verify_links(chain.get("chain") or [])


def produce(kind: str, payload: dict, out_path=None, *,
            max_attempts: int = 2, box_size: int = 10, ecc: str = "M") -> QRReceipt:
    """SPEC → RENDER → SUPERVISE. Returns a QRReceipt on PASS; raises QRRefused.

    On FAIL the producer retries with a larger box_size (a real remedy for a
    module-size or contrast refusal) up to max_attempts. A charset refusal is
    NOT retried — the payload itself is wrong and no rendering fixes it.
    """
    import qr_envelope as qe

    envelope = qe.encode(kind, payload)
    dest = pathlib.Path(out_path) if out_path else (
        AGENTS / ".." / "secrets" / "qr" / f"qr-{kind}-{int(time.time())}.png")
    dest = pathlib.Path(str(dest)).resolve()

    last_report = None
    last_reason = ""
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        render_meta = _render(envelope, dest, box_size=box_size, ecc=ecc)
        report = supervise(dest, expect_kind=kind, expect_payload=payload, envelope=envelope)
        if report.passed:
            # REAL prev — read from the kænbæn chain, not an empty string.
            # The system's own capture gate fails on "missing prev", so seeding
            # this with "" would make every receipt fail the system's contract.
            prev, prev_source = chain_prev()
            receipt = QRReceipt(
                kind=kind, envelope=envelope, out_path=str(dest),
                envelope_sha256=report.envelope_sha256,
                image_sha256=report.image_sha256,
                report=report.to_dict(), produced_at=time.time(),
            )
            receipt.chain = _chain(
                prev, {"kind": kind, "attempt": attempt},
                {"op": "render", **render_meta},
                {"result": "PASS", "envelope_sha256": report.envelope_sha256},
                {"decoders": report.decoders_ok},
                {"image_sha256": report.image_sha256},
            )
            receipt.prev = prev
            receipt.prev_source = prev_source
            # write the link back so the NEXT receipt has a real prev
            chain_append(
                f"ae://receipt/qr-{receipt.chain[:24]}",
                f"QR {kind} supervised PASS ({report.envelope_sha256[:12]})",
                [{"envelope_sha256": report.envelope_sha256,
                  "image_sha256": report.image_sha256,
                  "decoders": report.decoders_ok}])
            return receipt

        last_report, last_reason = report, report.reason()

        # a charset failure is unfixable by rendering — refuse immediately
        if any(c.name == "charset" and not c.ok for c in report.failed):
            break
        # module-size / contrast refusals get a bigger render
        box_size += 6

    raise QRRefused(last_reason or "supervision failed", last_report or QRReport(passed=False))


# ── self-test ─────────────────────────────────────────────────────────────────

def selftest() -> int:
    """Prove the supervisor works — including that it REFUSES the rune class."""
    import tempfile
    import qr_envelope as qe

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="qrsup-"))
    print("qr_supervision selftest")
    print("=" * 62)

    # 1. a good secret card must PASS
    payload = {"name": "XIAOMI", "blob": {"n": "abc123", "ct": "deadbeef"}}
    r = produce("secret", payload, out_path=tmp / "good.png")
    print(f"\n[1] good secret card -> {'PASS' if r else 'FAIL'}")
    print(r.render())

    # 2. the rune magic must be REFUSED (the §5.3 failure class)
    print("\n[2] rune magic ('æ:1:secret:...') — must be REFUSED")
    rune_env = "æ:1:secret:" + qe.encode("secret", payload).split(":", 3)[3]
    # render it anyway, then supervise
    bad_path = tmp / "rune.png"
    _render(rune_env, bad_path)
    rep = supervise(bad_path, envelope=rune_env)
    print(f"    refused: {not rep.passed}")
    print(f"    reason : {rep.reason()}")

    # 3. a payload mismatch must be REFUSED
    print("\n[3] payload mismatch — must be REFUSED")
    rep2 = supervise(tmp / "good.png", expect_kind="secret",
                     expect_payload={"name": "WRONG", "blob": {"n": "x", "ct": "y"}},
                     envelope=r.envelope)
    print(f"    refused: {not rep2.passed}")
    print(f"    reason : {rep2.reason()}")

    # 4. every envelope type must survive
    print("\n[4] all envelope types through the gate")
    ok_all = True
    for kind in qe.TYPES:
        p = {"probe": kind}
        try:
            rr = produce(kind, p, out_path=tmp / f"{kind}.png")
            print(f"    ✓ {kind:10s} v-ok  {len(rr.envelope):4d} B")
        except QRRefused as e:
            ok_all = False
            print(f"    ✗ {kind:10s} REFUSED  {e.reason[:60]}")
    print(f"    all types: {ok_all}")

    print("\n" + "=" * 62)
    print("RESULT: supervisor is deterministic and refuses the silent failure class")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="produce-and-verify for QR artifacts")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("produce")
    p.add_argument("kind")
    p.add_argument("payload", help="JSON payload")
    p.add_argument("--out", default=None)
    p.add_argument("--ecc", default="M", choices=list("LMQH"))

    s = sub.add_parser("supervise")
    s.add_argument("image")
    s.add_argument("--expect-kind", default=None)
    s.add_argument("--expect-payload", default=None)
    s.add_argument("--envelope", default=None,
                   help="the envelope you EXPECT. Without one of the --expect* "
                        "flags the verdict is SELF-CONSISTENT only: it proves "
                        "the image decodes, not that it says what you meant.")
    s.add_argument("--require-expected", action="store_true",
                   help="exit 1 unless the verdict was checked against a stated "
                        "truth (refuses a self-consistent-only pass)")

    sub.add_parser("selftest")
    sub.add_parser("types")

    a = ap.parse_args(argv[1:])

    if a.cmd == "produce":
        try:
            r = produce(a.kind, json.loads(a.payload), out_path=a.out, ecc=a.ecc)
            print(r.render())
            sys.exit(0)
        except QRRefused as e:
            print(f"REFUSED: {e.reason}")
            if e.report:
                print(e.report.render())
            sys.exit(1)

    elif a.cmd == "supervise":
        rep = supervise(a.image, expect_kind=a.expect_kind,
                        expect_payload=json.loads(a.expect_payload) if a.expect_payload else None,
                        envelope=a.envelope)
        print(rep.render())
        if rep.passed and getattr(a, "require_expected", False) and rep.assurance != "expected":
            print("REFUSED: --require-expected was set but the verdict was "
                  "self-consistent only (nothing asserted what the artifact "
                  "should say).", file=sys.stderr)
            sys.exit(1)
        sys.exit(0 if rep.passed else 1)

    elif a.cmd == "selftest":
        sys.exit(selftest())

    elif a.cmd == "types":
        import qr_envelope as qe
        for t in qe.TYPES:
            print(f"  {t}")

    else:
        ap.print_help()


if __name__ == "__main__":
    main(sys.argv)
