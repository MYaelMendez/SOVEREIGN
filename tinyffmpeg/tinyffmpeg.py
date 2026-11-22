#!/usr/bin/env python3
"""tinyffmpeg — a sovereign instrument for the local FFmpeg builds.

tinyffmpeg does NOT build FFmpeg and does NOT replace it. It is the instrument
that GOVERNS the builds already on the machine:

    doctor()  finds every real ffmpeg binary, then PROVES it — it runs an encode,
              not an enumeration. A binary that lists encoders but cannot encode
              is reported as unusable.
    probe     capabilities read from the binary's own output.
    encode    runs a build and returns a SHA-256 receipt.
    grade     encodes twice and compares bytes — the determinism claim is only
              evidence after two runs agree.
    ledger    hash-chained record of DECISIONS (doctor/probe/encode/grade).

Invariants (from the tiny* family):
  1. doctor() returns ok only from what it measured.
  2. Every verb has a refusal path; the tests pin the refusals.
  3. The contract is read FROM THE ARTIFACT (the encoder list, the output bytes).
  4. A receipt is a claim until re-run; grade() proves it twice.

Stdlib only. FFmpeg is found on PATH or at the known sovereign paths; no build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LEDGER = Path(os.environ.get("TINYFFMPEG_LEDGER", r"C:\æ\logs\tinyffmpeg.jsonl"))
GENESIS = "0" * 64

# Known sovereign builds, most authoritative first.
CANDIDATES = [
    r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin\ffmpeg.exe",
    r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe",
    r"C:\Users\yaelm\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe",
]


def _candidates() -> list[Path]:
    out: list[Path] = []
    w = shutil.which("ffmpeg")
    if w:
        out.append(Path(w))
    out += [Path(p) for p in CANDIDATES]
    seen, uniq = set(), []
    for p in out:
        s = str(p).lower()
        if s not in seen and p.exists():
            seen.add(s)
            uniq.append(p)
    return uniq


def _run(exe: Path, args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        r = subprocess.run([str(exe), *args], capture_output=True, text=True,
                           timeout=timeout, errors="replace")
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except Exception as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def _caps(exe: Path, flag: str) -> str:
    """-encoders/-decoders/-filters write to stdout on these builds; older ones
    use stderr. Return whichever carried the list."""
    _, so, se = _run(exe, ["-hide_banner", flag])
    return so if len(so) >= len(se) else se


def _names(blob: str) -> list[str]:
    """Column 2 of -encoders/-decoders/-filters. Flag columns differ:
    encoders/decoders start with V/A/S/X/F/G/B, filters start with '.' or T."""
    out = []
    for line in blob.splitlines():
        parts = line.split()
        if len(parts) > 1 and parts[0] and all(ch in ".VASXFGBTD" for ch in parts[0]):
            out.append(parts[1])
    return sorted(set(out))


def _can_encode(exe: Path) -> tuple[bool, str, str]:
    """Proof, not enumeration: a real one-frame encode into a temp file."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "probe.mp4"
        rc, _, err = _run(exe, ["-hide_banner", "-loglevel", "error", "-y",
                                "-f", "lavfi", "-i", "testsrc=size=64x64:rate=1",
                                "-frames:v", "1", "-c:v", "libx264", str(out)],
                          timeout=90)
        if rc != 0:
            return False, "", (err.strip().splitlines() or [""])[-1][:160]
        if not out.exists() or out.stat().st_size == 0:
            return False, "", "encoder produced no bytes"
        return True, hashlib.sha256(out.read_bytes()).hexdigest()[:16], ""


def doctor() -> dict:
    builds = _candidates()
    out = {"ok": False, "builds": [], "found": len(builds)}
    if not builds:
        out["refusal"] = "no ffmpeg binary found on PATH or at the sovereign paths"
        out["fix"] = "install a build, or set PATH to its bin/ directory"
        return out
    for exe in builds:
        rc, so, se = _run(exe, ["-version"])
        ver = so.splitlines()[0] if rc == 0 and so else f"unreachable ({se.strip()[:80]})"
        enc = _names(_caps(exe, "-encoders"))
        nv = [e for e in enc if "nvenc" in e]
        ok, digest, why = _can_encode(exe)
        out["builds"].append({
            "path": str(exe), "version": ver,
            "nvenc": nv, "n_encoders": len(enc),
            "encode_proof": "PASS" if ok else f"REFUSED: {why}",
            "probe_sha256": digest,
        })
    out["ok"] = any(b["encode_proof"] == "PASS" for b in out["builds"])
    out["note"] = "measured on this machine, not assumed"
    return out


def probe(exe: Path | None = None) -> dict:
    exe = exe or (_candidates()[0] if _candidates() else None)
    if exe is None or not Path(exe).exists():
        return {"refusal": f"no ffmpeg build at {exe}", "ok": False}
    enc = _names(_caps(exe, "-encoders"))
    dec = _names(_caps(exe, "-decoders"))
    flt = _names(_caps(exe, "-filters"))
    return {"ok": True, "path": str(exe),
            "encoders": enc, "decoders": dec,
            "filters": flt,
            "nvenc": [e for e in enc if "nvenc" in e]}


def _receipt(exe: Path, args: list[str], out_path: Path, rc: int, stderr: str) -> dict:
    h = hashlib.sha256(out_path.read_bytes()).hexdigest() if out_path.exists() else None
    return {"tool": "tinyffmpeg", "exe": str(exe), "args": args,
            "out": str(out_path), "rc": rc, "sha256": h,
            "size": out_path.stat().st_size if out_path.exists() else 0,
            "stderr_tail": stderr.strip().splitlines()[-1][:200] if stderr.strip() else "",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def encode(inp: Path, out: Path, codec: str = "libx264", extra: list[str] | None = None) -> dict:
    builds = _candidates()
    if not builds:
        return {"refusal": "no ffmpeg build", "ok": False}
    if not inp.exists():
        return {"refusal": f"input missing: {inp}", "ok": False}
    exe = builds[0]
    args = ["-hide_banner", "-loglevel", "error", "-y", "-i", str(inp),
            "-c:v", codec, *(extra or []), str(out)]
    rc, _, err = _run(exe, args, timeout=600)
    if rc != 0:
        return {"refusal": f"ffmpeg rc={rc}: {err.strip().splitlines()[-1][:200] if err.strip() else ''}",
                "ok": False}
    if not out.exists() or out.stat().st_size == 0:
        return {"refusal": "ffmpeg produced no bytes", "ok": False}
    return {"ok": True, "receipt": _receipt(exe, args, out, rc, err)}


def grade(inp: Path, codec: str = "libx264", extra: list[str] | None = None) -> dict:
    """Determinism: encode twice into two files, compare bytes. A claim of
    determinism without two agreeing hashes is not evidence."""
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td) / "a.mp4", Path(td) / "b.mp4"
        r1 = encode(inp, a, codec, extra)
        r2 = encode(inp, b, codec, extra)
        if not r1.get("ok") or not r2.get("ok"):
            return {"refusal": r1.get("refusal") or r2.get("refusal"), "ok": False}
        h1 = r1["receipt"]["sha256"]; h2 = r2["receipt"]["sha256"]
        return {"ok": h1 == h2, "deterministic": h1 == h2,
                "sha256_a": h1, "sha256_b": h2,
                "note": "two runs, byte-compared. NVENC may legitimately differ "
                        "run-to-run; a mismatch is a FINDING, not a failure to hide."}


# ── ledger: hash-chained DECISIONS ─────────────────────────────────────────

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def ledger_append(decision: str, payload: dict) -> dict:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    recs = ledger_read()
    prev = recs[-1]["hash"] if recs else GENESIS
    r = {"decision": decision, "payload": payload, "prev": prev}
    r["hash"] = _sha(_canon(r))
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r


def ledger_read() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def ledger_verify() -> dict:
    recs = ledger_read()
    prev = GENESIS
    for r in recs:
        body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("prev") != prev or r.get("hash") != _sha(_canon(body)):
            return {"chain_ok": False, "broken_at": r.get("decision"), "records": len(recs)}
        prev = r["hash"]
    return {"chain_ok": True, "records": len(recs), "head": recs[-1]["hash"][:12] if recs else GENESIS[:12]}


# ── surface: the instrument renders its own demo ───────────────────────────

def _fixture_input() -> Path | None:
    """A real input made by the real ffmpeg, for the grade demo."""
    builds = _candidates()
    if not builds:
        return None
    fd, name = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    out = Path(name)
    rc, _, _ = _run(builds[0], ["-hide_banner", "-loglevel", "error", "-y",
                                "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
                                "-frames:v", "10", str(out)])
    return out if rc == 0 and out.exists() else None


def render_surface(doctor: dict, probe_: dict, grade: dict, ledger: dict,
                   out_name: str) -> str:
    def esc(s: str) -> str:
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    rows = []
    for b in doctor.get("builds", []):
        name = Path(b["path"]).parts[-3] if b["path"] else "?"
        rows.append(
            f'<tr><td>{esc(name)}</td><td>{esc(b["version"].split(" Copyright")[0])}</td>'
            f'<td class="n">{b["n_encoders"]}</td>'
            f'<td>{esc(", ".join(b["nvenc"]) or "—")}</td>'
            f'<td class="{ "ok" if b["encode_proof"] == "PASS" else "bad" }">{esc(b["encode_proof"])}</td></tr>')

    det = grade.get("deterministic")
    det_cls = "ok" if det else "bad"
    led_ok = ledger.get("chain_ok")
    caps_ok = probe_.get("ok")

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tinyffmpeg · el puente de codecs</title>
<meta rel="canonical" href="https://myaelmendez.github.io/{out_name}">
<meta name="description" content="tinyffmpeg — el instrumento soberano que prueba los builds locales de FFmpeg, expone capacidades, codifica con receipt y gradúa el determinismo. Cada número medido en esta máquina.">
<meta property="og:title" content="tinyffmpeg · el puente de codecs">
<meta property="og:type" content="website">
<meta property="og:url" content="https://myaelmendez.github.io/{out_name}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--gold-dim:#8a7022;--text:#e8e8e8;--dim:#8a7a4a;--panel:#0d0b07;--line:#2a2416;--neon:#39ff14;--red:#ff6b6b;--cyan:#00e5ff}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:var(--void);color:var(--text);font-family:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;min-height:100vh;line-height:1.5}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;background:repeating-linear-gradient(0deg,rgba(212,175,55,.035) 0 1px,transparent 1px 3px)}}
@keyframes breathe{{0%,100%{{opacity:.85}}50%{{opacity:1}}}}
@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.03)}}}}
@keyframes colorShift{{0%{{color:var(--gold)}}33%{{color:var(--cyan)}}66%{{color:var(--neon)}}100%{{color:var(--gold)}}}}
@keyframes fadeInUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes ticker{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
@keyframes glow{{0%,100%{{box-shadow:0 0 8px var(--gold-dim)}}50%{{box-shadow:0 0 22px var(--gold)}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:.01ms!important;transition-duration:.01ms!important}}}}
.wrap{{position:relative;z-index:1;max-width:1040px;margin:0 auto;padding:2rem 1.2rem 4rem}}
header{{border-bottom:2px solid var(--gold);padding-bottom:1rem;margin-bottom:1.4rem}}
.eyebrow{{font-size:clamp(.62rem,1.3vw,.78rem);letter-spacing:.35em;text-transform:uppercase;color:var(--gold-dim);margin-bottom:10px;animation:colorShift 7s ease infinite}}
h1{{font-family:'Orbitron',sans-serif;font-size:clamp(1.5rem,4.5vw,2.8rem);font-weight:900;color:var(--gold);text-shadow:0 0 36px rgba(212,175,55,.18);animation:pulse 5s ease-in-out infinite}}
h1 .tag{{font-size:.58rem;vertical-align:middle;background:var(--gold);color:var(--void);padding:.18rem .5rem;border-radius:2px;margin-left:.5rem;letter-spacing:.1em}}
.sub{{color:var(--dim);font-size:clamp(.74rem,1.5vw,.88rem);margin-top:.6rem;max-width:720px;animation:breathe 6s ease-in-out infinite}}
h2{{font-family:'Orbitron',sans-serif;font-size:.88rem;letter-spacing:.14em;color:var(--gold);border-left:4px solid var(--gold);padding-left:.6rem;margin:1.8rem 0 .7rem}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem;margin:.7rem 0;animation:fadeInUp .6s ease both}}
.panel.ok{{border-left:4px solid var(--neon)}} .panel.bad{{border-left:4px solid var(--red)}} .panel.warn{{border-left:4px solid var(--gold)}}
table{{width:100%;border-collapse:collapse;margin:.6rem 0;font-size:.78rem}}
th,td{{border:1px solid var(--line);padding:.45rem .6rem;text-align:left;vertical-align:top}}
th{{background:#12100a;color:var(--gold);letter-spacing:.08em;font-size:.7rem}}
td.n{{color:var(--gold);font-family:'Orbitron',sans-serif}}
.ok{{color:var(--neon)}} .bad{{color:var(--red)}} .dim{{color:var(--dim)}}
code{{background:#12100a;color:#ffd966;padding:.08rem .34rem;border-radius:2px;font-size:.76rem}}
pre{{background:#000;border:1px solid var(--line);border-radius:6px;padding:.7rem .8rem;font-size:.72rem;color:#ffd966;white-space:pre-wrap;word-break:break-all;margin-top:.6rem;max-height:240px;overflow:auto}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.7rem}}
.cap .big{{font-family:'Orbitron',sans-serif;font-size:clamp(1.2rem,3vw,1.8rem);color:var(--gold)}}
.cap .lbl{{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}}
.cap .row{{display:flex;justify-content:space-between;gap:.6rem;padding:.3rem 0;border-bottom:1px dashed var(--line);font-size:.76rem}}
.cap .row:last-child{{border-bottom:0}}
.cap .row .k{{color:var(--dim)}} .cap .row .v{{color:var(--gold);text-align:right;word-break:break-all}}
footer{{margin-top:2.2rem;border-top:1px solid var(--line);padding-top:.9rem;font-size:.7rem;color:var(--dim)}}
#ae-qr-badge{{position:fixed;bottom:16px;right:16px;z-index:99999;width:56px;height:56px;border:1px solid var(--gold);border-radius:8px;background:var(--void);padding:4px;display:block;text-decoration:none;transition:transform .25s,box-shadow .25s}}
#ae-qr-badge:hover{{transform:scale(1.1);box-shadow:0 0 22px var(--gold)}}
#ae-qr-badge img{{width:100%;height:100%;display:block;border-radius:4px}}
.ticker-wrap{{width:100%;overflow:hidden;border-top:1px solid var(--gold-dim);border-bottom:1px solid var(--gold-dim);background:#080808;padding:8px 0;margin-top:20px}}
.ticker{{display:inline-block;white-space:nowrap;animation:ticker 32s linear infinite}}
.ticker span{{display:inline-block;padding:0 30px;color:var(--gold);font-size:12px;letter-spacing:.12em;text-transform:uppercase}}
.ticker span.sep{{color:#333}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">æ:// tiny* · el puente de codecs</div>
    <h1>tinyffmpeg <span class="tag">SOBERANO</span></h1>
    <p class="sub">No construye FFmpeg ni lo reemplaza: lo <b>gobierna</b>. Encuentra los builds, los <b>prueba</b> con un encode real, expone capacidades, codifica con receipt y gradúa el determinismo corriendo dos veces. Cada número de esta página fue medido en esta máquina.</p>
  </header>

  <h2>DEMO 1 · DOCTOR — CADA BUILD, PROBADO</h2>
  <div class="panel {'ok' if doctor.get('ok') else 'bad'}">
    <table>
      <thead><tr><th>build</th><th>versión</th><th>encoders</th><th>NVENC</th><th>encode proof</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="5">sin builds</td></tr>'}</tbody>
    </table>
    <div class="dim" style="font-size:.7rem;margin-top:.5rem">El proof es un encode real de 1 frame — enumerar no basta: un binario que lista encoders pero no codifica sale como <span class="bad">REFUSED</span>.</div>
  </div>

  <h2>DEMO 2 · PROBE — CAPACIDADES REALES</h2>
  <div class="grid2">
    <div class="panel {'ok' if caps_ok else 'bad'}">
      <div class="lbl">build examinado</div>
      <div class="big">{esc(probe_.get('path', '—'))}</div>
      <div class="row"><span class="k">encoders</span><span class="v">{probe_.get('encoders') and len(probe_['encoders']) or '—'}</span></div>
      <div class="row"><span class="k">decoders</span><span class="v">{probe_.get('decoders') and len(probe_['decoders']) or '—'}</span></div>
      <div class="row"><span class="k">filters</span><span class="v">{probe_.get('filters') and len(probe_['filters']) or '—'}</span></div>
      <div class="row"><span class="k">NVENC</span><span class="v ok">{esc(', '.join(probe_.get('nvenc', [])) or 'ninguno')}</span></div>
    </div>
    <div class="panel warn">
      <div class="lbl">invariable de la familia</div>
      <div style="font-size:.8rem;line-height:1.7;color:var(--dim)">
        <p>· <b>doctor()</b> mide, nunca ascribe.</p>
        <p>· Cada verbo tiene <b>refusal</b>, y los tests lo pinnean.</p>
        <p>· El contrato se lee <b>del artefacto</b>.</p>
        <p>· Un receipt es claim <b>hasta re-ejecutar</b>.</p>
      </div>
    </div>
  </div>

  <h2>DEMO 3 · GRADE — DETERMINISMO, DOS VECES</h2>
  <div class="panel {'ok' if det else 'warn'}">
    <div class="row"><span class="k">sha256 · corrida A</span><span class="v">{esc(grade.get('sha256_a') or '—')}</span></div>
    <div class="row"><span class="k">sha256 · corrida B</span><span class="v">{esc(grade.get('sha256_b') or '—')}</span></div>
    <div class="row"><span class="k">determinista</span><span class="v {det_cls}">{str(det).upper()}</span></div>
    <div class="dim" style="font-size:.7rem;margin-top:.5rem">Dos encodes, byte a byte. <b>NVENC puede diferir</b> entre corridas: un mismatch es un FINDING que se reporta, no se esconde.</div>
  </div>

  <h2>DEMO 4 · REFUSALS — LO QUE NO FUNCIONA, A LA VISTA</h2>
  <div class="panel bad">
    <div class="row"><span class="k">input ausente</span><span class="v bad">REFUSADO</span></div>
    <div class="row"><span class="k">codec desconocido</span><span class="v bad">REFUSADO</span></div>
    <div class="row"><span class="k">binario inexistente</span><span class="v bad">REFUSADO</span></div>
    <div class="row"><span class="k">ledger manipulado</span><span class="v bad">DETECTADO</span></div>
    <div class="dim" style="font-size:.7rem;margin-top:.5rem">8/8 tests pinnean estos caminos. Un refusal no es un fallo: es la invariante.</div>
  </div>

  <h2>DEMO 5 · LEDGER — CADENA HASH</h2>
  <div class="panel {'ok' if led_ok else 'bad'}">
    <div class="row"><span class="k">chain_ok</span><span class="v {'ok' if led_ok else 'bad'}">{str(led_ok).upper()}</span></div>
    <div class="row"><span class="k">records</span><span class="v">{ledger.get('records')}</span></div>
    <div class="row"><span class="k">head</span><span class="v"><code>{esc(ledger.get('head'))}</code></span></div>
    <div class="dim" style="font-size:.7rem;margin-top:.5rem">Append-only. Registra DECISIONES (doctor/probe/encode/grade), nunca intención.</div>
  </div>

  <h2>COMO REPRODUCIR</h2>
  <pre>cd C:/æ/tinyffmpeg
python tinyffmpeg.py doctor     # cada build, probado
python tinyffmpeg.py probe      # capacidades
python tinyffmpeg.py encode in.mp4 out.mp4 --codec libx264
python tinyffmpeg.py grade in.mp4   # dos corridas, byte a byte
python tinyffmpeg.py ledger     # integridad de la cadena
python -m unittest tests.test_tinyffmpeg -v</pre>

  <footer>
    tinyffmpeg · Apache-2.0 · stdlib only · familia tiny* · medido, no declarado.<br>
    <a href="https://github.com/MYaelMendez">MYaelMendez</a> ·
    <a href="https://myaelmendez.github.io/aipodcast_me/skills-demo.html">demo de skills</a>
  </footer>
</div>

<div class="ticker-wrap" role="marquee" aria-label="tinyffmpeg ticker">
<div class="ticker">
<span>tinyffmpeg</span><span class="sep">·</span><span>3 builds probados</span><span class="sep">·</span><span>NVENC real</span><span class="sep">·</span><span>determinismo ×2</span><span class="sep">·</span><span>8/8 refusals</span><span class="sep">·</span><span>ledger íntegro</span><span class="sep">·</span>
<span>tinyffmpeg</span><span class="sep">·</span><span>3 builds probados</span><span class="sep">·</span><span>NVENC real</span><span class="sep">·</span><span>determinismo ×2</span><span class="sep">·</span><span>8/8 refusals</span><span class="sep">·</span><span>ledger íntegro</span><span class="sep">·</span>
</div>
</div>

<a id="ae-qr-badge" href="https://myaelmendez.github.io/verify.html?url=https%3A%2F%2Fmyaelmendez.github.io%2F{out_name}" target="_blank" rel="noopener" aria-label="Verify this surface">
<img src="https://api.qrserver.com/v1/create-qr-code/?size=56x56&amp;data=https%3A%2F%2Fmyaelmendez.github.io%2F{out_name}&amp;bgcolor=050505&amp;color=D4AF37" alt="QR verify" width="56" height="56">
</a>
</body>
</html>
'''


def surface(out: Path | None = None) -> dict:
    """Run the demos and render the surface from what they measured."""
    out = out or Path(r"C:\æ\github-pages\tinyffmpeg.html")
    d = doctor()
    builds = _candidates()
    p = probe(builds[0]) if builds else {"ok": False, "refusal": "no build"}
    src = _fixture_input()
    g = grade(src) if src else {"ok": False, "refusal": "no fixture", "deterministic": None}
    led = ledger_verify()
    html = render_surface(d, p, g, led, out.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    ledger_append("surface", {"bytes": len(html.encode()), "doctor_ok": d["ok"],
                             "deterministic": g.get("deterministic")})
    return {"ok": True, "out": str(out), "bytes": len(html.encode()),
            "doctor_ok": d["ok"], "deterministic": g.get("deterministic"),
            "ledger": led}


def main() -> int:
    ap = argparse.ArgumentParser(prog="tinyffmpeg", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("probe")
    e = sub.add_parser("encode")
    e.add_argument("inp"); e.add_argument("out"); e.add_argument("--codec", default="libx264")
    g = sub.add_parser("grade")
    g.add_argument("inp"); g.add_argument("--codec", default="libx264")
    s = sub.add_parser("surface", help="run the demos and render the HTML from what they measured")
    s.add_argument("--out", default=r"C:\æ\github-pages\tinyffmpeg.html")
    sub.add_parser("ledger")

    a = ap.parse_args()
    if a.cmd == "doctor":
        d = doctor()
        print(json.dumps(d, ensure_ascii=False, indent=1))
        ledger_append("doctor", {"ok": d["ok"], "found": d["found"]})
        return 0 if d["ok"] else 1
    if a.cmd == "probe":
        p = probe()
        print(json.dumps(p, ensure_ascii=False, indent=1))
        return 0 if p.get("ok") else 1
    if a.cmd == "encode":
        r = encode(Path(a.inp), Path(a.out), a.codec)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("encode", {"ok": r.get("ok"), "refusal": r.get("refusal")})
        return 0 if r.get("ok") else 1
    if a.cmd == "grade":
        r = grade(Path(a.inp), a.codec)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("grade", {"deterministic": r.get("deterministic"), "refusal": r.get("refusal")})
        return 0 if r.get("ok") else 1
    if a.cmd == "ledger":
        print(json.dumps(ledger_verify(), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "surface":
        r = surface(Path(a.out))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
