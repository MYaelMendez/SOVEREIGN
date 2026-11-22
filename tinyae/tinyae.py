#!/usr/bin/env python3
"""doctor for tinyæ — the family registry derived from live doctors."""
import json, subprocess, sys, os
from pathlib import Path
GEN=Path(r"C:/æ/agents/gen_tinyae.py")
REG=Path(r"C:/æ/github-pages/tinyae-registry.json")
def doctor():
    if not GEN.exists() or not REG.exists(): return {"ok":False,"error":"generator or registry missing"}
    e=os.environ.copy()
    for k in ("PYTHONPATH","PYTHONHOME","VIRTUAL_ENV"): e.pop(k,None)
    r=subprocess.run([sys.executable,str(GEN),"--out",str(REG),"--check"],
       capture_output=True,text=True,timeout=120,encoding="utf-8",errors="replace",env=e)
    d=json.loads(REG.read_text(encoding="utf-8"))
    return {"ok":r.returncode==0,"check":r.stdout.strip() or r.stderr.strip()[:120],
      "families":d.get("families"),"green":d.get("green"),"not_green":d.get("not_green")}
if __name__=="__main__": print(json.dumps(doctor(),ensure_ascii=False))
