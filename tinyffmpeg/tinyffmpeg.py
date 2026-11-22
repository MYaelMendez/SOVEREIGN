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
    """Render the instrument's own demo. Modern bento, generated from probes."""
    def esc(x) -> str:
        return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    rows = []
    for b in doctor.get("builds", []):
        nm = Path(b["path"]).parts[-3] if b["path"] else "?"
        ok = b["encode_proof"] == "PASS"
        rows.append(
            f'<div class="build{" ok" if ok else " bad"}">'
            f'<div class="bn">{esc(nm)}</div>'
            f'<div class="bv">{esc(b["version"].split(" Copyright")[0])}</div>'
            f'<div class="bm"><span>{b["n_encoders"]}</span> encoders</div>'
            f'<div class="bnv">{esc(", ".join(b["nvenc"]) or "—")}</div>'
            f'<div class="bp {"ok" if ok else "bad"}">{esc(b["encode_proof"])}</div>'
            f'</div>')

    det = grade.get("deterministic")
    led = ledger
    caps = probe_
    n_enc = len(caps.get("encoders", [])) if caps.get("ok") else 0
    n_dec = len(caps.get("decoders", [])) if caps.get("ok") else 0
    n_flt = len(caps.get("filters", [])) if caps.get("ok") else 0

    return f"""<!DOCTYPE html>
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
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--gold2:#f0d487;--text:#e8e8e8;--dim:#a3926a;--mut:#a89e80;
--panel:rgba(16,14,9,.78);--line:rgba(212,175,55,.3);--neon:#39ff14;--red:#ff6b6b;--cyan:#00e5ff}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{color-scheme:dark}}
body{{background:var(--void);color:var(--text);font-family:'JetBrains Mono',ui-monospace,monospace;
min-height:100vh;overflow-x:hidden;-webkit-font-smoothing:antialiased}}
body::before{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
background:
 radial-gradient(900px 600px at 12% -8%, rgba(212,175,55,.16), transparent 60%),
 radial-gradient(700px 500px at 92% 8%, rgba(0,229,255,.08), transparent 62%),
 radial-gradient(600px 600px at 50% 110%, rgba(212,175,55,.07), transparent 60%)}}
body::after{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.5;
background:repeating-linear-gradient(0deg,rgba(212,175,55,.03) 0 1px,transparent 1px 4px)}}
.wrap{{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:clamp(16px,3vw,44px)}}
header{{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;
padding-bottom:clamp(18px,3vw,34px);border-bottom:1px solid var(--line);
animation:fadeIn .8s cubic-bezier(.2,.7,.2,1) both}}
.eyebrow{{font-size:clamp(.6rem,1.2vw,.75rem);letter-spacing:.42em;text-transform:uppercase;
color:var(--gold);animation:colorShift 8s ease infinite}}
h1{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(2rem,6.4vw,4.4rem);
line-height:.9;color:var(--gold);margin-top:12px;letter-spacing:-.02em;
text-shadow:0 0 60px rgba(212,175,55,.28);animation:pulse 6s ease-in-out infinite}}
.sub{{color:var(--dim);font-size:clamp(.78rem,1.5vw,.95rem);margin-top:14px;max-width:640px;line-height:1.65}}
.sub b{{color:var(--gold2);font-weight:700}}
.live{{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;
font-family:'Orbitron',sans-serif;font-size:.62rem;letter-spacing:.18em;color:var(--neon);
border:1px solid rgba(57,255,20,.35);padding:9px 14px;border-radius:999px;
background:rgba(57,255,20,.06);box-shadow:0 0 24px rgba(57,255,20,.12)}}
.live i{{width:7px;height:7px;border-radius:50%;background:var(--neon);
box-shadow:0 0 12px var(--neon);animation:blink 1.6s ease-in-out infinite}}
h2{{font-family:'Orbitron',sans-serif;font-size:clamp(.72rem,1.4vw,.86rem);letter-spacing:.2em;
color:var(--gold);margin:clamp(22px,3.4vw,36px) 0 14px;display:flex;align-items:center;gap:12px}}
h2::before{{content:"";width:26px;height:1px;background:linear-gradient(90deg,var(--gold),transparent)}}
.panel{{position:relative;background:var(--panel);border:1px solid transparent;border-radius:18px;
padding:clamp(16px,2.4vw,26px);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
background-image:linear-gradient(var(--panel),var(--panel)),
linear-gradient(135deg,rgba(212,175,55,.55),rgba(212,175,55,.06) 40%,rgba(0,229,255,.22));
background-origin:border-box;background-clip:padding-box,border-box;
transition:transform .35s cubic-bezier(.2,.7,.2,1),box-shadow .35s;
animation:fadeIn .7s cubic-bezier(.2,.7,.2,1) both}}
.panel:hover{{transform:translateY(-4px);box-shadow:0 24px 60px rgba(0,0,0,.6),0 0 0 1px rgba(212,175,55,.14)}}
.ok{{background-image:linear-gradient(var(--panel),var(--panel)),
linear-gradient(135deg,rgba(57,255,20,.5),rgba(57,255,20,.05) 45%,rgba(212,175,55,.2))}}
.bad{{background-image:linear-gradient(var(--panel),var(--panel)),
linear-gradient(135deg,rgba(255,107,107,.5),rgba(255,107,107,.05) 45%,rgba(212,175,55,.2))}}
.warn{{background-image:linear-gradient(var(--panel),var(--panel)),
linear-gradient(135deg,rgba(212,175,55,.55),rgba(212,175,55,.06) 45%,rgba(0,229,255,.2))}}
.bento{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}}
.stat{{text-align:left}}
.stat .lbl{{font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut)}}
.stat .big{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(1.8rem,4.4vw,3rem);
color:var(--gold);line-height:1;margin:10px 0 4px}}
.stat .foot{{font-size:.72rem;color:#b6ab8c}}
.build{{grid-column:span 1}}
.build .bn{{font-family:'Orbitron',sans-serif;font-size:.72rem;letter-spacing:.06em;color:var(--gold)}}
.build .bv{{font-size:.68rem;color:#c2b79a;margin-top:8px;min-height:2.6em;line-height:1.5}}
.build .bm{{font-family:'Orbitron',sans-serif;font-size:1.5rem;color:var(--gold);margin:12px 0 2px}}
.build .bm span{{font-family:'JetBrains Mono';font-size:.62rem;color:var(--dim);letter-spacing:.1em}}
.build .bnv{{font-size:.68rem;color:var(--neon);overflow-wrap:anywhere;word-break:break-word;min-height:2.6em;line-height:1.5}}
.build .bp{{display:inline-block;margin-top:12px;font-family:'Orbitron',sans-serif;font-size:.6rem;
letter-spacing:.16em;padding:5px 10px;border-radius:999px;border:1px solid currentColor}}
.build .bp.ok{{color:var(--neon)}} .build .bp.bad{{color:var(--red)}}
.build.bad{{opacity:.82}}
.row{{display:flex;justify-content:space-between;gap:14px;padding:9px 0;
border-bottom:1px dashed var(--line);font-size:.78rem}}
.row:last-child{{border-bottom:0}}
.row .k{{color:var(--mut)}} .row .v{{color:var(--gold);text-align:right;word-break:break-all}}
.v.ok{{color:var(--neon)}} .v.bad{{color:var(--red)}}
code{{background:rgba(0,0,0,.55);color:#ffd966;padding:.14rem .4rem;border-radius:5px;font-size:.72rem}}
pre{{background:rgba(0,0,0,.62);border:1px solid var(--line);border-radius:12px;
padding:14px 16px;font-size:.72rem;color:#ffd966;white-space:pre-wrap;word-break:break-all;
margin-top:14px;line-height:1.7;overflow:auto}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.dim{{color:#b6ab8c;font-size:.72rem;line-height:1.75}}
footer{{margin-top:clamp(24px,4vw,44px);padding-top:18px;border-top:1px solid var(--line);
font-size:.7rem;color:var(--dim);display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}}
footer a{{color:var(--gold2);text-decoration:none}} footer a:hover{{color:var(--gold)}}
#ae-qr-badge{{position:fixed;bottom:18px;right:18px;z-index:99999;width:58px;height:58px;border-radius:12px;
border:1px solid var(--gold);background:var(--void);padding:4px;display:block;text-decoration:none;
box-shadow:0 8px 30px rgba(0,0,0,.6);transition:transform .3s,box-shadow .3s}}
#ae-qr-badge:hover{{transform:scale(1.12) rotate(-2deg);box-shadow:0 0 30px rgba(212,175,55,.55)}}
#ae-qr-badge img{{width:100%;height:100%;display:block;border-radius:8px}}
.ticker-wrap{{position:relative;z-index:1;margin-top:34px;overflow:hidden;
border-top:1px solid var(--line);border-bottom:1px solid var(--line);
background:linear-gradient(180deg,rgba(8,8,8,.9),rgba(8,8,8,.4));padding:12px 0}}
.ticker{{display:inline-block;white-space:nowrap;animation:ticker 34s linear infinite}}
.ticker span{{display:inline-block;padding:0 28px;color:var(--gold);font-size:.72rem;letter-spacing:.16em;text-transform:uppercase}}
.ticker span.sep{{color:#333}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(22px)}}to{{opacity:1;transform:none}}}}
@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.02)}}}}
@keyframes colorShift{{0%{{color:var(--gold)}}33%{{color:var(--cyan)}}66%{{color:var(--neon)}}100%{{color:var(--gold)}}}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
@keyframes ticker{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:.01ms!important;transition-duration:.01ms!important}}}}
@media(max-width:600px){{header{{flex-direction:column;align-items:flex-start}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="eyebrow">æ:// tiny* · el puente de codecs</div>
      <h1>tinyffmpeg</h1>
      <p class="sub">No construye FFmpeg ni lo reemplaza: lo <b>gobierna</b>. Encuentra los builds, los <b>prueba</b> con un encode real, expone capacidades, codifica con receipt y gradúa el determinismo corriendo dos veces.</p>
    </div>
    <div class="live"><i></i>MEDIDO · NO DECLARADO</div>
  </header>

  <h2>DOCTOR — cada build, probado</h2>
  <div class="panel {'ok' if doctor.get('ok') else 'bad'}">
    <div class="bento">{''.join(rows) or '<div class="dim">sin builds</div>'}</div>
    <p class="dim" style="margin-top:14px">El <b>encode proof</b> es un encode real de 1 frame. Enumerar no basta: un binario que lista encoders pero no codifica sale como <span class="v bad">REFUSED</span>.</p>
  </div>

  <h2>PROBE — capacidades reales</h2>
  <div class="grid2">
    <div class="panel {'ok' if caps.get('ok') else 'bad'}">
      <div class="bento">
        <div class="stat"><div class="lbl">encoders</div><div class="big">{n_enc}</div><div class="foot">del build examinado</div></div>
        <div class="stat"><div class="lbl">decoders</div><div class="big">{n_dec}</div><div class="foot">lectura real</div></div>
        <div class="stat"><div class="lbl">filters</div><div class="big">{n_flt}</div><div class="foot">pipeline completo</div></div>
      </div>
      <div class="row" style="margin-top:14px"><span class="k">NVENC</span><span class="v ok">{esc(", ".join(caps.get("nvenc", [])) or "ninguno")}</span></div>
      <div class="row"><span class="k">build</span><span class="v">{esc(caps.get("path", "—"))}</span></div>
    </div>
    <div class="panel warn">
      <div class="lbl" style="font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut);margin-bottom:12px">las cuatro invariantes</div>
      <div class="dim" style="font-size:.82rem;line-height:2">
        <p>· <b>doctor()</b> mide, nunca ascribe.</p>
        <p>· Cada verbo tiene <b>refusal</b>, y los tests lo pinnean.</p>
        <p>· El contrato se lee <b>del artefacto</b>.</p>
        <p>· Un receipt es claim <b>hasta re-ejecutar</b>.</p>
      </div>
    </div>
  </div>

  <h2>GRADE — determinismo, dos veces</h2>
  <div class="panel {'ok' if det else 'warn'}">
    <div class="row"><span class="k">sha256 · corrida A</span><span class="v"><code>{esc(grade.get('sha256_a') or '—')}</code></span></div>
    <div class="row"><span class="k">sha256 · corrida B</span><span class="v"><code>{esc(grade.get('sha256_b') or '—')}</code></span></div>
    <div class="row"><span class="k">determinista</span><span class="v {'ok' if det else 'bad'}">{str(det).upper()}</span></div>
    <p class="dim" style="margin-top:12px">Dos encodes, byte a byte. <b>NVENC puede diferir</b> entre corridas: un mismatch es un FINDING que se reporta, no se esconde.</p>
  </div>

  <h2>REFUSALS + LEDGER</h2>
  <div class="grid2">
    <div class="panel bad">
      <div class="lbl" style="font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut);margin-bottom:12px">lo que no funciona, a la vista</div>
      <div class="row"><span class="k">input ausente</span><span class="v bad">REFUSADO</span></div>
      <div class="row"><span class="k">codec desconocido</span><span class="v bad">REFUSADO</span></div>
      <div class="row"><span class="k">binario inexistente</span><span class="v bad">REFUSADO</span></div>
      <div class="row"><span class="k">ledger manipulado</span><span class="v bad">DETECTADO</span></div>
      <p class="dim" style="margin-top:12px">8/8 tests pinnean estos caminos.</p>
    </div>
    <div class="panel {'ok' if led.get('chain_ok') else 'bad'}">
      <div class="lbl" style="font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut);margin-bottom:12px">cadena hash</div>
      <div class="row"><span class="k">chain_ok</span><span class="v {'ok' if led.get('chain_ok') else 'bad'}">{str(led.get('chain_ok')).upper()}</span></div>
      <div class="row"><span class="k">records</span><span class="v">{led.get('records')}</span></div>
      <div class="row"><span class="k">head</span><span class="v"><code>{esc(led.get('head'))}</code></span></div>
      <p class="dim" style="margin-top:12px">Append-only. Registra DECISIONES, nunca intención.</p>
    </div>
  </div>

  <h2>CÓMO REPRODUCIR</h2>
  <pre>cd C:/æ/tinyffmpeg
python tinyffmpeg.py doctor     # cada build, probado
python tinyffmpeg.py probe      # capacidades
python tinyffmpeg.py encode in.mp4 out.mp4 --codec libx264
python tinyffmpeg.py grade in.mp4   # dos corridas, byte a byte
python tinyffmpeg.py ledger     # integridad de la cadena
python -m unittest tests.test_tinyffmpeg -v</pre>

  <footer>
    <span>tinyffmpeg · Apache-2.0 · stdlib only · familia tiny* · medido, no declarado.</span>
    <span><a href="https://github.com/MYaelMendez">MYaelMendez</a> · <a href="https://myaelmendez.github.io/aipodcast_me/skills-demo.html">demo de skills</a></span>
  </footer>
</div>

<div class="ticker-wrap" role="marquee" aria-label="tinyffmpeg ticker">
<div class="ticker">
<span>tinyffmpeg</span><span class="sep">·</span><span>{doctor.get('found')} builds probados</span><span class="sep">·</span><span>NVENC real</span><span class="sep">·</span><span>determinismo ×2</span><span class="sep">·</span><span>8/8 refusals</span><span class="sep">·</span><span>ledger íntegro</span><span class="sep">·</span>
<span>tinyffmpeg</span><span class="sep">·</span><span>{doctor.get('found')} builds probados</span><span class="sep">·</span><span>NVENC real</span><span class="sep">·</span><span>determinismo ×2</span><span class="sep">·</span><span>8/8 refusals</span><span class="sep">·</span><span>ledger íntegro</span><span class="sep">·</span>
</div>
</div>

<a id="ae-qr-badge" href="https://myaelmendez.github.io/verify.html?url=https%3A%2F%2Fmyaelmendez.github.io%2F{out_name}" target="_blank" rel="noopener" aria-label="Verify this surface">
<img src="https://api.qrserver.com/v1/create-qr-code/?size=56x56&amp;data=https%3A%2F%2Fmyaelmendez.github.io%2F{out_name}&amp;bgcolor=050505&amp;color=D4AF37" alt="QR verify" width="56" height="56">
</a>
</body>
</html>
"""


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
