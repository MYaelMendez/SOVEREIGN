#!/usr/bin/env python3
"""tinyAUDIO — the sovereign instrument for the audio channel.

tinyAUDIO does NOT make sound. It GOVERNS the channel: it proves the local
codecs really encode, measures what goes in, what comes out and — the part
nobody does — **how much was lost**. AAC and MP3 are lossy; the instrument
declares the loss instead of pretending fidelity.

    doctor   prove the real encoders, read the studio WAV, grade determinism
    probe    duration, rate, channels, codec, bitrate, peak, RMS, clipping
    encode   transcode with a receipt (codec, bitrate, sha256)
    loss     SNR / sample difference between original and decoded — the number
             a lossy codec hides
    sync     the real offset between an audio and a video track
    grade    two encodes, byte-compared; LOSSY is honestly not deterministic

Invariants (tiny* family): doctor() measures; every verb refuses; the contract is
read from the artifact; a receipt is a claim until re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(r"C:\æ")
BINDIR = Path(r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin")
FFMPEG = BINDIR / "ffmpeg.exe"
FFPROBE = BINDIR / "ffprobe.exe"

STUDIO = ROOT / "agents" / "scratch_studio" / "v1-studio" / "track.wav"
LEDGER = Path(os.environ.get("TINYAUDIO_LEDGER", r"C:\æ\logs\tinyaudio.jsonl"))
GENESIS = "0" * 64

#: lossless codecs are reproducible; lossy ones are not, and tinyAUDIO says so
LOSSLESS = ("flac", "pcm_s16le", "wav")
LOSSY = ("aac", "libmp3lame", "libopus", "mp3")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


#: ffmpeg picks the muxer from the EXTENSION — a codec name is not a container
EXT = {"flac": ".flac", "aac": ".aac", "libmp3lame": ".mp3",
       "libopus": ".opus", "mp3": ".mp3", "pcm_s16le": ".wav", "wav": ".wav"}


def _run(args: list[str]) -> subprocess.CompletedProcess:
    if not FFMPEG.exists():
        raise RuntimeError(f"ffmpeg no encontrado: {FFMPEG}")
    return subprocess.run(args, capture_output=True, text=True, timeout=300,
                          errors="replace")


# ── probe ──────────────────────────────────────────────────────────────────

def probe(path: Path | str) -> dict:
    """Read the artifact with ffprobe. Never from the filename."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "refusal": f"no such file: {p}"}
    if not FFPROBE.exists():
        return {"ok": False, "refusal": f"ffprobe no encontrado: {FFPROBE}"}
    r = _run([str(FFPROBE), "-hide_banner", "-v", "quiet", "-print_format", "json",
              "-show_format", "-show_streams", str(p)])
    if r.returncode != 0:
        return {"ok": False, "refusal": f"ffprobe rc={r.returncode}: {r.stderr[:160]}"}
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "refusal": "ffprobe no devolvio JSON"}
    st = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    if st is None:
        return {"ok": False, "refusal": "sin pista de audio"}
    fmt = d.get("format", {})
    out = {"ok": True, "file": p.name, "codec": st.get("codec_name"),
           "sample_rate": int(st.get("sample_rate") or 0),
           "channels": int(st.get("channels") or 0),
           "duration_s": round(float(fmt.get("duration") or 0), 3),
           "format": fmt.get("format_name"), "bitrate": int(fmt.get("bit_rate") or 0),
           "bits_per_sample": st.get("bits_per_sample")}
    # levels: peak + RMS from ffmpeg's astats
    lv = _run([str(FFMPEG), "-hide_banner", "-i", str(p), "-af", "astats=metadata=1",
               "-f", "null", "-"])
    peak = rms = None
    for line in (lv.stderr or "").splitlines():
        if "Peak level dB" in line:
            try: peak = float(line.split(":")[-1].strip())
            except ValueError: pass
        if "RMS level dB" in line:
            try: rms = float(line.split(":")[-1].strip())
            except ValueError: pass
    out["peak_dB"] = peak
    out["rms_dB"] = rms
    out["clipping"] = bool(peak is not None and peak > 0.0)
    return out


def _wav_samples(path: Path) -> tuple[int, list[int]]:
    with wave.open(str(path), "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        vals = list(struct.unpack(f"<{len(raw)//2}h", raw))
    elif sw == 1:
        vals = [b - 128 for b in raw]
    else:
        return ch, []
    return ch, vals


# ── encode ─────────────────────────────────────────────────────────────────

def encode(src: Path | str, dst: Path | str, codec: str = "flac",
           bitrate: int | None = None) -> dict:
    """Transcode with a receipt. Reads the artifact, never the name."""
    s, d = Path(src), Path(dst)
    if not s.exists():
        return {"ok": False, "refusal": f"no such file: {s}"}
    if not d.suffix:
        d = d.with_suffix(EXT.get(codec, ".out"))
    args = [str(FFMPEG), "-hide_banner", "-y", "-i", str(s)]
    args += ["-c:a", codec]
    if bitrate:
        args += ["-b:a", f"{bitrate}k"]
    args += [str(d)]
    r = _run(args)
    if r.returncode != 0 or not d.exists():
        return {"ok": False, "refusal": f"encode rc={r.returncode}: {r.stderr[-200:]}"}
    sha = _sha(d.read_bytes())
    out = {"ok": True, "src": s.name, "dst": d.name, "codec": codec,
           "bitrate_k": bitrate, "bytes": d.stat().st_size, "sha256": sha}
    p = probe(d)
    if p.get("ok"):
        out.update({"duration_s": p["duration_s"], "sample_rate": p["sample_rate"],
                    "channels": p["channels"], "peak_dB": p["peak_dB"]})
    return out


# ── loss: the number a lossy codec hides ────────────────────────────────────

def loss(src: Path | str, dst: Path | str) -> dict:
    """SNR between the original and the decoded transcode. Lossless ~infinite."""
    s, d = Path(src), Path(dst)
    for f in (s, d):
        if not f.exists():
            return {"ok": False, "refusal": f"no such file: {f}"}
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a.wav"; b = Path(td) / "b.wav"
        for src_f, out in ((s, a), (d, b)):
            r = _run([str(FFMPEG), "-hide_banner", "-y", "-i", str(src_f),
                      "-c:a", "pcm_s16le", str(out)])
            if r.returncode != 0:
                return {"ok": False, "refusal": f"no se pudo decodificar {src_f.name}"}
        cha, sa = _wav_samples(a)
        chb, sb = _wav_samples(b)
        if not sa or not sb:
            return {"ok": False, "refusal": "muestras no legibles (PCM de 24/32 bits)"}
        n = min(len(sa), len(sb))
        if cha != chb:
            return {"ok": False, "refusal": f"canales distintos: {cha} vs {chb}"}
        # mix down to mono for the comparison
        def mono(v, ch):
            return [sum(v[i:i+ch]) / ch for i in range(0, len(v) - ch + 1, ch)] if ch > 1 else v
        ma, mb = mono(sa[:n], cha), mono(sb[:n], chb)
        n = min(len(ma), len(mb))
        sig = sum(x * x for x in ma[:n]) / max(n, 1)
        err = sum((ma[i] - mb[i]) ** 2 for i in range(n)) / max(n, 1)
        snr = 10 * math.log10(sig / err) if err > 0 else 999.0
        peak_diff = max(abs(ma[i] - mb[i]) for i in range(n)) if n else 0
    p = probe(d)
    return {"ok": True, "src": s.name, "dst": d.name, "codec": p.get("codec"),
            "snr_dB": round(snr, 2), "peak_sample_diff": peak_diff,
            "samples_compared": n,
            "lossless": snr > 90,
            "note": "lossless ~999 dB · lossy se mide y se declara"}


# ── sync ───────────────────────────────────────────────────────────────────

def sync(audio: Path | str, video: Path | str) -> dict:
    """The real offset between an audio and a video track."""
    a, v = Path(audio), Path(video)
    for f in (a, v):
        if not f.exists():
            return {"ok": False, "refusal": f"no such file: {f}"}
    pa, pv = probe(a), probe(v)
    if not pa.get("ok") or not pv.get("ok"):
        bad = "audio" if not pa.get("ok") else "video"
        return {"ok": False, "refusal": f"sin pista de audio en {bad}"}
    da, dv = pa["duration_s"], pv["duration_s"]
    return {"ok": True, "audio": a.name, "video": v.name,
            "audio_s": da, "video_s": dv,
            "delta_s": round(dv - da, 3),
            "verdict": "sincronizados" if abs(dv - da) < 0.05 else
                       ("el video es mas largo" if dv > da else "el audio es mas largo"),
            "note": "compara duraciones; el offset de muestra requiere correlacion"}


# ── grade ──────────────────────────────────────────────────────────────────

def grade(src: Path | str, codec: str = "flac", bitrate: int | None = None) -> dict:
    """Determinism, and the honest verdict: LOSSY is not reproducible."""
    s = Path(src)
    if not s.exists():
        return {"ok": False, "refusal": f"no such file: {s}"}
    with tempfile.TemporaryDirectory() as td:
        ext = EXT.get(codec, ".out")
        a = Path(td) / f"a{ext}"; b = Path(td) / f"b{ext}"
        ra = encode(s, a, codec, bitrate)
        rb = encode(s, b, codec, bitrate)
        if not (ra.get("ok") and rb.get("ok")):
            return {"ok": False, "refusal": ra.get("refusal") or rb.get("refusal")}
        ha, hb = ra["sha256"], rb["sha256"]
    lossy = codec in LOSSY
    det = ha == hb
    return {"ok": True, "deterministic": det, "sha256_a": ha, "sha256_b": hb,
            "codec": codec, "lossy": lossy,
            "verdict": (f"determinista en esta maquina ({'lossy' if lossy else 'lossless'})"
                        if det else "NO determinista"),
            "note": "medido, no asumido: un codec lossy puede ser reproducible en una "
                    "maquina y no en otra; tinyAUDIO lo dice, no lo supone"}


# ── doctor ─────────────────────────────────────────────────────────────────

def doctor() -> dict:
    out = {"ok": False, "checks": {}}
    if not FFMPEG.exists():
        out["checks"]["ffmpeg"] = f"REFUSED: {FFMPEG} no existe"
        return out
    out["checks"]["ffmpeg"] = str(FFMPEG)

    # 1. every claimed codec really encodes (1 s of silence → real file)
    enc = {}
    with tempfile.TemporaryDirectory() as td:
        for codec in ("flac", "aac", "libmp3lame", "libopus"):
            dst = Path(td) / f"{codec}{EXT[codec]}"
            r = _run([str(FFMPEG), "-hide_banner", "-y", "-f", "lavfi",
                      "-i", "anullsrc=r=24000:cl=mono", "-t", "0.2",
                      "-c:a", codec, str(dst)])
            enc[codec] = (r.returncode == 0 and dst.exists() and dst.stat().st_size > 0)
    missing = [c for c, ok in enc.items() if not ok]
    out["checks"]["codecs"] = ", ".join(f"{c}={'ok' if ok else 'NO'}" for c, ok in enc.items())
    if missing:
        out["checks"]["codecs"] += f" · REFUSED: sin {missing}"
        return out

    # 2. analysis stack
    try:
        import numpy  # noqa: F401
        out["checks"]["numpy"] = "ok"
    except Exception:
        out["checks"]["numpy"] = "ausente (el analisispectral seria con scipy)"
    import wave  # noqa: F401
    out["checks"]["wave"] = "ok"

    # 3. the studio artifact
    if STUDIO.exists():
        p = probe(STUDIO)
        if p.get("ok"):
            out["checks"]["studio"] = (f"{p['duration_s']}s · {p['sample_rate']}Hz · "
                                       f"{p['channels']}ch · {p['codec']} · "
                                       f"peak {p['peak_dB']} dB")
        else:
            out["checks"]["studio"] = f"REFUSED: {p.get('refusal')}"
    else:
        out["checks"]["studio"] = f"REFUSED: {STUDIO} no existe"

    # 4. determinism: lossless reproducible, lossy honestly not
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "t.wav"
        _run([str(FFMPEG), "-hide_banner", "-y", "-f", "lavfi",
              "-i", "sine=frequency=440:r=24000:duration=0.5", str(src)])
        g_flac = grade(src, "flac")
        g_aac = grade(src, "aac", 128)
    out["checks"]["grade_flac"] = g_flac.get("verdict")
    out["checks"]["grade_aac"] = g_aac.get("verdict")
    if not g_flac.get("deterministic"):
        out["checks"]["grade_flac"] = f"REFUSED: {g_flac.get('verdict')}"
        return out
    # lossy reproducibility is MEASURED, not assumed: the same encoder on the
    # same machine often is byte-identical, and tinyAUDIO reports what it saw.
    out["checks"]["grade_aac"] = g_aac.get("verdict")

    # 5. loss is measured, not assumed
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "s.wav"; mp3 = Path(td) / "s.mp3"
        _run([str(FFMPEG), "-hide_banner", "-y", "-f", "lavfi",
              "-i", "sine=frequency=440:r=24000:duration=0.5", str(src)])
        encode(src, mp3, "libmp3lame", 128)
        l = loss(src, mp3)
    out["checks"]["loss_mp3_128k"] = (f"{l['snr_dB']} dB SNR" if l.get("ok")
                                      else f"REFUSED: {l.get('refusal')}")
    if not l.get("ok"):
        return out

    out["ok"] = True
    out["note"] = "medido en esta maquina, no asumido"
    return out


# ── ledger ─────────────────────────────────────────────────────────────────

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
        if line.strip():
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
    return {"chain_ok": True, "records": len(recs),
            "head": recs[-1]["hash"][:12] if recs else GENESIS[:12]}


def main() -> int:
    ap = argparse.ArgumentParser(prog="tinyAUDIO", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    p = sub.add_parser("probe"); p.add_argument("path")
    e = sub.add_parser("encode"); e.add_argument("src"); e.add_argument("dst")
    e.add_argument("--codec", default="flac"); e.add_argument("--bitrate", type=int, default=None)
    l = sub.add_parser("loss"); l.add_argument("src"); l.add_argument("dst")
    s = sub.add_parser("sync"); s.add_argument("audio"); s.add_argument("video")
    g = sub.add_parser("grade"); g.add_argument("src"); g.add_argument("--codec", default="flac")
    g.add_argument("--bitrate", type=int, default=None)
    sub.add_parser("ledger")
    a = ap.parse_args()

    if a.cmd == "doctor":
        r = doctor(); print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("doctor", {"ok": r["ok"]}); return 0 if r["ok"] else 1
    if a.cmd == "probe":
        r = probe(a.path); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if a.cmd == "encode":
        r = encode(a.src, a.dst, a.codec, a.bitrate)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("encode", {"ok": r.get("ok"), "sha256": r.get("sha256")})
        return 0 if r.get("ok") else 1
    if a.cmd == "loss":
        r = loss(a.src, a.dst); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if a.cmd == "sync":
        r = sync(a.audio, a.video); print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
    if a.cmd == "grade":
        r = grade(a.src, a.codec, a.bitrate)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        ledger_append("grade", {"deterministic": r.get("deterministic")})
        return 0 if r.get("ok") else 1
    if a.cmd == "ledger":
        print(json.dumps(ledger_verify(), ensure_ascii=False, indent=1)); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
