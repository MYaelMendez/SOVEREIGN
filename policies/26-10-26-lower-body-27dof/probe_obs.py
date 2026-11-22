import onnxruntime as ort, numpy as np, mujoco

LEG = ["left_hip_pitch_joint","left_hip_roll_joint","left_hip_yaw_joint","left_knee_joint",
       "left_ankle_pitch_joint","left_ankle_roll_joint","right_hip_pitch_joint","right_hip_roll_joint",
       "right_hip_yaw_joint","right_knee_joint","right_ankle_pitch_joint","right_ankle_roll_joint"]
SLOT = [[0,1,6,7],[2,3,8,9],[4,5,10,11]]
default = np.array([-0.15,0,0,0.45,-0.3,0, 0.15,0,0,-0.45,0.3,0], np.float32)

sess = ort.InferenceSession("policy/policy.onnx", providers=["CPUExecutionProvider"])
name = sess.get_inputs()[0].name
m = mujoco.MjModel.from_xml_path("model/asimov_1_policy_physics.xml")
d = mujoco.MjData(m)
mujoco.mj_resetData(m, d)
d.qpos[:3] = [0, 0, 0.639]; d.qpos[3:7] = [1, 0, 0, 0]
qadr = np.array([m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, j)] for j in LEG])
vadr = np.array([m.jnt_dofadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, j)] for j in LEG])
for i, adr in enumerate(qadr):
    d.qpos[adr] = default[i]
mujoco.mj_forward(m, d)
bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "waist_yaw_link")
R = np.asarray(d.xmat[bid]).reshape(3, 3)
v = np.zeros(6)
mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, bid, v, 0)
ang = R.T @ v[:3]
grav = R.T @ np.array([0, 0, -1.0])


def obs(cmd, prev):
    jp = [d.qpos[qadr[s]] - default[s] for s in SLOT]
    jv = [0.1 * d.qvel[vadr[s]] for s in SLOT]
    return np.concatenate([0.25 * ang, grav, cmd, *jp, *jv, prev]).astype(np.float32)


print("qadr", qadr)
print("default", default)
for cmd in ([0, 0, 0], [0.4, 0, 0], [-0.4, 0, 0], [0, 0.4, 0], [0, 0, 0.5]):
    o = obs(np.array(cmd, np.float32), np.zeros(12, np.float32))
    a = np.asarray(sess.run(None, {name: o[None, :]})[0])[0]
    print(f"cmd={cmd} obs[:9]={np.round(o[:9],3)} act={np.round(a,3)} maxabs={np.abs(a).max():.3f}")
