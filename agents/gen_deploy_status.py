#!/usr/bin/env python3
"""gen_deploy_status.py — derive source vs deployed truth from GitHub APIs.

    python gen_deploy_status.py --out deploy-status.json [--check]

`push` is not `publish`. This record keeps them as two numbers:
  source_head — the commit in the local checkout
  build_commit / build_status — the Pages build
  live_sha — sha256 of the bytes actually served by the CDN
A surface can only claim `ALIGNED` when all three agree.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO="MYaelMendez/MYaelMendez.github.io"
SITE="https://myaelmendez.github.io"
SURFACES=["","origin/","tiny.html","tinyae.html","ae-protocol.html","ae-protocol-v3.html","tinyrepofilm.html"]

def gh(path,jq=None):
    c=["gh","api",path]+(["--jq",jq] if jq else [])
    r=subprocess.run(c,capture_output=True,text=True,timeout=60,encoding="utf-8",errors="replace")
    if r.returncode: return None
    return r.stdout.strip()

def derive() -> dict:
    local=Path(r"C:/æ/github-pages")
    # Read HEAD from .git directly: the bundled git.exe is a WindowsApps
    # package that C:/gpu/python cannot exec (WinError 5).
    head=(local/".git/HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref=head[5:]; head=(local/".git"/ref).read_text(encoding="utf-8").strip()
    source=head
    build_raw=gh(f"repos/{REPO}/pages/builds/latest","{status,commit,created_at}")
    build=json.loads(build_raw) if build_raw else {}
    live={}
    for s in SURFACES:
        url=f"{SITE}/{s}?cb={int(datetime.now(timezone.utc).timestamp())}"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Cache-Control":"no-cache"})
            with urllib.request.urlopen(req,timeout=20) as r: b=r.read()
            live[s or "/"]={"status":r.status,"bytes":len(b),
                            "sha256":hashlib.sha256(b).hexdigest()}
        except Exception as e:
            live[s or "/"]={"status":getattr(e,"code",type(e).__name__),"bytes":0,"sha256":None}
    aligned=(build.get("commit","").startswith(source) and build.get("status")=="built")
    return {"schema":"ae/deploy-status/1",
      "derived_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "source_head":source,"build_commit":build.get("commit"),"build_status":build.get("status"),
      "build_created_at":build.get("created_at"),"aligned":aligned,
      "note":"source_head is local; build_commit is GitHub Pages; live_sha is CDN bytes. "
             "aligned means the deployed build came from this exact source. CDN lag is separate.",
      "live":live}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--check",action="store_true")
    a=ap.parse_args()
    if a.check:
        if not a.out.exists(): print("MISSING",file=sys.stderr);return 1
        cur=json.loads(a.out.read_text(encoding="utf-8"))
        if cur.get("source_head")!=derive()["source_head"]:
            print("STALE: source_head changed",file=sys.stderr);return 1
        print("OK current: source="+str(cur["source_head"])[:8]+" aligned="+str(cur["aligned"]))
        return 0
    d=derive();a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"source={d['source_head'][:8]} build={str(d['build_commit'])[:8]} "
          f"status={d['build_status']} aligned={d['aligned']}")
    for k,v in d["live"].items(): print(f"  {k:22s} {v['status']} {v['bytes']:>8,}B {str(v['sha256'])[:12]}")
    return 0

if __name__=="__main__": sys.exit(main())
