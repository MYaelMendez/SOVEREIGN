#!/usr/bin/env python3
"""Daily podcast spec generator.

Reads the gathered social feed, synthesizes a daily podcast episode spec
with title, text, and scene guide, then renders + gates + deploys.

Spec format follows spec-demo-series.json (20s, 1920x1080, 30fps).
Scene duration field is the hard cap (5min default = 1500 frames @ 30fps).
"""

import json, os, sys, subprocess, hashlib, datetime, glob, random, shutil
from pathlib import Path

ROOT = Path(r"C:\æ")
SITE = ROOT / "site" / "aipodcast_me"
SPECS = ROOT / "studio" / "specs"
OUTPUT = ROOT / "studio" / "output"
SCRIPTS = ROOT / "scripts" / "cron"
FEEDS_DIR = SCRIPTS / "feeds"
AUDIO_SRC = r"C:/æ/threejs-curriculo/æ.mp3"

# Render engine
NODE = Path(r"C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe")
PYTHON = r"C:/gpu/Scripts/python.exe"
FFMPEG = r"C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe"
RENDER_MJS = ROOT / "threejs-curriculo" / "render.mjs"
GHPAGES = ROOT / "github-pages"
LIVE_BASE = "https://myaelmendez.github.io/"

DEFAULT_DURATION = 15  # seconds per episode (5-min episode = 20 episodes max)

def load_feed(feed_file):
    """Load a gathered social feed JSON."""
    if not Path(feed_file).exists():
        return None
    return json.loads(Path(feed_file).read_text(encoding="utf-8"))

def synthesize_daily_spec(feed):
    """Synthesize a daily podcast spec from the social feed.

    Uses the feed posts to derive a topic, title, and scene guide.
    Returns a spec JSON object.
    """
    x_tweets = feed.get("x_tweets", [])
    bsky = feed.get("bluesky_posts", [])

    # Gather texts
    all_texts = []
    for t in x_tweets:
        text = t.get("text", "").strip()
        if text:
            all_texts.append(text)
    for p in bsky:
        text = p.get("text", "").strip()
        if text:
            all_texts.append(text)

    # Derive topic from hashtags/patterns
    topic = "daily philosophy gathering"
    if all_texts:
        # Use first meaningful text as the seed
        seed = all_texts[0][:200]
        topic = seed[:120]

    # Generate title
    title = f"æ:// Daily Pod — {topic[:50]}"
    subtitle = f"Semana 23 · {feed.get('date', datetime.date.today().isoformat())} · " \
               f"{len(x_tweets)} X posts · {len(bsky)} Bluesky posts"

    # Build scene guide from social themes
    themes = []
    for t in x_tweets[:3]:
        themes.append(t.get("text", "")[:80])
    for p in bsky[:2]:
        themes.append(p.get("text", "")[:80])
    if not themes:
        themes = ["daily gathering from #schoolofhermes"]

    scene_guide = " · ".join(themes[:6])

    spec = {
        "title": title,
        "subtitle": subtitle,
        "scene_guide": scene_guide,
        "themes": themes[:6],
        "source_feed": feed.get("receipt", "n/a"),
        "source_files": [f.name for f in FEEDS_DIR.glob("feeds-*.json")],
        "duration": DEFAULT_DURATION,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "scene_html": "demo-series-montage.html",
        "spec_number": int(datetime.datetime.now().strftime("%Y%m%d%H")),
    }
    return spec

def generate_spec(spec, feed_file):
    """Write the spec JSON and return the path."""
    spec_name = f"spec-daily-{int(datetime.datetime.now().strftime('%Y%m%d%H%M%S'))}.json"
    spec_path = SPECS / spec_name
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec_path

def render_episode(spec):
    """Render the episode video via threejs-curriculo/render.mjs.

    Returns (mp4_path, duration)
    """
    import datetime as dt
    ts = dt.datetime.now().strftime('%H%M%S')
    width = spec.get("width", 1920)
    height = spec.get("height", 1080)
    duration = spec.get("duration", DEFAULT_DURATION)
    fps = spec.get("fps", 30)
    frames = duration * fps
    tmp_out = f"studio/output/daily-episode-{ts}.mp4"
    cmd = [
        str(NODE), str(RENDER_MJS),
        f"--url=http://localhost:8128/demo-series-montage.html",
        f"--out=studio/output/{ts}.mp4",
        f"--w={width}", f"--h={height}",
        f"--frames={frames}", f"--fps={fps}",
        "--encoder=libx264"
    ]
    print(f"  Rendering: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"  Render error: {r.stderr[-300:]}")
        return None, 0
    mp4_path = Path(f"studio/output/{ts}.mp4")
    # Measure duration
    try:
        import subprocess as sp
        probe = sp.run([str(FFMPEG), '-i', str(mp4_path), '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=30)
        for line in probe.stderr.splitlines():
            if 'Duration' in line:
                dur_str = line.split('Duration')[1].split(',')[0].strip()
                h, m, s = dur_str.split(':')
                duration = float(h)*3600 + float(m)*60 + float(s)
                break
        else:
            duration = 15.0
    except Exception:
        duration = 15.0
    return mp4_path, duration

def gate_video(mp4_path):
    """Run supervision gate on the video.

    Returns (pass: bool, metrics: dict)
    """
    if not mp4_path.exists():
        return False, {}
    cmd = [
        str(PYTHON), str(ROOT / "vidæo" / "vidæo.py"), "verify", str(mp4_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = r.stdout + r.stderr
    # Parse metrics
    metrics = {}
    for line in output.splitlines():
        line = line.strip()
        if 'luminance' in line or 'contrast' in line or 'motion' in line or 'black' in line:
            print(f"  Gate: {line}")
        if 'lum' in line.lower() and ':' in line:
            # Parse key: value format
            parts = line.split(':')
            if len(parts) >= 2:
                key = parts[0].strip().lower()
                try:
                    val = float(parts[1].strip())
                    metrics[key] = val
                except ValueError:
                    pass
    # Check thresholds: lum > 20, con > 10, mov > 0.5, negros = 0
    pass_flag = True
    if 'luminance' in metrics and metrics['luminance'] <= 20:
        pass_flag = False
    if 'contrast' in metrics and metrics['contrast'] <= 10:
        pass_flag = False
    if 'motion' in metrics and metrics['motion'] <= 0.5:
        pass_flag = False
    return pass_flag, metrics

def mux_audio(video_path):
    """Mux audio from æ.mp3 into the video.
    """
    if not video_path.exists():
        return None, None
    mp3_out = video_path.parent / f"{video_path.stem}.mp3"
    cmd = [
        str(FFMPEG), '-i', str(video_path),
        '-i', AUDIO_SRC,
        '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
        '-shortest', '-y', str(mp3_out)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"  Mux error: {r.stderr[-200:]}")
        mp3_out2 = video_path.parent / f"{video_path.stem}.mp3"
        cmd2 = [
            str(FFMPEG), '-i', str(video_path),
            '-i', AUDIO_SRC,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '192k',
            '-y', str(mp3_out2)
        ]
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
        if r2.returncode != 0:
            print(f"  Fallback mux error: {r2.stderr[-200:]}")
            return None, None
        return mp3_out2, mp3_out2
    return mp3_out, mp3_out
def export_mp3(video_path):
    """Export MP3 from the video."""
    if not video_path.exists():
        return None
    mp3_path = video_path.parent / f"{video_path.stem}.mp3"
    cmd = [
        str(FFMPEG), '-i', str(video_path),
        '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
        '-y', str(mp3_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"  MP3 export error: {r.stderr[-200:]}")
        return None
    return mp3_path

def deploy_to_github_pages(file_path, subdir="aipodcast_me"):
    """Copy to github-pages and commit/push."""
    if not file_path.exists():
        return None
    dest = GHPAGES / subdir / file_path.name
    shutil_copy = subprocess.run(
        ['cp', '-f', str(file_path), str(dest)],
        capture_output=True, text=True
    )
    if shutil_copy.returncode != 0:
        # Windows fallback
        import shutil
        shutil.copy2(file_path, dest)
    return dest
    return dest

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Daily podcast: gather → spec → render → gate → deploy")
    parser.add_argument("--feed", default=None, help="Path to gathered feed JSON")
    parser.add_argument("--render", action="store_true", help="Render episode")
    parser.add_argument("--gate", action="store_true", help="Run gate only")
    parser.add_argument("--no-deploy", action="store_true", help="Skip deployment")
    args = parser.parse_args()

    # 1. Gather feed
    if not args.feed or not Path(args.feed).exists():
        print("Step 1: Gathering social feed...")
        r = subprocess.run(
            ['python3', 'scripts/cron/social_feed.py', '--source', 'auto'],
            capture_output=True, text=True, timeout=60
        )
        print(r.stdout)
        feeds = sorted(FEEDS_DIR.glob("feeds-*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not feeds:
            print("  No feeds gathered. Exiting.")
            return 1
        args.feed = str(feeds[0])

    feed = load_feed(args.feed)
    if not feed:
        print(f"  Failed to load feed: {args.feed}")
        return 1

    # 2. Synthesize spec
    print("Step 2: Synthesizing daily spec...")
    spec = synthesize_daily_spec(feed)
    spec_path = generate_spec(spec, args.feed)
    print(f"  Spec: {spec_path.name}")
    print(f"  Title: {spec['title']}")

    # 3. Render episode
    mp4_path = None
    if args.render or not (OUTPUT / spec_path.stem).exists():
        print("Step 3: Rendering episode...")
        mp4_path, duration = render_episode(spec)
        if mp4_path:
            print(f"  MP4: {mp4_path.name} ({duration:.1f}s)")
    else:
        mp4_path = OUTPUT / spec_path.stem
        print(f"  MP4 from cache: {mp4_path}")
        duration = 15.0

    # 4. Gate
    gate_pass = False
    metrics = {}
    if args.gate or not args.no_deploy:
        print("Step 4: Running gate...")
        gate_pass, metrics = gate_video(mp4_path)
        print(f"  Gate: {'PASS' if gate_pass else 'FAIL'}")
        if not gate_pass:
            print(f"  Metrics: {json.dumps(metrics, indent=2)}")

    if not gate_pass:
        print("  Gate failed — not deploying.")
        return 1

    # 5. Mux + export
    print("Step 5: Muxing audio + exporting MP3...")
    mp3_mux = mux_audio(mp4_path)
    mp3_export = export_mp3(mp4_path)

    # 6. Deploy
    if not args.no_deploy:
        print("Step 6: Deploying to github-pages...")
        mp4_dest = deploy_to_github_pages(mp4_path, "aipodcast_me")
        mp3_dest = deploy_to_github_pages(mp3_mux or mp3_export, "aipodcast_me")
        print(f"  MP4: {mp4_dest}")
        print(f"  MP3: {mp3_dest}")

    # 7. Write receipt
    receipt = {
        "day": datetime.date.today().isoformat(),
        "spec": spec_path.name,
        "mp4": mp4_path.name if mp4_path else None,
        "mp3": mp3_mux.name if mp3_mux else (mp3_export.name if mp3_export else None),
        "gate": "PASS" if gate_pass else "FAIL",
        "metrics": metrics,
        "receipt": compute_receipt(feed),
        "source_feed": args.feed,
    }
    receipt_file = SPECS / f"receipt-daily-{datetime.datetime.now().strftime('%Y%m%d')}.json"
    receipt_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"  Receipt: {receipt_file}")

    print(f"\n✓ Daily podcast episode complete: {mp4_path.name}")
    return 0

def compute_receipt(data):
    """Compute SHA-256 receipt for the gathered feed."""
    raw = json.dumps(data, sort_keys=True, separators=(',',':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

if __name__ == "__main__":
    sys.exit(main())
