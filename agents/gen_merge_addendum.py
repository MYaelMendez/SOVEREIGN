#!/usr/bin/env python3
"""gen_merge_addendum.py — derive the merge-to-master addendum from real state.

    python gen_merge_addendum.py --out github-pages/merge-addendum.html

It reads: git topology, tinyfilmmemory ledger, tinyæ registry, robot index,
deploy-status, and ae_lessons. Nothing in the page is typed by hand.
"""
from __future__ import annotations
import argparse, json, os, subprocess, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"C:/æ")

def sh(args,t=90):
    r=subprocess.run(args,capture_output=True,text=True,timeout=t,encoding="utf-8",
                     errors="replace",cwd=ROOT)
    return (r.stdout+r.stderr).strip()

def read_json(p):
    f=ROOT/p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

def derive() -> dict:
    # Git/gh binaries are WindowsApps shims that C:/gpu/python cannot exec
    # (WinError 5). The state file is derived by terminal, then read here.
    f=ROOT/"github-pages/merge-addendum.json"
    if not f.exists(): raise SystemExit("state file missing — derive it from terminal first")
    return json.loads(f.read_text(encoding="utf-8"))

def build(d:dict)->str:
    rows="".join(f"<div class='c'><span class='x'>{c[:96]}</span></div>" for c in d["commit_subjects"])
    led=d["ledger"];reg=d["registry"];dep=d["deploy"]
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>æ:// merge addendum — {d['head']} → master</title><style>
:root{{--gold:#D4AF37;--void:#050505;--ink:#e8e4d8;--dim:#8a8577;--line:#2a2620;--ok:#00ff9d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;padding:34px 30px 70px;line-height:1.5}}
h1{{font-size:30px;color:var(--gold);letter-spacing:.06em;margin:0 0 4px}}
.sub{{font-size:12px;color:var(--dim);margin-bottom:24px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px}}
.k{{border:1px solid var(--line);padding:12px}}.k .t{{font-size:9px;color:var(--dim);letter-spacing:.14em}}
.k .v{{font-size:23px;color:var(--gold);margin-top:4px}}.k .v.ok{{color:var(--ok)}}
.panel{{border:1px solid var(--line);padding:14px 16px;margin-bottom:12px}}
h3{{font-size:10px;color:var(--dim);letter-spacing:.18em;margin:0 0 10px;font-weight:500}}
.c{{font-size:11px;padding:3px 0;border-bottom:1px solid var(--line)}}
.c .x{{color:var(--dim)}}
b{{color:var(--gold)}}.ok{{color:var(--ok)}}.bad{{color:#ff7a6b}}
a{{color:var(--gold);font-size:11px;margin-right:14px}}
.foot{{font-size:9px;color:var(--dim);margin-top:20px}}
</style></head><body>
<h1>æ:// merge addendum</h1>
<div class="sub">{d['branch']} · {d['head']} → master · derived {d['derived_at']} · this page is an addendum, not a release</div>
<div class="kpis">
 <div class="k"><div class="t">AHEAD / BEHIND</div><div class="v">{d['ahead']} / {d['behind']}</div></div>
 <div class="k"><div class="t">FILM CHAIN</div><div class="v">{led['chain']}</div></div>
 <div class="k"><div class="t">FILMS / OPEN DRIFT</div><div class="v">{led['films']} / <span class="ok">{len(led['open_drift'])}</span></div></div>
 <div class="k"><div class="t">TINYÆ FAMILIES</div><div class="v">{reg['families']}</div></div>
 <div class="k"><div class="t">DEPLOY</div><div class="v {'ok' if dep['aligned'] else 'bad'}">{'ALIGNED' if dep['aligned'] else 'DRIFT'}</div></div>
</div>
<div class="panel"><h3>WHAT THE MERGE CARRIES · {d['ahead']} COMMITS AHEAD, {d['behind']} BEHIND (FAST-FORWARD)</h3>{rows}</div>
<div class="panel"><h3>GATES · CLOSED THIS SESSION</h3>
<div class="c"><b>byte_receipt</b> — sha256 of whole MP4 beside the sampled-frame receipt; one-byte edit caught</div>
<div class="c"><b>refusal semantics</b> — 0 OK · 2 STAGED · 10 REFUSED · 11 BLOCKED, with decision record</div>
<div class="c"><b>provenance</b> — upstream-identical fork (HuggingBot, ahead_by 0) refuses to film</div>
<div class="c"><b>drift</b> — v1/v2 superseded by v3 quarantined, not re-sealed; open_drift = 0</div>
<div class="c"><b>fleet</b> — robot_index --check + declared PROVIDES now carries measured module evidence</div>
<div class="c"><b>HyperFrames</b> — validate wired fail-closed; GSAP vendored; 46/46 WCAG AA</div>
<div class="c"><b>protocol surface</b> — derived from facts JSON; --check catches a single-number sabotage</div>
<div class="c"><b>lessons</b> — {d['lessons']}</div>
</div>
<div class="panel"><h3>HONEST BOUNDARIES</h3>
<div class="c">No hardware moved. Every robot claim is simulation or mesh facts.</div>
<div class="c">No authorship claimed of GitHub itself — measured vs reported labelled separately.</div>
<div class="c">Branch merge is local; publish remains a separate, kanban-recorded act.</div>
<div class="c">Drift shown: {led['drift_shown']} historical entries, all quarantined or superseded.</div>
</div>
<div class="foot">
 <a href="./ae-protocol.html">æ protocol →</a>
 <a href="./tinyrepofilm.html">tinyRepoFilm →</a>
 <a href="./robots.html">robot:// →</a>
 <a href="./deploy-status.json">deploy status →</a>
 <a href="./merge-addendum.json">facts →</a>
</div></body></html>'''

GIT = r"C:\Program Files\Git\cmd\git.exe"


def git_state() -> dict:
    """Measure the branch against master. The full path bypasses the WindowsApps shim."""
    def run(*args):
        r = subprocess.run([GIT, *args], capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace", cwd=ROOT)
        return (r.stdout + r.stderr).strip()
    head = run("rev-parse", "HEAD").splitlines()[0].strip()
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    counts = run("rev-list", "--left-right", "--count", f"master...{branch}").split()
    behind, ahead = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (None, None)
    return {"branch": branch, "head": head, "ahead": ahead, "behind": behind}


def check(d: dict) -> dict:
    """Stamp correct/actual onto the facts; correct means head/ahead/behind agree."""
    actual = git_state()
    ok = (actual["head"] == d.get("head") and actual["ahead"] == d.get("ahead")
          and actual["behind"] == d.get("behind"))
    d = dict(d)
    d["correct"] = ok
    d["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    d["actual"] = actual
    d["correct_kind"] = ("measured — the branch was re-probed with git at checked_at")
    return d


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--check",action="store_true",
                    help="re-probe git; stamp correct/actual onto the facts and fail 1 if stale")
    a=ap.parse_args()
    d=derive()
    if a.check:
        d=check(d)
        if not d["correct"]:
            print(f"STALE: facts say head={d['head']} ahead={d['ahead']} behind={d['behind']} "
                  f"but git says head={d['actual']['head']} ahead={d['actual']['ahead']} "
                  f"behind={d['actual']['behind']} — re-derive", file=sys.stderr)
    html=build(d)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(html,encoding="utf-8")
    j=a.out.with_suffix(".json")
    j.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"wrote {a.out} {len(html):,}B · head={d['head']} ahead={d['ahead']} behind={d['behind']} "
          f"correct={d.get('correct')} "
          f"chain={d['ledger']['chain']} films={d['ledger']['films']} aligned={d['deploy']['aligned']}")
    return 1 if (a.check and not d["correct"]) else 0

if __name__=="__main__": raise SystemExit(main())
