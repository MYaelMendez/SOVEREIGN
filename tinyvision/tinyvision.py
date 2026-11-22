#!/usr/bin/env python3
"""tinyVISION — supervision for the robot policy.

We have supervised our videos: luminance, contrast, motion, gates, receipts.
This is the same instrument pointed at the POLICY. A policy trace becomes a film
of the real CAD; the film is supervised and tracked; and the visual trajectory
is compared with the physics trace that produced it.

    policy trace → render (rtx_asimov) → film → supervise + track → compare

THE QUESTION IT ANSWERS
  Does the picture agree with the physics? A trace can claim success while the
  film shows a frozen body; a film can look alive while the trace says it fell.
  Both instruments must be read, and their disagreement is the finding.

    tinyvision doctor            engine + renderer present?
    tinyvision render <trace>    trace → film (the real CAD)
    tinyvision supervise <film>  the gate: lum/contraste/movimiento/calidad
    tinyvision track <film>      the robot's bounding-box trajectory
    tinyvision agree <trace> <film>   do picture and physics agree?

RULES
  1. The gate is read from the film, never assumed.
  2. Pixels and metres are different units: the comparison reports BOTH and an
     implied px/m. A scale is never invented silently.
  3. One dominant track is required; a film that splits into many tracks is
     reported as incoherent, not averaged.
  4. Every run is a hash in the ledger.
  5. Simulation only — a film of a trace is a picture of a plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

RTX = HERE.parent / 'agents' / 'rtx_asimov.py'
LEDGER = Path(os.environ.get('TINYVISION_LEDGER',
                             Path(os.environ.get('HERMES_HOME',
                                                 Path.home() / 'AppData/Local/hermes'))
                             / 'tinyvision.jsonl'))
GENESIS = '0' * 64

try:
    sys.path.insert(0, str(HERE.parent / 'supervisionvidaeo'))
    from supervisionvidaeo import vision as V
except Exception:                                # pragma: no cover
    try:
        import vision_supervision as V        # the shim
    except Exception:
        V = None


# ------------------------------------------------------------------ ledger
def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def receipt(action: str, detail: dict) -> dict:
    chain = _read()
    prev = chain[-1]['hash'] if chain else GENESIS
    body = {'action': action, 'detail': detail, 'prev': prev, 'ts': time.time()}
    h = _sha(_canonical(body))
    rec = dict(body, hash=h)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
    return rec


def ledger() -> dict:
    chain = _read()
    prev = GENESIS
    for i, r in enumerate(chain):
        body = {k: v for k, v in r.items() if k != 'hash'}
        if body.get('prev') != prev or _sha(_canonical(body)) != r.get('hash'):
            return {'ok': False, 'length': len(chain), 'broken_at': i + 1, 'head': prev}
        prev = r['hash']
    return {'ok': True, 'length': len(chain), 'head': prev}


# ------------------------------------------------------------- supervise
def supervise(video: Path) -> dict:
    """The gate, read from the film."""
    if V is None:
        return {'ok': False, 'refused': True, 'reason': 'supervision engine unavailable'}
    p = Path(video)
    if not p.exists():
        return {'ok': False, 'refused': True, 'reason': f'no such film: {p}'}
    r = V.supervisar_video(str(p))
    rec = receipt('supervise', {'film': str(p), 'calidad': r.get('calidad'),
                                'movimiento': r.get('movimiento_medio')})
    r['ledger'] = rec['hash']
    return r


# ----------------------------------------------------------------- render
def render(trace_path: Path, out: Path, seconds: float = 12.0, fps: int = 24) -> dict:
    """Trace → film, through the real-CAD CUDA renderer."""
    import shutil
    which = os.environ.get('TINYVISION_PYTHON')
    if not which:
        for cand in ('C:/gpu/Scripts/python.exe', sys.executable, shutil.which('python')):
            if cand and Path(cand).exists():
                which = cand
                break
    if not RTX.exists():
        return {'ok': False, 'refused': True, 'reason': f'renderer missing: {RTX}'}
    model_dir = os.environ.get('TINYVISION_MODEL_DIR', str(HERE.parent / 'tinygpu' / 'model'))
    cmd = [which, str(RTX), '--trace', str(trace_path), '--out', str(out),
           '--seconds', str(seconds), '--fps', str(fps), '--silent',
           '--model-dir', model_dir]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and Path(out).exists()
    rec = receipt('render', {'trace': str(trace_path), 'film': str(out), 'ok': ok,
                             'seconds': seconds, 'fps': fps})
    return {'ok': ok, 'trace': str(trace_path), 'film': str(out),
            'seconds': seconds, 'fps': fps,
            'stderr': (r.stderr or '')[-400:], 'ledger': rec['hash']}


# ----------------------------------------------------------------- track
def track(video: Path, colors: list[str] | None = None, area_min: int = 2000,
          aspect: tuple = (0.4, 3.0)) -> dict:
    """The robot's trajectory, from a palette-aware colour detector + IoU.

    A rendered film has a HUD band and a floor in the palette; a raw motion
    detector fragments into hundreds of tracks. The accent colour isolates the
    robot, and aspect/position filters reject the HUD and floor bands.
    """
    if V is None:
        return {'ok': False, 'refused': True, 'reason': 'supervision engine unavailable'}
    import cv2
    p = Path(video)
    if not p.exists():
        return {'ok': False, 'refused': True, 'reason': f'no such film: {p}'}
    det = V.DetectorColor(colores=colors or ['azul'], area_minima=area_min)
    trk = V.RastreadorIOU()
    cap = cv2.VideoCapture(str(p))
    traj, n, H = {}, 0, 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        H = frame.shape[0]
        n += 1
        lote = trk.actualizar(det.detectar(frame))
        for d in lote.detecciones:
            tid = getattr(d, 'track_id', None)
            if tid is None:
                continue
            x1, y1, x2, y2 = [float(v) for v in d.xyxy]
            w, h = x2 - x1, y2 - y1
            if w <= 0 or h <= 0 or not (aspect[0] <= h / w <= aspect[1]):
                continue
            if y2 > H * 0.9:                     # the floor band, not the robot
                continue
            traj.setdefault(tid, []).append(
                {'f': n, 'cx': round((x1 + x2) / 2, 1), 'cy': round((y1 + y2) / 2, 1),
                 'w': int(w), 'h': int(h)})
    cap.release()
    if not traj:
        rec = receipt('track', {'film': str(p), 'ok': False, 'tracks': 0})
        return {'ok': False, 'reason': 'no track could be established',
                'frames': n, 'ledger': rec['hash']}
    dom = max(traj.items(), key=lambda kv: len(kv[1]))
    pts = dom[1]
    dx = pts[-1]['cx'] - pts[0]['cx']
    dy = pts[-1]['cy'] - pts[0]['cy']
    rec = receipt('track', {'film': str(p), 'ok': True, 'tracks': len(traj),
                            'frames': n, 'dominant': dom[0],
                            'dx_px': round(dx, 1), 'dy_px': round(dy, 1)})
    return {'ok': True, 'film': str(p), 'frames': n, 'tracks': len(traj),
            'dominant': dom[0], 'points': len(pts),
            'displacement_px': {'dx': round(dx, 1), 'dy': round(dy, 1)},
            'trajectory': pts[::max(1, len(pts) // 24)],
            'ledger': rec['hash']}


# --------------------------------------------------------------- compare
def agree(trace_path: Path, video: Path, px_per_m: float | None = None) -> dict:
    """Do the picture and the physics agree? Both units, no silent scale."""
    t = json.loads(Path(trace_path).read_text(encoding='utf-8'))
    tk = track(video)
    if not tk.get('ok'):
        rec = receipt('agree', {'trace': str(trace_path), 'ok': False,
                                'reason': tk.get('reason')})
        return {'ok': False, 'reason': tk.get('reason'), 'ledger': rec['hash']}
    base = t.get('base') or []
    physics_m = float(base[-1][0] - base[0][0]) if len(base) >= 2 else 0.0
    cmd = t.get('command', [0.4, 0, 0])
    dx_px = float(tk['displacement_px']['dx'])
    if px_per_m is None and physics_m > 0.05:
        px_per_m = abs(dx_px) / physics_m
    implied = (abs(dx_px) / physics_m) if physics_m > 0.05 else None
    # coherence: one dominant track, and the visual motion has a direction
    coherent = tk['tracks'] <= 3 and (abs(dx_px) > 2.0 or abs(float(tk['displacement_px']['dy'])) > 2.0)
    direction_ok = (dx_px * float(cmd[0])) >= -2.0 if abs(float(cmd[0])) > 0.05 else True
    ok = bool(coherent and direction_ok)
    rec = receipt('agree', {'trace': str(trace_path), 'film': str(video),
                            'ok': ok, 'physics_m': round(physics_m, 4),
                            'dx_px': dx_px, 'implied_px_per_m': round(implied, 1) if implied else None})
    return {'ok': ok, 'trace': str(trace_path), 'film': str(video),
            'physics': {'travel_x_m': round(physics_m, 4),
                        'duration_s': t.get('duration_s'), 'success': t.get('success')},
            'visual': {'dx_px': dx_px, 'dy_px': tk['displacement_px']['dy'],
                       'tracks': tk['tracks'], 'frames': tk['frames']},
            'implied_px_per_m': round(implied, 1) if implied else None,
            'px_per_m': round(px_per_m, 1) if px_per_m else None,
            'coherent': coherent, 'direction_ok': direction_ok,
            'ledger': rec['hash'],
            'note': 'pixels and metres are different units; both are reported, '
                    'and the scale is never invented silently'}


def doctor() -> dict:
    try:
        import cv2
        cv = cv2.__version__
    except Exception as exc:
        cv = f'MISSING ({exc})'
    return {'ok': V is not None and 'MISSING' not in cv,
            'engine': (V.__name__ if V else None), 'opencv': cv,
            'renderer': str(RTX) if RTX.exists() else f'MISSING {RTX}',
            'ledger': ledger(),
            'why': 'the same supervision we use for our films, pointed at the policy'}


def main() -> int:
    ap = argparse.ArgumentParser(description='tinyVISION — supervision for the robot policy')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor'); sub.add_parser('ledger')
    p_ren = sub.add_parser('render')
    p_ren.add_argument('trace'); p_ren.add_argument('out')
    p_ren.add_argument('--seconds', type=float, default=12.0)
    p_ren.add_argument('--fps', type=int, default=24)
    p_sup = sub.add_parser('supervise'); p_sup.add_argument('film')
    p_trk = sub.add_parser('track'); p_trk.add_argument('film')
    p_agr = sub.add_parser('agree')
    p_agr.add_argument('trace'); p_agr.add_argument('film')
    p_agr.add_argument('--px-per-m', type=float, default=None)
    a = ap.parse_args()
    if a.cmd == 'render':
        r = render(a.trace, a.out, seconds=a.seconds, fps=a.fps)
    elif a.cmd == 'supervise':
        r = supervise(a.film)
    elif a.cmd == 'track':
        r = track(a.film)
    elif a.cmd == 'agree':
        r = agree(a.trace, a.film, px_per_m=a.px_per_m)
    else:
        r = globals()[a.cmd]()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
