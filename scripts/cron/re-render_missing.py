#!/usr/bin/env python3
"""
re-render_missing.py — Auto-complete threejs curriculum (W4-W12).
Checks which weeks lack MP4 outputs or gate PASS, re-renders them via
vidaeo-producer, runs the supervision gate, and deploys to github-pages.

Usage:
  python re-render_missing.py --once   # one pass, exit
  python re-render_missing.py --check-only  # no render, just report
  python re-render_missing.py --sync-scenes [--check-only]  # sync newer scene HTML to github-pages
"""
import argparse, json, os, shutil, subprocess, sys, time, socket, urllib.request
from pathlib import Path

ROOT = Path(r"C:\æ")
SITE = ROOT / "site" / "aipodcast_me"
SPECS = ROOT / "studio" / "specs"
OUTPUT = ROOT / "studio" / "output"
GHPAGES = ROOT / "github-pages"
NODE = Path(r"C:\Users\yaelm\AppData\Local\hermes\tools\node-26.7.0-win32-x64\node.exe")
PYTHON = r"C:\gpu\Scripts\python.exe"
VIDÆO = str(ROOT / "vidæo" / "vidæo.py")
PRODUCER_DIR = ROOT / "store" / "mp4-factory-app"
LIVE_BASE = "https://myaelmendez.github.io/"

WEEKS = {
    4:  ("spec-fase4.json",  "fase4-shaders.html",        "fase4-shaders.mp4",        "Semana 04 — Shader Foundations"),
    5:  ("spec-fase5.json",  "fase5-shaders.html",        "fase5-shaders.mp4",        "Semana 05 — Intermediate Shaders"),
    6:  ("spec-fase6.json",  "fase6-shaders.html",        "fase6-shaders.mp4",        "Semana 06 — Advanced Shaders"),
    7:  ("spec-fase7.json",  "fase7-performance.html",    "fase7-performance.mp4",    "Semana 07 — Massive Scalability"),
    8:  ("spec-fase8.json",  "fase8-architecture.html",   "fase8-architecture.mp4",   "Semana 08 — Complex Scene Architecture"),
    9:  ("spec-fase9.json",  "fase9-webworkers.html",     "fase9-webworkers.mp4",     "Semana 09 — Web Workers + Async"),
    10: ("spec-fase10.json", "fase10-postprocessing.html","fase10-postprocessing.mp4","Semana 10 — Post-Processing"),
    11: ("spec-fase11.json", "fase11-effects.html",       "fase11-effects.mp4",       "Semana 11 — Advanced Effects"),
    12: ("spec-fase12.json", "fase12-integration.html",  "fase12-integration.mp4",  "Semana 12 — WebMCP + Agent Loop"),
}

def kill_port(port=8123):
    """Kill any LISTENING process on the given port."""
    for _ in range(3):
        r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        pids = set()
        for line in r.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line:
                pid = line.split()[-1]
                if pid.isdigit() and pid != '0':
                    pids.add(pid)
        if not pids:
            break
        for pid in pids:
            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
        time.sleep(2)
    s = socket.socket()
    s.settimeout(2)
    r2 = s.connect_ex(('127.0.0.1', port))
    s.close()
    return r2 != 0  # True = FREE

def render_week(week, spec, scene_html, mp4_name):
    """Render a week. Returns (success: bool, output_text: str)."""
    spec_path = SPECS / spec
    scene = SITE / scene_html
    out = OUTPUT / mp4_name

    if not spec_path.exists():
        return False, f"spec missing: {spec_path}"
    if not scene.exists():
        return False, f"scene missing: {scene}"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    kill_port(8123)
    time.sleep(1)

    cmd = (
        f'cmd /c "cd /d {PRODUCER_DIR} && '
        f'{NODE} vidaeo-producer.js {spec_path} {out}"'
    )
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, shell=True)
    log = r.stdout + r.stderr

    if not out.exists() or out.stat().st_size < 1000:
        return False, f"no output (size {out.stat().st_size if out.exists() else 0})"

    return True, f"{out.stat().st_size // 1024} KB"

def gate_week(mp4_name):
    """Run supervision gate. Returns (passed: bool, metrics: dict)."""
    out = OUTPUT / mp4_name
    cmd = f'{PYTHON} {VIDÆO} verify {out}'
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=True)
    text = r.stdout + r.stderr

    # Parse JSON receipt from output
    try:
        start = text.index('{')
        data = json.loads(text[start:])
        passed = data.get('calidad', '').upper() == 'PASS'
        return passed, data
    except (ValueError, json.JSONDecodeError):
        return False, {'raw': text[-500:]}

def deploy_week(scene_html, mp4_name, week_label):
    """Copy + commit + push to github-pages. Returns (success, msg)."""
    scene = SITE / scene_html
    mp4 = OUTPUT / mp4_name

    for f in [scene, mp4]:
        shutil.copy2(f, GHPAGES / f.name)

    os.chdir(GHPAGES)
    subprocess.run(['git', 'add', str(mp4.name), str(scene.name)], capture_output=True)
    msg = f'video: {mp4_name} — {week_label} (gate PASS)'
    subprocess.run(['git', 'commit', '-m', msg], capture_output=True)

    # pull --rebase + push (handle non-fast-forward)
    subprocess.run(['git', 'pull', '--rebase', 'origin', 'gh-pages'],
                   capture_output=True, timeout=60)
    r = subprocess.run(['git', 'push', 'origin', 'gh-pages'],
                       capture_output=True, text=True, timeout=60)
    ok = 'gh-pages -> gh-pages' in r.stdout or 'Everything up-to-date' in r.stdout
    return ok, r.stdout[-300:] + r.stderr[-300:]

def sync_scenes(check_only=False):
    """Compare site scene HTML vs deployed; copy newer ones + git add/commit/push.

    Returns list of synced (or would-be-synced) scene filenames.
    """
    site_scenes = sorted(SITE.glob('fase*.html'))
    if not site_scenes:
        print("  --sync-scenes: no scene HTML found in site dir")
        return []

    to_sync = []
    for src in site_scenes:
        dst = GHPAGES / src.name
        if not dst.exists():
            to_sync.append((src.name, 'new'))
        elif src.stat().st_mtime > dst.stat().st_mtime:
            to_sync.append((src.name, 'site newer'))

    if not to_sync:
        print("  --sync-scenes: all scenes up to date")
        return []

    action = 'Would sync' if check_only else 'Syncing'
    print(f"  --sync-scenes: {action} {len(to_sync)} scene(s):")
    for name, why in to_sync:
        print(f"    - {name} ({why})")

    if check_only:
        return [name for name, _ in to_sync]

    os.chdir(GHPAGES)
    synced = []
    for name, _ in to_sync:
        shutil.copy2(SITE / name, GHPAGES / name)
        subprocess.run(['git', 'add', name], capture_output=True)
        synced.append(name)

    if synced:
        msg = 'sync scenes: ' + ', '.join(synced)
        subprocess.run(['git', 'commit', '-m', msg], capture_output=True, timeout=60)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'gh-pages'],
                       capture_output=True, timeout=60)
        r = subprocess.run(['git', 'push', 'origin', 'gh-pages'],
                           capture_output=True, text=True, timeout=60)
        ok = 'gh-pages -> gh-pages' in r.stdout or 'Everything up-to-date' in r.stdout
        print(f"    push: {'OK' if ok else 'FAIL — ' + (r.stderr or r.stdout)[-200:]}")
    return synced

def live_ok(mp4_name):
    """Check if the MP4 returns HTTP 200 on github.io."""
    try:
        req = urllib.request.Request(LIVE_BASE + mp4_name, method='HEAD')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true', help='one pass then exit')
    ap.add_argument('--check-only', action='store_true', help='report only, no render')
    ap.add_argument('--sync-scenes', action='store_true',
                    help='sync newer scene HTML to github-pages (respects --check-only)')
    args = ap.parse_args()

    if args.sync_scenes:
        synced = sync_scenes(check_only=args.check_only)
        if synced:
            print(f"  synced: {synced}")
        return

    print("=== curriculum-complete: scanning W4-W12 ===")
    missing, need_render, need_deploy = [], [], []
    complete = []

    for wk, (spec, scene, mp4, label) in WEEKS.items():
        out = OUTPUT / mp4
        if not out.exists() or out.stat().st_size < 1000:
            missing.append(wk)
            continue

        # Check gate
        passed, _ = gate_week(mp4)
        if not passed:
            need_render.append(wk)
            continue

        # Check deployed
        if not (GHPAGES / mp4).exists():
            need_deploy.append(wk)
            continue

        complete.append(wk)

    print(f"  complete: {complete}")
    if missing:
        print(f"  missing output: {missing}")
    if need_render:
        print(f"  gate FAIL (needs re-render): {need_render}")
    if need_deploy:
        print(f"  gate PASS but not deployed: {need_deploy}")

    if args.check_only:
        print("  --check-only: no action taken")
        return

    if not missing and not need_render and not need_deploy:
        print("  ALL 12 WEEKS COMPLETE ✅")
        return

    # Re-render missing/failed
    for wk in missing + need_render:
        spec, scene, mp4, label = WEEKS[wk]
        print(f"\n  → rendering W{wk}: {label}")
        ok, msg = render_week(wk, spec, scene, mp4)
        if not ok:
            print(f"    FAIL: {msg}")
            continue
        print(f"    rendered: {msg}")

        passed, metrics = gate_week(mp4)
        if not passed:
            print(f"    GATE FAIL: {metrics}")
            continue
        print(f"    gate PASS (lum {metrics.get('luminancia_media', '?')})")

        ok, msg = deploy_week(scene, mp4, label)
        print(f"    deploy: {'OK' if ok else 'FAIL'} — {msg[-200:]}")

    # Deploy gate-passing but not-yet-deployed
    for wk in need_deploy:
        spec, scene, mp4, label = WEEKS[wk]
        print(f"\n  → deploying W{wk}: {label}")
        ok, msg = deploy_week(scene, mp4, label)
        print(f"    deploy: {'OK' if ok else 'FAIL'} — {msg[-200:]}")

    # Final live check
    print("\n  === live check ===")
    for wk, (_, _, mp4, label) in WEEKS.items():
        live = live_ok(mp4)
        print(f"    W{wk}: {'✅ 200' if live else '❌'} {mp4}")

if __name__ == '__main__':
    main()
