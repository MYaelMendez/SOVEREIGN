#!/usr/bin/env python3
"""Recompute whether a trace walked — from geometry, not from its success flag.

Mirrors tinypython.verify, applied to measure.py's trace format.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np

FALL_Z = 0.35


def verify(p: Path) -> dict:
    d = json.loads(p.read_text(encoding='utf-8'))
    base = np.array(d['base'])
    z = base[:, 2]
    travel = float(base[-1, 0] - base[0, 0])
    travel_y = float(base[-1, 1] - base[0, 1])
    fell = bool((z < FALL_Z).any())
    cmd = np.array(d.get('command', [0.4, 0, 0]), float)
    speed = float(np.linalg.norm(cmd[:2]))
    if speed < 0.05 and abs(float(cmd[2])) < 0.05:
        obeyed = (travel ** 2 + travel_y ** 2) ** 0.5 < 0.30
    elif abs(float(cmd[2])) > 0.05:
        q = base[-1, 3:7]
        yaw = float(np.arctan2(2 * (q[0] * q[2] + q[1] * q[3]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)))
        obeyed = abs(yaw) > 0.05
    else:
        obeyed = travel * float(cmd[0]) + travel_y * float(cmd[1]) > 0.05
    return {
        'ok': bool(not fell and obeyed),
        'obeyed_command': obeyed, 'command': cmd.tolist(),
        'frames': len(base), 'duration_s': d.get('duration_s'),
        'travel_x_m': round(travel, 4), 'travel_y_m': round(travel_y, 4),
        'min_z_m': round(float(z.min()), 4), 'fell': fell,
        'claims_success': d.get('success'),
        'agrees_with_claim': bool((not fell and obeyed) == bool(d.get('success'))),
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))
