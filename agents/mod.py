#!/usr/bin/env python3
"""mod:// — mixture of devices. Many small machines, one addressable compute.

The mixture of robots is not five minds. It is five ROUTES, each resolving to a
mixture of devices. A residential GPU, a laptop CPU, a droplet, a phone — none
is enough alone. Addressed together they are a compute surface a person owns.

    mod:// inventory              every device, MEASURED, with its honest capacity
    mod:// plan <workload>        split a job across the devices that can carry it
    mod:// pool <agent>           which devices this cast member may route to

THE LAW (already in the MoH registry, enforced here)
    "a harness may degrade; it may never lie about which mode served"
    "an address is not a permission; a scale is not an authority"

    A device that has not been probed is DECLARED, not measured. The plan says
    which is which, and a declared device is never counted toward capacity.

WHY AGGREGATION IS NOT JUST ADDITION
    Two 6 TFLOP cards do not make a 12 TFLOP card. They make two 6 TFLOP cards
    with a transfer cost between them. A plan is only worth splitting when the
    work is divisible AND the pieces are larger than the transfer. This module
    reports the split it can justify, and refuses the ones it cannot.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def home() -> Path:
    return Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))


def probe_cpu() -> dict:
    """Measure the CPU rather than reporting its marketing name."""
    import numpy as np
    n = os.cpu_count() or 1
    # fixed operands: repeated squaring overflows float32 to inf, and timing
    # inf arithmetic measures nothing. Same work every iteration.
    a = np.random.rand(512, 512).astype(np.float32)
    b = np.random.rand(512, 512).astype(np.float32)
    c = np.empty_like(a)
    t0 = time.perf_counter()
    for _ in range(5):
        np.matmul(a, b, out=c)
    dt = (time.perf_counter() - t0) / 5
    assert np.isfinite(c).all(), 'benchmark produced non-finite values'
    return {'threads': n, 'matmul_ms': round(dt * 1000, 2),
            'gflops': round(2 * 512**3 / dt / 1e9, 2)}


def probe_gpu() -> dict:
    try:
        import cupy as cp
        p = cp.cuda.runtime.getDeviceProperties(0)
        sm = p['multiProcessorCount']; ghz = p['clockRate'] / 1e6
        a = cp.random.rand(1024, 1024, dtype=cp.float32)
        b = cp.random.rand(1024, 1024, dtype=cp.float32)
        cp.cuda.Stream.null.synchronize()
        t0 = time.perf_counter()
        for _ in range(10):
            c = a @ b                      # fixed operands, no overflow
        cp.cuda.Stream.null.synchronize()
        dt = (time.perf_counter() - t0) / 10
        assert bool(cp.isfinite(c).all()), 'benchmark produced non-finite values'
        return {'name': p['name'].decode() if isinstance(p['name'], bytes) else str(p['name']),
                'vram_mib': int(p['totalGlobalMem'] / 1048576),
                'cc': f"{p['major']}.{p['minor']}", 'sms': sm,
                'tflops_fp32': round(sm * 128 * 2 * ghz / 1000, 1),
                'matmul_ms': round(dt * 1000, 2),
                'gflops': round(2 * 1024**3 / dt / 1e9, 1)}
    except Exception as exc:
        return {'available': False, 'reason': f'{type(exc).__name__}: {exc}'}


def probe_remote() -> dict:
    """The droplet. Reachability is measured; capacity is NOT assumed."""
    host = os.environ.get('AE_VPS_HOST')
    if not host:
        return {'available': False, 'declared': True,
                'reason': 'AE_VPS_HOST not set — the remote tier is DECLARED, not measured'}
    try:
        r = subprocess.run(['ssh', '-o', 'ConnectTimeout=6', '-o', 'BatchMode=yes',
                            f'root@{host}', 'nproc; free -m | head -2 | tail -1'],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return {'available': False, 'reason': 'ssh failed', 'declared': True}
        lines = r.stdout.strip().splitlines()
        return {'available': True, 'cores': int(lines[0]),
                'mem_line': lines[1] if len(lines) > 1 else None,
                'note': 'reachability and cores measured; FLOPS not probed'}
    except Exception as exc:
        return {'available': False, 'reason': str(exc), 'declared': True}


def inventory() -> dict:
    cpu = probe_cpu()
    gpu = probe_gpu()
    rem = probe_remote()
    devices = [
        {'id': 'cpu://teknium', 'tier': 'local', 'kind': 'cpu',
         'measured': True, 'capacity': cpu,
         'good_at': ['physics', 'policy inference', 'orchestration', 'I/O']},
        {'id': 'gpu://teknium', 'tier': 'local', 'kind': 'gpu',
         'measured': bool(gpu.get('gflops')), 'capacity': gpu,
         'good_at': ['rasterisation', 'batched math', 'encode']},
        {'id': 'vps://backbone', 'tier': 'remote', 'kind': 'cpu',
         'measured': bool(rem.get('available')), 'capacity': rem,
         'good_at': ['public surface', 'tunnel', 'broker', 'always-on']},
        {'id': 'hardware://asimov', 'tier': 'embodied', 'kind': 'robot',
         'measured': False, 'capacity': {'available': False,
         'reason': 'no physical robot attached'},
         'good_at': ['nothing yet — this tier is DECLARED']},
    ]
    measured = [d for d in devices if d['measured']]
    return {'ok': True, 'scheme': 'mod://', 'authority': 'HUMAN://ROOT',
            'devices': devices, 'measured_count': len(measured),
            'declared_count': len(devices) - len(measured),
            'law': 'a harness may degrade; it may never lie about which mode served',
            'grants': False,
            'note': 'a declared device contributes ZERO to a capacity sum'}


# Workloads and how they divide. `divisible` is a property of the WORK, not a
# hope about the hardware. A frame is divisible; a physics step is not.
WORKLOADS = {
    'film': {'divisible': True, 'unit': 'frame', 'device': 'gpu://teknium',
             'note': 'frames are independent; shard by frame range, concatenate after'},
    'physics': {'divisible': False, 'unit': 'tick', 'device': 'cpu://teknium',
                'note': 'a trajectory is sequential — step N needs step N-1. Cannot shard.'},
    'policy': {'divisible': True, 'unit': 'rollout', 'device': 'cpu://teknium',
               'note': 'independent rollouts parallelise; one rollout does not'},
    'voice': {'divisible': True, 'unit': 'line', 'device': 'cpu://teknium',
              'note': 'each scene line synthesises independently'},
    'world': {'divisible': True, 'unit': 'layer', 'device': 'cpu://teknium',
              'note': 'bed and event layers render independently, then sum'},
    'publish': {'divisible': False, 'unit': 'push', 'device': 'vps://backbone',
                'note': 'a push is serialised by the kanban lock — never parallel'},
}


def plan(workload: str, units: int = 240) -> dict:
    w = WORKLOADS.get(workload)
    if not w:
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': f'unknown workload {workload!r}',
                'available': sorted(WORKLOADS)}
    inv = inventory()
    dev = next((d for d in inv['devices'] if d['id'] == w['device']), None)
    if dev is None or not dev['measured']:
        return {'ok': False, 'refused': True, 'grants': False,
                'workload': workload, 'device': w['device'],
                'reason': 'the target device is DECLARED, not measured. '
                          'A plan may not spend capacity it has not probed.'}
    if not w['divisible']:
        return {'ok': True, 'workload': workload, 'units': units,
                'shards': 1, 'device': w['device'], 'parallel': False,
                'reason': w['note'], 'grants': False,
                'note': 'indivisible work runs on one device. Splitting it would be a lie.'}
    # how many workers of this kind exist on THIS machine?
    cap = dev['capacity']
    workers = cap.get('threads', 1) if dev['kind'] == 'cpu' else 1
    # measured earlier: 4 workers gave 2.05x, 8 gave 2.26x on the render probe.
    # diminishing returns are real; cap the shard count at the measured sweet spot.
    shards = max(1, min(workers, 8, units))
    return {'ok': True, 'workload': workload, 'units': units,
            'shards': shards, 'device': w['device'], 'parallel': shards > 1,
            'per_shard': units // shards, 'remainder': units % shards,
            'reason': w['note'],
            'expected_speedup': 'measured 2.05x at 4 workers, 2.26x at 8 — not linear',
            'grants': False,
            'note': 'one GPU is one GPU. Sharding overlaps CPU work with GPU work; '
                    'it does not multiply the card.'}


def pool(agent: str) -> dict:
    """Which devices a cast member may route to. Routing is not authority."""
    sys.path.insert(0, str(home() / 'plugins' / 'hermes-asimov' / 'scripts'))
    try:
        import moh
        reg, err = moh.load()
    except Exception as exc:
        return {'ok': False, 'refused': True, 'reason': str(exc), 'grants': False}
    if err:
        return {'ok': False, 'refused': True, 'reason': err, 'grants': False}
    a = next((x for x in reg['agents'] if x['id'] == agent), None)
    if not a:
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': f'unknown agent {agent!r}',
                'available': [x['id'] for x in reg['agents']]}
    inv = {d['id']: d for d in inventory()['devices']}
    scales = [a['default_scale']] + [s for s in reg['scales'] if s != a['default_scale']]
    rows = [{'scale': s, 'measured': inv.get(s, {}).get('measured', False),
             'kind': inv.get(s, {}).get('kind'),
             'tier': inv.get(s, {}).get('tier')} for s in scales]
    return {'ok': True, 'agent': agent, 'default': a['default_scale'],
            'harnesses': a['harnesses'], 'pool': rows,
            'measured_devices': sum(1 for r in rows if r['measured']),
            'authority': 'HUMAN://ROOT', 'grants': False,
            'note': 'a scale is not an authority. The pool says where work MAY run, '
                    'never who may sign for it.'}


def main():
    ap = argparse.ArgumentParser(prog='mod')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('inventory')
    p = sub.add_parser('plan'); p.add_argument('workload'); p.add_argument('--units', type=int, default=240)
    q = sub.add_parser('pool'); q.add_argument('agent')
    a = ap.parse_args()
    res = inventory() if a.cmd == 'inventory' else (
        plan(a.workload, a.units) if a.cmd == 'plan' else pool(a.agent))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
