#!/usr/bin/env python3
"""Faithful adapter: run the Menlo 27-DOF lower-body policy on the pinned MJCF.

WHY THIS FILE EXISTS
    The local harness `tinypython.py` hardcodes the 0818 contract: a 78-float
    observation and 23 actions (it drives every joint, upper body included).
    This checkpoint is a *lower-body* policy: 45-float observation, 12 leg
    actions, torso-mounted IMU, independent upper-body targets. Feeding the
    harness's 78-vector to this ONNX raises

        InvalidArgument: Got invalid dimensions for input: obs
        index: 1 Got: 78 Expected: 45

    So the harness cannot run it as-is. This adapter implements the policy's
    OWN contract (from policy/env.yaml actor group + ONNX deploy metadata) and
    drives only the 12 leg joints, holding the 15 upper-body joints at their
    default pose with PD. The physics body is the pinned 25-DOF MJCF
    (nq=30, nv=29) — the 12 leg joints and their actuators all exist.

    It is a MEASUREMENT of the policy against a physics body it was not
    trained on. Deviations from training are listed in the output and in
    README-measurement.md. Nothing here commands hardware.

Usage:
    python run_policy_27dof.py --vx 0.4 --duration 12 --out trace_0p4.json
"""
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
POLICY = HERE / "policy" / "policy.onnx"
MJCF = HERE / "model" / "asimov_1_policy_physics.xml"

# ── the actor contract, from policy/env.yaml (observations.policy) + ONNX meta ─
# leg motor slots (order matters; matches ONNX observation_names / code_state.yaml)
SLOTS = [
    ["left_hip_pitch_joint", "left_hip_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint"],
    ["left_hip_yaw_joint", "left_knee_joint", "right_hip_yaw_joint", "right_knee_joint"],
    ["left_ankle_pitch_joint", "left_ankle_roll_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint"],
]
LEG = [j for slot in SLOTS for j in slot]           # 12 leg joints, policy action order
# flat index groups into LEG, matching the ONNX motor-slot order
SLOT_IDX = [[LEG.index(j) for j in slot] for slot in SLOTS]
DEFAULT_POS = {                                     # env.yaml init_state / ONNX action_offset
    "left_hip_pitch_joint": -0.15, "right_hip_pitch_joint": 0.15,
    "left_knee_joint": 0.45, "right_knee_joint": -0.45,
    "left_ankle_pitch_joint": -0.3, "right_ankle_pitch_joint": 0.3,
}
ACTION_SCALE = np.array([0.25, 0.25, 0.25, 0.25, 0.25, 0.08,
                         0.25, 0.25, 0.25, 0.25, 0.25, 0.08], np.float32)
ANKLE_ROLL = {5, 11}                                 # action indices with clip +-0.09
ANKLE_ROLL_CLIP = 0.09
# training armature per actuator group (env.yaml); MJCF differs (esp. ankle pitch)
ARMATURE = {"hip_pitch": 0.0698, "hip_roll": 0.14, "hip_yaw": 0.0687, "knee": 0.033,
            "ankle_pitch": 0.42984, "ankle_roll": 0.05814}
FRICTION = {"hip_pitch": 0.70, "hip_roll": 0.20, "hip_yaw": 0.70, "knee": 0.70,
            "ankle_pitch": 0.40, "ankle_roll": 0.40}
# ONNX metadata joint_stiffness / joint_damping (leg order)
KP = np.array([150, 150, 150, 150, 224.42, 35.2, 150, 150, 150, 150, 224.42, 35.2], np.float32)
KD = np.array([5, 5, 5, 5, 10.201, 1.6, 5, 5, 5, 5, 10.201, 1.6], np.float32)
TAU = np.array([45, 45, 28, 45, 72, 18, 45, 45, 28, 45, 72, 18], np.float32)  # env.yaml effort_limit
# upper-body joints (NOT driven by the policy): default pose + harness 0818 PD gains
UPPER = ["waist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
         "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_yaw_joint",
         "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint",
         "left_elbow_joint", "left_wrist_yaw_joint"]
UPPER_DEFAULT = np.array([0, 0.25, 0.05, 0, -0.4, 0, -0.25, -0.05, 0, 0.4, 0], np.float32)
UKP = np.array([65, 57, 86, 96, 40, 40, 57, 86, 96, 40, 40], np.float32)
UKD = np.array([5, 5, 5, 5, 2, 2, 5, 5, 5, 2, 2], np.float32)
UTAU = np.array([40, 30, 25, 20, 12, 12, 30, 25, 20, 12, 12], np.float32)

POLICY_DT = 0.02          # 50 Hz
SUBSTEPS = 4              # sim dt 0.005 * 4 = 0.02
FALL_Z = 0.35


def quat_to_mat(q):
    w, x, y, z = q
    n = np.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vx", type=float, default=0.4)
    ap.add_argument("--vy", type=float, default=0.0)
    ap.add_argument("--wz", type=float, default=0.0)
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--out", default="trace.json")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--training-armature", action="store_true",
                    help="override MJCF dof armature with the training values from env.yaml")
    a = ap.parse_args()

    import mujoco, onnxruntime as ort

    sess = ort.InferenceSession(str(POLICY), providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    model = mujoco.MjModel.from_xml_path(str(MJCF))
    data = mujoco.MjData(model)

    jid = lambda name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    aid = lambda name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
    leg_qadr = np.array([model.jnt_qposadr[jid(j)] for j in LEG])
    leg_vadr = np.array([model.jnt_dofadr[jid(j)] for j in LEG])
    leg_act = np.array([aid(j[:-7]) for j in LEG])           # actuator name = joint minus '_joint'
    upper_qadr = np.array([model.jnt_qposadr[jid(j)] for j in UPPER])
    upper_vadr = np.array([model.jnt_dofadr[jid(j)] for j in UPPER])
    upper_act = np.array([aid(j[:-7]) for j in UPPER])
    # cyclotron delayed_obs calls base_mdp.base_ang_vel/projected_gravity on the
    # articulation ROOT (pelvis_link); the env's body_names: waist_yaw_link is not
    # forwarded to the quantity fn. So the exported actor observes PELVIS-frame IMU.
    root_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pelvis_link")
    if a.training_armature:
        for j in LEG + UPPER:
            jid_ = jid(j)
            if jid_ >= 0:
                for key, val in ARMATURE.items():
                    if key in j:
                        model.dof_armature[model.jnt_dofadr[jid_]] = val
                        model.dof_frictionloss[model.jnt_dofadr[jid_]] = FRICTION[key]
                        break

    # default pose for the 12 legs (scalar defaults + explicit map)
    default_leg = np.zeros(12, np.float32)
    for i, j in enumerate(LEG):
        default_leg[i] = DEFAULT_POS.get(j, 0.0)

    # actuators are direct motors (gainprm=1, bias 0) -> ctrl IS torque; clip manually
    mujoco.mj_resetData(model, data)
    data.qpos[:3] = [0, 0, 0.639]
    data.qpos[3:7] = [1, 0, 0, 0]
    data.qpos[leg_qadr] = default_leg
    data.qpos[upper_qadr] = UPPER_DEFAULT
    mujoco.mj_forward(model, data)

    def torso_frame():
        """Rotation of the root body (pelvis_link) -> world."""
        # body xmat is row-major 3x3, world-from-body
        return np.asarray(data.xmat[root_bid]).reshape(3, 3)

    cmd = np.array([a.vx, a.vy, a.wz], np.float32)
    ticks = int(round(a.duration / POLICY_DT))
    prev_action = np.zeros(12, np.float32)
    base_h, com_h, qpos_h = [], [], []
    min_z, fell_at = 99.0, None
    t0 = time.perf_counter()

    # training observation lag (cyclotron delayed_obs): random per-env lag
    rng = np.random.default_rng(0)
    ang_lag = int(rng.integers(0, 1 + 1))       # min_lag 0, max_lag 1
    grav_lag = int(rng.integers(0, 2 + 1))      # min_lag 0, max_lag 2
    ang_buf = np.zeros((ang_lag + 1, 3), np.float32)
    grav_buf = np.zeros((grav_lag + 1, 3), np.float32)
    # actuator delay (DelayedPDActuator): delayed position target, 0..5 sim steps
    act_delay = int(rng.integers(0, 5 + 1))
    act_buf = np.zeros((act_delay + 1, 12), np.float32)

    for t in range(ticks):
        R = torso_frame()                                   # world <- root (pelvis)
        # root-body angular velocity via mj_objectVelocity (world frame), then body frame
        vel = np.zeros(6)
        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, root_bid, vel, 0)  # world
        ang_world = vel[:3]                                 # mj_objectVelocity = [angular, linear]
        ang_root = R.T @ ang_world
        grav_root = R.T @ np.array([0.0, 0.0, -1.0])
        ang_buf = np.roll(ang_buf, 1, axis=0); ang_buf[0] = ang_root
        grav_buf = np.roll(grav_buf, 1, axis=0); grav_buf[0] = grav_root
        ang_obs = ang_buf[ang_lag]
        grav_obs = grav_buf[grav_lag]
        obs = np.concatenate([
            (0.25 * ang_obs).astype(np.float32),
            grav_obs.astype(np.float32),
            cmd,
            *[(data.qpos[leg_qadr[s]] - default_leg[s]).astype(np.float32) for s in SLOT_IDX],
            *[(0.1 * data.qvel[leg_vadr[s]]).astype(np.float32) for s in SLOT_IDX],
            prev_action,
        ]).astype(np.float32)
        assert obs.shape == (45,), obs.shape
        raw = np.asarray(sess.run(None, {in_name: obs[None, :]})[0])[0]
        if raw.shape != (12,) or not np.all(np.isfinite(raw)):
            raise SystemExit(f"policy returned bad actions shape={raw.shape}")
        action = raw.astype(np.float32)
        prev_action = action
        target = default_leg + ACTION_SCALE * action
        target[5] = float(np.clip(target[5], -ANKLE_ROLL_CLIP, ANKLE_ROLL_CLIP))
        target[11] = float(np.clip(target[11], -ANKLE_ROLL_CLIP, ANKLE_ROLL_CLIP))
        act_buf = np.roll(act_buf, 1, axis=0); act_buf[0] = target
        target_used = act_buf[act_delay]
        for _ in range(SUBSTEPS):
            tau_leg = KP * (target_used - data.qpos[leg_qadr]) - KD * data.qvel[leg_vadr]
            data.ctrl[leg_act] = np.clip(tau_leg, -TAU, TAU)
            tau_up = UKP * (UPPER_DEFAULT - data.qpos[upper_qadr]) - UKD * data.qvel[upper_vadr]
            data.ctrl[upper_act] = np.clip(tau_up, -UTAU, UTAU)
            mujoco.mj_step(model, data)
        z = float(data.qpos[2])
        min_z = min(min_z, z)
        if z < FALL_Z and fell_at is None:
            fell_at = round(t * POLICY_DT, 3)
        base_h.append(data.qpos[:7].copy())
        qpos_h.append(data.qpos.copy())
        mujoco.mj_comPos(model, data)
        com_h.append(np.asarray(data.subtree_com[0]).copy())

    wall = time.perf_counter() - t0
    base = np.array(base_h)
    com = np.array(com_h)
    travel_x = float(base[-1, 0] - base[0, 0])
    travel_y = float(base[-1, 1] - base[0, 1])
    com_x = float(com[-1, 0] - com[0, 0])
    speed = float(np.linalg.norm(cmd[:2]))
    upright = fell_at is None
    if speed < 0.05 and abs(float(cmd[2])) < 0.05:
        obeyed = abs(travel_x) < 0.30
    elif abs(float(cmd[2])) > 0.05:
        q = base[-1, 3:7]
        yaw = float(np.arctan2(2 * (q[0] * q[2] + q[1] * q[3]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)))
        obeyed = abs(yaw) > 0.05
    else:
        along = travel_x * float(cmd[0]) + travel_y * float(cmd[1])
        obeyed = along > 0.05
    success = bool(upright and obeyed)

    trace = {
        "policy": "Menlo/asimov1-locomotion-26-10-26-lower-body-27dof",
        "policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        "mjcf_sha256": hashlib.sha256(MJCF.read_bytes()).hexdigest(),
        "obs_dim": 45, "action_dim": 12,
        "base": base.tolist(), "com": com.tolist(),
        "command": cmd.tolist(), "duration_s": a.duration,
        "ticks": ticks, "physics_steps": ticks * SUBSTEPS,
        "travel_x_m": round(travel_x, 4), "travel_y_m": round(travel_y, 4),
        "com_x_m": round(com_x, 4), "min_z_m": round(min_z, 4),
        "fell_at": fell_at, "upright": upright, "obeyed_command": obeyed,
        "success": success, "wall_s": round(wall, 2),
        "realtime_factor": round(a.duration / wall, 2),
        "grants": False, "executed": False, "hardware": False,
        "note": "adapter implements the policy's own 45/12 contract on the pinned 25-DOF MJCF; "
                "simulation only, not hardware.",
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace, separators=(",", ":")), encoding="utf-8")
    receipt = hashlib.sha256(out.read_bytes()).hexdigest()
    print(json.dumps({**trace, "trace": str(out), "receipt": receipt}, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
