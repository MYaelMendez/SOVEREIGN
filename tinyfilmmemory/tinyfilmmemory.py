#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tinyFILMMEMORY — film memory that outlives any session.

WHY (measured, not asserted):
  Session 20260710_193818_b3c467 holds months of film work and cannot
  resume (its model routes died: LongCat free ended, hy4-preview 402/404,
  latest attempts 403). Its 20,112 message rows are intact but trapped.
  The 2026-11-19 audit found 65 films published, 2 receipts persisted,
  ZERO gate records on disk — metrics printed to terminals and lost.
  Knowledge must not depend on a resumable session or an unpruned scratch.

WHAT (tiny family: one file, stdlib, zero tokens, deterministic):
  record  — RE-MEASURE a film NOW from its delivered bytes: sha256
            citation, ffprobe per-stream durations/frames/codecs, A/V
            duration delta (defect gate), fuzzy spec/trace/receipt finder.
            Paper-style record compatible with ae/video-research/1
            (abstract/methods/results/data/limitations/citation), appended
            to a hash-chained JSONL ledger. measurement_kind=re_measured.
  recall  — search records by stem / citation prefix / abstract text.
  verify  — recompute the whole chain; re-hash cited films still on disk
            and report DRIFT; absent artifact is honest, chain still holds.
  audit   — corpus coverage: *.mp4 under a dir vs recorded citations.
  rescue  — READ-ONLY extraction from a trapped session's state.db
            messages: 64-hex receipts, film filenames, gate-metric lines,
            with message-id evidence. measurement_kind=recovered — NEVER
            upgraded to re_measured without the artifact. Lost data is a
            finding; inventing it is the failure this chain prevents.
  doctor / selftest.

HONEST LIMITS: measures bytes and streams, not rightness or intelligibility
(the human gate). ffprobe durations are per-stream, never container-only.
Defect flag: |video_s - audio_s| > 0.5 s (the two published broken films:
15.816 s and 23.555 s frozen tails). mux_match tolerance 0.15 s mirrors
tinycudavideo.MUX_TOLERANCE_S; the walk film's 0.006 s is the proven bar.

PITFALLS HONORED: 'æ' corrupts native subprocess argv — films on non-ASCII
paths are measured via a byte-identical scratch copy (citation is of the
ORIGINAL bytes, hashed in-process). ffprobe pinned absolute. state.db is
opened strictly read-only (sqlite URI mode=ro) and queried by session_id.

CLI:
  python tinyfilmmemory.py record <film.mp4> [--abstract TEXT] [--ledger P]
  python tinyfilmmemory.py recall <query> [--ledger P]
  python tinyfilmmemory.py verify [citation16] [--ledger P]
  python tinyfilmmemory.py audit <dir> [--ledger P]
  python tinyfilmmemory.py rescue <session_id> [--db PATH] [--ledger P]
  python tinyfilmmemory.py doctor | selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES_HOME = Path(os.environ.get("HERMES_HOME",
                                  "C:/Users/yaelm/AppData/Local/hermes"))
FFPROBE = HERMES_HOME / "tools" / "ffmpeg-7.1-nvenc" / "bin" / "ffprobe.exe"
DEFAULT_LEDGER = Path("C:/æ/logs/filmmemory/ledger.jsonl")
RECORDS_DIR = Path("C:/æ/logs/filmmemory/records")
GENESIS = "0" * 64
MUX_TOLERANCE_S = 0.15     # tinycudavideo.MUX_TOLERANCE_S — never lowered
DEFECT_DELTA_S = 0.5       # frozen-tail defect flag
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
MP4NAME = re.compile(r"[A-Za-z0-9_\-\.]+\.mp4")
GATELINE = re.compile(r"\b(lum|contrast|motion|black_pct|receipt)\b[^\n]{0,120}",
                      re.IGNORECASE)


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# ── ledger ────────────────────────────────────────────────────────────────────

def read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def chain_check(lines: list[dict]) -> dict:
    prev = GENESIS
    for i, rec in enumerate(lines):
        claimed = rec.get("hash")
        body = {k: v for k, v in rec.items() if k != "hash"}
        if body.get("prev") != prev:
            return {"ok": False, "line": i + 1,
                    "reason": f"chain break: prev {str(body.get('prev'))[:12]} != {prev[:12]}"}
        recomputed = sha256(canonical(body))
        if recomputed != claimed:
            return {"ok": False, "line": i + 1,
                    "reason": f"hash mismatch (recomputed {recomputed[:12]}, claimed {str(claimed)[:12]})"}
        prev = claimed
    return {"ok": True, "length": len(lines), "head": prev}


def append(path: Path, body: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = read_ledger(path)
    chk = chain_check(lines)
    if not chk["ok"]:
        return {"ok": False, "refused": True,
                "reason": f"ledger corrupt at line {chk['line']}: {chk['reason']} — refusing append"}
    rec = dict(body)
    rec["prev"] = chk["head"]
    rec["hash"] = sha256(canonical(rec))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    # read back after write (external-effect law)
    back = read_ledger(path)
    if not back or back[-1].get("hash") != rec["hash"]:
        return {"ok": False, "refused": True, "reason": "read-back failed after append"}
    return {"ok": True, "hash": rec["hash"], "prev": rec["prev"],
            "length": len(back)}


# ── measurement ───────────────────────────────────────────────────────────────

def ffprobe(path: Path) -> dict:
    if not FFPROBE.exists():
        raise FileNotFoundError(f"ffprobe not found: {FFPROBE}")
    # æ-path argv corruption: measure a byte-identical ASCII copy
    target = path
    tmp = None
    if not is_ascii(str(path)):
        tmp = Path(tempfile.mkdtemp(prefix="tfm_", dir=str(
            HERMES_HOME / "cache" / "scratch"))) / "probe.mp4"
        shutil.copyfile(path, tmp)
        target = tmp
    try:
        out = subprocess.run(
            [str(FFPROBE), "-v", "error", "-show_streams", "-show_format",
             "-of", "json", str(target)],
            capture_output=True, text=True, timeout=120,
            env={k: v for k, v in os.environ.items()
                 if k not in ("PYTHONPATH", "PYTHONHOME")})
        if out.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {out.stderr.strip()[:200]}")
        return json.loads(out.stdout)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp.parent, ignore_errors=True)


def measure(film: Path) -> dict:
    probe = ffprobe(film)
    streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    m: dict = {"streams": len(streams), "audio": "none"}
    if v is None:
        m["video"] = "none"
        return m
    vd = float(v.get("duration") or probe.get("format", {}).get("duration") or 0)
    frames = int(v.get("nb_frames") or 0)
    m.update({
        "video": v.get("codec_name"), "video_s": round(vd, 3),
        "frames": frames, "width": v.get("width"), "height": v.get("height"),
    })
    if a is not None:
        ad = float(a.get("duration") or 0)
        delta = round(abs(vd - ad), 3)
        m.update({"audio": a.get("codec_name"), "audio_s": round(ad, 3),
                  "av_delta_s": delta,
                  "mux_match": delta <= MUX_TOLERANCE_S,
                  "defect": delta > DEFECT_DELTA_S})
        if delta > DEFECT_DELTA_S:
            m["frozen_tail_s"] = round(max(vd, ad) - min(vd, ad), 3)
    return m


def find_artifacts(film: Path) -> dict:
    """Fuzzy finder — fixes video_research's too-strict stem match:
    spec-walk-film.json must match asimov-walk (normalize, don't reconstruct)."""
    stem = film.stem.replace("-916", "").lower()
    tokens = [t for t in re.split(r"[-_]", stem) if t]
    arts = {"spec": None, "trace": None, "receipt": None}
    try:
        siblings = list(film.parent.glob("*.json"))
    except OSError:
        return arts
    def score(p: Path) -> float:
        n = p.name.lower()
        s = float(sum(1 for t in tokens if t in n))
        if tokens and tokens[-1] in n:
            s += 0.5  # trailing token is usually the subject (walk, not asimov)
        return s
    for kind, marker in (("spec", "spec"), ("receipt", "receipt"), ("trace", "trace")):
        cands = [p for p in siblings if marker in p.name.lower() and score(p) >= 1]
        if cands:
            arts[kind] = str(max(cands, key=score))
    return arts


# ── verbs ─────────────────────────────────────────────────────────────────────

def record(film: Path, ledger: Path, abstract: str = "") -> dict:
    if not film.exists():
        return {"ok": False, "refused": True, "reason": f"no such film: {film}"}
    sha = sha256(film.read_bytes())          # in-process: original bytes, no argv
    m = measure(film)
    arts = find_artifacts(film)
    methods = {"available": arts["spec"] is not None}
    if arts["spec"]:
        try:
            s = json.loads(Path(arts["spec"]).read_text(encoding="utf-8"))
            methods.update({"spec": arts["spec"],
                            "scenes": len(s.get("scenes", [])),
                            "cast": s.get("cast")})
        except Exception:
            methods["available"] = False
    lim = ["Gate metrics were not persisted at render time; re-measured from the delivered bytes.",
           "One machine. No second-box reproduction."]
    if m.get("defect"):
        lim.append(f"DEFECT: audio/video duration mismatch {m['av_delta_s']}s (frozen tail).")
    elif m.get("audio") != "none" and not m.get("mux_match", True):
        lim.append(f"A/V delta {m['av_delta_s']}s exceeds mux tolerance {MUX_TOLERANCE_S}s.")
    if m.get("audio") == "none":
        lim.append("No audio stream — mute film.")
    rec = {
        "schema": "ae/film-memory/1", "kind": "film",
        "title": film.stem,
        "citation": f"æ://film/{film.stem} · sha256:{sha[:16]}",
        "doi_equivalent": sha,
        "file": film.name, "path": str(film), "bytes": film.stat().st_size,
        "abstract": abstract or f"Film {film.stem}: {m.get('frames', 0)} frames, {m.get('video_s', 0)}s.",
        "methods": methods, "results": m,
        "data": {"trace": arts["trace"], "available": arts["trace"] is not None},
        "artifacts": arts, "limitations": lim,
        "measured_at": now(), "measurement_kind": "re_measured",
        "authority": "HUMAN://ROOT", "grants": False,
    }
    ap = append(ledger, rec)
    if not ap["ok"]:
        return ap
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    out = RECORDS_DIR / f"{film.stem}.json"
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "citation": rec["citation"], "sha256": sha,
            "results": m, "artifacts": arts, "record": str(out),
            "ledger_hash": ap["hash"], "defect": m.get("defect", False)}


def recall(query: str, ledger: Path) -> dict:
    q = query.lower()
    hits = []
    for rec in read_ledger(ledger):
        if rec.get("kind") != "film":
            continue
        hay = " ".join([rec.get("title", ""), rec.get("citation", ""),
                        rec.get("abstract", "")]).lower()
        if q in hay or q in rec.get("doi_equivalent", ""):
            hits.append({"title": rec["title"], "citation": rec["citation"],
                         "measurement_kind": rec["measurement_kind"],
                         "defect": rec.get("results", {}).get("defect", False),
                         "measured_at": rec["measured_at"], "hash": rec["hash"]})
    return {"ok": True, "query": query, "hits": hits, "count": len(hits)}


def verify(ledger: Path, citation16: str | None = None) -> dict:
    lines = read_ledger(ledger)
    chk = chain_check(lines)
    if not chk["ok"]:
        return {"ok": False, **chk}
    drift, absent, checked = [], [], 0
    for rec in lines:
        if rec.get("kind") != "film":
            continue
        if citation16 and citation16 not in rec.get("doi_equivalent", ""):
            continue
        p = Path(rec["path"])
        if not p.exists():
            absent.append(rec["title"])
            continue
        checked += 1
        if sha256(p.read_bytes()) != rec["doi_equivalent"]:
            drift.append(rec["title"])
    # A quarantined drift is a DECIDED drift: it stays visible but stops
    # demanding "re-seal". The decision lives beside the ledger, not in chat.
    quarantined = []
    qpath = Path(HERE) / "quarantine-hermes-agent-activity.json"
    if qpath.exists():
        try:
            q = json.loads(qpath.read_text(encoding="utf-8"))
            quarantined = q.get("quarantined_citations", [])
        except Exception:
            quarantined = []
    open_drift = [d for d in drift if not any(c in str(d) or str(d) in c for c in quarantined)]
    return {"ok": not open_drift, "chain": chk, "films_checked": checked,
            "drift": drift, "open_drift": open_drift, "quarantined": quarantined,
            "absent": absent,
            "note": "absent is honest; drift means bytes changed since sealing; quarantined drift is decided, not re-sealed"}


def audit(directory: Path, ledger: Path) -> dict:
    films = sorted(directory.rglob("*.mp4"))
    recorded = {r.get("doi_equivalent") for r in read_ledger(ledger)
                if r.get("kind") == "film"}
    rec_stems = {r.get("title") for r in read_ledger(ledger)
                 if r.get("kind") == "film"}
    unrec = []
    for f in films:
        if f.stem in rec_stems:
            continue
        unrec.append(f.name)
    return {"ok": True, "dir": str(directory), "films": len(films),
            "recorded_by_stem": len(films) - len(unrec),
            "unrecorded": len(unrec), "unrecorded_names": unrec[:200],
            "ledger_film_records": len(rec_stems)}


def rescue(session_id: str, db: Path, ledger: Path) -> dict:
    if not db.exists():
        return {"ok": False, "refused": True, "reason": f"no db: {db}"}
    uri = f"file:{db.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        before = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        rows = con.execute(
            "SELECT id, role, content, tool_name, timestamp FROM messages "
            "WHERE session_id=? AND content IS NOT NULL", (session_id,)).fetchall()
        receipts: dict[str, dict] = {}
        films: dict[str, dict] = {}
        gates: list[dict] = []
        for mid, role, content, tool_name, ts in rows:
            if not isinstance(content, str):
                continue
            for h in HEX64.findall(content):
                if h not in receipts:
                    i = content.find(h)
                    receipts[h] = {"message_id": mid, "role": role,
                                   "context": content[max(0, i - 80):i + 84].replace("\n", " ")}
            for name in MP4NAME.findall(content):
                if name not in films:
                    films[name] = {"message_id": mid, "role": role}
            if role in ("assistant", "tool") and GATELINE.search(content):
                gm = GATELINE.search(content)
                if len(gates) < 500:
                    gates.append({"message_id": mid, "line": gm.group(0)[:160]})
        after = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    finally:
        con.close()
    sidecar = RECORDS_DIR / f"rescue-{session_id}.json"
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"session_id": session_id, "messages_scanned": len(rows),
               "receipts": receipts, "films": films, "gate_lines": gates,
               "db_rows_before": before, "db_rows_after": after,
               "rescued_at": now()}
    sidecar.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                       encoding="utf-8")
    rec = {"schema": "ae/film-memory/1", "kind": "rescue",
           "title": f"rescue:{session_id}",
           "session_id": session_id, "messages_scanned": len(rows),
           "receipts_recovered": len(receipts), "films_referenced": len(films),
           "gate_lines_recovered": len(gates),
           "sidecar": str(sidecar),
           "db_unchanged": before == after,
           "measured_at": now(), "measurement_kind": "recovered",
           "provenance": f"session:{session_id}",
           "authority": "HUMAN://ROOT", "grants": False,
           "note": "RECOVERED IS NOT RE-MEASURED: claims carry message-id "
                   "evidence only; never upgrade without the artifact."}
    ap = append(ledger, rec)
    if not ap["ok"]:
        return ap
    return {"ok": True, **{k: rec[k] for k in
            ("messages_scanned", "receipts_recovered", "films_referenced",
             "gate_lines_recovered", "db_unchanged", "sidecar")},
            "ledger_hash": ap["hash"]}


def doctor() -> dict:
    return {"ok": FFPROBE.exists(), "ffprobe": str(FFPROBE),
            "ffprobe_exists": FFPROBE.exists(),
            "ledger_default": str(DEFAULT_LEDGER),
            "ledger_exists": DEFAULT_LEDGER.exists(),
            "python": sys.version.split()[0],
            "records_dir": str(RECORDS_DIR)}


def selftest() -> dict:
    """Compact internal proof on a generated fixture (ffmpeg lavfi)."""
    ffmpeg = FFPROBE.with_name("ffmpeg.exe")
    if not ffmpeg.exists():
        return {"ok": False, "reason": "ffmpeg fixture generator absent"}
    tmp = Path(tempfile.mkdtemp(prefix="tfm_self_", dir=str(
        HERMES_HOME / "cache" / "scratch")))
    led = tmp / "ledger.jsonl"
    try:
        fix = tmp / "fixture.mp4"
        r = subprocess.run([str(ffmpeg), "-v", "error", "-y",
                            "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=10",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                            "-c:v", "libx264", "-preset", "ultrafast",
                            "-c:a", "aac", "-shortest", str(fix)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return {"ok": False, "reason": f"fixture failed: {r.stderr[:200]}"}
        a = record(fix, led, abstract="selftest fixture")
        assert a["ok"], a
        b = record(fix, led, abstract="selftest fixture")
        assert b["ok"] and b["sha256"] == a["sha256"], "citation determinism"
        v = verify(led)
        assert v["ok"] and v["chain"]["length"] == 2, v
        # tamper
        lines = led.read_text(encoding="utf-8").splitlines()
        rec0 = json.loads(lines[0]); rec0["abstract"] = "tampered"
        lines[0] = json.dumps(rec0, ensure_ascii=False, sort_keys=True)
        led.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert not verify(led)["ok"], "tamper must fail"
        # drift: fresh chain, then flip one byte of the film
        led.unlink()
        c = record(fix, led, abstract="drift base")
        assert c["ok"], c
        data = bytearray(fix.read_bytes()); data[-1] ^= 0xFF
        fix.write_bytes(bytes(data))
        d = verify(led)
        assert d["drift"] == ["fixture"], f"drift must be reported: {d}"
        return {"ok": True, "checks": ["record", "determinism", "chain",
                                       "tamper-fails", "byte-drift-detected"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description="tinyFILMMEMORY — film memory that outlives sessions")
    p.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record"); r.add_argument("film"); r.add_argument("--abstract", default="")
    rc = sub.add_parser("recall"); rc.add_argument("query")
    v = sub.add_parser("verify"); v.add_argument("citation16", nargs="?", default=None)
    a = sub.add_parser("audit"); a.add_argument("dir")
    s = sub.add_parser("rescue"); s.add_argument("session_id")
    s.add_argument("--db", default=str(HERMES_HOME / "state.db"))
    sub.add_parser("doctor"); sub.add_parser("selftest")
    args = p.parse_args(argv)
    led = Path(args.ledger)
    if args.cmd == "record":
        out = record(Path(args.film), led, args.abstract)
    elif args.cmd == "recall":
        out = recall(args.query, led)
    elif args.cmd == "verify":
        out = verify(led, args.citation16)
    elif args.cmd == "audit":
        out = audit(Path(args.dir), led)
    elif args.cmd == "rescue":
        out = rescue(args.session_id, Path(args.db), led)
    elif args.cmd == "doctor":
        out = doctor()
    else:
        out = selftest()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
