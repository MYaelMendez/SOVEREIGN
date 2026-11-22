#!/usr/bin/env python3
"""tinyffmpeg.integrate — one import for any repo that encodes video.

Every repo in the fleet that produces an MP4 should bind its artifact the same
way: a real build, a real sha256, a readable container. This module is that
contract, so a repo wires it in one line instead of reimplementing it.

    from tinyffmpeg.integrate import gate
    verdict = gate(out_mp4)
    if not verdict["ok"]:
        raise SystemExit(verdict["refusal"])

It never builds FFmpeg and never replaces it. It refuses when it cannot prove.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

_MOD = Path(__file__).resolve().parent / "tinyffmpeg.py"
_FFPROBE = Path(r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin\ffprobe.exe")


def _load():
    spec = importlib.util.spec_from_file_location("tinyffmpeg", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def doctor() -> Dict[str, Any]:
    return _load().doctor()


def probe() -> Dict[str, Any]:
    return _load().probe()


def gate(out: Path | str, require_container: bool = True) -> Dict[str, Any]:
    """Prove an encoded artifact. Refuses when it cannot.

    Returns {ok, sha256, size_bytes, build, encode_proof, ...} on proof, or
    {ok: False, refusal, ...} when the build or the container cannot be measured.
    """
    tf = _load()
    out = Path(out)
    if not out.exists():
        return {"ok": False, "refusal": f"no output file: {out}"}
    d = tf.doctor()
    if not d.get("ok"):
        return {"ok": False, "refusal": "no usable ffmpeg build (doctor refused)",
                "doctor": d}
    b = d["builds"][0]
    blob = out.read_bytes()
    verdict: Dict[str, Any] = {
        "ok": True, "sha256": hashlib.sha256(blob).hexdigest(),
        "size_bytes": len(blob), "build": b["path"], "encode_proof": b["encode_proof"],
    }
    if require_container and _FFPROBE.exists():
        p = subprocess.run([str(_FFPROBE), "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,nb_frames,codec_name",
                            "-show_entries", "format=duration", "-of", "json", str(out)],
                           capture_output=True, text=True, timeout=60, errors="replace")
        try:
            j = json.loads(p.stdout)
            st = (j.get("streams") or [{}])[0]
            info = {"width": st.get("width"), "height": st.get("height"),
                    "frames": st.get("nb_frames"), "codec": st.get("codec_name"),
                    "duration": j.get("format", {}).get("duration")}
        except Exception:
            info = {}
        if not info.get("frames"):
            return {"ok": False, "refusal": "container not readable by ffprobe",
                    "build": b["path"], "sha256": verdict["sha256"]}
        verdict.update(info)
    return verdict


def grade(inp: Path | str, codec: str = "libx264") -> Dict[str, Any]:
    """Determinism: two encodes, byte-compared."""
    return _load().grade(Path(inp), codec)


if __name__ == "__main__":
    print(json.dumps(doctor(), ensure_ascii=False, indent=1))
    raise SystemExit(0 if doctor().get("ok") else 1)
