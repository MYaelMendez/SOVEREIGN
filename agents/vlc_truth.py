#!/usr/bin/env python3
"""
vlc_truth.py — make github.io VLC's source of truth.

THE IDEA
--------
VLC currently plays local files. The deployed surface is the truth: it is what
actually serves to anyone, anywhere. So VLC should read its media list FROM the
surface, not from a hand-kept folder listing.

WHAT "SOURCE OF TRUTH" HAS TO MEAN
----------------------------------
A playlist is only a source of truth if every entry in it actually resolves.
A hand-written list drifts: a file gets renamed, the entry 404s, and VLC shows
a dead item that looks real. So this generator PROBES each URL and includes
only what answers 200 — the playlist cannot contain an entry that does not
serve, because the entry is created by the probe that proved it.

Order of operations (the probe is what admits an entry):
    1. scan the deployed tree for media
    2. build the absolute github.io URL for each
    3. HEAD it — 200 admits, anything else is reported and excluded
    4. write the .m3u with real metadata
    5. emit a receipt (count, total bytes, hash of the playlist)

COMMANDS
    python vlc_truth.py build              # probe + write playlist.m3u
    python vlc_truth.py build --offline    # skip the probe (marks entries unverified)
    python vlc_truth.py verify             # re-probe every entry in the playlist
    python vlc_truth.py play [--index N]   # load it into a running VLC
    python vlc_truth.py status             # is VLC up, what is it playing

VLC NOTE (3.x): `in_play` loads media; `pl_add` is a silent no-op that makes a
receipt lie. The HTTP interface is :8081, password from VLC_PASS.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

AE = pathlib.Path(os.environ.get("AE_ROOT", r"C:\æ"))
GH = AE / "github-pages"
SITE = "https://myaelmendez.github.io"
PLAYLIST = GH / "playlist.m3u"
RECEIPT = AE / "logs" / "vlc-truth-receipt.json"

VLC_EXE = pathlib.Path(os.environ.get(
    "VLC_EXE", r"C:\Program Files\VideoLAN\VLC\vlc.exe"))
VLC_HTTP = os.environ.get("VLC_HTTP", "http://127.0.0.1:8081/requests/status.json")
VLC_PASS = os.environ.get("VLC_PASS", "hermes")

MEDIA_EXT = {".mp4": "video", ".webm": "video", ".mkv": "video",
             ".mp3": "audio", ".m4a": "audio", ".ogg": "audio", ".wav": "audio"}

# Files that are scratch/derived and should not clutter the truth playlist.
EXCLUDE = re.compile(r"(^|/)(node_modules|\.git|_site|dist|build)/", re.I)


def scan() -> list[dict]:
    """Every media file in the deployed tree, as an absolute URL."""
    out = []
    for p in sorted(GH.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in MEDIA_EXT:
            continue
        rel = p.relative_to(GH).as_posix()
        if EXCLUDE.search(rel):
            continue
        out.append({
            "rel": rel,
            "url": f"{SITE}/{urllib.parse.quote(rel)}",
            "kind": MEDIA_EXT[p.suffix.lower()],
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        })
    return out


def probe(url: str, timeout: int = 20) -> tuple[bool, int, int]:
    """HEAD the URL. Returns (ok, status, content_length)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "vlc-truth/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            n = int(r.headers.get("Content-Length") or 0)
            return (200 <= r.status < 300), r.status, n
    except urllib.error.HTTPError as e:
        return False, e.code, 0
    except Exception:
        return False, 0, 0


def title_of(rel: str) -> str:
    """A human title from the path — no invented copy."""
    stem = pathlib.PurePosixPath(rel).stem
    return stem.replace("-", " ").replace("_", " ").strip()


def build(do_probe: bool = True, limit: int | None = None) -> dict:
    items = scan()
    if limit:
        items = items[:limit]

    admitted, rejected = [], []
    for i, it in enumerate(items, 1):
        if do_probe:
            ok, status, live_len = probe(it["url"])
            it["http"] = status
            it["verified"] = ok
            # a served length that disagrees with the local file is a real
            # finding: the deployed bytes are not the bytes we think they are
            it["length_matches"] = (not ok) or (live_len == 0) or (live_len == it["bytes"])
            if ok:
                admitted.append(it)
            else:
                rejected.append(it)
            if i % 20 == 0:
                print(f"    probed {i}/{len(items)}…", flush=True)
        else:
            it["http"] = None
            it["verified"] = False
            it["length_matches"] = None
            admitted.append(it)

    lines = [
        "#EXTM3U",
        "# source of truth: " + SITE,
        f"# generated {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"# {len(admitted)} entries"
        + (f" · probed, all HTTP 200" if do_probe else " · NOT probed"),
        f"# excluded (did not answer 200): {len(rejected)}",
    ]
    for it in admitted:
        secs = -1  # unknown duration; -1 is VLC's "unspecified"
        lines.append(f"#EXTINF:{secs},{title_of(it['rel'])}")
        lines.append(f"#EXTALB:{it['kind']}")
        lines.append(f"# æsha256:{it['sha256']}")
        lines.append(it["url"])

    PLAYLIST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ph = hashlib.sha256(PLAYLIST.read_bytes()).hexdigest()

    receipt = {
        "playlist": str(PLAYLIST),
        "url": f"{SITE}/playlist.m3u",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "probed": do_probe,
        "scanned": len(items),
        "admitted": len(admitted),
        "rejected": len(rejected),
        "total_bytes": sum(i["bytes"] for i in admitted),
        "playlist_sha256": ph,
        "rejected_detail": [
            {"url": r["url"], "http": r["http"]} for r in rejected[:40]
        ],
        "length_mismatches": [
            {"url": i["url"], "local": i["bytes"]}
            for i in admitted if i.get("length_matches") is False
        ],
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    return receipt


def verify() -> dict:
    """Re-probe every entry currently in the playlist."""
    if not PLAYLIST.exists():
        return {"error": "no playlist — run build first"}
    urls = [l.strip() for l in PLAYLIST.read_text(encoding="utf-8").splitlines()
            if l.strip().startswith("http")]
    bad = []
    for u in urls:
        ok, status, _ = probe(u)
        if not ok:
            bad.append({"url": u, "http": status})
    return {"entries": len(urls), "dead": len(bad), "dead_detail": bad[:20],
            "ok": not bad}


# ── VLC control ──────────────────────────────────────────────────────────────

def _vlc_auth() -> str:
    return "Basic " + base64.b64encode(f":{VLC_PASS}".encode()).decode()


def vlc_alive() -> bool:
    try:
        req = urllib.request.Request(VLC_HTTP)
        req.add_header("Authorization", _vlc_auth())
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def vlc_status() -> dict:
    try:
        req = urllib.request.Request(VLC_HTTP)
        req.add_header("Authorization", _vlc_auth())
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def vlc_in_play(target: str) -> bool:
    """Load `target` (a URL or file path). in_play is the VLC 3.x verb that
    actually loads; pl_add is a no-op that would make this receipt a lie."""
    qs = urllib.parse.urlencode({"command": "in_play", "input": target})
    req = urllib.request.Request(VLC_HTTP + "?" + qs)
    req.add_header("Authorization", _vlc_auth())
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            r.read()
        return True
    except Exception:
        return False


def ensure_vlc() -> bool:
    """Start VLC with the HTTP interface if none is up. Never claims a window
    that did not open."""
    if vlc_alive():
        return True
    if not VLC_EXE.exists():
        return False
    subprocess.Popen([
        str(VLC_EXE),
        "--extraintf", "http",
        "--http-password", VLC_PASS,
        "--http-port", "8081",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.5)
        if vlc_alive():
            return True
    return False


def play(index: int | None = None, remote: bool = True) -> dict:
    """Load the truth playlist (or one entry) into VLC."""
    if not ensure_vlc():
        return {"ok": False, "error": "VLC not running and could not be started"}
    if index is None:
        target = f"{SITE}/playlist.m3u" if remote else str(PLAYLIST)
    else:
        if not PLAYLIST.exists():
            return {"ok": False, "error": "no playlist"}
        urls = [l.strip() for l in PLAYLIST.read_text(encoding="utf-8").splitlines()
                if l.strip().startswith("http")]
        if not (0 <= index < len(urls)):
            return {"ok": False, "error": f"index {index} out of range (0..{len(urls)-1})"}
        target = urls[index]
    ok = vlc_in_play(target)
    time.sleep(2)
    st = vlc_status()
    return {
        "ok": ok,
        "loaded": target,
        "source": "github.io" if remote else "local",
        # report what VLC says it is doing, not what we hoped
        "vlc_state": st.get("state"),
        "vlc_now_playing": (st.get("information", {})
                            .get("category", {})
                            .get("meta", {})
                            .get("filename")),
    }


def main(argv):
    ap = argparse.ArgumentParser(description="github.io as VLC's source of truth")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build")
    b.add_argument("--offline", action="store_true",
                   help="skip the live probe (entries marked unverified)")
    b.add_argument("--limit", type=int, default=None)
    sub.add_parser("verify")
    p = sub.add_parser("play")
    p.add_argument("--index", type=int, default=None)
    p.add_argument("--local", action="store_true", help="use the local file, not the URL")
    sub.add_parser("status")
    a = ap.parse_args(argv[1:])

    if a.cmd == "build":
        print(f"  scanning {GH} …")
        r = build(do_probe=not a.offline, limit=a.limit)
        print(f"  scanned   {r['scanned']}")
        print(f"  admitted  {r['admitted']}  (HTTP 200)")
        print(f"  rejected  {r['rejected']}")
        print(f"  bytes     {r['total_bytes']:,}")
        print(f"  playlist  {r['playlist']}")
        print(f"  sha256    {r['playlist_sha256'][:32]}…")
        if r["length_mismatches"]:
            print(f"  !! {len(r['length_mismatches'])} length mismatch(es) — "
                  f"served bytes differ from local")
        if r["rejected_detail"]:
            print("  rejected:")
            for d in r["rejected_detail"][:10]:
                print(f"    {d['http']}  {d['url']}")
        return 0

    if a.cmd == "verify":
        r = verify()
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r.get("ok") else 1

    if a.cmd == "play":
        r = play(a.index, remote=not a.local)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r.get("ok") else 1

    if a.cmd == "status":
        print(f"  vlc alive : {vlc_alive()}")
        st = vlc_status()
        if "error" in st:
            print(f"  {st['error']}")
        else:
            print(f"  state     : {st.get('state')}")
            print(f"  time      : {st.get('time')} / {st.get('length')}")
            fn = (st.get("information", {}).get("category", {})
                  .get("meta", {}).get("filename"))
            print(f"  playing   : {fn}")
        if PLAYLIST.exists():
            n = sum(1 for l in PLAYLIST.read_text(encoding="utf-8").splitlines()
                    if l.strip().startswith("http"))
            print(f"  playlist  : {n} entries")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
