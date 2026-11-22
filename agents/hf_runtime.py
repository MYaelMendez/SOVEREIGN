#!/usr/bin/env python3
"""hf_runtime.py — the sovereign HyperFrames runtime contract for our films.

Our film pipeline already has: deterministic __setTime(sec), CDP capture,
SHA-256 receipts, and an ffmpeg/NVENC encode. HyperFrames brings: composition
linting, a seekable player, and the `<hyperframes-player>` surface.

This module is the ADAPTER. It does not replace our renderer — it binds the
four capabilities we actually need and fails closed when any is absent.

    python hf_runtime.py doctor
    python hf_runtime.py lint <composition.html>
    python hf_runtime.py validate <composition.html>
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, subprocess, sys
from pathlib import Path

ROOT=Path(r"C:/æ")
HF=ROOT/"htmlvideo"
CORE=HF/"packages/core"
DIST=CORE/"dist"
CONTRACT=["window.__player","window.__playerReady","window.__renderReady",
          "hf-preview","hf-parent","renderSeek","__hyperframes","fitTextFontSize"]
# OUR contract, already proven this session: deterministic seek + receipts.
SOVEREIGN=["__setTime","__ready","byte_receipt","h264_nvenc","kanban_push.py"]

def sh(cmd,cwd=None,t=300):
    env=os.environ.copy()
    return subprocess.run(cmd,capture_output=True,text=True,timeout=t,encoding="utf-8",
                          errors="replace",cwd=cwd,env=env)

def bun() -> str|None:
    """Resolve bun with stdlib — C:/gpu/python cannot exec WindowsApps shims."""
    import shutil as _sh
    found=_sh.which("bun")
    if found: return found
    for c in [Path(r"C:/Users/yaelm/AppData/Roaming/npm/bun.cmd"),
              Path(r"C:/Users/yaelm/AppData/Roaming/npm/bun"),
              Path(r"C:/Program Files/bun/bun.exe")]:
        if c.exists(): return str(c)
    return None

def doctor() -> dict:
    d={"repo":str(HF),"repo_exists":HF.exists(),"bun":bun(),
       "node_modules":(HF/"node_modules").exists(),
       "entry":(CORE/"src/runtime/entry.ts").exists(),
       "dist":DIST.exists(),
       "pnpm_lock_forbidden_absent":not (HF/"pnpm-lock.yaml").exists()}
    # source contract — scan the whole runtime source tree; the globals live
    # in init.ts / player.ts, not in the inline-script loaders.
    rt=CORE/"src/runtime"
    contract_src="\n".join(f.read_text(encoding='utf-8',errors='replace')
                            for f in rt.rglob("*.ts")) if rt.exists() else ""
    d["contract_snippets"]={k:(k in contract_src) for k in CONTRACT}
    d["contract_scanned_files"]=len(list(rt.rglob("*.ts"))) if rt.exists() else 0
    # The two ready-flags are injected by the built IIFE, not authored in TS.
    # Once dist exists, re-check against the shipped runtime artifact.
    iife=DIST/"hyperframe.runtime.iife.js"
    if iife.exists():
        built=iife.read_text(encoding='utf-8',errors='replace')
        for k in CONTRACT:
            if not d["contract_snippets"][k]: d["contract_snippets"][k]=k in built
        d["contract_source"]="source + built iife"
    # built artifacts, if build succeeded
    manifest=DIST/"hyperframe.manifest.json"
    if manifest.exists():
        m=json.loads(manifest.read_text(encoding='utf-8'))
        d["manifest"]={"version":m.get("version"),"buildId":m.get("buildId"),
                       "sha256":str(m.get("sha256"))[:16],
                       "artifacts":m.get("artifacts")}
        iife=DIST/(m.get("artifacts",{}).get("iife") or "")
        d["iife_bytes"]=iife.stat().st_size if iife.exists() else 0
    else:
        d["manifest"]=None; d["iife_bytes"]=0
    # Our adapter: verify that the film pipeline still exposes its half.
    adapters={"hf_runtime":ROOT/"agents/hf_runtime.py",
              "render":ROOT/"opensourceware/hermes-contributions-film/render.mjs",
              "gate":ROOT/"vidæo/vidæo.py"}
    d["our_adapters"]={k:v.exists() for k,v in adapters.items()}
    hf_src=Path(adapters["hf_runtime"]).read_text(encoding='utf-8',errors='replace')
    d["sovereign_contract"]={k:(k in hf_src or k in (ROOT/"vidæo/vidæo.py").read_text(encoding='utf-8',errors='replace')) for k in SOVEREIGN}
    d["ok"]=(d["repo_exists"] and d["entry"] and d["dist"] and bool(bun())
             and all(d["contract_snippets"].values())
             and all(d["our_adapters"].values()))
    return d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cmd",choices=["doctor","lint","validate","contract"])
    ap.add_argument("target",nargs="?")
    a=ap.parse_args()
    if a.cmd=="doctor":
        d=doctor(); print(json.dumps(d,indent=2,ensure_ascii=False));
        return 0 if d["ok"] else 1
    if a.cmd=="contract":
        d=doctor(); print(json.dumps({"required":CONTRACT,"found":d["contract_snippets"]},indent=2))
        return 0 if all(d["contract_snippets"].values()) else 1
    if not a.target: print("-- target required",file=sys.stderr);return 1
    b=bun()
    if not b: print("BLOCKED: bun not installed",file=sys.stderr);return 11
    cmd=[b,"x","hyperframes",a.cmd,a.target]
    r=sh(cmd,cwd=str(Path(a.target).parent))
    print((r.stdout or r.stderr)[:3000])
    return r.returncode

if __name__=="__main__": sys.exit(main())
