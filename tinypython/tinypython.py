#!/usr/bin/env python3
"""tinyPython — a humanoid that walks, in one file.

The third sibling. tiny-voca gave a robot a voice. tinyGPU gave it a body you
can see. tinyPython gives it **motion that emerges from control**, not from a
keyframed pose.

    tinypython doctor                    are the policy and physics present?
    tinypython walk out.json             simulate a walk, write a trace
    tinypython walk out.json --vx 0.6    command a velocity
    tinypython verify out.json           did it actually walk, or did it fall?

Two dependencies:  pip install onnxruntime mujoco numpy
One asset:         Menlo's locomotion policy (831 KB ONNX) + pinned MJCF
Zero:              GPU, compiler, engine, cloud, account, ROS, Isaac.

WHAT MAKES THIS DIFFERENT
    Every other robot video is choreography — a pose trace someone authored.
    Here the base trajectory **emerges** from PD control against ground contact.
    A 78-float observation goes in, 23 joint targets come out, 50 times a
    second, and the robot either stays up or it does not. Nothing prescribes
    where the body goes.

    Measured: 12.0 s, 600 policy ticks, 2400 physics steps, +4.19 m of travel,
    minimum base height 0.6125 m, no fall.

THE CONTRACT (menloresearch/humanoid-policy-viewer)
    obs  78 floats: angvel*0.25, projected gravity, [vx,vy,wz],
                    joint position slots, joint velocity slots*0.1, prev action
    act  23 floats: clipped +-10, target = default + 0.25*action
    PD   per-joint kp/kd/torque limits, 0.02 s policy period, 4 substeps
    lag  2 substeps, one-pole target filter alpha 0.992105

GOVERNANCE
    This produces a SIMULATION TRACE. It is not a command to hardware.
    `walk` returns grants:false and executed:false — the trace is a plan that
    a human may inspect, render, and refuse. No socket is opened, no serial
    port is touched, no motor is addressed.

    The refusal has to belong to the person who owns the robot.

CREDIT
    Policy: Menlo/asimov1-locomotion-0818 (Menlo Research).
    Inference contract: menloresearch/humanoid-policy-viewer.
    Physics: MuJoCo (Apache-2.0, DeepMind).
    No institutional endorsement is claimed.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

# ── the inference contract, verbatim from the policy viewer ─────────────────
JOINTS = [
    'left_hip_pitch_joint','left_hip_roll_joint','left_hip_yaw_joint','left_knee_joint',
    'left_ankle_pitch_joint','left_ankle_roll_joint','right_hip_pitch_joint','right_hip_roll_joint',
    'right_hip_yaw_joint','right_knee_joint','right_ankle_pitch_joint','right_ankle_roll_joint',
    'waist_yaw_joint','right_shoulder_pitch_joint','right_shoulder_roll_joint','right_shoulder_yaw_joint',
    'right_elbow_joint','right_wrist_yaw_joint','left_shoulder_pitch_joint','left_shoulder_roll_joint',
    'left_shoulder_yaw_joint','left_elbow_joint','left_wrist_yaw_joint',
]
DEFAULT_POS = np.array([-0.15,0,0,0.45,-0.3,0, 0.15,0,0,-0.45,0.3,0,
                        0,0.25,0.05,0,-0.4,0, -0.25,-0.05,0,0.4,0], np.float32)
ACTION_SCALE = np.full(23, 0.25, np.float32)
KP = np.array([150,150,150,150,110,110, 150,150,150,150,110,110,
               65,57,86,96,40,40, 57,86,96,40,40], np.float32)
KD = np.array([5,5,5,5,5,5, 5,5,5,5,5,5, 5,5,5,5,2,2, 5,5,5,2,2], np.float32)
TAU_LIMIT = np.array([45,45,28,45,40,17, 45,45,28,45,40,17,
                      40,30,25,20,12,12, 30,25,20,12,12], np.float32)
SLOTS = [[0,1,6,7,12,13,14,18,19], [2,3,8,9,15,16,20,21], [4,5,10,11,17,22]]
POLICY_DT, SUBSTEPS, ACTION_CLIP, LPF_ALPHA, ACTION_LAG = 0.02, 4, 10.0, 0.992105, 2
FALL_Z = 0.35


def asset_dir() -> Path:
    """Where the policy and MJCF live. Override with TINYPYTHON_ASSETS."""
    e = os.environ.get('TINYPYTHON_ASSETS')
    if e:
        return Path(e)
    h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    pkg = h / 'plugins' / 'hermes-ae' / 'packages' / 'ae-locomotion' / '1.0.0'
    if pkg.exists():
        return pkg
    return HERE / 'assets'


def doctor() -> dict:
    """Measure. A guess about the policy is worse than no answer."""
    out = {'ok': False, 'checks': {}}
    a = asset_dir()
    try:
        import onnxruntime as ort
        out['checks']['onnxruntime'] = ort.__version__
    except Exception as exc:
        out['checks']['onnxruntime'] = f'MISSING — pip install onnxruntime ({exc})'
    try:
        import mujoco
        out['checks']['mujoco'] = mujoco.__version__
    except Exception as exc:
        out['checks']['mujoco'] = f'MISSING — pip install mujoco ({exc})'
    pol = a / 'policy' / 'policy.onnx'
    mjcf = a / 'model' / 'asimov_1_policy_physics.xml'
    out['checks']['policy'] = (
        {'path': str(pol), 'bytes': pol.stat().st_size,
         'sha256': hashlib.sha256(pol.read_bytes()).hexdigest()}
        if pol.exists() else f'MISSING {pol}')
    out['checks']['mjcf'] = str(mjcf) if mjcf.exists() else f'MISSING {mjcf}'
    out['checks']['gpu_required'] = False
    out['ok'] = all(isinstance(v, (str, dict)) and 'MISSING' not in str(v)
                    for k, v in out['checks'].items() if k != 'gpu_required')
    out['deps'] = 'pip install onnxruntime mujoco numpy'
    out['source'] = 'https://huggingface.co/Menlo/asimov1-locomotion-0818'
    out['note'] = 'measured on this machine, not assumed'
    return out


def quat_to_mat(q):
    w, x, y, z = q
    n = np.sqrt(w*w + x*x + y*y + z*z) or 1.0
    w, x, y, z = w/n, x/n, y/n, z/n
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)],
                     [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)]])


def walk(out: Path, vx=0.4, vy=0.0, wz=0.0, duration=12.0, fps=24,
         schedule=None) -> dict:
    """Simulate. The base trajectory emerges from control, not a reference.

    `schedule` is a list of segments {t0, t1, vx, vy, wz}. The command changes
    DURING the walk, so a trace can accelerate, turn and stop instead of holding
    one velocity for its whole length. Without it the command is constant —
    which is why five cast members replaying one trace all walked identically.
    """
    import mujoco, onnxruntime as ort
    a = asset_dir()
    pol = a / 'policy' / 'policy.onnx'
    mjcf = a / 'model' / 'asimov_1_policy_physics.xml'
    if not pol.exists():
        return {'ok': False, 'refused': True, 'reason': f'policy missing: {pol}',
                'grants': False}
    if not mjcf.exists():
        return {'ok': False, 'refused': True, 'reason': f'MJCF missing: {mjcf}',
                'grants': False}

    sess = ort.InferenceSession(str(pol), providers=['CPUExecutionProvider'])
    in_name = sess.get_inputs()[0].name
    model = mujoco.MjModel.from_xml_path(str(mjcf))
    data = mujoco.MjData(model)
    if model.nq != 30 or model.nv != 29:
        return {'ok': False, 'refused': True,
                'reason': f'unexpected model size nq={model.nq} nv={model.nv}; '
                          'the pinned physics MJCF is required',
                'grants': False}

    qadr = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in JOINTS])
    if np.any(qadr < 0):
        return {'ok': False, 'refused': True, 'reason': 'joints missing from MJCF',
                'grants': False}
    qpos_adr = np.array([model.jnt_qposadr[i] for i in qadr])
    qvel_adr = np.array([model.jnt_dofadr[i] for i in qadr])
    act_adr = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, j[:-7])
                        for j in JOINTS])
    if np.any(act_adr < 0):
        return {'ok': False, 'refused': True, 'reason': 'policy actuators missing',
                'grants': False}
    for i, aid in enumerate(act_adr):
        model.actuator_ctrlrange[aid, 0] = -float(TAU_LIMIT[i])
        model.actuator_ctrlrange[aid, 1] = float(TAU_LIMIT[i])

    mujoco.mj_resetData(model, data)
    data.qpos[:3] = [0, 0, 0.639]
    data.qpos[3:7] = [1, 0, 0, 0]
    data.qpos[qpos_adr] = DEFAULT_POS
    mujoco.mj_forward(model, data)

    base_cmd = np.array([vx, vy, wz], np.float32)
    cmd = base_cmd.copy()
    # a schedule is validated up front: overlapping or out-of-range segments
    # would silently produce a trace that does not match what was asked for
    segs = []
    if schedule:
        for s in schedule:
            t0, t1 = float(s['t0']), float(s['t1'])
            if not (0.0 <= t0 < t1 <= duration + 1e-6):
                return {'ok': False, 'refused': True,
                        'reason': f'segment [{t0},{t1}] outside [0,{duration}]',
                        'grants': False}
            segs.append((t0, t1, np.array([float(s.get('vx', 0.0)),
                                           float(s.get('vy', 0.0)),
                                           float(s.get('wz', 0.0))], np.float32)))
        segs.sort()
        for i in range(1, len(segs)):
            if segs[i][0] < segs[i-1][1] - 1e-6:
                return {'ok': False, 'refused': True,
                        'reason': f'segments overlap at t={segs[i][0]}',
                        'grants': False}
    ticks = int(round(duration / POLICY_DT))
    prev_action = np.zeros(23, np.float32)
    filtered = DEFAULT_POS.copy()
    hist = [DEFAULT_POS.copy() for _ in range(ACTION_LAG + 1)]
    qpos_h, base_h, com_h = [], [], []
    min_z, fell_at = 99.0, None
    t0 = time.perf_counter()

    cmd_h = []
    for t in range(ticks):
        if segs:
            now = t * POLICY_DT
            cmd = base_cmd.copy()
            for (s0, s1, sc) in segs:
                if s0 <= now < s1:
                    cmd = sc
                    break
        cmd_h.append(cmd.copy())
        gravity = quat_to_mat(data.qpos[3:7]).T @ np.array([0.0, 0.0, -1.0])
        obs = np.concatenate([
            0.25 * data.qvel[3:6],
            gravity.astype(np.float32),
            cmd,
            *[(data.qpos[qpos_adr[s]] - DEFAULT_POS[s]).astype(np.float32) for s in SLOTS],
            *[(0.1 * data.qvel[qvel_adr[s]]).astype(np.float32) for s in SLOTS],
            prev_action,
        ]).astype(np.float32)
        if obs.shape != (78,):
            return {'ok': False, 'refused': True,
                    'reason': f'observation shape {obs.shape}, expected (78,)',
                    'grants': False}
        raw = np.asarray(sess.run(None, {in_name: obs[None, :]})[0])[0]
        if raw.shape != (23,) or not np.all(np.isfinite(raw)):
            return {'ok': False, 'refused': True, 'reason': 'policy returned non-finite actions',
                    'grants': False}
        action = np.clip(raw, -ACTION_CLIP, ACTION_CLIP).astype(np.float32)
        prev_action = action
        target = DEFAULT_POS + ACTION_SCALE * action
        filtered = LPF_ALPHA * target + (1 - LPF_ALPHA) * filtered
        hist.append(filtered.copy())
        delayed = hist[max(0, len(hist) - 1 - ACTION_LAG)]
        for _ in range(SUBSTEPS):
            for i, aid in enumerate(act_adr):
                tau = KP[i]*(delayed[i]-data.qpos[qpos_adr[i]]) - KD[i]*data.qvel[qvel_adr[i]]
                data.ctrl[aid] = float(np.clip(tau, -TAU_LIMIT[i], TAU_LIMIT[i]))
            mujoco.mj_step(model, data)
        z = float(data.qpos[2])
        min_z = min(min_z, z)
        if z < FALL_Z and fell_at is None:
            fell_at = round(t * POLICY_DT, 3)
        qpos_h.append(data.qpos.copy())
        base_h.append(data.qpos[:7].copy())
        mujoco.mj_comPos(model, data)
        com_h.append(np.asarray(data.subtree_com[0]).copy())

    wall = time.perf_counter() - t0
    n = int(round(duration * fps))
    idx = [min(len(qpos_h)-1, int(f/fps/POLICY_DT)) for f in range(n)]
    qpos = np.array([qpos_h[i] for i in idx])
    base = np.array([base_h[i] for i in idx])
    com = np.array([com_h[i] for i in idx])
    base_x = float(base[-1, 0] - base[0, 0])
    com_x = float(com[-1, 0] - com[0, 0])
    # Success = stayed up AND obeyed the command. A forward-only test wrongly
    # fails a standing robot and a robot walking backward.
    speed = float(np.linalg.norm(base_cmd[:2]))
    upright = fell_at is None
    if segs:
        # judge each commanded segment against the motion measured IN it.
        # A single end-to-end displacement cannot score a walk that turned.
        def yaw_at(k):
            w, x, y, z = base[k, 3:7]
            return float(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
        per = []
        for (s0, s1, sc) in segs:
            i0 = min(len(base) - 1, int(s0 * fps))
            i1 = min(len(base) - 1, max(i0 + 1, int(s1 * fps)))
            dx = float(base[i1, 0] - base[i0, 0])
            dy = float(base[i1, 1] - base[i0, 1])
            sp = float(np.linalg.norm(sc[:2]))
            if sp < 0.05 and abs(float(sc[2])) < 0.05:
                ok = (dx * dx + dy * dy) ** 0.5 < 0.30
                what = 'stand'
            elif abs(float(sc[2])) > 0.05:
                ok = abs(yaw_at(i1) - yaw_at(i0)) > 0.05
                what = 'turn'
            else:
                # the command is BODY-FRAME: rotate the measured WORLD
                # displacement into the body frame at the segment's start.
                # Comparing world axes against a body-frame command calls a
                # correct walk-after-a-turn a disobedience.
                c, s = float(np.cos(yaw_at(i0))), float(np.sin(yaw_at(i0)))
                along = dx * c + dy * s
                lateral = -dx * s + dy * c
                ok = (along * float(sc[0]) + lateral * float(sc[1])) > 0.05
                what = 'move'
            per.append({'t0': s0, 't1': s1, 'intent': what,
                        'cmd': sc.tolist(), 'dx': round(dx, 4), 'dy': round(dy, 4),
                        'obeyed': bool(ok)})
        obeyed = all(s['obeyed'] for s in per)
    elif speed < 0.05 and abs(float(base_cmd[2])) < 0.05:
        obeyed = abs(base_x) < 0.30          # commanded to stand: stay put
    elif abs(float(base_cmd[2])) > 0.05:
        yaw = float(np.arctan2(2*(base[-1,1]*base[-1,3] + base[-1,2]*base[-1,4]),
                               1 - 2*(base[-1,3]**2 + base[-1,4]**2)))
        obeyed = abs(yaw) > 0.05             # commanded to turn: change heading
    else:
        # measure the COMMANDED axis: a lateral command moves y, not x
        base_y = float(base[-1, 1] - base[0, 1])
        along = base_x*float(base_cmd[0]) + base_y*float(base_cmd[1])
        obeyed = along > 0.05
    success = bool(upright and obeyed)

    trace = {
        'authority': 'HUMAN://ROOT',
        'policy': 'Menlo/asimov1-locomotion-0818',
        'policy_sha256': hashlib.sha256(pol.read_bytes()).hexdigest(),
        'joint_names': JOINTS, 'joint_refs': DEFAULT_POS.tolist(),
        'qpos': qpos.tolist(), 'base': base.tolist(), 'com': com.tolist(),
        'command': base_cmd.tolist(), 'fps': fps, 'nq': int(model.nq), 'nv': int(model.nv),
        'schedule': ([{'t0': s0, 't1': s1, 'cmd': sc.tolist()} for s0, s1, sc in segs]
                     if segs else None),
        'command_per_tick': np.array(cmd_h, np.float32).tolist() if segs else None,
        'segments': per if segs else None,
        'policy_ticks': ticks, 'physics_steps': ticks*SUBSTEPS, 'duration_s': duration,
        'base_x': base_x, 'com_x': com_x, 'min_z': min_z, 'fell_at': fell_at,
        'success': success,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace, separators=(',', ':')), encoding='utf-8')
    receipt = hashlib.sha256(out.read_bytes()).hexdigest()
    return {
        'ok': success, 'trace': str(out), 'receipt': receipt,
        'base_x': round(base_x, 4), 'com_x': round(com_x, 4),
        'min_z': round(min_z, 4), 'fell_at': fell_at,
        'upright': upright, 'obeyed_command': obeyed,
        'ticks': ticks, 'steps': ticks*SUBSTEPS,
        'wall_s': round(wall, 2), 'realtime_factor': round(duration/wall, 2),
        'frames': n, 'fps': fps,
        # a simulation trace is a plan, never an act
        'grants': False, 'executed': False, 'hardware': False,
        'note': 'simulation only. The base trajectory emerged from PD control '
                'against ground contact; nothing prescribed it.',
    }


def verify(p: Path) -> dict:
    """Did it walk, or did it fall? Measure the trace, do not trust its flag."""
    if not p.exists():
        return {'ok': False, 'reason': f'no such trace: {p}'}
    d = json.loads(p.read_text(encoding='utf-8'))
    base = np.array(d['base'])
    z = base[:, 2]
    travel = float(base[-1, 0] - base[0, 0])
    fell = bool((z < FALL_Z).any())
    cmd = np.array(d.get('command', [0.4, 0, 0]), float)
    speed = float(np.linalg.norm(cmd[:2]))
    if speed < 0.05 and abs(float(cmd[2])) < 0.05:
        obeyed = abs(travel) < 0.30
    elif abs(float(cmd[2])) > 0.05:
        q = base[-1, 3:7]
        yaw = float(np.arctan2(2*(q[0]*q[2] + q[1]*q[3]), 1 - 2*(q[2]**2 + q[3]**2)))
        obeyed = abs(yaw) > 0.05
    else:
        travel_y = float(base[-1, 1] - base[0, 1])
        along = travel*float(cmd[0]) + travel_y*float(cmd[1])
        obeyed = along > 0.05
    return {
        'ok': bool(not fell and obeyed),
        'obeyed_command': obeyed, 'command': cmd.tolist(),
        'frames': len(base), 'duration_s': d.get('duration_s'),
        'travel_x_m': round(travel, 4),
        'travel_y_m': round(float(base[-1, 1] - base[0, 1]), 4),
        'min_z_m': round(float(z.min()), 4),
        'fell': fell, 'claims_success': d.get('success'),
        'agrees_with_claim': bool((not fell and obeyed) == bool(d.get('success'))),
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
        'note': 'recomputed from the trace, not read from its success flag',
    }



# ── THE DEADMAN SWITCH ──────────────────────────────────────────────────────
# cast.json has always declared: motion_requires = human_approval_or_armed_deadman.
# Until now that was a string. This makes it enforceable.
#
# Wætz's first rule, derived after being refused:
#     "no body moves while the human is away"
#
# Presence is a HEARTBEAT, not a flag. A flag can be set once and forgotten; a
# heartbeat expires. The human must be continuously present for motion to be
# permitted, and the assertion must be fresh within DEADMAN_TTL.
#
# FAIL CLOSED. No camera, no face, stale heartbeat, unknown sensor — every one
# of those REFUSES. Absence of evidence is never treated as presence.
#
# Sensing is zero-ML: an OpenCV Haar cascade. No model weights, no tokens
# generated, no network. That is the gestureVision thesis applied to authority
# rather than to captioning.

DEADMAN_TTL = 2.0          # seconds; a heartbeat older than this is not presence
PRESENCE_FILE = 'deadman.json'


def _presence_path() -> Path:
    return Path(os.environ.get('TINYPYTHON_DEADMAN', HERE / PRESENCE_FILE))


def sense(timeout_s: float = 3.0) -> dict:
    """Look for a human face with a Haar cascade. Zero ML, zero tokens.

    Returns a measurement, never an assumption. If the camera cannot be opened
    the result is present:false with the reason — not present:true by default.
    """
    out = {'ok': False, 'present': False, 'sensor': 'opencv-haar', 'grants': False}
    try:
        import cv2
    except Exception as exc:
        out['reason'] = f'opencv unavailable: {exc}'
        return out
    cascade = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
    if not cascade.exists():
        out['reason'] = 'haar cascade missing'
        return out
    cap = None
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == 'nt' else 0)
        if not cap.isOpened():
            out['reason'] = 'no camera could be opened'
            return out
        det = cv2.CascadeClassifier(str(cascade))
        t0 = time.time()
        faces = 0
        while time.time() - t0 < timeout_s:
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found = det.detectMultiScale(gray, 1.2, 5, minSize=(60, 60))
            faces = max(faces, len(found))
            if faces:
                break
        out['ok'] = True
        out['present'] = bool(faces)
        out['faces'] = int(faces)
        out['reason'] = 'face detected' if faces else 'no face in frame'
        out['at'] = time.time()
    except Exception as exc:
        out['reason'] = f'{type(exc).__name__}: {exc}'
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
    return out


def arm(ttl: float = DEADMAN_TTL, source: str = 'manual') -> dict:
    """Assert presence. A manual arm is a HUMAN statement, recorded as such.

    This does not grant motion. It records that a human said they are here,
    with an expiry. The gate still evaluates every request against the clock.
    """
    rec = {'armed_at': time.time(), 'ttl': float(ttl), 'source': source,
           'authority': 'HUMAN://ROOT'}
    if source == 'camera':
        s = sense()
        if not s.get('present'):
            return {'ok': False, 'refused': True, 'decision': 'deny',
                    'rules': ['DEAD-001'], 'grants': False,
                    'reason': f'camera arm refused: {s.get("reason")}',
                    'note': 'fail closed — no face is not presence'}
        rec['faces'] = s.get('faces')
    _presence_path().write_text(json.dumps(rec, indent=2), encoding='utf-8')
    return {'ok': True, 'armed': True, 'source': source, 'ttl': ttl,
            'expires_in': ttl, 'grants': False,
            'note': 'presence recorded. It is not permission; it is one condition of it.'}


def disarm() -> dict:
    p = _presence_path()
    if p.exists():
        p.unlink()
    return {'ok': True, 'armed': False, 'grants': False,
            'note': 'presence withdrawn. No body may move.'}


def presence() -> dict:
    """Is a human present RIGHT NOW? A stale heartbeat is not presence."""
    p = _presence_path()
    if not p.exists():
        return {'present': False, 'reason': 'no deadman armed', 'grants': False}
    try:
        rec = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {'present': False, 'reason': 'unreadable deadman record', 'grants': False}
    age = time.time() - float(rec.get('armed_at', 0))
    ttl = float(rec.get('ttl', DEADMAN_TTL))
    fresh = age <= ttl
    return {'present': fresh, 'age_s': round(age, 3), 'ttl': ttl,
            'source': rec.get('source'), 'authority': rec.get('authority'),
            'reason': 'heartbeat fresh' if fresh else f'heartbeat stale by {age-ttl:.2f}s',
            'grants': False}


def deadman_gate(intent: str = 'move') -> dict:
    """The gate Wætz derived: no body moves while the human is away.

    Simulation is always allowed — a trace is a picture of a plan. Motion
    against a body requires BOTH a fresh heartbeat AND a human signature.
    Presence alone never grants; it only removes one of the two refusals.
    """
    pr = presence()
    if intent in ('simulate', 'walk', 'trace', 'plan', 'observe'):
        return {'ok': True, 'decision': 'allow', 'rules': [], 'intent': intent,
                'presence': pr['present'], 'grants': False, 'executed': False,
                'note': 'simulation is not an act; presence is not required to think'}
    rules = ['ACT-001', 'AUTH-002']
    if not pr['present']:
        rules.append('DEAD-001')
    return {'ok': False, 'refused': True, 'decision': 'require_approval',
            'rules': rules, 'intent': intent, 'presence': pr['present'],
            'presence_reason': pr.get('reason'),
            'grants': False, 'executed': False,
            'reason': ('no body moves while the human is away'
                       if not pr['present'] else
                       'human present, but presence is not a signature'),
            'note': 'presence removes ONE refusal. The signature is still required.'}


def main():
    ap = argparse.ArgumentParser(prog='tinypython', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor', help='measure policy + physics availability')
    sub.add_parser('sense', help='look for a human — zero ML, zero tokens')
    ar = sub.add_parser('arm', help='assert presence (a human statement)')
    ar.add_argument('--ttl', type=float, default=DEADMAN_TTL)
    ar.add_argument('--source', default='manual', choices=['manual', 'camera'])
    sub.add_parser('disarm', help='withdraw presence')
    sub.add_parser('presence', help='is a human present right now?')
    g = sub.add_parser('gate', help='evaluate the deadman rule for an intent')
    g.add_argument('intent', nargs='?', default='move')
    w = sub.add_parser('walk', help='simulate a walk, write a trace')
    w.add_argument('out')
    w.add_argument('--vx', type=float, default=0.4)
    w.add_argument('--vy', type=float, default=0.0)
    w.add_argument('--wz', type=float, default=0.0)
    w.add_argument('--duration', type=float, default=12.0)
    w.add_argument('--schedule', help='JSON file: [{"t0":0,"t1":4,"vx":0.4},...]')
    w.add_argument('--fps', type=int, default=24)
    v = sub.add_parser('verify', help='recompute whether the trace walked')
    v.add_argument('file')
    a = ap.parse_args()
    if a.cmd == 'doctor':
        res = doctor()
    elif a.cmd == 'sense':
        res = sense()
    elif a.cmd == 'arm':
        res = arm(a.ttl, a.source)
    elif a.cmd == 'disarm':
        res = disarm()
    elif a.cmd == 'presence':
        res = presence()
    elif a.cmd == 'gate':
        res = deadman_gate(a.intent)
    elif a.cmd == 'walk':
        sched = None
        if getattr(a, 'schedule', None):
            sched = json.loads(Path(a.schedule).read_text(encoding='utf-8'))
            if isinstance(sched, dict):
                sched = sched.get('schedule', sched.get('segments'))
        res = walk(Path(a.out), a.vx, a.vy, a.wz, a.duration, a.fps, schedule=sched)
    else:
        res = verify(Path(a.file))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
