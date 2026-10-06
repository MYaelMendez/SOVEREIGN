# 🛸 opensourceware media studio

Sovereign video production. Local. Deterministic. With receipt.

```
Concepto (llama.cpp GPU)
  → Storyboard (llama.cpp GPU)
  → Script (llama.cpp GPU)
  → Frames (CuPy GPU o Chrome CDP)
  → Encode (NVENC GPU)
  → Verify (supervisionvidaeo:// gate)
  → Receipt (SHA-256)
  → Deploy (github.io truth surface)

Todo local. Todo determinista. Todo con receipt.
Cero nube. Cero ML. Cero dependencia externa.
```

## Capabilities

| Scheme | Role | Status |
|---|---|---|
| `draw://` | Spec-driven vector drawing, stroke-by-stroke | ✅ operational |
| `æRTXrender` | Deterministic HTML→MP4 render | ✅ operational |
| `supervisionvidaeo://` | Gate + contract (produce → Receipt \| Refused) | ✅ operational |
| `vidæoproducer://` | Pipeline orchestrator | ✅ operational |
| `video-ae` | AEE cycle (SPEC → TEST) | ✅ operational |
| VLC pane | Human visual gate | ✅ v0.2.0 sovereign |

## Quick start

```bash
# Render a scene
cd C:/æ/store/mp4-factory-app
node vidaeo-producer.js specs/spec-draw-video.json output/draw-video.mp4

# Gate
C:/gpu/Scripts/python.exe C:/æ/vidæo/vidæo.py verify output/draw-video.mp4

# VLC pane
C:/gpu/Scripts/python.exe C:/æ/vidæo/vidæo.py vlc output/draw-video.mp4

# Deploy
cp output/*.mp4 C:/æ/github-pages/
```

## Specs

| Spec | Scene | Duration | Gate |
|---|---|---|---|
| `spec-draw-video.json` | draw:// vector drawing | 6s | PASS |
| `spec-golden-ratio.json` | golden ratio visualization | — | — |
| `spec-text-video.json` | text overlay | — | — |
| `spec-this-is-agentic.json` | agentic engineering | — | — |
| `spec-toolchain.json` | toolchain demo | — | — |
| `spec-ufo-8s.json` | UFO animation | — | — |

## Sovereignty

- **Secrets**: local custody at `C:/æ/secrets/`, never hardcoded
- **Receipts**: SHA-256 on every action
- **Gate**: supervisionvidaeo:// verifies before deploy
- **Truth surface**: github.io = point of truth
- **License**: #opensourceware — open source, local first

## Learn to draw

The `draw://` capability is taught to all agents via:
- `mp4-factory/SKILL.md` — "Drawing in Video — draw://" section
- `AGENTS.md` — "Drawing in Video — draw://" section

Shape model: JSON `shapes[]` array → producer injects as `?shapes=<json>` → scene strokes progressively.

Primitives: `line · rect · circle · arrow · polyline · polygon · text`

---

`æ://` — the agentic language chassis
