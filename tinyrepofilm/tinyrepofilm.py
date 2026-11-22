#!/usr/bin/env python3
"""doctor for tinyrepofilm — report the real artifact, not a fabricated module.

The CLI lives in opensourceware/tinyrepofilm (the family convention expects
C:/æ/tinyrepofilm/tinyrepofilm.py). This doctor refuses to pretend a second
copy exists: it verifies the canonical source and its derived gates.
"""
import json, sys, importlib.util, subprocess, os
from pathlib import Path
CANON=Path(r"C:/æ/opensourceware/tinyrepofilm/tinyrepofilm.py")
D=Path(r"C:/æ/tinyrepofilm")
def doctor():
    if not CANON.exists(): return {"ok":False,"error":"canonical source missing"}
    src=CANON.read_text(encoding="utf-8")
    guards=["count_contributors","def gate(","tinyfilmmemory","next brief:","--publish"]
    missing=[g for g in guards if g not in src]
    e=os.environ.copy()
    for k in ("PYTHONPATH","PYTHONHOME","VIRTUAL_ENV"): e.pop(k,None)
    r=subprocess.run([sys.executable,str(CANON),"--target","openclaw/openclaw","--dry-run"],
       capture_output=True,text=True,timeout=60,encoding="utf-8",errors="replace",env=e)
    return {"ok":not missing and r.returncode==0,"source":str(CANON),
      "missing_guards":missing,"dry_run_rc":r.returncode,
      "note":"delegates to canonical source; no duplicate module"}
if __name__=="__main__": print(json.dumps(doctor(),ensure_ascii=False))
