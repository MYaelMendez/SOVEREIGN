#!/usr/bin/env python3
"""measure.py — run the Menlo Asimov *upper-body-blind* policy (45 obs -> 12 actions).

WHY THIS FILE EXISTS
    The sibling harness `C:/æ/tinypython/tinypython.py` is pinned to the
    2026-08-18 policy contract: 78-float observation, 23 actions, one ONNX
    input named `obs` of shape [1, 78]. This checkpoint is a DIFFERENT
    contract:

        obs   [1, 45]  base_ang_vel*0.25, projected_gravity, command,
                        joint_pos slots (12), joint_vel slots (12), last action
        act   [1, 12]  12 leg joints; waist/arms are NOT policy-driven

    Feeding the 45-dim observation into that harness raises
    `InvalidArgument: Got invalid dimensions for input: obs ... Got: 78
    Expected: 45`. So the stock harness cannot measure this checkpoint, and a
    number produced by it would be a number about the WRONG policy.

    This runner reproduces the inference contract documented in the policy's
    own README, its ONNX deploy metadata, and `env.yaml`, against the same
    pinned physics MJCF. It invents nothing: every constant is read from the
    artifact or quoted from env.yaml.

GOVERNANCE
    Simulation only. No socket, no serial port, no motor. `grants:false`.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
POLICY = HERE / 'policy' / 'policy.onnx'
MJCF = HERE / 'model' / 'asimov_1_policy_physics.xml'

# ── the 12 leg joints, in the policy's own output order ──────────────────────
LEG_JOINTS = [
    'left_hip_pitch_joint', 'left_hip_roll_joint', 'left_hip_yaw_joint',
    'left_knee_joint', 'left_ankle_pitch_joint', 'left_ankle_roll_joint',
    'right_hip_pitch_joint', 'right_hip_roll_joint', 'right_hip_yaw_joint',
    'right_knee_joint', 'right_ankle_pitch_joint', 'right_ankle_roll_joint',
]
# observation slot partition (indices into LEG_JOINTS), from env.yaml
SLOTS = [[0, 1, 6, 7], [2, 3, 8, 9], [4, 5, 10, 11]]

# ── 11 upper-body joints, held at their env.yaml init pose ───────────────────
UPPER_JOINTS = [
    'waist_yaw_joint',
    'right_shoulder_pitch_joint', 'right_shoulder_roll_joint',
    'right_shoulder_yaw_joint', 'right_elbow_joint', 'right_wrist_yaw_joint',
    'left_shoulder_pitch_joint', 'left_shoulder_roll_joint',
    'left_shoulder_yaw_joint', 'left_elbow_joint', 'left_wrist_yaw_joint',
]
UPPER_DEFAULT = {
    'waist_yaw_joint': 0.0,
    'right_shoulder_pitch_joint': 0.25, 'left_shoulder_pitch_joint': -0.25,
    'right_shoulder_roll_joint': 0.05, 'left_shoulder_roll_joint': -0.05,
    'right_shoulder_yaw_joint': 0.0, 'left_shoulder_yaw_joint': 0.0,
    'right_elbow_joint': -0.4, 'left_elbow_joint': 0.4,
    'right_wrist_yaw_joint': 0.0, 'left_wrist_yaw_joint': 0.0,
}
# env.yaml actuator groups (stiffness, damping, effort_limit)
UPPER_GAINS = {
    'waist_yaw_joint': (65.0, 5.0, 40.0),
    'right_shoulder_pitch_joint': (57.0, 5.0, 30.0),
    'left_shoulder_pitch_joint': (57.0, 5.0, 30.0),
    'right_shoulder_roll_joint': (86.0, 5.0, 25.0),
    'left_shoulder_roll_joint': (86.0, 5.0, 25.0),
    'right_shoulder_yaw_joint': (96.0, 5.0, 20.0),
    'left_shoulder_yaw_joint': (96.0, 5.0, 20.0),
    'right_elbow_joint': (40.0, 2.0, 12.0),
    'left_elbow_joint': (40.0, 2.0, 12.0),
    'right_wrist_yaw_joint': (40.0, 2.0, 12.0),
    'left_wrist_yaw_joint': (40.0, 2.0, 12.0),
}

POLICY_DT = 0.02        # 50 Hz
SUBSTEPS = 4            # physics 200 Hz (sim.dt 0.005)
FALL_Z = 0.35


def quat_to_mat(q):
    w, x, y, z = q
    n = np.sqrt(w*w + x*x + y*y + z*z) or 1.0
    w, x, y, z = w/n, x/n, y/n, z/n
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)],
                     [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)]])


def read_deploy_metadata() -> dict:
    """Read the contract the exporter recorded inside the ONNX itself."""
    import onnxruntime as ort
    md = ort.InferenceSession(str(POLICY), providers=['CPUExecutionProvider']) \
        .get_modelmeta().custom_metadata_map
    return {
        'joint_names': json.loads(md['joint_names']),
        'action_offset': json.loads(md['action_offset']),
        'action_scale': json.loads(md['action_scale']),
        'action_clip': json.loads(md['action_clip']),
        'joint_stiffness': json.loads(md['joint_stiffness']),
        'joint_damping': json.loads(md['joint_damping']),
        'obs_dim': int(md['obs_dim']),
        'action_dim': int(md['action_dim']),
        'policy_rate_hz': float(md['policy_rate_hz']),
        'sim_dt': float(md['sim_dt']),
        'decimation': int(md['decimation']),
        'observation_names': json.loads(md['observation_names']),
        'raw_action_clip': md['raw_action_clip'],
        'trained_commit': md['trained_commit'],
    }


def simulate(vx=0.4, vy=0.0, wz=0.0, duration=12.0, fps=24,
             schedule=None, lpf_alpha=None, action_lag=0) -> dict:
    """Run the policy against MuJoCo. The base trajectory emerges from control."""
    import mujoco, onnxruntime as ort

    if not POLICY.exists() or not MJCF.exists():
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': f'assets missing: policy={POLICY.exists()} mjcf={MJCF.exists()}'}

    meta = read_deploy_metadata()
    default_pos = np.array(meta['action_offset'], np.float32)
    action_scale = np.array(meta['action_scale'], np.float32)
    kp = np.array(meta['joint_stiffness'], np.float32)
    kd = np.array(meta['joint_damping'], np.float32)
    # effort limits are NOT in the ONNX metadata; quoted from env.yaml actuators
    tau_limit = np.array([45, 45, 28, 45, 40, 17,
                          45, 45, 28, 45, 40, 17], np.float32)
    ankle_roll = [i for i, n in enumerate(meta['joint_names'])
                  if n.endswith('ankle_roll_joint')]
    ankle_clip = 0.09
    if meta['action_clip']:
        for i, c in enumerate(meta['action_clip']):
            if c and c[0] is not None:
                ankle_clip = float(c[0])

    sess = ort.InferenceSession(str(POLICY), providers=['CPUExecutionProvider'])
    in_name = sess.get_inputs()[0].name

    model = mujoco.MjModel.from_xml_path(str(MJCF))
    data = mujoco.MjData(model)
    if model.nq != 30 or model.nv != 29:
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': f'unexpected MJCF nq={model.nq} nv={model.nv}'}

    leg_ids = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, j)
                        for j in LEG_JOINTS])
    up_ids = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, j)
                       for j in UPPER_JOINTS])
    if np.any(leg_ids < 0) or np.any(up_ids < 0):
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': 'joints missing from MJCF'}
    leg_qpos = np.array([model.jnt_qposadr[i] for i in leg_ids])
    leg_qvel = np.array([model.jnt_dofadr[i] for i in leg_ids])
    up_qpos = np.array([model.jnt_qposadr[i] for i in up_ids])
    up_qvel = np.array([model.jnt_dofadr[i] for i in up_ids])
    leg_act = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, j[:-7])
                        for j in LEG_JOINTS])
    up_act = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, j[:-7])
                       for j in UPPER_JOINTS])
    if np.any(leg_act < 0) or np.any(up_act < 0):
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': 'actuators missing from MJCF'}
    for i, aid in enumerate(leg_act):
        model.actuator_ctrlrange[aid, 0] = -float(tau_limit[i])
        model.actuator_ctrlrange[aid, 1] = float(tau_limit[i])
    for i, aid in enumerate(up_act):
        model.actuator_ctrlrange[aid, 0] = -UPPER_GAINS[UPPER_JOINTS[i]][2]
        model.actuator_ctrlrange[aid, 1] = UPPER_GAINS[UPPER_JOINTS[i]][2]

    foot_l = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'left_ankle_roll_link')
    foot_r = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'right_ankle_roll_link')

    mujoco.mj_resetData(model, data)
    data.qpos[:3] = [0, 0, 0.639]
    data.qpos[3:7] = [1, 0, 0, 0]
    data.qpos[leg_qpos] = default_pos
    data.qpos[up_qpos] = [UPPER_DEFAULT[j] for j in UPPER_JOINTS]
    mujoco.mj_forward(model, data)

    base_cmd = np.array([vx, vy, wz], np.float32)
    cmd = base_cmd.copy()
    segs = []
    if schedule:
        for s in schedule:
            t0, t1 = float(s['t0']), float(s['t1'])
            if not (0.0 <= t0 < t1 <= duration + 1e-6):
                return {'ok': False, 'refused': True, 'grants': False,
                        'reason': f'segment [{t0},{t1}] outside [0,{duration}]'}
            segs.append((t0, t1, np.array([float(s.get('vx', 0.0)),
                                           float(s.get('vy', 0.0)),
                                           float(s.get('wz', 0.0))], np.float32)))
        segs.sort()
        for i in range(1, len(segs)):
            if segs[i][0] < segs[i-1][1] - 1e-6:
                return {'ok': False, 'refused': True, 'grants': False,
                        'reason': f'segments overlap at t={segs[i][0]}'}

    ticks = int(round(duration / POLICY_DT))
    prev_action = np.zeros(12, np.float32)
    filtered = default_pos.copy()
    hist = [filtered.copy() for _ in range(action_lag + 1)]
    qpos_h, base_h, com_h, feet_h = [], [], [], []
    min_z, fell_at = 99.0, None
    t0 = time.perf_counter()

    for t in range(ticks):
        if segs:
            now = t * POLICY_DT
            cmd = base_cmd.copy()
            for (s0, s1, sc) in segs:
                if s0 <= now < s1:
                    cmd = sc
                    break
        gravity = quat_to_mat(data.qpos[3:7]).T @ np.array([0.0, 0.0, -1.0])
        obs = np.concatenate([
            0.25 * data.qvel[3:6],
            gravity.astype(np.float32),
            cmd,
            *[(data.qpos[leg_qpos[s]] - default_pos[s]).astype(np.float32) for s in SLOTS],
            *[(0.1 * data.qvel[leg_qvel[s]]).astype(np.float32) for s in SLOTS],
            prev_action,
        ]).astype(np.float32)
        if obs.shape != (45,):
            return {'ok': False, 'refused': True, 'grants': False,
                    'reason': f'obs shape {obs.shape}, expected (45,)'}
        raw = np.asarray(sess.run(None, {in_name: obs[None, :]})[0])[0]
        if raw.shape != (12,) or not np.all(np.isfinite(raw)):
            return {'ok': False, 'refused': True, 'grants': False,
                    'reason': 'policy returned non-finite actions'}
        prev_action = raw.astype(np.float32)
        target = default_pos + action_scale * raw
        for i in ankle_roll:
            target[i] = float(np.clip(target[i], -ankle_clip, ankle_clip))
        if lpf_alpha is not None:
            filtered = lpf_alpha * target + (1 - lpf_alpha) * filtered
        else:
            filtered = target
        hist.append(filtered.copy())
        delayed = hist[max(0, len(hist) - 1 - action_lag)]
        for _ in range(SUBSTEPS):
            for i, aid in enumerate(leg_act):
                tau = kp[i] * (delayed[i] - data.qpos[leg_qpos[i]]) \
                    - kd[i] * data.qvel[leg_qvel[i]]
                data.ctrl[aid] = float(np.clip(tau, -tau_limit[i], tau_limit[i]))
            for i, aid in enumerate(up_act):
                g = UPPER_GAINS[UPPER_JOINTS[i]]
                tau = g[0] * (UPPER_DEFAULT[UPPER_JOINTS[i]] - data.qpos[up_qpos[i]]) \
                    - g[1] * data.qvel[up_qvel[i]]
                data.ctrl[aid] = float(np.clip(tau, -g[2], g[2]))
            mujoco.mj_step(model, data)
        z = float(data.qpos[2])
        min_z = min(min_z, z)
        if z < FALL_Z and fell_at is None:
            fell_at = round(t * POLICY_DT, 3)
        qpos_h.append(data.qpos.copy())
        base_h.append(data.qpos[:7].copy())
        mujoco.mj_comPos(model, data)
        com_h.append(np.asarray(data.subtree_com[0]).copy())
        feet_h.append([np.asarray(data.xpos[foot_l]).copy(),
                       np.asarray(data.xpos[foot_r]).copy()])

    wall = time.perf_counter() - t0
    n = int(round(duration * fps))
    idx = [min(len(qpos_h)-1, int(f/fps/POLICY_DT)) for f in range(n)]
    qpos = np.array([qpos_h[i] for i in idx])
    base = np.array([base_h[i] for i in idx])
    com = np.array([com_h[i] for i in idx])
    feet = np.array([feet_h[i] for i in idx])

    base_x = float(base[-1, 0] - base[0, 0])
    base_y = float(base[-1, 1] - base[0, 1])
    com_x = float(com[-1, 0] - com[0, 0])
    upright = fell_at is None

    # ── command obedience ────────────────────────────────────────────────────
    if segs:
        per = []
        for (s0, s1, sc) in segs:
            i0 = min(len(base)-1, int(s0 * fps))
            i1 = min(len(base)-1, max(i0+1, int(s1 * fps)))
            dx = float(base[i1, 0] - base[i0, 0])
            dy = float(base[i1, 1] - base[i0, 1])
            sp = float(np.linalg.norm(sc[:2]))
            if sp < 0.05 and abs(float(sc[2])) < 0.05:
                ok = (dx*dx + dy*dy) ** 0.5 < 0.30
                what = 'stand'
            elif abs(float(sc[2])) > 0.05:
                def yaw_at(k):
                    w, x, y, z = base[k, 3:7]
                    return float(np.arctan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)))
                ok = abs(yaw_at(i1) - yaw_at(i0)) > 0.05
                what = 'turn'
            else:
                ok = (dx*float(sc[0]) + dy*float(sc[1])) > 0.05
                what = 'move'
            per.append({'t0': s0, 't1': s1, 'intent': what, 'cmd': sc.tolist(),
                        'dx': round(dx, 4), 'dy': round(dy, 4), 'obeyed': bool(ok)})
        obeyed = all(s['obeyed'] for s in per)
    elif float(np.linalg.norm(base_cmd[:2])) < 0.05 and abs(float(base_cmd[2])) < 0.05:
        obeyed = abs(base_x) < 0.30
    elif abs(float(base_cmd[2])) > 0.05:
        q = base[-1, 3:7]
        yaw = float(np.arctan2(2*(q[0]*q[2] + q[1]*q[3]),
                               1 - 2*(q[2]**2 + q[3]**2)))
        obeyed = abs(yaw) > 0.05
    else:
        along = base_x*float(base_cmd[0]) + base_y*float(base_cmd[1])
        obeyed = along > 0.05
    success = bool(upright and obeyed)

    # ── gait, measured from the feet ─────────────────────────────────────────
    knee_l = np.array([qpos[:, 10]]).ravel()   # left_knee qpos index 10
    knee_r = np.array([qpos[:, 16]]).ravel()   # right_knee qpos index 16
    sep = np.linalg.norm(feet[:, 0, :2] - feet[:, 1, :2], axis=1)
    gait = {
        'foot_separation_min_m': round(float(sep.min()), 4),
        'foot_separation_max_m': round(float(sep.max()), 4),
        'foot_separation_mean_m': round(float(sep.mean()), 4),
        'left_knee_min_deg': round(float(np.degrees(knee_l.min())), 2),
        'left_knee_max_deg': round(float(np.degrees(knee_l.max())), 2),
        'right_knee_min_deg': round(float(np.degrees(knee_r.min())), 2),
        'right_knee_max_deg': round(float(np.degrees(knee_r.max())), 2),
        'left_foot_z_min_m': round(float(feet[:, 0, 2].min()), 4),
        'right_foot_z_min_m': round(float(feet[:, 1, 2].min()), 4),
        'left_foot_z_max_m': round(float(feet[:, 0, 2].max()), 4),
        'right_foot_z_max_m': round(float(feet[:, 1, 2].max()), 4),
    }

    trace = {
        'authority': 'HUMAN://ROOT',
        'policy': 'Menlo/asimov1-locomotion-26-10-17-upper-body-blind',
        'policy_path': str(POLICY),
        'policy_sha256': hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        'mjcf': str(MJCF),
        'mjcf_sha256': hashlib.sha256(MJCF.read_bytes()).hexdigest(),
        'contract': {'obs_dim': 45, 'action_dim': 12, 'policy_rate_hz': 50.0,
                     'sim_dt': 0.005, 'decimation': 4,
                     'deploy_metadata': meta},
        'leg_joints': LEG_JOINTS, 'joint_refs': default_pos.tolist(),
        'qpos': qpos.tolist(), 'base': base.tolist(), 'com': com.tolist(),
        'feet': feet.tolist(),
        'command': base_cmd.tolist(), 'fps': fps, 'nq': int(model.nq), 'nv': int(model.nv),
        'schedule': ([{'t0': s0, 't1': s1, 'cmd': sc.tolist()} for s0, s1, sc in segs]
                     if segs else None),
        'segments': per if segs else None,
        'policy_ticks': ticks, 'physics_steps': ticks*SUBSTEPS, 'duration_s': duration,
        'base_x': base_x, 'base_y': base_y, 'com_x': com_x,
        'min_z': min_z, 'fell_at': fell_at, 'success': success,
        'gait': gait,
        'assumptions': {
            'upper_body': 'held at env.yaml init pose with env.yaml PD gains '
                          '(the policy does not drive waist/arms)',
            'action_filter': ('none (documented runtime: target = default + '
                              'scale*action, ankle-roll clip +-0.09)'
                              if lpf_alpha is None else f'one-pole alpha {lpf_alpha}'),
            'action_lag_substeps': action_lag,
            'obs_delay': 'none (documented recipe; env.yaml delayed_obs not applied)',
        },
    }
    return {'ok': success, 'trace': trace, 'wall_s': round(wall, 2),
            'realtime_factor': round(duration/wall, 2),
            'grants': False, 'executed': False, 'hardware': False,
            'note': 'simulation only. Not a command to hardware.'}


def verify(trace: dict) -> dict:
    """Recompute the verdict from the trace, never from its success flag."""
    base = np.array(trace['base'])
    z = base[:, 2]
    travel = float(base[-1, 0] - base[0, 0])
    travel_y = float(base[-1, 1] - base[0, 1])
    fell = bool((z < FALL_Z).any())
    cmd = np.array(trace.get('command', [0.4, 0, 0]), float)
    if float(np.linalg.norm(cmd[:2])) < 0.05 and abs(float(cmd[2])) < 0.05:
        obeyed = abs(travel) < 0.30
    elif abs(float(cmd[2])) > 0.05:
        q = base[-1, 3:7]
        yaw = float(np.arctan2(2*(q[0]*q[2] + q[1]*q[3]),
                               1 - 2*(q[2]**2 + q[3]**2)))
        obeyed = abs(yaw) > 0.05
    else:
        obeyed = travel*float(cmd[0]) + travel_y*float(cmd[1]) > 0.05
    return {'ok': bool(not fell and obeyed), 'obeyed_command': obeyed,
            'command': cmd.tolist(), 'frames': len(base),
            'duration_s': trace.get('duration_s'),
            'travel_x_m': round(travel, 4), 'travel_y_m': round(travel_y, 4),
            'min_z_m': round(float(z.min()), 4), 'fell': fell,
            'claims_success': trace.get('success'),
            'agrees_with_claim': bool((not fell and obeyed) == bool(trace.get('success'))),
            'note': 'recomputed from the trace'}


def doctor() -> dict:
    out = {'ok': False, 'checks': {}}
    try:
        import onnxruntime as ort
        out['checks']['onnxruntime'] = ort.__version__
    except Exception as exc:
        out['checks']['onnxruntime'] = f'MISSING ({exc})'
    try:
        import mujoco
        out['checks']['mujoco'] = mujoco.__version__
    except Exception as exc:
        out['checks']['mujoco'] = f'MISSING ({exc})'
    out['checks']['policy'] = ({'path': str(POLICY), 'bytes': POLICY.stat().st_size,
                                'sha256': hashlib.sha256(POLICY.read_bytes()).hexdigest()}
                               if POLICY.exists() else f'MISSING {POLICY}')
    out['checks']['mjcf'] = str(MJCF) if MJCF.exists() else f'MISSING {MJCF}'
    try:
        out['checks']['deploy_metadata'] = read_deploy_metadata()
    except Exception as exc:
        out['checks']['deploy_metadata'] = f'UNREADABLE ({exc})'
    out['checks']['stock_harness_contract'] = {
        'path': 'C:/æ/tinypython/tinypython.py',
        'obs_dim': 78, 'action_dim': 23,
        'compatible_with_this_checkpoint': False,
        'reason': 'onnxruntime InvalidArgument: obs Got 78 Expected 45',
    }
    out['ok'] = all('MISSING' not in str(v) for k, v in out['checks'].items()
                    if k != 'stock_harness_contract')
    return out


def main():
    ap = argparse.ArgumentParser(prog='measure')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor')
    w = sub.add_parser('walk')
    w.add_argument('out')
    w.add_argument('--vx', type=float, default=0.4)
    w.add_argument('--vy', type=float, default=0.0)
    w.add_argument('--wz', type=float, default=0.0)
    w.add_argument('--duration', type=float, default=12.0)
    w.add_argument('--fps', type=int, default=24)
    w.add_argument('--schedule', help='JSON file: [{"t0":0,"t1":4,"vx":0.4},...]')
    w.add_argument('--lpf', type=float, default=None,
                   help='one-pole target filter alpha (documented runtime uses none)')
    w.add_argument('--lag', type=int, default=0, help='action lag in substeps')
    v = sub.add_parser('verify')
    v.add_argument('file')
    a = ap.parse_args()

    if a.cmd == 'doctor':
        res = doctor()
    elif a.cmd == 'walk':
        sched = None
        if a.schedule:
            sched = json.loads(Path(a.schedule).read_text(encoding='utf-8'))
            if isinstance(sched, dict):
                sched = sched.get('schedule', sched.get('segments'))
        res = simulate(a.vx, a.vy, a.wz, a.duration, a.fps, sched,
                       lpf_alpha=a.lpf, action_lag=a.lag)
        if 'trace' in res:
            out = Path(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(res['trace'], separators=(',', ':')),
                           encoding='utf-8')
            res['trace_file'] = str(out)
            res['trace_sha256'] = hashlib.sha256(out.read_bytes()).hexdigest()
            res['trace_size_bytes'] = out.stat().st_size
            res['gait'] = res['trace']['gait']
            res['base_x'] = round(res['trace']['base_x'], 4)
            res['base_y'] = round(res['trace']['base_y'], 4)
            res['com_x'] = round(res['trace']['com_x'], 4)
            res['min_z'] = round(res['trace']['min_z'], 4)
            res['fell_at'] = res['trace']['fell_at']
            res['upright'] = res['trace']['fell_at'] is None
            res['obeyed_command'] = (res['trace']['segments'] is None or
                                    all(s['obeyed'] for s in res['trace']['segments']))
            res['policy_ticks'] = res['trace']['policy_ticks']
            res['physics_steps'] = res['trace']['physics_steps']
            res.pop('trace')
    else:
        res = verify(json.loads(Path(a.file).read_text(encoding='utf-8')))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
