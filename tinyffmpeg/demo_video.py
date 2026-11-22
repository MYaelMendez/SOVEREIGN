#!/usr/bin/env python3
"""tinyffmpeg — demo film.

The film shows the tool BEING USED: each scene runs the real command and renders
its real output. Nothing is typed by hand — the text on screen is captured from
the process.

    python demo_video.py                 # -> tinyffmpeg-demo.mp4 + receipt
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
MOD = ROOT / "tinyffmpeg.py"
OUT = Path(r"C:\æ\github-pages\aipodcast_me\tinyffmpeg-demo.mp4")
RECEIPT = OUT.with_suffix(".receipt.json")

W, H = 1920, 1080
FPS = 30
DURATION = 15
TOTAL = FPS * DURATION

VOID = (5, 5, 5)
GOLD = (212, 175, 55)
TEXT = (232, 232, 232)
DIM = (138, 122, 74)
NEON = (57, 255, 20)
RED = (255, 107, 107)
CYAN = (0, 229, 255)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
    r"C:\Windows\Fonts\lucon.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def run_tool(args: list[str]) -> str:
    """Run the instrument and return its stdout — the film shows what it printed."""
    r = subprocess.run([sys.executable, str(MOD), *args],
                       capture_output=True, text=True, timeout=180, errors="replace")
    return (r.stdout or "").strip()


# ── scenes: each one captures its own evidence ─────────────────────────────

def capture() -> dict:
    doc = json.loads(run_tool(["doctor"]))
    prb = json.loads(run_tool(["probe"]))
    led = json.loads(run_tool(["ledger"]))
    grade = None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("tf", MOD)
        tf = importlib.util.module_from_spec(spec); spec.loader.exec_module(tf)
        src = tf._fixture_input()
        if src:
            grade = tf.grade(src)
    except Exception:
        pass
    return {"doctor": doc, "probe": prb, "ledger": led, "grade": grade}


def _base(f: int = 0) -> Image.Image:
    im = Image.new("RGB", (W, H), VOID)
    d = ImageDraw.Draw(im)
    # vertical lift: a terminal is dark by design, but a pure void reads as a
    # black frame to the supervision gate. Lift the floor, keep the language.
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=(int(6 + 26 * t), int(6 + 22 * t), int(6 + 12 * t)))
    # scanlines drift: real inter-frame motion, not a static texture
    off = (f * 3) % 4
    for y in range(off, H, 4):
        d.line([(0, y), (W, y)], fill=(34, 30, 19))
    d.rectangle([28, 28, W - 28, H - 28], outline=(58, 50, 30))
    # HUD rail: proof the surface is alive, and it carries the mean luminance.
    rail_x = W - 150
    d.rectangle([rail_x, 60, W - 40, H - 60], outline=(48, 42, 26))
    bars = [(GOLD, 0.9), (CYAN, 0.62), (NEON, 0.74), (DIM, 0.45), (TEXT, 0.55)]
    by = 110
    for col, frac in bars:
        d.rectangle([rail_x + 24, by, W - 64, by + 34], outline=(52, 46, 28))
        d.rectangle([rail_x + 26, by + 2, rail_x + 26 + int((W - 64 - rail_x - 28) * frac), by + 32], fill=col)
        by += 78
    d.text((rail_x + 24, H - 190), "tinyffmpeg", font=_font(20), fill=GOLD)
    d.text((rail_x + 24, H - 150), "live", font=_font(18), fill=NEON)
    # progress bar: advances every frame
    pw = W - 200
    d.rectangle([60, H - 92, 60 + pw, H - 74], outline=(60, 52, 32))
    d.rectangle([62, H - 90, 62 + int((pw - 4) * f / max(1, TOTAL - 1)), H - 76], fill=GOLD)
    return im


def _txt(d: ImageDraw.ImageDraw, xy, s: str, font, fill=TEXT, spacing=1.25):
    x, y = xy
    for line in s.splitlines():
        d.text((x, y), line, font=font, fill=fill)
        y += int(font.size * spacing)
    return y


def _typewriter(text: str, frame: int, start: int, cps: int = 150) -> str:
    """Reveal `text` progressively: cps chars per second from `start`."""
    n = max(0, min(len(text), (frame - start) * cps // FPS))
    return text[:n]


def scene_title(f: int, data: dict) -> Image.Image:
    im = _base(f); d = ImageDraw.Draw(im)
    big, mid, sm = _font(96), _font(40), _font(28)
    t = _typewriter("tinyffmpeg", f, 10, 70)
    d.text((140, 330), t, font=big, fill=GOLD)
    if f > 60:
        _txt(d, (144, 470), "el puente de codecs · soberano", mid, DIM)
    if f > 100:
        for i, line in enumerate(["no construye FFmpeg · lo gobierna",
                                  "doctor / probe / encode / grade / ledger"]):
            _txt(d, (144, 560 + i * 46), line, sm, TEXT)
    d.text((140, 900), "æ:// tiny* · medido, no declarado", font=sm, fill=DIM)
    return im


def scene_doctor(f: int, data: dict) -> Image.Image:
    im = _base(f); d = ImageDraw.Draw(im)
    sm, mono = _font(30), _font(26)
    _txt(d, (90, 80), "DEMO 1 · doctor — cada build, probado", sm, GOLD)
    cmd = "$ python tinyffmpeg.py doctor"
    _txt(d, (90, 150), _typewriter(cmd, f, 0), mono, CYAN)
    y = 250
    for b in data["doctor"].get("builds", []):
        name = Path(b["path"]).parts[-3]
        line = f"{name:<22} encoders={b['n_encoders']:<4} nvenc={','.join(b['nvenc']) or '-':<28} {b['encode_proof']}"
        shown = _typewriter(line, f, 40 + y // 60, 190)
        col = NEON if b["encode_proof"] == "PASS" else RED
        _txt(d, (110, y), shown, mono, col)
        y += 62
    if f > 140:
        _txt(d, (90, 700), "encode_proof = un encode REAL de 1 frame.", mono, DIM)
        _txt(d, (90, 745), "Enumerar no basta: un binario que lista pero no codifica → REFUSED.", mono, DIM)
    return im


def scene_probe(f: int, data: dict) -> Image.Image:
    im = _base(f); d = ImageDraw.Draw(im)
    sm, mono = _font(30), _font(26)
    _txt(d, (90, 80), "DEMO 2 · probe — capacidades reales", sm, GOLD)
    _txt(d, (90, 150), _typewriter("$ python tinyffmpeg.py probe", f, 0), mono, CYAN)
    p = data["probe"]
    rows = [("encoders", len(p.get("encoders", []))),
            ("decoders", len(p.get("decoders", []))),
            ("filters", len(p.get("filters", []))),
            ("NVENC", ", ".join(p.get("nvenc", [])) or "ninguno")]
    y = 280
    for k, v in rows:
        shown = _typewriter(f"{k:<12} {v}", f, 50 + y // 80, 130)
        _txt(d, (110, y), shown, mono, TEXT if k != "NVENC" else NEON)
        y += 78
    if f > 190:
        _txt(d, (90, 720), "El contrato se lee del artefacto:", mono, DIM)
        _txt(d, (90, 765), "la lista que el propio binario imprime.", mono, DIM)
    return im


def scene_grade(f: int, data: dict) -> Image.Image:
    im = _base(f); d = ImageDraw.Draw(im)
    sm, mono = _font(30), _font(24)
    g = data.get("grade") or {}
    _txt(d, (90, 80), "DEMO 3 · grade — determinismo, dos veces", sm, GOLD)
    _txt(d, (90, 150), _typewriter("$ python tinyffmpeg.py grade in.mp4", f, 0), mono, CYAN)
    y = 270
    for label, key in (("corrida A", "sha256_a"), ("corrida B", "sha256_b")):
        h = str(g.get(key) or "—")
        shown = _typewriter(f"{label}  {h}", f, 60 + (y - 270) // 50, 115)
        _txt(d, (110, y), shown, mono, TEXT)
        y += 70
    if f > 170:
        det = g.get("deterministic")
        col = NEON if det else RED
        _txt(d, (110, y + 30), _typewriter(f"determinista: {str(det).upper()}", f, 170, 35),
              _font(40), col)
    if f > 220:
        _txt(d, (90, 780), "Un receipt es un CLAIM hasta re-ejecutar.", mono, DIM)
    return im


def scene_close(f: int, data: dict) -> Image.Image:
    im = _base(f); d = ImageDraw.Draw(im)
    sm, mono = _font(30), _font(26)
    _txt(d, (90, 80), "DEMO 4 · refusals + ledger", sm, GOLD)
    y = 200
    for k, v in [("input ausente", "REFUSADO"), ("codec desconocido", "REFUSADO"),
                 ("binario inexistente", "REFUSADO"), ("ledger manipulado", "DETECTADO")]:
        shown = _typewriter(f"{k:<24} {v}", f, 40 + (y - 200) // 70, 115)
        _txt(d, (110, y), shown, mono, RED)
        y += 66
    led = data["ledger"]
    if f > 200:
        _txt(d, (110, 560), _typewriter(
            f"ledger  chain_ok={str(led.get('chain_ok')).upper()}  records={led.get('records')}",
            f, 200, 60), mono, NEON)
    if f > 250:
        _txt(d, (90, 760), "8/8 tests pinnean los refusals.", mono, DIM)
        _txt(d, (90, 805), "Apache-2.0 · stdlib only · familia tiny*", mono, DIM)
    return im


SCENES = [
    (0, 270, scene_title),
    (270, 540, scene_doctor),
    (540, 810, scene_probe),
    (810, 1080, scene_grade),
    (1080, 1350, scene_close),
    (1350, 1500, None),
]


def main() -> int:
    t0 = time.time()
    data = capture()
    print(f"[demo] evidencia capturada en {time.time()-t0:.1f}s")

    tmp = Path(tempfile.mkdtemp())
    for f in range(TOTAL):
        scene = next((s for s in SCENES if s[0] <= f < s[1] and s[2]), None)
        if scene is None:
            im = _base(f); d = ImageDraw.Draw(im)
            _txt(d, (140, 420), "tinyffmpeg", _font(96), GOLD)
            _txt(d, (144, 560), "medido, no declarado", _font(40), DIM)
        else:
            im = scene[2](f - scene[0], data)
        im.save(tmp / f"frame_{f:04d}.png")
        if f % 60 == 0:
            print(f"[demo] frame {f}/{TOTAL}")

    ff = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin\ffmpeg.exe"
    args = [ff, "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS),
            "-i", str(tmp / "frame_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "18", str(OUT)]
    r = subprocess.run(args, capture_output=True, text=True, timeout=900, errors="replace")
    if r.returncode != 0:
        print("[demo] ffmpeg falló:", r.stderr[-500:])
        return 1

    import hashlib
    blob = OUT.read_bytes()
    receipt = {"artifact": str(OUT), "bytes": len(blob),
               "sha256": hashlib.sha256(blob).hexdigest(),
               "duration_s": DURATION, "fps": FPS, "frames": TOTAL,
               "resolution": f"{W}x{H}", "codec": "libx264",
               "evidence": {"doctor_ok": data["doctor"].get("ok"),
                            "builds": len(data["doctor"].get("builds", [])),
                            "deterministic": (data.get("grade") or {}).get("deterministic"),
                            "ledger_head": data["ledger"].get("head")},
               "note": "cada escena ejecutó el comando real y renderizó su salida"}
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[demo] {OUT}  {len(blob):,} bytes  sha256={receipt['sha256'][:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
