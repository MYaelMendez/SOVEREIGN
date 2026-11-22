#!/usr/bin/env python3
"""Measure Menlo asimov1-locomotion-26-10-05-upper-body through tinyPython's loop.

The pinned tinyPython harness targets the 0818 policy (23 actions). This policy
is a DIFFERENT inference contract: 12 leg-only actions, per-joint ankle gains
recorded in the ONNX metadata, ankle-roll action scale 0.08, and an ankle-roll
target clip of +-0.09 rad. Running the stock walk() would feed 12 actions into a
23-wide slot and report garbage, so this script mirrors the harness's PD loop,
observation recipe and command logic exactly, and overrides only the terms this
policy's own metadata specifies.

    obs  78 floats, same order as env.yaml: angvel*0.25, projected gravity,
         [vx,vy,wz], joint_pos slots (3), joint_vel slots*0.1, prev action(23)
    act  12 raw leg actions -> clip(+-10) -> default + scale*a,
         ankle-roll target clipped to +-0.09; waist+arms held at default (PD)
    PD   per-joint kp/kd from ONNX metadata (legs), 0.02 s period, 4 substeps
    prev 12 leg actions + 11 zeros = 23 (the policy's own prev-action layout)

GOVERNANCE: this produces a SIMULATION TRACE only. grants:false, executed:false.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, 'C:/æ/tinypython')
import tinypython as TP  # JOINTS, DEFAULT_POS, SLOTS, PD constants, quat_to_mat

import mujoco
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
POLICY = HERE / 'policy' / 'policy.onnx'
MJCF = HERE / 'model' / 'asimov_1_policy_physics.xml'

# ── the contract, read from the ONNX metadata ────────────────────────────────
_sess = ort.InferenceSession(str(POLICY), providers=['CPUExecutionProvider'])
_meta = _sess.get_modelmeta().custom_metadata_map
IN_NAME = _sess.get_inputs()[0].name

LEG_JOINTS = json.loads(_meta['joint_names'])            # 12, in action order
ACTION_SCALE = np.array(json.loads(_meta['action_scale']), np.float32)   # 12
ACTION_OFFSET = np.array(json.loads(_meta['action_offset']), np.float32)  # 12
KP_LEG = np.array(json.loads(_meta['joint_stiffness']), np.float32)       # 12
KD_LEG = np.array(json.loads(_meta['joint_damping']), np.float32)         # 12
_aclip = json.loads(_meta['action_clip'])                # 12 pairs or null

# per-joint target clip, expressed over the 23-joint vector
TARGET_CLIP = np.full((23, 2), np.nan, np.float32)
for i, pair in enumerate(_aclip):
    if pair and pair[0] is not None:
        TARGET_CLIP[i, 0], TARGET_CLIP[i, 1] = float(pair[0]), float(pair[1])

# action order (12) -> harness joint index (0..22)
LEG_IDX = [TP.JOINTS.index(j) for j in LEG_JOINTS]

# harness PD gains, overridden on the leg joints by the policy metadata
KP = TP.KP.copy()
KD = TP.KD.copy()
for k, ji in enumerate(LEG_IDX):
    KP[ji] = KP_LEG[k]
    KD[ji] = KD_LEG[k]

ACTION_CLIP = 10.0          # raw action clip, as in the harness
FALL_Z = TP.FALL_Z
OBS_NOISE = 0.0             # training randomizations are NOT reproduced


def quat_to_mat(q):
    return TP.quat_to_mat(q)


def build_obs(data, cmd, prev_action, qpos_adr, qvel_adr):
    gravity = quat_to_mat(data.qpos[3:7]).T @ np.array([0.0, 0.0, -1.0])
    return np.concatenate([
        0.25 * data.qvel[3:6],
        gravity.astype(np.float32),
        cmd,
        *[(data.qpos[qpos_adr[s]] - TP.DEFAULT_POS[s]).astype(np.float32) for s in TP.SLOTS],
        *[(0.1 * data.qvel[qvel_adr[s]]).astype(np.float32) for s in TP.SLOTS],
        prev_action,
    ]).astype(np.float32)


def walk(out: Path, vx=0.4, vy=0.0, wz=0.0, duration=12.0, fps=24):
    model = mujoco.MjModel.from_xml_path(str(MJCF))
    data = mujoco.MjData(model)
    assert model.nq == 30 and model.nv == 29, f'unexpected model nq={model.nq} nv={model.nv}'

    qadr = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in TP.JOINTS])
    qpos_adr = np.array([model.jnt_qposadr[i] for i in qadr])
    qvel_adr = np.array([model.jnt_dofadr[i] for i in qadr])
    act_adr = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, j[:-7])
                        for j in TP.JOINTS])
    assert np.all(act_adr >= 0) and np.all(qadr >= 0)
    for i, aid in enumerate(act_adr):
        model.actuator_ctrlrange[aid, 0] = -float(TP.TAU_LIMIT[i])
        model.actuator_ctrlrange[aid, 1] = float(TP.TAU_LIMIT[i])

    mujoco.mj_resetData(model, data)
    data.qpos[:3] = [0, 0, 0.639]
    data.qpos[3:7] = [1, 0, 0, 0]
    data.qpos[qpos_adr] = TP.DEFAULT_POS
    mujoco.mj_forward(model, data)

    base_cmd = np.array([vx, vy, wz], np.float32)
    cmd = base_cmd.copy()
    ticks = int(round(duration / TP.POLICY_DT))

    prev_action = np.zeros(23, np.float32)               # 12 raw + 11 zeros
    filtered = TP.DEFAULT_POS.copy()
    hist = [TP.DEFAULT_POS.copy() for _ in range(TP.ACTION_LAG + 1)]

    base_h, com_h, foot_h, knee_h = [], [], [], []
    min_z, fell_at = 99.0, None
    t0 = time.perf_counter()

    for t in range(ticks):
        obs = build_obs(data, cmd, prev_action, qpos_adr, qvel_adr)
        assert obs.shape == (78,), obs.shape
        raw = np.asarray(_sess.run(None, {IN_NAME: obs[None, :]})[0])[0]
        assert raw.shape == (12,), raw.shape
        if not np.all(np.isfinite(raw)):
            return {'ok': False, 'refused': True, 'reason': 'policy returned non-finite actions'}
        leg = np.clip(raw, -ACTION_CLIP, ACTION_CLIP).astype(np.float32)

        # 12 leg actions -> 23-wide target; waist+arms held at default
        action23 = np.zeros(23, np.float32)
        action23[LEG_IDX] = leg
        prev_action = action23.copy()                    # policy's prev-action layout

        target = TP.DEFAULT_POS + 0.0 * action23
        tgt_leg = TP.DEFAULT_POS[LEG_IDX] + ACTION_SCALE * leg
        lo, hi = TARGET_CLIP[LEG_IDX, 0], TARGET_CLIP[LEG_IDX, 1]
        tgt_leg = np.where(np.isnan(lo), tgt_leg, np.clip(tgt_leg, lo, hi))
        target[LEG_IDX] = tgt_leg

        filtered = TP.LPF_ALPHA * target + (1 - TP.LPF_ALPHA) * filtered
        hist.append(filtered.copy())
        delayed = hist[max(0, len(hist) - 1 - TP.ACTION_LAG)]

        for _ in range(TP.SUBSTEPS):
            for i, aid in enumerate(act_adr):
                tau = KP[i] * (delayed[i] - data.qpos[qpos_adr[i]]) - KD[i] * data.qvel[qvel_adr[i]]
                data.ctrl[aid] = float(np.clip(tau, -TP.TAU_LIMIT[i], TP.TAU_LIMIT[i]))
            mujoco.mj_step(model, data)

        z = float(data.qpos[2])
        min_z = min(min_z, z)
        if z < FALL_Z and fell_at is None:
            fell_at = round(t * TP.POLICY_DT, 3)
        base_h.append(data.qpos[:7].copy())
        mujoco.mj_comPos(model, data)
        com_h.append(np.asarray(data.subtree_com[0]).copy())
        # foot height = z of each ankle_roll_link body
        foot_h.append(np.array([
            data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'left_ankle_roll_link')][2],
            data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'right_ankle_roll_link')][2],
        ]))
        knee_h.append(np.array([data.qpos[qpos_adr[3]], data.qpos[qpos_adr[9]]]))

    wall = time.perf_counter() - t0
    base = np.array(base_h)
    com = np.array(com_h)
    base_x = float(base[-1, 0] - base[0, 0])
    base_y = float(base[-1, 1] - base[0, 1])
    com_x = float(com[-1, 0] - com[0, 0])
    feet = np.array(foot_h)
    knees = np.array(knee_h)

    # success: upright AND obeyed the command (mirrors harness verify logic)
    speed = float(np.linalg.norm(base_cmd[:2]))
    upright = fell_at is None
    if speed < 0.05 and abs(float(base_cmd[2])) < 0.05:
        obeyed = (base_x ** 2 + base_y ** 2) ** 0.5 < 0.30
    elif abs(float(base_cmd[2])) > 0.05:
        q = base[-1, 3:7]
        yaw = float(np.arctan2(2 * (q[0] * q[2] + q[1] * q[3]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)))
        obeyed = abs(yaw) > 0.05
    else:
        obeyed = base_x * float(base_cmd[0]) + base_y * float(base_cmd[1]) > 0.05
    success = bool(upright and obeyed)

    trace = {
        'authority': 'HUMAN://ROOT',
        'policy': 'Menlo/asimov1-locomotion-26-10-05-upper-body',
        'policy_sha256': hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        'contract': '12 leg actions; ankle gains from ONNX metadata; ankle-roll scale 0.08, target clip +-0.09',
        'command': base_cmd.tolist(),
        'base': base.tolist(),
        'policy_ticks': ticks, 'physics_steps': ticks * TP.SUBSTEPS, 'duration_s': duration,
        'base_x': base_x, 'base_y': base_y, 'com_x': com_x, 'min_z': min_z, 'fell_at': fell_at,
        'success': success,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace, separators=(',', ':')), encoding='utf-8')

    return {
        'ok': success, 'trace': str(out),
        'command': base_cmd.tolist(),
        'base_x': round(base_x, 4), 'base_y': round(base_y, 4), 'com_x': round(com_x, 4),
        'min_z': round(min_z, 4), 'fell_at': fell_at, 'upright': upright,
        'obeyed_command': obeyed, 'ticks': ticks, 'steps': ticks * TP.SUBSTEPS,
        'wall_s': round(wall, 2), 'realtime_factor': round(duration / wall, 2),
        'left_knee_swing_deg': round(float(np.degrees(knees[:, 0].max() - knees[:, 0].min())), 2),
        'right_knee_swing_deg': round(float(np.degrees(knees[:, 1].max() - knees[:, 1].min())), 2),
        'foot_z_spread_m': round(float(feet[:, 0].max() - feet[:, 0].min()), 4),
        'grants': False, 'executed': False, 'hardware': False,
        'note': 'simulation only; upper body held at default (policy controls 12 legs)',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--vx', type=float, default=0.4)
    ap.add_argument('--vy', type=float, default=0.0)
    ap.add_argument('--wz', type=float, default=0.0)
    ap.add_argument('--duration', type=float, default=12.0)
    a = ap.parse_args()
    res = walk(Path(a.out), a.vx, a.vy, a.wz, a.duration)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
