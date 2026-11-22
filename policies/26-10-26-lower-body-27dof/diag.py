import onnxruntime as ort, numpy as np, mujoco

LEG = ["left_hip_pitch_joint","left_hip_roll_joint","left_hip_yaw_joint","left_knee_joint",
       "left_ankle_pitch_joint","left_ankle_roll_joint","right_hip_pitch_joint","right_hip_roll_joint",
       "right_hip_yaw_joint","right_knee_joint","right_ankle_pitch_joint","right_ankle_roll_joint"]
SLOT = [[0,1,6,7],[2,3,8,9],[4,5,10,11]]
default = np.array([-0.15,0,0,0.45,-0.3,0, 0.15,0,0,-0.45,0.3,0], np.float32)
KP = np.array([150,150,150,150,224.42,35.2,150,150,150,150,224.42,35.2], np.float32)
KD = np.array([5,5,5,5,10.201,1.6,5,5,5,5,10.201,1.6], np.float32)
TAU = np.array([45,45,28,45,72,18,45,45,28,45,72,18], np.float32)
SCALE = np.array([0.25]*5+[0.08]+[0.25]*5+[0.08], np.float32)

sess = ort.InferenceSession("policy/policy.onnx", providers=["CPUExecutionProvider"])
name = sess.get_inputs()[0].name
m = mujoco.MjModel.from_xml_path("model/asimov_1_policy_physics.xml")
d = mujoco.MjData(m)
mujoco.mj_resetData(m, d)
d.qpos[:3] = [0, 0, 0.639]; d.qpos[3:7] = [1, 0, 0, 0]
qadr = np.array([m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, j)] for j in LEG])
vadr = np.array([m.jnt_dofadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, j)] for j in LEG])
act = np.array([mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, j[:-7]) for j in LEG])
d.qpos[qadr] = default
mujoco.mj_forward(m, d)
bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "waist_yaw_link")

cmd = np.array([0.0, 0, 0], np.float32)
prev = np.zeros(12, np.float32)
print(" t     z      pitch   roll   LhipP  Lknee  LankP  act0   act3   act4   |tau|max")
for t in range(60):
    R = np.asarray(d.xmat[bid]).reshape(3, 3)
    v = np.zeros(6); mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, bid, v, 0)
    ang = R.T @ v[:3]; grav = R.T @ np.array([0, 0, -1.0])
    jp = [d.qpos[qadr[s]] - default[s] for s in SLOT]
    jv = [0.1 * d.qvel[vadr[s]] for s in SLOT]
    obs = np.concatenate([0.25 * ang, grav, cmd, *jp, *jv, prev]).astype(np.float32)
    a = np.asarray(sess.run(None, {name: obs[None, :]})[0])[0]
    prev = a
    target = default + SCALE * a
    target[5] = np.clip(target[5], -0.09, 0.09); target[11] = np.clip(target[11], -0.09, 0.09)
    tau_max = 0.0
    for _ in range(4):
        tau = KP * (target - d.qpos[qadr]) - KD * d.qvel[vadr]
        tau_max = max(tau_max, float(np.abs(tau).max()))
        d.ctrl[act] = np.clip(tau, -TAU, TAU)
        mujoco.mj_step(m, d)
    q = d.qpos[3:7]
    pitch = np.arctan2(2*(q[0]*q[2]+q[1]*q[3]), 1-2*(q[2]**2+q[3]**2))
    roll = np.arctan2(2*(q[0]*q[1]-q[2]*q[3]), 1-2*(q[1]**2+q[2]**2))
    if t % 5 == 0 or t < 10:
        print(f"{t*0.02:4.2f} {d.qpos[2]:.4f} {pitch:7.3f} {roll:7.3f} "
              f"{d.qpos[qadr[0]]:6.3f} {d.qpos[qadr[3]]:6.3f} {d.qpos[qadr[4]]:6.3f} "
              f"{a[0]:6.3f} {a[3]:6.3f} {a[4]:6.3f} {tau_max:8.2f}")
