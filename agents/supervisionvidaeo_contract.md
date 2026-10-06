# supervisionvidaeo:// — Scheme Contract Index

> Authoritative index for the **supervisionvidaeo://** produce-and-verify video contract.
> Two on-disk copies exist (see §5). Values below are read from the canonical source
> `C:\æ\supervisionvidaeo\supervisionvidaeo\` as of the current checkout; where the
> historical CLI mirror at `C:\æ\vision-supervision\vision_supervision\` diverges,
> the divergence is called out.

---

## 1. AEE cycle

```
SPEC → PRODUCE → SUPERVISE → (PASS: emit Receipt) | (FAIL: raise SupervisionRefused)
```

- The producer **proposes**; bounds are enforced **before** a frame renders.
- The verifier is **deterministic** (statistics + geometry, OpenCV only — no ML).
  Every verdict traces to a measurable threshold → auditable.
- A stage advances when its gate passes, never on a timer.
- **PASS** ⇒ `Receipt`; **FAIL** ⇒ `SupervisionRefused`. There is no code path
  that returns a path to a broken render — that is the whole point.

---

## 2. API surface

All public entries live in `supervisionvidaeo/__init__.py` (the package contract).

### `produce(raw_spec, out_path, *, producer, sample_every, max_attempts) -> Receipt`

```
def produce(
    raw_spec: Optional[Dict[str, Any]] = None,
    out_path: Optional[str] = None,
    *,
    producer: Optional[ProducerFn] = None,
    sample_every: int = 20,
    max_attempts: int = 1,
) -> Receipt
```

- **`raw_spec`** — anything; coerced into a bounded `SceneSpec` via
  `SceneSpec.bounded(raw, **overrides)`. Never raises on bad input (clamps).
- **`out_path`** — destination MP4. Default:
  `$HERMES_HOME/cache/generated/videos/supervisionvidaeo_<epoch>.mp4`
  (falls back to `~/AppData/Local/hermes`).
- **`producer`** — injected render callable `(spec: SceneSpec, out: Path) -> int`
  returning the frame count. Default = the local vidæo toolchain:
  `C:\æ\vidæo\vidæo.py cycle <spec.json> <out.mp4>` under `C:\gpu\Scripts\python.exe`,
  900 s timeout. A GPU-free producer can be substituted — refusal tests need no GPU.
- **`sample_every`** — supervise 1 of every N frames (`muestrear`).
- **`max_attempts`** — re-produce on FAIL up to N times (spec fingerprint is stable
  across attempts; only the producer output changes).
- **Returns** a `Receipt` **only on PASS**. On exhaustion raises
  `SupervisionRefused(last_reason, last_report)`.

Control flow:

```
for attempt in 1..max_attempts:
    frames = producer(spec, out)                       # PRODUCE
    if not out.exists(): continue                      # PRODUCE failure
    report = supervisar_video(out, muestrear=...)      # SUPERVISE (the gate)
    if report["calidad"] != "PASS": continue           # FAIL → retry
    return Receipt(...)                                # PASS → emit proof
raise SupervisionRefused(...)
```

### `verify(mp4, sample_every=20) -> Dict[str, Any]`

```
def verify(mp4_path: str, sample_every: int = 20) -> Dict[str, Any]
```

Supervise an existing video — the gate alone, no producer. Thin wrapper over
`supervisar_video(mp4_path, muestrear=sample_every)`. Returns the raw supervisor
report dict (see §4).

### `SceneSpec.bounded(raw=None, **overrides) -> SceneSpec`

**Total** — coerces any input into a renderable spec; clamps, never raises.

```
@classmethod
def bounded(cls, raw: Optional[Dict[str, Any]] = None, **overrides: Any) -> "SceneSpec"
```

- `raw` merged with `overrides` → base `cls()`.
- `_int(v, default, lo, hi)` / `_float(...)` clamp each field with a safe fallback.
- `palette` validated against `PALETTES`; unknown → `gold`.
- `title` truncated to 48 chars.

### `Receipt.as_dict()`

```
@dataclass
class Receipt:
    spec: Dict[str, Any]
    spec_fingerprint: str
    output: str
    frames: int
    size_bytes: int
    supervision: Dict[str, Any]   # calidad, luminancia, contraste, movimiento, frames_negros
    supervision_receipt: str
    sha256: str = ""              # set in __post_init__
    produced_at: str = ""         # ISO-8601 UTC, set in __post_init__

    def as_dict(self) -> Dict[str, Any]   # asdict(self)
    def to_json(self, path: Optional[str] = None) -> str
```

`__post_init__`: if `sha256` empty, compute it; if `produced_at` empty, stamp UTC now.

### `SupervisionRefused(reason, report=None)`

```
class SupervisionRefused(Exception):
    def __init__(self, reason: str, report: Optional[Dict[str, Any]] = None):
        super().__init__(reason)
        self.reason = reason          # the FAIL string
        self.report = report or {}    # stage/attempt context + supervisor payload
```

### `toolchain_status() -> Dict[str, Any]`

Never assumes — reports whether this package can actually produce:

```
{
  "package": "supervisionvidaeo",
  "version": "1.0.0",
  "producer": {
    "vidaeo_cli": str | None,      # C:\æ\vidæo\vidæo.py  (None if missing)
    "gpu_python": str | None,      # C:\gpu\Scripts\python.exe (None if missing)
    "available": bool,             # both present?
  },
  "verifier": {"opencv": True, "ml_required": False},
  "bounds": {
    "particles": [MIN_PARTICLES, MAX_PARTICLES],
    "motion": [MIN_MOTION, MAX_MOTION],
    "duration": [MIN_DURATION, MAX_DURATION],
    "palettes": list(PALETTES),
  },
}
```

---

## 3. Gate thresholds (bounds)

### Spec bounds — enforced by `SceneSpec.bounded` (and mirrored by `vidæo`'s
`gate_spec`)

| Field      | Min   | Max   | Default | Notes                                  |
|------------|-------|-------|---------|----------------------------------------|
| particles  | 2000  | 20000 | 6000    | RATIO_NEGRO_MIN context                |
| motion     | 0.01  | 0.08  | 0.03    |                                        |
| duration   | 2     | 6     | 4       | seconds; × fps = frames planned        |
| fps        | 1     | 120   | 30      |                                        |
| width      | 16    | 4096  | 720     |                                        |
| height     | 16    | 4096  | 1280    |                                        |
| palette    | —     | —     | gold    | in {gold, cyan, neon, amber, mono}     |

> Note: `vidæo.py` `gate_spec` allows `duration` 2–10, but `SceneSpec.bounded`
> (the producer-bounder) clamps to **2–6**. A spec of 12 s / 1458 particles
> renders fine in raw form but **REFUSES** at produce-time — clamped to 6 s and
> raised to 2000 particles. Bounds, not render params, win the gate.

### Vision thresholds — `SupervisorVideo` class
(`supervisionvidaeo/vision/video_supervision.py`)

| Constant                  | Value  | Meaning                                  |
|---------------------------|--------|------------------------------------------|
| `UMBRAL_NEGRO`            | 12.0   | per-frame luminance < this ⇒ frame negro |
| `UMBRAL_LUMINANCIA_MIN`   | 20.0   | mean luminance < this ⇒ video demasiado oscuro (FAIL) |
| `UMBRAL_LUMINANCIA_MAX`   | 235.0  | over-exposure ceiling (see §3.2)         |
| `UMBRAL_CONTRASTE_MIN`    | 8.0    | std-dev < this ⇒ video plano / sin detalle (FAIL) |
| `UMBRAL_MOVIMIENTO_MIN`   | 0.5    | mean frame-delta < this ⇒ WARN estático |
| `RATIO_NEGRO_MAX`         | 0.05   | > 5 % black frames ⇒ FAIL                |
| `MAX_FRAMES_NEGROS_WARN`  | 0.01   | > 1 % black frames ⇒ WARN                |

> The two luminance thresholds are distinct and intentional:
> - `UMBRAL_NEGRO = 12` — per-frame; a single frame below 12 is flagged negro.
> - `UMBRAL_LUMINARIA_MIN = 20` — aggregate; if the video's mean luminance is
>   between 12 and 20, **no individual frames are "black" yet the video still
>   FAILS** as too dark. The skill's gold-on-void `æ://` design (#010204 ≈ 10)
>   triggers exactly this: bump particle/bg brightness or ambient light to clear
>   the 20-bar.

### 3.2 Gate evaluation order (the verdict)

Both `SupervisorVideo.supervisar_frames` and the module-level `supervisar_video`
apply this ordered ladder (first match wins):

```
1. pct_negros > RATIO_NEGRO_MAX (0.05)          → FAIL   (frames negros)
2. luminancia_media < UMBRAL_LUMINANCIA_MIN (20)  → FAIL   (luminancia baja)
3. contraste_medio < UMBRAL_CONTRASTE_MIN (8)     → FAIL   (contraste bajo)
4. pct_negros > MAX_FRAMES_NEGROS_WARN (0.01)    → WARN   (frames negros leves)
5. movimiento_medio < UMBRAL_MOVIMIENTO_MIN (0.5) → WARN   (movimiento bajo)
6. otherwise                                     → PASS
```

**`UMBRAL_LUMINANCIA_MAX` (235)** is declared on `SupervisorVideo` as the
over-exposure ceiling but is **not** an enforced gate in the current `supervisar_video`
ladder — `produce()` only gates on `calidad != "PASS"` (i.e. FAIL/WARN), so an
over-bright render that is otherwise statistically healthy still PASSes. Document
the intended ceiling; do not claim it auto-refuses over-exposure. (Raw `muestrear`
in vidæo is 20; the function default is 30 — `produce`/`verify` pass
`sample_every` through, so the contract call site is authoritative.)

**`RATIO_NEGRO_MAX`** is the FAIL bound; `MAX_FRAMES_NEGROS_WARN` (0.01) is the
WARN bound on the same axis.

---

## 4. Receipt format

### `supervisar_video` report dict (the inner supervision_receipt source)

```
{
  "video": str,                       # path
  "frames_analizados": int,           # sampled frames
  "frames_negros": int,
  "frames_con_qr": int,
  "luminancia_media": float (2 dp),
  "contraste_medio": float (2 dp),
  "movimiento_medio": float (3 dp),
  "calidad": "PASS" | "WARN" | "FAIL",
  "razones": List[str],
  "receipt": str,                     # sha256 of {analizados, negros, lum, contraste, movimiento, calidad}
  "supervisado_at": str,              # ISO-8601 UTC
  "error": str,                       # present only on open failure
}
```

### Outer `Receipt` (the proof `produce()` returns)

```
sha256 = H(spec_fingerprint ⊕ supervision_receipt ⊕ frames ⊕ size_bytes)
```

where the payload is JSON-serialized with `sort_keys=True`:

```
sha256 = sha256(
  json.dumps({
    "spec_fingerprint":  <spec.fingerprint()>,   # sha256(json.dumps(spec.as_dict(), sort_keys=True))
    "supervision_receipt": <report["receipt"]>,
    "frames":             <int, producer returned>,
    "size_bytes":         <int, out.stat().st_size>,
  }, sort_keys=True)
)
```

Semantics:
- **Same scene → same proof.** Deterministic spec hash + deterministic supervisor
  hash ⇒ identical `Receipt.sha256` for a stable render.
- **Change the spec OR the render ⇒ proof changes.** A different `supervision_receipt`
  (any metric shifted) or a different `frames`/`size_bytes` rederives a new
  `sha256`. This binds producer output to the verifier verdict irreversibly.
- `supervision_receipt` is the inner `report["receipt"]` — the supervisor's own
  sha256 over the sample statistics — so the outer hash chains:
  **spec fingerprint ⊕ supervisor verdict ⊕ producer facts**.

`Receipt.supervision` (the readable slice stored on the receipt) maps:

| receipt key        | report source          |
|--------------------|------------------------|
| `calidad`          | `report["calidad"]`    |
| `luminancia`       | `report["luminancia_media"]`   |
| `contraste`        | `report["contraste_medio"]`    |
| `movimiento`       | `report["movimiento_medio"]`   |
| `frames_negros`    | `report["frames_negros"]`      |

### Receipt chain

```
prev = receipt                    # prior link
chain.append(next_receipt)        # append; verified by re-deriving sha256
```

A consumer re-derives the leaf `sha256` from the four bound inputs and rejects any
link whose recomputed hash ≠ stored hash (tamper / drift detected).

---

## 5. Toolchain

```
C:\æ\supervisionvidaeo\
  supervisionvidaeo/__init__.py     produce / verify / SceneSpec / Receipt / toolchain_status
  supervisionvidaeo/vision/         canonical verifier (10 modules)
    __init__.py                      re-exports
    deteccion.py                     Deteccion / LoteDetecciones  (geometry engine, no deps)
    anotador.py                     Anotador  (label overlay)
    rastreador.py                   RastreadorIOU  (tracking)
    procesador.py                   ProcesadorVideo  (frame pipeline)
    metricas.py                     Metricas  (quality metrics)
    detectores.py                   DetectorColor / DetectorMovimiento
    qr_vision.py                    QRDeteccion / DetectorQR / ProcesadorQRVideo
    qr_coder.py                     QRCode / QRCoder / QRBatchCoder  (lazy deps — qr extra)
    video_supervision.py            FrameAnalysis / VideoReport / SupervisorVideo / supervisar_video
  tests/                            82 tests
  pyproject.toml                    MIT; extras: [qr], [dev]

C:\æ\vision-supervision\          historical CLI mirror (vidæo verify)
  vision_supervision/__init__.py   compatibility shim → re-exports canonical vision
  vision_supervision/*.py          physical copies of the 10 modules above

C:\æ\vidæo\vidæo.py               agentic video engineering CLI
  status / verify / render / generate / corpus / cycle

C:\æ\store\mp4-factory-app\
  render.mjs                      æRTXrender — deterministic CDP→NVENC harness
  aertxrender.html                render surface (GSAP-driven, deterministic seek)

C:\æ\threejs-curriculo\           scene/Three.js render roots
```

### Component roles

| Component                  | Path                        | Role in the contract                              |
|----------------------------|-----------------------------|---------------------------------------------------|
| `supervisionvidaeo` package | `C:\æ\supervisionvidaeo\`    | public API: `produce` / `verify` / `SceneSpec` / `Receipt` / `toolchain_status` |
| `vision` engine             | `…\vision\`                  | deterministic OpenCV verifier: `supervisar_video`, `SupervisorVideo` |
| `vidæo` CLI                 | `C:\æ\vidæo\vidæo.py`        | orchestrator: `cycle` (SPEC→…→TEST gates), `verify`, `status`; the default producer |
| `render.mjs` (æRTXrender)   | `…\mp4-factory-app\render.mjs` | CDP capture → NVENC frame encode; deterministic `tl.progress(0..1)` seek (NOT `pause`) |
| historical mirror           | `C:\æ\vision-supervision\`  | `vidæo verify` imports `vision_supervision`; shim re-exports canonical vision so both roots share identical thresholds |

### Two copies on disk — the divergence rule

`C:\æ\vision-supervision\vision_supervision\` (used by `vidæo verify`) and
`C:\æ\supervisionvidaeo\vision\` (used by `supervisionvidaeo.produce()`) share
**identical thresholds** but different import roots. The
`vision_supervision/__init__.py` shim (`sys.modules` aliasing) now re-exports the
canonical package, so `from vision_supervision.video_supervision import X` resolves
to the same object as `from supervisionvidaeo.vision.video_supervision import X`.
When results disagree post-shim, the cause is import-root drift, not threshold
drift — check which module's `supervisar_video` is in play.

### NVENC / ffmpeg pairing

- **Encoder ffmpeg: 7.1** (`…/ffmpeg-7.1-nvenc/bin/ffmpeg.exe` for h264_nvenc).
  ffmpeg-9.0.1 requires NVENC API 13.1 and fails on driver 13.0 → use 7.1.
  `render.mjs` hard-codes the 7.1 binary for encode.
- **Probe ffprobe: the 9.x build** (`…/ffmpeg-9.0.1-win32-x64/bin/ffprobe.exe`) —
  used only for metadata probing, intentionally not paired for encode.
- **NVENC test res ≥ 128×128.** Smaller frames are rejected; the render surface
  uses 720×1280 (portrait) — safe.

### Producer injectability

```
def my_producer(spec: SceneSpec, out: Path) -> int:
    render(spec, out)
    return spec.duration * spec.fps

receipt = produce({"palette": "gold"}, "out.mp4", producer=my_producer)
```

---

## 6. SupervisionRefused reasons

`produce()` raises `SupervisionRefused(reason, report)`. `reason` is the FAIL
string; `report` carries `{"stage": ..., "attempt": ..., **supervisor_payload}`.

### Stage: PRODUCE

| Reason                                                | Trigger                                     |
|-------------------------------------------------------|---------------------------------------------|
| `no producer available: C:\æ\vidæo\vidæo.py or the GPU python is missing` | `_default_producer` pre-check      |
| `producer returned but produced no file`              | `out.exists()` is False after call          |
| `producer failed: <tail of stderr/stdout>`            | subprocess non-zero exit                     |
| (timeout)                                             | subprocess > 900 s                           |

### Stage: SUPERVISE (gate verdict becomes the reason)

`reason = "{calidad}: {'; '.join(razones)}"` — i.e. the gate ladder of §3.2.

| `calidad` | `razones` (examples)                                              |
|-----------|-------------------------------------------------------------------|
| `FAIL`    | `luminancia baja (10.2)`  — mean < 20                            |
| `FAIL`    | `contraste bajo (7.4) — video plano` — std-dev < 8               |
| `FAIL`    | `N/M frames negros (P%)` — black ratio > 5 %                     |
| `WARN`    | `movimiento bajo (0.32) — video estático` — mean delta < 0.5      |
| `WARN`    | `frames negros` (leves, 1–5 %)                                 |

> A video that returns `WARN` is **not returned** as a `Receipt` — `produce()`
> treats any verdict `!= "PASS"` as a refusal and retries. Only `PASS` emits proof.
> (WARN still carries `report["receipt"]`; downstream tooling may treat WARN as
> advisory, but `produce()` itself never ships it.)

### Stage: open failure

| Reason                        | Trigger                              |
|-------------------------------|--------------------------------------|
| `cannot open {video}`         | `cv2.VideoCapture` fails to open MP4 |

---

## 7. Pitfalls (learned in practice)

- **GSAP seek: use `tl.progress(0..1)`, not `tl.pause()`.** `pause()` takes
  seconds, not a 0–1 position — `tl.pause(0.5)` pauses at 0.5 s, producing 360
  identical frames (motion = 0 → FAIL).
- **NVENC test res ≥ 128×128.** Render surface is 720×1280 — safe.
- **ffmpeg pairing.** Encode with 7.1; the 9.x build only probes.
- **Bright-first.** vidæo gate luminance is > 20, not 12. #010204 ≈ 10 → FAIL.
  Start #0a1420 for gold-on-void.
- **seekFrame vs loadeddata.** In headless CDP, `<video>` `loadeddata` may not
  fire before capture; guard `seekFrame` to read `video.duration` when `_loaded`
  is false, else textures stay on frame 0 = black + FAIL.
- **WebGL video-texture headroom.** Gold-on-void opacity 0.35 + #050505 bg ⇒
  luminance ~12–16 (FAIL). Use #1a1a2e bg + opacity ≥ 0.7.
- **Lazy optional deps.** `qr_coder` must guard `qrcode`/`PIL` imports and the
  dataclass annotation (`_ImageType = Any` when absent); ship as `pip install
  'supervisionvidaeo[qr]'`. Test the clean-venv install, not the source tree.
- **`SceneSpec.bounded()` must be total.** Bad input clamps; never raises,
  because a throwing spec forces the caller to guard.
- **PID lock** at `${OUT}.lock` is the default producer's concurrency guard for
  the render pass; released on exit.

---

## 8. Quick reference

```python
from supervisionvidaeo import produce, verify, SceneSpec, Receipt, SupervisionRefused, toolchain_status

# 1. Full cycle (produce → supervise → receipt, or refuse)
receipt = produce(
    {"palette": "gold", "motion": 0.03, "duration": 3},
    out_path="C:/æ/out/scene.mp4",          # or None → cache
    sample_every=20,                         # 1 of every 20 frames
    max_attempts=2,                          # retry once on FAIL/WARN
)
print(receipt.sha256)   # spec ⊕ supervision ⊕ frames ⊕ size

# 2. Gate only (existing MP4)
report = verify("C:/æ/out/scene.mp4", sample_every=20)
assert report["calidad"] == "PASS"

# 3. Bounds a wild spec — total, never raises
spec = SceneSpec.bounded({"particles": 1458, "duration": 12, "palette": "ultraviolet"})
# → particles=2000, duration=6, palette=gold  (clamped to bounds)

# 4. Receipt is JSON-serializable proof
Receipt(...).to_json("receipt.json")

# 5. Tool status before burning GPU time
print(toolchain_status()["producer"]["available"])
```

### Constant quick-list

```
MIN_PARTICLES      = 2000
MAX_PARTICLES      = 20000
MIN_DURATION       = 2
MAX_DURATION       = 6
DEFAULT_FPS        = 30
PALETTES           = ("gold", "cyan", "neon", "amber", "mono")

UMBRAL_NEGRO             = 12.0   # per-frame black
UMBRAL_LUMINANCIA_MIN    = 20.0   # video too dark (FAIL)
UMBRAL_LUMINANCIA_MAX    = 235.0  # over-exposure ceiling (declared; not an enforced gate)
UMBRAL_CONTRASTE_MIN     = 8.0    # flat video (FAIL)
UMBRAL_MOVIMIENTO_MIN    = 0.5    # static video (WARN)
RATIO_NEGRO_MAX          = 0.05   # >5% black frames (FAIL)
MAX_FRAMES_NEGROS_WARN   = 0.01   # >1% black frames (WARN)
```
