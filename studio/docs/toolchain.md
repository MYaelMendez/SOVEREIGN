# opensourceware media studio — toolchain spec

## Pipeline (8 steps)

```
1. Concept     llama.cpp GPU     text → idea
2. Storyboard  llama.cpp GPU     idea → visual plan
3. Script      llama.cpp GPU     plan → narration
4. Frames      CuPy GPU / CDP    script → frames
5. Encode      NVENC GPU         frames → MP4
6. Verify      supervisionvidaeo  MP4 → PASS | Refused
7. Receipt     SHA-256           PASS → hash
8. Deploy      github.io         receipt → truth surface
```

## Draw capability

### Shape model

```json
{ "t": "polyline", "pts": [[x,y],...], "w": 8, "c": "#D4AF37" }
{ "t": "rect",   "x": x, "y": y, "w": w, "h": h, "r": r, "lw": 8, "c": "#D4AF37" }
{ "t": "circle", "cx": cx, "cy": cy, "r": r, "lw": 8, "c": "#00eaff" }
{ "t": "arrow",  "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": 7, "c": "#D4AF37" }
{ "t": "text",   "x": x, "y": y, "s": 72, "c": "#ffd98a", "tx": "draw://" }
{ "t": "line",   "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": 6, "c": "#D4AF37" }
```

### Stroke engine

Every shape → stroke path. At progress `p` the canvas reveals the first `p` fraction of the path with a pen-tip dot at the head. This is what makes it read as *drawing* rather than appearing.

### Scene

`C:/æ/site/aipodcast_me/draw-video.html` — Canvas 2D, zero deps, no CDN.

### Producer injection

```javascript
// vidaeo-producer.js line ~142
const q = new URLSearchParams();
if (Array.isArray(spec.shapes) && spec.shapes.length) q.set('shapes', JSON.stringify(spec.shapes));
if (Array.isArray(spec.text_lines) && spec.text_lines.length) q.set('text', spec.text_lines.join('|'));
else if (typeof spec.text === 'string' && spec.text) q.set('text', spec.text);
if (spec.title) q.set('title', spec.title);
```

## VLC pane (sovereign v0.2.0)

### Changes from v0.1.0

| # | Before | After |
|---|---|---|
| 1 | Cloud broker URL | Local only |
| 2 | Hardcoded password | `_load_secret()` from `C:/æ/secrets/` |
| 3 | No receipt | SHA-256 receipt on every endpoint |
| 4 | No gate verification | State check after open |
| 5 | `pl_add` (no-op in VLC 3.x) | `in_play` |
| 6 | No Unicode handling | ASCII temp copy |
| 7 | `_start_vlc()` always True | Returns False on failure |

### Endpoints

```
GET  /health     → {ok, plugin, version, sovereign}
GET  /status     → receipt + state
POST /play       → receipt
POST /pause      → receipt
POST /stop       → receipt
POST /next       → receipt
POST /prev       → receipt
POST /seek       → receipt + percent
POST /volume     → receipt + volume
POST /open       → receipt + gate verification (state, filename, ok)
POST /fullscreen → receipt
```

### Gate verification (open_file)

```
1. ASCII copy if Unicode path
2. pl_empty
3. in_play with file:// URI
4. Wait 1.5s
5. Read state from VLC
6. ok = bool(filename) and state in (playing, paused)
7. Return receipt with ok
```

## SupervisorVideo gate thresholds

```
luminancia_media  > 20
contraste_medio   > 8
movimiento_medio  > 0.5
frames_negros     < 5%
```

## Receipt format

```json
{
  "action": "open",
  "ts": 1717020000.123,
  "sha256": "faedda2523ff2fdbfebb1458050f6e0650901a0791a6cb3ca5de5728f04f5e02",
  "result": { "state": "playing", "filename": "draw-video.mp4", "ok": true }
}
```

## Sovereignty rules

1. **Spec-driven** — shapes in spec, not hardcoded in scene
2. **Strokes, not sprites** — progressive path reveal = drawing
3. **Deterministic** — `p = i/(total-1)`, no wall-clock
4. **Local only** — no cloud, no CDN, no external dependency
5. **Receipts** — SHA-256 on every action
6. **Gate before deploy** — supervisionvidaeo verifies first
7. **Truth surface** — github.io is the point of truth
8. **Secrets local** — `C:/æ/secrets/`, never in code
