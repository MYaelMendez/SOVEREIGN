#!/usr/bin/env python3
"""
degraded_capture.py — improvement #6: the gate has only ever seen clean PNGs.

Every check in qr_supervision runs on an axis-aligned synthetic render. Never
tested: rotation, perspective, blur, glare, occlusion, print-then-scan, or a
phone camera. The paper's §6.3 concedes the camera path is unmeasured; the gate
inherits that gap, and the camera path is the one most likely to hold the next
silent failure.

This module DEGRADES a clean render in the ways a real capture degrades it, then
measures the pass rate. The output is a measured property, not an assumption:

    "the gate passes N/M degraded captures at severity S"

WHAT IT DOES NOT DO
-------------------
It does not simulate a camera. A real phone adds lens distortion, rolling
shutter, autofocus hunting, and colour science. This is a lower bound: if the
gate fails here, it certainly fails on a phone.

USAGE
    python degraded_capture.py sweep           run the full severity sweep
    python degraded_capture.py sweep --json    machine-readable
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile

AGENTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))

import qr_envelope as qe
import qr_supervision as qs


def _degradations():
    """Each degradation: name -> fn(img, severity 0..1) -> img."""
    import cv2
    import numpy as np

    def rotate(img, s):
        h, w = img.shape[:2]
        ang = 12.0 * s                       # up to 12 degrees
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
        return cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))

    def blur(img, s):
        k = int(1 + 6 * s) | 1               # odd kernel, up to 7
        return cv2.GaussianBlur(img, (k, k), 0)

    def glare(img, s):
        h, w = img.shape[:2]
        out = img.copy()
        # a soft white blob over one corner — a specular highlight
        yy, xx = np.mgrid[0:h, 0:w]
        cx, cy, r = w * 0.25, h * 0.25, max(h, w) * 0.45 * s
        mask = np.clip(1.0 - (((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5) / max(r, 1), 0, 1)
        for c in range(3):
            out[:, :, c] = np.clip(out[:, :, c] + 255 * mask * 0.9, 0, 255).astype(np.uint8)
        return out

    def perspective(img, s):
        h, w = img.shape[:2]
        d = 0.10 * s * w                     # how far a corner moves inward
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[d, d * 0.4], [w - d * 0.3, d], [w, h - d], [d * 0.5, h - d * 0.6]])
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(img, M, (w, h), borderValue=(255, 255, 255))

    def occlude(img, s):
        h, w = img.shape[:2]
        out = img.copy()
        # a finger/sticker over one corner of the code
        bw, bh = int(w * 0.16 * s), int(h * 0.16 * s)
        out[h - bh:, :bw] = 40
        return out

    def low_contrast(img, s):
        # compress the dynamic range toward mid-grey
        import numpy as np
        f = 1.0 - 0.75 * s
        return np.clip(128 + (img.astype(float) - 128) * f, 0, 255).astype(np.uint8)

    def jpeg(img, s):
        # print-then-scan style compression artefacts
        import cv2
        q = max(20, int(95 - 70 * s))
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR) if ok else img

    return {"rotate": rotate, "blur": blur, "glare": glare,
            "perspective": perspective, "occlude": occlude,
            "low_contrast": low_contrast, "jpeg": jpeg}


def sweep(severities=(0.25, 0.5, 1.0), kinds=("route", "secret")) -> dict:
    """Degrade, render, and measure. Returns pass rates per degradation."""
    import cv2

    degradations = _degradations()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="degrade-"))
    results = {}

    for name, fn in degradations.items():
        rows = []
        for sev in severities:
            for kind in kinds:
                env = qe.encode(kind, {"probe": kind, "n": 40})
                clean = tmp / f"{name}-{sev}-{kind}.png"
                qs._render(env, clean, box_size=10, border=4)
                img = cv2.imread(str(clean))
                if img is None:
                    rows.append({"sev": sev, "kind": kind, "passed": False,
                                 "why": "render failed"})
                    continue
                deg = fn(img, sev)
                dp = tmp / f"{name}-{sev}-{kind}-deg.png"
                cv2.imwrite(str(dp), deg)
                rep = qs.supervise(str(dp), envelope=env)
                failed = [c.name for c in rep.failed]
                rows.append({"sev": sev, "kind": kind, "passed": rep.passed,
                             "failed": failed,
                             "why": rep.reason()[:90] if not rep.passed else ""})
        passed = sum(1 for r in rows if r["passed"])
        results[name] = {"passed": passed, "total": len(rows), "rows": rows,
                         "rate": passed / len(rows) if rows else 0.0}
    return results


def main(argv):
    ap = argparse.ArgumentParser(description="measure the gate on degraded captures")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("sweep")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv[1:])

    if a.cmd != "sweep":
        ap.print_help()
        return 1

    r = sweep()
    if a.json:
        print(json.dumps(r, indent=2))
        return 0

    total_p = sum(v["passed"] for v in r.values())
    total_n = sum(v["total"] for v in r.values())
    print(f"DEGRADED-CAPTURE SWEEP — {total_p}/{total_n} pass "
          f"({100*total_p/total_n:.0f}%)\n")
    print(f"  {'degradation':14s} {'pass':>7s}  first failure")
    print("  " + "-" * 66)
    for name, v in sorted(r.items(), key=lambda kv: kv[1]["rate"]):
        first = next((x for x in v["rows"] if not x["passed"]), None)
        why = f"sev={first['sev']} {','.join(first['failed'])[:34]}" if first else "—"
        print(f"  {name:14s} {v['passed']:>3d}/{v['total']:<3d}  {why}")
    print("\n  A lower bound, not a camera simulation: if the gate fails here it")
    print("  certainly fails on a phone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
