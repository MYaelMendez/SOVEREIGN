# tinyVISION — supervision for the robot policy

The instrument we already use on our films — luminance, contrast, motion, gates,
receipts — pointed at the **policy**. A policy trace becomes a film of the real
CAD; the film is supervised and tracked; the visual trajectory is compared with
the physics trace that produced it.

```
policy trace → render (rtx_asimov, CUDA) → film → supervise + track → compare
```

## The question it answers

**Does the picture agree with the physics?** A trace can claim success while the
film shows a frozen body; a film can look alive while the trace says it fell.
Both instruments are read, and their disagreement is the finding.

## Measured on the `0818` policy film (288 frames)

| stage | result |
|---|---|
| supervise | **PASS** — luminance 23.04 · contrast 46.46 · motion 1.83 · 0 black |
| track | **1 coherent blob** over 288 frames (dx 23 px, dy 10 px) |
| agree | **ok** — coherent + direction ok, implied px/m 24.0 |

## The finding

A raw motion detector **fragments into 227 tracks**, because the render palette
carries a gold HUD band and a blue floor. A **palette-aware colour detector**
isolates the robot; aspect and position filters reject the HUD and floor bands.
Pixels and metres remain separate units — the scale is reported, never invented.

## Use

```bash
tinyvision.py doctor                      # engine + renderer present?
tinyvision.py render <trace> <film>       # trace → film (the real CAD)
tinyvision.py supervise <film>            # lum/contraste/movimiento/calidad
tinyvision.py track <film> [--colors azul]
tinyvision.py agree <trace> <film> [--px-per-m N]
tinyvision.py ledger
```

Renderer interpreter: `TINYVISION_PYTHON` (defaults to `C:/gpu/Scripts/python.exe`,
which has CuPy). Model dir: `TINYVISION_MODEL_DIR` (defaults to `tinygpu/model`,
the 26 meshes).

## Tests

7 tests pin the gate read, the single-blob tracking, the cross-unit comparison,
the missing-film refusal, and the ledger chain + tamper.

## Rules

1. The gate is read from the film, never assumed.
2. Pixels and metres are different units; both are reported.
3. One dominant track is required; a fragmented film is incoherent, not averaged.
4. Every run is a hash in the ledger.
5. Simulation only — a film of a trace is a picture of a plan.
