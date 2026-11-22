#!/usr/bin/env python3
"""Measure the 26-09-24 policy through the tinyPython harness.

Runs the command space, then recomputes gait metrics from each trace with
MuJoCo forward kinematics. Writes one JSON report next to this script.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
os.environ.setdefault('TINYPYTHON_ASSETS', str(HERE))
sys.path.insert(0, 'C:/æ/tinypython')
import tinypython as TP  # noqa: E402
import mujoco  # noqa: E402

MJCF = HERE / 'model' / 'asimov_1_policy_physics.xml'
D2R = 180.0 / np.pi


def fk_metrics(trace_path: Path) -> dict:
    d = json.loads(trace_path.read_text(encoding='utf-8'))
    qpos = np.array(d['qpos'], float)          # (F, 30)
    base = np.array(d['base'], float)          # (F, 7)
    model = mujoco.MjModel.from_xml_path(str(MJCF))
    data = mujoco.MjData(model)
    lid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'left_ankle_roll_link')
    rid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'right_ankle_roll_link')
    lz = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'left_knee_joint')
    rz = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'right_knee_joint')
    lq = model.jnt_qposadr[lz]
    rq = model.jnt_qposadr[rz]
    lf, rf, lz_j, rz_j = [], [], [], []
    for q in qpos:
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        lf.append(np.asarray(data.xpos[lid]).copy())
        rf.append(np.asarray(data.xpos[rid]).copy())
        lz_j.append(float(q[lq]))
        rz_j.append(float(q[rq]))
    lf, rf = np.array(lf), np.array(rf)
    sep = np.linalg.norm(lf - rf, axis=1)
    sep_xy = np.linalg.norm((lf - rf)[:, :2], axis=1)
    lz_j, rz_j = np.array(lz_j), np.array(rz_j)
    return {
        'frames': int(len(qpos)),
        'foot_sep_3d_min': round(float(sep.min()), 4),
        'foot_sep_3d_max': round(float(sep.max()), 4),
        'foot_sep_3d_mean': round(float(sep.mean()), 4),
        'foot_sep_xy_mean': round(float(sep_xy.mean()), 4),
        'left_knee_deg_min': round(float(lz_j.min() * D2R), 2),
        'left_knee_deg_max': round(float(lz_j.max() * D2R), 2),
        'left_knee_swing_deg': round(float((lz_j.max() - lz_j.min()) * D2R), 2),
        'right_knee_deg_min': round(float(rz_j.min() * D2R), 2),
        'right_knee_deg_max': round(float(rz_j.max() * D2R), 2),
        'right_knee_swing_deg': round(float((rz_j.max() - rz_j.min()) * D2R), 2),
        'left_foot_z_abs_min': round(float(lf[:, 2].min()), 4),
        'left_foot_z_abs_max': round(float(lf[:, 2].max()), 4),
        'right_foot_z_abs_min': round(float(rf[:, 2].min()), 4),
        'right_foot_z_abs_max': round(float(rf[:, 2].max()), 4),
        'left_foot_z_rel_base_max': round(float((lf[:, 2] - base[:, 2]).max()), 4),
        'right_foot_z_rel_base_max': round(float((rf[:, 2] - base[:, 2]).max()), 4),
        'base_z_min': round(float(base[:, 2].min()), 4),
    }


COMMANDS = [
    ('stand',        0.0,  0.0, 0.0),
    ('vx0.4',        0.4,  0.0, 0.0),
    ('vx0.6',        0.6,  0.0, 0.0),
    ('turn_wz0.5',   0.0,  0.0, 0.5),
    ('back_vx-0.2', -0.2,  0.0, 0.0),
    ('strafe_vy0.3', 0.0,  0.3, 0.0),
    ('strafe_vy-0.3',0.0, -0.3, 0.0),
]


def main() -> dict:
    report = {'policy': 'Menlo/asimov1-locomotion-26-09-24',
              'policy_sha256': TP.hashlib.sha256((HERE / 'policy' / 'policy.onnx').read_bytes()).hexdigest(),
              'mjcf': str(MJCF), 'commands': {}}
    for name, vx, vy, wz in COMMANDS:
        out = HERE / f'trace_{name}.json'
        r = TP.walk(out, vx=vx, vy=vy, wz=wz, duration=8.0)
        v = TP.verify(out)
        m = fk_metrics(out)
        report['commands'][name] = {
            'cmd': [vx, vy, wz],
            'walk_ok': r.get('ok'), 'verify_ok': v.get('ok'),
            'travel_x_m': v.get('travel_x_m'), 'travel_y_m': v.get('travel_y_m'),
            'min_z_m': v.get('min_z_m'), 'fell': v.get('fell'),
            'upright': r.get('upright'), 'obeyed_command': r.get('obeyed_command'),
            'ticks': r.get('ticks'), 'steps': r.get('steps'),
            'wall_s': r.get('wall_s'), 'realtime_factor': r.get('realtime_factor'),
            'receipt_sha256': r.get('receipt'),
            'gait': m,
        }
        print(f"[{name}] ok={r.get('ok')} x={v.get('travel_x_m')} "
              f"min_z={v.get('min_z_m')} sep={m['foot_sep_3d_mean']} "
              f"kneeL={m['left_knee_swing_deg']} kneeR={m['right_knee_swing_deg']}")
    (HERE / 'measure_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    main()
