"""SimTransport — a MuJoCo-backed transport for the official Menlo SDK.

One file, no robot required. Implements ``menlo.asimov.transport.base.Transport``
against the Asimov 1 25-DOF MJCF so the same ``Robot`` verbs (stand / damp /
balance / set_velocity / trajectory) run on a laptop.

Honesty notes (read before using):

* **kind.** ``TransportKind`` is ``Literal["udp", "hybrid", "livekit"]`` in the
  installed SDK; ``"sim"`` is not a member. Widening that Literal is an upstream
  change we do not make locally, and we do not monkeypatch their typing. This
  transport therefore labels itself ``kind="udp"`` (the wire-compatible label),
  sets ``simulated=True`` and ``endpoint="mujoco://asimov_1_25dof"`` so any
  consumer can tell it apart from a real LAN wire. Check ``simulated`` before
  believing a verdict came from hardware.
* **No hardware is driven.** Everything below is simulation. The studio MJCF
  welds the pelvis to the world (no free joint), so a ``Velocity`` command is
  applied as a *bounded posture intent* (small mirrored hip/knee/ankle flex and
  waist yaw, clamped to the firmware caps and the actuator ctrlranges). The
  simulated body does not translate, and this transport makes no locomotion
  claim.
* **Media.** No camera and no microphone are faked: ``subscribe_frames`` and
  ``subscribe_audio`` raise ``UnsupportedError``. ``play_audio`` genuinely
  accepts chunks and records them (bounded log, no hardware), so ``speaker`` is
  declared in ``capabilities``.
* **Battery** is a fixed simulated constant, declared as such. Joint ``current``
  and ``temp`` are ``None`` — the simulator does not report them, and the SDK's
  rule is "None, never a plausible default".
* **Outcomes.** The simulator is its own arbiter: every accepted command gets an
  ``Applied`` verdict, dispatched from the step thread (never inside ``send``).
  Motion while damped is ``Refused(FW_DAMPED)`` and a wrong-length trajectory is
  ``Refused(BAD_LENGTH)``, mirroring Asimov Edge's refusal vocabulary.
  Controller-change callbacks are accepted but never fired: there is no arbiter
  hand-off in simulation.
* The MJCF on disk is never modified. Two in-memory edits before
  ``from_xml_string``: ``meshdir`` is rewritten to the absolute native mesh
  directory, and a ``<visual><global offwidth="720" offheight="800"/></visual>``
  block is appended (MuJoCo merges repeated ``<visual>`` sections; the later
  ``global`` attributes win).

Threading: one daemon thread steps ``mj_step`` at the model timestep in real
time and pushes ``State`` samples (default 50 Hz). A single ``RLock`` guards
model/data, mode and subscriber lists; callbacks run outside the lock.
``send`` never blocks on the robot. ``close`` is idempotent and never raises;
``open`` is callable again after ``close`` (fresh model, fresh data; sequence
counters are per-instance and keep counting). ``mujoco``/``numpy`` are imported
lazily inside ``open`` so importing this module never requires them.

The ``Transport`` protocol is *not* ``runtime_checkable`` in the installed SDK,
so conformance is structural (mypy), not an ``isinstance`` check.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from menlo.asimov import ConnectError, LinkLostError, NotConnectedError, UnsupportedError
from menlo.asimov._command import Command, Limits, ModeCommand, Trajectory, Velocity
from menlo.asimov._media import AudioChunk, Frame
from menlo.asimov._outcome import Applied, Refusal, Refused
from menlo.asimov._state import (
    Battery,
    BatteryProtection,
    Joint,
    Mode,
    State,
    TransportKind,
)
from menlo.asimov.robots import ASIMOV_1_BIPED_JOINTS, PROTOCOL_VERSION
from menlo.asimov.transport.base import (
    AudioCallback,
    ControllerCallback,
    FrameCallback,
    OutcomeCallback,
    StateCallback,
)

if TYPE_CHECKING:
    import mujoco  # type: ignore[import-untyped]
    import numpy as np

__all__ = ["SimTransport"]

#: The studio MJCF this transport loads (never written to).
_DEFAULT_XML: Final[Path] = Path(
    "C:/Users/yaelm/AppData/Local/hermes/plugins/hermes-ae/model/xml/"
    "asimov_1_25dof_actuated.xml"
)

#: Fixed simulated pack summary. Not a measurement; declared so scripts can run.
_SIM_BATTERY: Final[Battery] = Battery(
    voltage_v=25.2,
    current_a=-2.0,
    soc_percent=87.0,
    max_cell_temp_c=31.0,
    protection=BatteryProtection(0),
)

_UINT32: Final[int] = 0xFFFFFFFF

#: Firmware name -> MJCF joint name. Ankle A/B are the pitch/roll motors the
#: firmware reads there (see menlo.asimov._command.Trajectory docstring).
_FW_TO_MJCF: Final[dict[str, str]] = {
    "L_Hip_Pitch": "left_hip_pitch_joint",
    "L_Hip_Roll": "left_hip_roll_joint",
    "L_Hip_Yaw": "left_hip_yaw_joint",
    "L_Knee": "left_knee_joint",
    "L_Ankle_A": "left_ankle_pitch_joint",
    "L_Ankle_B": "left_ankle_roll_joint",
    "R_Hip_Pitch": "right_hip_pitch_joint",
    "R_Hip_Roll": "right_hip_roll_joint",
    "R_Hip_Yaw": "right_hip_yaw_joint",
    "R_Knee": "right_knee_joint",
    "R_Ankle_A": "right_ankle_pitch_joint",
    "R_Ankle_B": "right_ankle_roll_joint",
    "L_Shoulder_Pitch": "left_shoulder_pitch_joint",
    "L_Shoulder_Roll": "left_shoulder_roll_joint",
    "L_Shoulder_Yaw": "left_shoulder_yaw_joint",
    "L_Elbow": "left_elbow_joint",
    "L_Wrist_Yaw": "left_wrist_yaw_joint",
    "R_Shoulder_Pitch": "right_shoulder_pitch_joint",
    "R_Shoulder_Roll": "right_shoulder_roll_joint",
    "R_Shoulder_Yaw": "right_shoulder_yaw_joint",
    "R_Elbow": "right_elbow_joint",
    "R_Wrist_Yaw": "right_wrist_yaw_joint",
    "Waist_Yaw": "waist_yaw_joint",
    "Neck_Yaw": "neck_yaw_joint",
    "Neck_Pitch": "neck_pitch_joint",
}


def _rotate_by_conjugate(
    q: tuple[float, float, float, float], v: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Rotate world vector ``v`` into the body frame of quat ``q`` (w,x,y,z)."""
    w, x, y, z = q
    # conjugate q* = (w, -x, -y, -z); v' = v + 2*w*(qxyz x v) + 2*(qxyz x (qxyz x v))
    cx, cy, cz = -x, -y, -z
    tx = 2.0 * (cy * v[2] - cz * v[1])
    ty = 2.0 * (cz * v[0] - cx * v[2])
    tz = 2.0 * (cx * v[1] - cy * v[0])
    return (
        v[0] + w * tx + (cy * tz - cz * ty),
        v[1] + w * ty + (cz * tx - cx * tz),
        v[2] + w * tz + (cx * ty - cy * tx),
    )


class SimTransport:
    """MuJoCo simulation wire for the Menlo SDK. See the module docstring.

    Structural implementation of ``menlo.asimov.transport.base.Transport``
    (the protocol is not ``runtime_checkable``). ``kind`` is the wire-compatible
    ``"udp"`` label; ``simulated`` and ``endpoint`` tell the truth about it.
    """

    kind: TransportKind = "udp"
    endpoint: str = "mujoco://asimov_1_25dof"
    #: drive + state are mandatory; battery is delivered in every State sample
    #: (simulated constant) and speaker chunks are genuinely accepted+recorded.
    capabilities: frozenset[str] = frozenset({"drive", "state", "battery", "speaker"})
    default_outcome_timeout: float = 0.5
    #: Not part of the SDK protocol; the honest discriminator for this wire.
    simulated: bool = True

    def __init__(
        self,
        xml_path: str | Path | None = None,
        *,
        state_hz: float = 50.0,
    ) -> None:
        if not math.isfinite(state_hz) or state_hz <= 0.0:
            raise ValueError(f"state_hz must be finite and positive, got {state_hz!r}")
        self._xml_path: Path = Path(xml_path) if xml_path is not None else _DEFAULT_XML
        self._state_hz: float = float(state_hz)
        self._lock: threading.RLock = threading.RLock()
        self._stop: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self._model: mujoco.MjModel | None = None
        self._data: mujoco.MjData | None = None
        self._dead: str | None = None  # step-thread failure reason, if any
        self._mode: Mode = Mode.DAMP
        self._cmd_seq: int = 0
        self._state_seq: int = 0
        self._on_state: list[StateCallback] = []
        self._on_outcome: list[OutcomeCallback] = []
        self._on_controller: list[ControllerCallback] = []
        self._pending_outcomes: deque[Applied | Refused] = deque()
        self._speaker_log: deque[AudioChunk] = deque(maxlen=256)
        # filled in open():
        self._fw_to_act: tuple[int, ...] = ()
        self._act_to_qposadr: tuple[int, ...] = ()
        self._stand_targets: np.ndarray[Any, np.dtype[np.float64]] | None = None
        self._gainprm_orig: np.ndarray[Any, np.dtype[np.float64]] | None = None
        self._biasprm_orig: np.ndarray[Any, np.dtype[np.float64]] | None = None
        self._gainprm_cur: np.ndarray[Any, np.dtype[np.float64]] | None = None
        self._biasprm_cur: np.ndarray[Any, np.dtype[np.float64]] | None = None
        self._gyro_adr: int = -1
        self._quat_adr: int = -1
        self._steps_per_sample: int = 1
        self._step_count: int = 0

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self._thread is not None and self._model is not None

    @property
    def dof(self) -> int:
        """Motors on this wire: the 25-DOF biped, in firmware order."""
        return len(ASIMOV_1_BIPED_JOINTS)

    @property
    def mode(self) -> Mode:
        with self._lock:
            return self._mode

    @property
    def played_audio(self) -> tuple[AudioChunk, ...]:
        """Speaker chunks accepted so far (bounded log; no hardware played)."""
        with self._lock:
            return tuple(self._speaker_log)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def open(self) -> None:
        """Load the MJCF in memory and start the step thread.

        Raises ``ConnectError`` on failure (missing mujoco, unreadable XML,
        compiler error, or already open — mirroring ``UdpTransport``). Callable
        again after ``close()``.
        """
        if self._thread is not None:
            raise ConnectError("this SimTransport is already open")
        try:
            import mujoco  # lazy: importing this module must not need mujoco
            import numpy as np
        except ImportError as exc:
            raise ConnectError(
                f"SimTransport needs mujoco and numpy: pip install mujoco numpy ({exc})"
            ) from exc
        try:
            xml = self._xml_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConnectError(f"cannot read MJCF {self._xml_path}: {exc}") from exc

        # In-memory edit 1: absolute native meshdir. Never touch the file.
        meshdir = (self._xml_path.parent.parent / "meshes").resolve()
        needle = 'meshdir="../meshes"'
        if needle not in xml:
            raise ConnectError(f"MJCF {self._xml_path} has no {needle!r} to rewrite")
        xml = xml.replace(needle, f'meshdir="{meshdir.as_posix()}"', 1)
        # In-memory edit 2: offscreen render size. MuJoCo merges repeated
        # <visual> sections; appended last so these global attributes win.
        injection = '<visual><global offwidth="720" offheight="800"/></visual>'
        if "</mujoco>" not in xml:
            raise ConnectError("MJCF has no closing </mujoco> tag")
        xml = xml.replace("</mujoco>", f"{injection}\n</mujoco>", 1)

        try:
            model = mujoco.MjModel.from_xml_string(xml)
        except Exception as exc:
            raise ConnectError(f"MuJoCo could not compile the MJCF: {exc}") from exc
        data = mujoco.MjData(model)
        self._model = model
        self._data = data

        try:
            if model.nu != len(ASIMOV_1_BIPED_JOINTS) or model.nq != model.nu:
                raise ConnectError(
                    f"expected a welded-base {len(ASIMOV_1_BIPED_JOINTS)}-DOF model, "
                    f"got nu={model.nu} nq={model.nq}"
                )
            # firmware order -> actuator index, via joint names.
            act_of_joint: dict[int, int] = {}
            for a in range(model.nu):
                jid = int(model.actuator_trnid[a, 0])
                act_of_joint[jid] = a
            fw_to_act: list[int] = []
            qposadr: list[int] = []
            for fw_name in ASIMOV_1_BIPED_JOINTS:
                mjcf_name = _FW_TO_MJCF[fw_name]
                jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, mjcf_name)
                if jid < 0 or jid not in act_of_joint:
                    raise ConnectError(f"MJCF lacks actuated joint {mjcf_name!r}")
                fw_to_act.append(act_of_joint[jid])
                qposadr.append(int(model.jnt_qposadr[jid]))
            self._fw_to_act = tuple(fw_to_act)
            self._act_to_qposadr = tuple(qposadr)
            self._stand_targets = np.array(model.qpos0, dtype=np.float64)
            self._gainprm_orig = np.array(model.actuator_gainprm, dtype=np.float64)
            self._biasprm_orig = np.array(model.actuator_biasprm, dtype=np.float64)
            self._gainprm_cur = self._gainprm_orig.copy()
            self._biasprm_cur = self._biasprm_orig.copy()
            self._gyro_adr = self._sensor_adr(mujoco, model, "imu_ang_vel")
            self._quat_adr = self._sensor_adr(mujoco, model, "imu_quat")
            self._steps_per_sample = max(
                1, round(1.0 / (self._state_hz * float(model.opt.timestep)))
            )
            self._step_count = 0
            self._dead = None
            self._mode = Mode.DAMP
            self._pending_outcomes.clear()
            # start compliant: zero stiffness, keep the PD's kv as damping.
            self._write_gains(stiff=False)
            data.ctrl[:] = self._stand_targets
            mujoco.mj_forward(model, data)
        except ConnectError:
            self._model = None
            self._data = None
            raise
        except Exception as exc:
            self._model = None
            self._data = None
            raise ConnectError(
                f"SimTransport setup failed: {type(exc).__name__}: {exc}"
            ) from exc

        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="simtransport-mujoco", daemon=True
        )
        self._thread.start()

    @staticmethod
    def _sensor_adr(mujoco_mod: mujoco, model: mujoco.MjModel, name: str) -> int:
        sid = mujoco_mod.mj_name2id(model, mujoco_mod.mjtObj.mjOBJ_SENSOR, name)
        return int(model.sensor_adr[sid]) if sid >= 0 else -1

    def close(self) -> None:
        """Stop the step thread and release the model. Idempotent; never raises."""
        try:
            self._stop.set()
            thread = self._thread
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=2.0)
            with self._lock:
                self._thread = None
                self._model = None
                self._data = None
                self._pending_outcomes.clear()
        except Exception:
            pass  # the contract: close() never raises

    # ── commands ─────────────────────────────────────────────────────────────

    def send(self, command: Command) -> int:
        """Apply one command to the simulation. Returns its uint32 sequence.

        Never blocks on the robot: the only wait is the short state lock.
        Verdicts (Applied/Refused) are dispatched later, from the step thread.
        """
        if self._model is None or self._thread is None:
            raise NotConnectedError("this SimTransport is not open")
        if self._dead is not None:
            raise LinkLostError(f"simulation thread stopped: {self._dead}")
        with self._lock:
            self._cmd_seq = (self._cmd_seq + 1) & _UINT32
            seq = self._cmd_seq
            if isinstance(command, ModeCommand):
                self._apply_mode(command)
                self._pending_outcomes.append(Applied(sequence=seq))
            elif isinstance(command, Velocity):
                if self._mode is Mode.DAMP:
                    self._pending_outcomes.append(
                        Refused(sequence=seq, reason=Refusal.FW_DAMPED,
                                detail="velocity while damped", verb="set_velocity")
                    )
                else:
                    self._apply_velocity(command.clamped(Limits()))
                    self._pending_outcomes.append(Applied(sequence=seq))
            elif isinstance(command, Trajectory):
                if len(command.positions) != len(self._fw_to_act):
                    self._pending_outcomes.append(
                        Refused(sequence=seq, reason=Refusal.BAD_LENGTH,
                                detail=f"{len(command.positions)} targets for "
                                       f"{len(self._fw_to_act)} motors",
                                verb="trajectory")
                    )
                elif self._mode is Mode.DAMP:
                    self._pending_outcomes.append(
                        Refused(sequence=seq, reason=Refusal.FW_DAMPED,
                                detail="trajectory while damped", verb="trajectory")
                    )
                else:
                    self._apply_trajectory(command)
                    self._pending_outcomes.append(Applied(sequence=seq))
            else:  # pragma: no cover - Command is a closed union
                self._pending_outcomes.append(
                    Refused(sequence=seq, reason=Refusal.UNKNOWN_COMMAND,
                            detail=type(command).__name__, verb="command")
                )
            return seq

    def _apply_mode(self, command: ModeCommand) -> None:
        """Caller holds the lock. STAND: stiff PD to the rest pose. DAMP: compliant."""
        assert self._stand_targets is not None and self._data is not None
        if command.mode == "stand":
            self._write_gains(stiff=True)
            self._data.ctrl[:] = self._stand_targets
            self._mode = Mode.STAND
        else:  # "damp" — validated by ModeCommand itself
            self._write_gains(stiff=False)
            self._mode = Mode.DAMP

    def _apply_velocity(self, v: Velocity) -> None:
        """Caller holds the lock. Bounded posture intent, not locomotion.

        The pelvis is welded in this MJCF, so the body cannot translate. The
        (already firmware-clamped) intent becomes a small mirrored flex at the
        hips/knees/ankles, a waist yaw, and a hip roll — each clamped to the
        actuator's ctrlrange. Nonzero intent reports MOVE; zero reports STAND.
        """
        assert (
            self._stand_targets is not None
            and self._data is not None
            and self._model is not None
        )
        targets = self._stand_targets.copy()
        flex = 0.15 * v.vx  # <= 0.06 rad at the 0.4 m/s firmware cap
        roll = 0.10 * v.vy  # <= 0.04 rad
        yaw = 0.30 * v.vyaw  # <= 0.24 rad at the 0.8 rad/s cap
        # Mirrored joint axes: right-side pitch joints negate the left's sign.
        for fw_name, delta in (
            ("L_Hip_Pitch", flex), ("R_Hip_Pitch", -flex),
            ("L_Knee", flex), ("R_Knee", -flex),
            ("L_Ankle_A", -flex), ("R_Ankle_A", flex),
            ("L_Hip_Roll", roll), ("R_Hip_Roll", roll),
            ("Waist_Yaw", yaw),
        ):
            i = ASIMOV_1_BIPED_JOINTS.index(fw_name)
            targets[i] += delta
        self._write_ctrl_clamped(targets)
        self._mode = Mode.STAND if v.is_zero else Mode.MOVE

    def _apply_trajectory(self, command: Trajectory) -> None:
        """Caller holds the lock. Joint targets in firmware order, clamped."""
        assert self._model is not None and self._data is not None
        targets = self._stand_targets.copy() if self._stand_targets is not None else None
        assert targets is not None
        for i, pos in enumerate(command.positions):
            targets[i] = float(pos)
        if command.kp is not None and command.kd is not None:
            assert self._gainprm_cur is not None and self._biasprm_cur is not None
            for i, (kp, kd) in enumerate(zip(command.kp, command.kd, strict=True)):
                a = self._fw_to_act[i]
                self._gainprm_cur[a, 0] = float(kp)
                self._biasprm_cur[a, 1] = -float(kp)
                self._biasprm_cur[a, 2] = -float(kd)
            self._write_gains(stiff=True)
        self._write_ctrl_clamped(targets)

    def _write_ctrl_clamped(self, targets: np.ndarray[Any, np.dtype[np.float64]]) -> None:
        """Caller holds the lock. Clamp firmware-order targets to ctrlrange."""
        assert self._model is not None and self._data is not None
        for i, a in enumerate(self._fw_to_act):
            lo, hi = float(self._model.actuator_ctrlrange[a, 0]), float(
                self._model.actuator_ctrlrange[a, 1]
            )
            self._data.ctrl[a] = max(lo, min(hi, float(targets[i])))

    def _write_gains(self, *, stiff: bool) -> None:
        """Caller holds the lock. Position actuators: force = kp*(ctrl-q) - kv*qvel.

        DAMP zeroes kp (gain and the -kp bias term) and keeps kv: every motor is
        a pure damper, compliant like the firmware's DAMP. STAND/trajectory
        restore the active gains.
        """
        assert (
            self._model is not None
            and self._gainprm_cur is not None
            and self._biasprm_cur is not None
        )
        gain = self._gainprm_cur.copy()
        bias = self._biasprm_cur.copy()
        if not stiff:
            gain[:, 0] = 0.0
            bias[:, 1] = 0.0
        self._model.actuator_gainprm[:] = gain
        self._model.actuator_biasprm[:] = bias

    # ── subscriptions (all legal before open()) ─────────────────────────────

    def subscribe_state(self, callback: StateCallback) -> None:
        with self._lock:
            self._on_state.append(callback)

    def subscribe_outcome(self, callback: OutcomeCallback) -> None:
        with self._lock:
            self._on_outcome.append(callback)

    def subscribe_controller_change(self, callback: ControllerCallback) -> None:
        # Accepted for protocol completeness; simulation has no arbiter hand-off.
        with self._lock:
            self._on_controller.append(callback)

    def subscribe_frames(self, callback: FrameCallback) -> None:
        raise UnsupportedError("camera", self.kind)

    def subscribe_audio(self, callback: AudioCallback) -> None:
        raise UnsupportedError("microphone", self.kind)

    def play_audio(self, chunk: AudioChunk) -> None:
        """Accept a speaker chunk and record it. No hardware exists here."""
        if self._model is None or self._thread is None:
            raise NotConnectedError("this SimTransport is not open")
        with self._lock:
            self._speaker_log.append(chunk)

    # ── step thread ──────────────────────────────────────────────────────────

    def _run(self) -> None:
        import mujoco

        model, data = self._model, self._data
        if model is None or data is None:  # pragma: no cover - open() sets both
            return
        dt = float(model.opt.timestep)
        next_t = time.monotonic()
        while not self._stop.is_set():
            sample: State | None = None
            outcomes: list[Applied | Refused] = []
            with self._lock:
                try:
                    mujoco.mj_step(model, data)
                except Exception as exc:
                    self._dead = f"{type(exc).__name__}: {exc}"
                    break
                self._step_count += 1
                if self._step_count % self._steps_per_sample == 0:
                    sample = self._build_state_locked(model, data)
                while self._pending_outcomes:
                    outcomes.append(self._pending_outcomes.popleft())
            # dispatch outside the lock; a bad subscriber must not kill the wire
            for outcome in outcomes:
                for ocb in tuple(self._on_outcome):
                    try:
                        ocb(outcome)
                    except Exception:
                        pass
            if sample is not None:
                for scb in tuple(self._on_state):
                    try:
                        scb(sample)
                    except Exception:
                        pass
            # real-time pacing; wait on the stop event so close() is prompt
            next_t += dt
            lag = next_t - time.monotonic()
            if lag > 0.0:
                self._stop.wait(lag)
            elif lag < -0.25:
                next_t = time.monotonic()  # drop backlog, never spiral

    def _build_state_locked(self, model: mujoco.MjModel, data: mujoco.MjData) -> State:
        """Caller holds the lock. One telemetry sample, firmware joint order."""
        joints: list[Joint] = []
        for i, name in enumerate(ASIMOV_1_BIPED_JOINTS):
            adr = self._act_to_qposadr[i]
            joints.append(
                Joint(
                    name=name,
                    pos=float(data.qpos[adr]),
                    vel=float(data.qvel[adr]),
                    current=None,  # not reported by the simulator; never guessed
                    temp=None,
                )
            )
        gyro: tuple[float, float, float] | None = None
        if self._gyro_adr >= 0:
            g = data.sensordata[self._gyro_adr : self._gyro_adr + 3]
            gyro = (float(g[0]), float(g[1]), float(g[2]))
        quat: tuple[float, float, float, float] | None = None
        gravity: tuple[float, float, float] | None = None
        if self._quat_adr >= 0:
            q = data.sensordata[self._quat_adr : self._quat_adr + 4]
            quat = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
            gravity = _rotate_by_conjugate(quat, (0.0, 0.0, -1.0))
        self._state_seq = (self._state_seq + 1) & _UINT32
        return State(
            mode=self._mode,
            joints=tuple(joints),
            gravity=gravity,
            gyro=gyro,
            quat=quat,
            error_flags=0,
            alerts=(),
            sequence=self._state_seq,
            fw_timestamp_us=int(data.time * 1e6),  # simulated firmware clock
            protocol_version=PROTOCOL_VERSION,
            battery=_SIM_BATTERY,
            edge_timestamp_us=0,
        )
