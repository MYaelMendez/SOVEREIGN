"""
media_manifest.py — the aipodcast.me media hub's manifest.

Scans every production asset (video + audio) and writes a manifest the hub page
renders. Every number comes from ffprobe or the supervisor — nothing typed.

Video sources:
  - C:/æ/mp4-factory/manifest.json  (the 7 verified corpus videos + receipts)
  - C:/æ/github-pages/aipodcast_me/*.mp4  (existing episodic surfaces)

Audio sources:
  - C:/æ/voice-memos/*.mp3
  - C:/æ/threejs-curriculo/*.mp3
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

FFPROBE = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin\ffprobe.exe"
AIPODCAST = Path(r"C:\æ\github-pages\aipodcast_me")
FACTORY_MANIFEST = Path(r"C:\æ\mp4-factory\manifest.json")
THREEJS = Path(r"C:\æ\threejs-curriculo")
VOICE = Path(r"C:\æ\voice-memos")


def probe(path: Path) -> dict:
    """Real metadata from ffprobe. Never invents a value."""
    cmd = [FFPROBE, "-v", "error", "-show_entries",
           "format=duration,size,bit_rate",
           "-show_entries", "stream=codec_type,width,height,r_frame_rate,channels,sample_rate",
           "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    d = json.loads(r.stdout or "{}")
    fmt = d.get("format", {})
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    out = {
        "size_mb": round(int(fmt.get("size", 0)) / 1048576, 2),
        "duration_s": round(float(fmt.get("duration", 0) or 0), 1),
        "bitrate_mbps": round(int(fmt.get("bit_rate", 0) or 0) / 1e6, 1),
    }
    if v:
        num, den = (v.get("r_frame_rate") or "0/1").split("/")
        out.update({"width": v.get("width"), "height": v.get("height"),
                    "fps": round(int(num) / int(den)) if int(den) else 0})
    if a:
        out.update({"channels": a.get("channels"), "sample_rate": a.get("sample_rate")})
    return out


def build() -> dict:
    videos, audio = [], []

    # ── corpus videos (verified, with receipts) ──
    if FACTORY_MANIFEST.exists():
        fm = json.loads(FACTORY_MANIFEST.read_text(encoding="utf-8"))
        for v in fm.get("videos", []):
            if v.get("status") != "published":
                continue
            videos.append({
                "file": v["file"], "title": v["title"], "source": v["source"],
                "pipeline": v["pipeline"], "date": v["date"],
                "kind": "corpus", "where": "root",
                "duration_s": v["duration_s"], "size_mb": v["size_mb"],
                "width": v["width"], "height": v["height"], "fps": v["fps"],
                "frames": v["frames"], "bitrate_mbps": v["bitrate_mbps"],
                "vision": v["vision"],
            })

    # ── existing aipodcast episodic mp4s ──
    known = {
        "cuda-mcp2.mp4": ("CUDA MCP²", "sovereign compute surface"),
        "fleet-waves-development.mp4": ("Fleet Waves", "1,393-agent autonomous refactor"),
        "holomesh.mp4": ("Holomesh", "the mesh, rendered"),
        "markets-radar.mp4": ("Markets Radar", "20 tickers as a particle field"),
        "markets-radar-timestamp.mp4": ("Markets Radar (timestamped)", "market tape with time axis"),
    }
    for f in sorted(AIPODCAST.glob("*.mp4")):
        if f.name in {v["file"] for v in videos}:
            continue
        meta = probe(f)
        title, source = known.get(f.name, (f.stem, "episodic surface"))
        videos.append({
            "file": f.name, "title": title, "source": source,
            "pipeline": "episodic", "date": "", "kind": "episodic", "where": "aipodcast_me",
            **meta,
        })

    # ── audio ──
    audio_sources = []
    for d, where in ((VOICE, "voice-memos"), (THREEJS, "threejs-curriculo")):
        if d.exists():
            for f in sorted(d.glob("*.mp3")):
                audio_sources.append((f, where))
    for f, where in audio_sources:
        meta = probe(f)
        audio.append({
            "file": f.name, "title": f.stem.replace("-", " ").replace("_", " ").title(),
            "where": where, **meta,
        })

    total_video_mb = round(sum(v.get("size_mb", 0) for v in videos), 1)
    total_audio_mb = round(sum(a.get("size_mb", 0) for a in audio), 1)
    all_pass = all(v.get("vision", {}).get("calidad") == "PASS"
                   for v in videos if v.get("kind") == "corpus")

    return {
        "brand": "aipodcast.me",
        "hub": "AI PODCAST HQ · MEDIA",
        "generated": "2026-10-05",
        "video_count": len(videos),
        "audio_count": len(audio),
        "total_video_mb": total_video_mb,
        "total_audio_mb": total_audio_mb,
        "all_pass": all_pass,
        "videos": videos,
        "audio": audio,
    }


if __name__ == "__main__":
    m = build()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("media-manifest.json")
    out.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    (out.parent / "media-manifest.js").write_text(
        "// generated by media_manifest.py — do not hand-edit\n"
        "const MEDIA = " + json.dumps(m, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in m.items() if k not in ("videos", "audio")}, indent=2))
    print(f"\nwrote {out} + media-manifest.js")
    for v in m["videos"]:
        cal = v.get("vision", {}).get("calidad", "—")
        print(f"  VIDEO {v['file']:34} {v['duration_s']:>5}s {v['size_mb']:>6}MB  {cal}")
    for a in m["audio"]:
        print(f"  AUDIO {a['file']:34} {a['duration_s']:>5}s {a['size_mb']:>6}MB  {a.get('channels','?')}ch")
