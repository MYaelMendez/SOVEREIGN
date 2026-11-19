"""Parallelism probe — measure before committing to a factory.

MuJoCo offscreen rendering is single-threaded per GL context. The win is
sharding FRAMES across processes: each worker owns its own MjModel / MjData /
Renderer, so there is no shared state.

Two things must be measured, not assumed:
  1. throughput at 1 / 2 / 4 / 8 workers (E-cores are slower; contexts cost RAM)
  2. DETERMINISM — frame i must be byte-identical regardless of worker count.
     A faster render that changes the picture is not a faster render.

    python parallel_probe.py --frames 24 --workers 1,2,4,8
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

H = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
PL = Path(os.environ.get('HERMES_AE_HOME', H / 'plugins' / 'hermes-ae'))
OUT = H / 'cache' / 'scratch' / 'parallel-probe'
W, VH = 720, 720


def _worker(job):
    """One process: own model, own data, own renderer. Returns hashes only."""
    idxs, tag = job
    import mujoco
    import numpy as np
    src = (PL / 'model/xml/asimov_1_25dof_actuated.xml').read_text(encoding='utf-8')
    src = re.sub(r'meshdir="[^"]*"', f'meshdir="{(PL/"model/meshes").as_posix()}"', src)
    vis = f'<visual><global offwidth="{W}" offheight="{VH}"/><quality shadowsize="2048"/></visual>'
    src = (re.sub(r'<visual>.*?</visual>', vis, src, count=1, flags=re.S)
           if '<visual>' in src else src.replace('</mujoco>', vis + '</mujoco>'))
    t0 = time.time()
    m = mujoco.MjSpec.from_string(src).compile()
    d = mujoco.MjData(m)
    d.ctrl[:] = np.clip(0.0, m.actuator_ctrlrange[:, 0], m.actuator_ctrlrange[:, 1])
    for _ in range(600):
        mujoco.mj_step(m, d)
    mujoco.mj_forward(m, d)
    base = d.qpos.copy()
    r = mujoco.Renderer(m, height=VH, width=W)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat = np.array([0.0, 0.0, 0.9])
    cam.distance = 1.55
    cam.azimuth = 180
    cam.elevation = -3
    compile_s = time.time() - t0

    # WARMUP: the first render in a fresh GL context returns different pixels
    # than every subsequent render of the same scene. Discard one, or frame 0
    # of each shard is an artifact and the output depends on worker count.
    cam.azimuth = 180
    r.update_scene(d, camera=cam)
    r.render()

    t1 = time.time()
    hashes = {}
    for i in idxs:
        d.qpos[:] = base
        mujoco.mj_forward(m, d)
        cam.azimuth = 180 + 3 * np.sin(i / 24.0 * 0.42)
        r.update_scene(d, camera=cam)
        px = r.render()
        hashes[i] = hashlib.sha256(px.tobytes()).hexdigest()[:16]
    render_s = time.time() - t1
    r.close()
    return dict(tag=tag, n=len(idxs), compile_s=round(compile_s, 2),
                render_s=round(render_s, 2), hashes=hashes)


def run(nframes, workers):
    shards = [[] for _ in range(workers)]
    for i in range(nframes):
        shards[i % workers].append(i)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_worker, [(s, f'w{k}') for k, s in enumerate(shards) if s]))
    wall = time.time() - t0
    hashes = {}
    for r in res:
        hashes.update(r['hashes'])
    comp = max(r['compile_s'] for r in res)
    return dict(workers=workers, frames=nframes, wall_s=round(wall, 2),
                s_per_frame=round(wall / nframes, 3),
                compile_max_s=comp,
                pure_render_s=round(max(r['render_s'] for r in res), 2),
                hashes=hashes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', type=int, default=24)
    ap.add_argument('--workers', default='1,2,4,8')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"  MuJoCo parallelism probe — {a.frames} frames, {W}x{VH}, shadows on")
    print(f"  logical cores: {os.cpu_count()}\n")
    results = []
    base_hashes = None
    for w in [int(x) for x in a.workers.split(',')]:
        r = run(a.frames, w)
        if base_hashes is None:
            base_hashes = r['hashes']
            r['deterministic'] = True
        else:
            same = r['hashes'] == base_hashes
            r['deterministic'] = same
            if not same:
                diff = [i for i in base_hashes if base_hashes[i] != r['hashes'].get(i)]
                r['differing_frames'] = diff[:8]
        results.append(r)
        sp = results[0]['wall_s'] / r['wall_s']
        print(f"  {w} worker(s): wall {r['wall_s']:6.2f}s  {r['s_per_frame']:.3f} s/frame  "
              f"speedup {sp:.2f}x  compile {r['compile_max_s']:.1f}s  "
              f"identical={r['deterministic']}")
        if r.get('differing_frames'):
            print(f"      DIFFERS at frames {r['differing_frames']}")
    p = OUT / 'probe.json'
    p.write_text(json.dumps([{k: v for k, v in r.items() if k != 'hashes'}
                             for r in results], indent=2), encoding='utf-8')
    print(f"\n  {p}")
    best = min(results, key=lambda r: r['wall_s'])
    print(f"  best: {best['workers']} workers, {best['wall_s']}s "
          f"({results[0]['wall_s']/best['wall_s']:.2f}x)")
    allok = all(r['deterministic'] for r in results)
    print(f"  DETERMINISM ACROSS ALL WORKER COUNTS: {allok}")
    if not allok:
        print("  -> parallelism changes the picture. Do not ship it.")


if __name__ == '__main__':
    main()
