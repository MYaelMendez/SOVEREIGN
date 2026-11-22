"""emoji_scene — an emoji is an ADDRESS that opens a film context.

Not decoration. Given one Unicode symbol, derive a deterministic scene: a
context colour palette, a camera posture and a motion family. Same emoji ->
same scene, every run, on any machine. Zero tokens, zero network, zero model.

    from emoji_scene import scene_for, render_frames
    sc = scene_for("🍊")
    # {'emoji':'🍊','codepoints':[127822],'seed':…,'palette':{…},'camera':{…},'motion':{…}}
    frames = render_frames("🍊", seconds=5)      # deterministic (needs tinyCUDA)

THE PRINCIPLE
    Unicode emoji open up contexts. A symbol is a stable, language-independent
    address — it survives platforms, keyboards and locales, and it hashes to the
    same scene everywhere. So the film pipeline takes the emoji as a FIRST-CLASS
    INPUT: address a film by its symbol, reproduce it, grade it, receipt it.

    The palette keeps the sovereign base (gold on void); the emoji contributes a
    CONTEXT HUE (the accent). The camera azimuth/elevation and the motion family
    come from the symbol's seed, so two different emoji render two different
    films and the same emoji renders the same film twice.

Determinism: no Date.now, no unseeded random, no network. The seed is
sha256(str(codepoints))[:8] — VS16 included, so 🏎️ and 🏎 are different
addresses (they are: one is an emoji, one is a text glyph).
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

MOTION_FAMILIES = ("orbit", "pulse", "drift", "spin")
GOLD = (0.82, 0.69, 0.22)
VOID = (0.075, 0.062, 0.034)
ACCENT_S = 0.85
ACCENT_V = 0.95

__all__ = [
    "MOTION_FAMILIES", "codepoints", "seed_for", "palette_for", "scene_for",
    "is_addressable", "render_frames",
]


def codepoints(emoji: str) -> tuple:
    """The emoji's Unicode code points — the stable address (VS16 included)."""
    return tuple(ord(c) for c in emoji)


def seed_for(emoji: str) -> int:
    """A stable 64-bit seed from the code points. Same emoji -> same seed."""
    return int.from_bytes(
        hashlib.sha256(str(codepoints(emoji)).encode("utf-8")).digest()[:8], "big"
    )


def _hsv(h: float, s: float, v: float) -> tuple:
    """HSV -> RGB, all 0-1. h in degrees."""
    h = h % 360.0
    c = v * s
    x = c * (1.0 - abs((h / 60.0) % 2.0 - 1.0))
    m = v - c
    if h < 60.0:
        r, g, b = c, x, 0.0
    elif h < 120.0:
        r, g, b = x, c, 0.0
    elif h < 180.0:
        r, g, b = 0.0, c, x
    elif h < 240.0:
        r, g, b = 0.0, x, c
    elif h < 300.0:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return (round(r + m, 4), round(g + m, 4), round(b + m, 4))


def palette_for(emoji: str) -> dict:
    """Gold-on-void base; the emoji contributes a context hue (the accent)."""
    cp = codepoints(emoji)
    hue = (sum(cp) * 37 + cp[0] * 3) % 360
    return {
        "base": GOLD,
        "void": VOID,
        "accent": _hsv(hue, ACCENT_S, ACCENT_V),
        "context_hue": hue,
    }


def scene_for(emoji: str) -> dict:
    """The whole deterministic context for one emoji."""
    cp = codepoints(emoji)
    seed = seed_for(emoji)
    az = ((cp[0] % 360) + (seed % 72)) * math.pi / 180.0
    el = 0.16 + (seed % 44) / 100.0
    return {
        "emoji": emoji,
        "codepoints": list(cp),
        "seed": seed,
        "palette": palette_for(emoji),
        "camera": {"az": round(az, 4), "el": round(el, 4), "dist": 5.6, "fov": 42.0},
        "motion": {
            "family": MOTION_FAMILIES[seed % len(MOTION_FAMILIES)],
            "speed": round(0.6 + (seed % 40) / 100.0, 2),
        },
    }


def is_addressable(emoji: str) -> bool:
    """True when the symbol is a short, non-empty cluster we can address."""
    if not emoji or len(emoji) > 8:
        return False
    return any(not (ord(c) >= 0x0300 and ord(c) <= 0x036F) for c in emoji)


# ── deterministic renderer ───────────────────────────────────────────────────
def _octahedron(cx, cy, cz, r, col):
    import numpy as np

    top = (cx, cy + r, cz)
    bot = (cx, cy - r, cz)
    ring = [(cx + r, cy, cz), (cx, cy, cz + r), (cx - r, cy, cz), (cx, cy, cz - r)]
    tris = []
    for i in range(4):
        a = ring[i]
        b = ring[(i + 1) % 4]
        tris.append((top, a, b))
        tris.append((bot, b, a))
    verts = np.array(tris, np.float32)
    norms = np.empty((len(tris), 3), np.float32)
    for i, (p0, p1, p2) in enumerate(tris):
        n = np.cross(np.array(p1, np.float32) - np.array(p0, np.float32),
                     np.array(p2, np.float32) - np.array(p0, np.float32))
        ln = float(np.linalg.norm(n))
        norms[i] = n / ln if ln > 1e-9 else (0.0, 0.0, 1.0)
    cols = np.tile(np.array(col, np.float32), (len(tris), 1))
    return verts, norms, cols


def _band(rx, ry, segs, col, w=0.05):
    import numpy as np

    tris = []
    for i in range(segs):
        a0 = 2 * math.pi * i / segs
        a1 = 2 * math.pi * (i + 1) / segs
        p00 = ((rx - w) * math.cos(a0), (ry - w) * math.sin(a0), 0.0)
        p01 = ((rx - w) * math.cos(a1), (ry - w) * math.sin(a1), 0.0)
        p10 = ((rx + w) * math.cos(a0), (ry + w) * math.sin(a0), 0.0)
        p11 = ((rx + w) * math.cos(a1), (ry + w) * math.sin(a1), 0.0)
        tris.append((p00, p10, p11))
        tris.append((p00, p11, p01))
    verts = np.array(tris, np.float32)
    norms = np.tile(np.array([0.0, 0.0, 1.0], np.float32), (len(tris), 1))
    cols = np.tile(np.array(col, np.float32), (len(tris), 1))
    return verts, norms, cols


def _grade(frame, w, h):
    """Sovereign grade: a warm radial glow, so the void is never empty."""
    import numpy as np

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w * 0.5) / (w * 0.52)) ** 2 + ((yy - h * 0.44) / (h * 0.52)) ** 2)
    glow = np.clip(1.0 - d, 0.0, 1.0) ** 2.2
    out = frame.astype(np.float32) + glow[..., None] * np.array([115.0, 92.0, 33.0], np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)


def _load_tinycuda():
    """Import tinyCUDA, looking in the sibling æ package when it is not on path.

    tinycudavideo is a standalone PyPI package; tinyCUDA is its optional render
    backend, not a hard dependency. An absent backend is reported, never silently
    substituted.
    """
    try:
        from tinycuda import Raster, persp, look_at
        return Raster, persp, look_at
    except Exception as exc:
        here = Path(__file__).resolve().parent
        for cand in (here.parent / "tinycuda", here.parent / "tinygpu", here):
            src = cand / "tinycuda.py"
            if not src.exists():
                continue
            # a sibling package dir named `tinycuda` is a NAMESPACE package and
            # shadows tinycuda.py when the parent is on sys.path — load the file
            # by path instead of relying on the import system to prefer it
            import importlib.util
            spec = importlib.util.spec_from_file_location("tinycuda", src)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["tinycuda"] = mod
            spec.loader.exec_module(mod)
            return mod.Raster, mod.persp, mod.look_at
        raise ImportError(
            "render_frames needs tinyCUDA + CUDA (no tinycuda.py found beside "
            f"tinycudavideo): {type(exc).__name__}: {exc}"
        )


def render_frames(emoji: str, seconds: float = 5.0, fps: int = 24,
                  w: int = 720, h: int = 1280, nodes: int = 12):
    """Deterministic frames for one emoji. Requires tinyCUDA + CUDA.

    A gold halo of `nodes` gems tinted by the emoji's context palette, with the
    camera and motion the emoji's seed selects. Same emoji -> same frames ->
    same bytes. Raises ImportError when CUDA/tinyCUDA is absent — never a silent
    fallback to something else.
    """
    Raster, persp, look_at = _load_tinycuda()
    import numpy as np

    sc = scene_for(emoji)
    pal = sc["palette"]
    cam = sc["camera"]
    fam = sc["motion"]["family"]
    speed = sc["motion"]["speed"]
    n = max(1, int(round(seconds * fps)))
    r = Raster(w, h)
    rx, ry = 1.05, 1.05
    out = []
    for i in range(n):
        t = i / fps
        az = cam["az"] + (speed * t if fam in ("orbit", "spin") else 0.0)
        el = cam["el"] + (0.05 * math.sin(t * speed) if fam == "drift" else 0.0)
        eye = np.array([cam["dist"] * math.cos(az) * math.cos(el),
                        cam["dist"] * math.sin(el),
                        cam["dist"] * math.cos(az) * math.sin(el)], np.float32)
        mvp = persp(cam["fov"], 0.05, 40.0) @ look_at(eye, np.array([0.0, 0.0, 0.0], np.float32))
        parts = [_band(rx, ry, 96, pal["base"], w=0.05)]
        for k in range(nodes):
            a = 2 * math.pi * k / nodes + (speed * t if fam in ("orbit", "spin", "drift") else 0.0)
            rr = 0.16 if fam == "pulse" and k == int((t * speed * 6) % nodes) else 0.10
            col = pal["accent"] if k == int((t * speed * 6) % nodes) else pal["base"]
            parts.append(_octahedron(rx * math.cos(a), ry * math.sin(a), 0.0, rr, col))
        parts.append(_octahedron(0.0, 0.0, 0.0, 0.30 + 0.03 * math.sin(t * 3.0), pal["base"]))
        v = np.concatenate([p[0] for p in parts], axis=0)
        nm = np.concatenate([p[1] for p in parts], axis=0)
        cl = np.concatenate([p[2] for p in parts], axis=0)
        out.append(_grade(r.render(v, nm, cl, mvp, bg=pal["void"]), w, h))
    return out
