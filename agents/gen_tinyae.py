#!/usr/bin/env python3
"""gen_tinyae.py — derive the tinyæ family registry from live doctor gates.

    python gen_tinyae.py --out tinyae-registry.json
    python gen_tinyae.py --out ... --check

The family is NOT a hand-written list: names come from tinylab.doctor(),
status comes from each instrument's own `doctor` subcommand run now.
A missing or failing doctor is reported, never painted green.
"""
from __future__ import annotations
import argparse, importlib.util, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"C:/æ")
PY=r"C:/gpu/Scripts/python.exe"

def lab_families() -> list:
    # Canonical family is tiny_family.py's FAMILY (the constellation surface).
    # tinylab.doctor() reports a different, older set — using it made the
    # registry say 13 while tiny.html measured 20. One source of truth.
    spec=importlib.util.spec_from_file_location("tiny_family",ROOT/"tiny/tiny_family.py")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return [entry[0] for entry in m.FAMILY]

def doctor(name:str) -> dict:
    f=ROOT/name/f"{name}.py"
    if not f.exists(): return {"ok":False,"status":"MODULE MISSING"}
    env=os.environ.copy()
    for k in ("PYTHONPATH","PYTHONHOME","VIRTUAL_ENV"): env.pop(k,None)
    try:
        r=subprocess.run([PY,str(f),"doctor"],capture_output=True,text=True,timeout=30,
                         encoding="utf-8",errors="replace",env=env,cwd=str(ROOT/name))
    except subprocess.TimeoutExpired:
        return {"ok":False,"status":"TIMEOUT (30s)"}
    out=(r.stdout or "").strip()
    try: d=json.loads(out)
    except Exception: return {"ok":False,"status":f"NON-JSON rc={r.returncode}"}
    if not isinstance(d,dict): return {"ok":False,"status":"UNEXPECTED SHAPE"}
    return {"ok":bool(d.get("ok")), "status":"GREEN" if d.get("ok") else "NOT GREEN",
        "reason":str(d.get("error") or d.get("reason") or ("engine: null (no supervision engine resolved)" if d.get("engine") is None else "doctor ok:false, no reason field"))[:180],
            "rc":r.returncode}

def derive() -> dict:
    fam=lab_families()
    instruments=[]
    for n in sorted(fam):
        d=doctor(n)
        instruments.append({"name":n,"module":(ROOT/n/f"{n}.py").exists(),**d})
    green=[i["name"] for i in instruments if i["ok"]]
    return {"schema":"ae/tinyae-registry/1","name":"tinyæ",
      "derived_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "source":"tinylab.doctor() names + each instrument's own `doctor` subcommand, run now",
      "families":len(instruments),"green":len(green),"not_green":len(instruments)-len(green),
      "green_names":green,"instruments":instruments,
      "note":"Measured now. Missing/failing doctors are reported as such, never painted green."}

def html(d:dict) -> str:
    rows="".join(
      f'<tr><td>{i["name"]}</td><td class="{"ok" if i["ok"] else "bad"}">'
      f'{"GREEN" if i["ok"] else "NOT GREEN"}</td>'
      f'<td>{i.get("reason") or i.get("status") or "—"}</td></tr>' for i in d["instruments"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tinyæ — the instrument family</title><style>
:root{{--gold:#D4AF37;--void:#050505;--ink:#e8e4d8;--dim:#8a8577;--line:#2a2620}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;padding:34px 30px 70px}}
h1{{font-size:clamp(28px,5vw,52px);color:var(--gold);letter-spacing:.04em;margin:0 0 6px}}
.tag{{color:var(--dim);font-size:12px;margin-bottom:24px}}
.kpi{{display:flex;gap:30px;border-block:1px solid var(--line);padding:14px 0;margin-bottom:22px}}
.kpi b{{color:var(--gold);font-size:26px;display:block}}span{{font-size:10px;color:var(--dim);letter-spacing:.14em}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
td{{padding:7px 10px;border-bottom:1px solid var(--line)}}td:first-child{{color:var(--gold)}}
td.ok{{color:#00ff9d}}td.bad{{color:#ff7a6b}}
a{{color:var(--gold);font-size:12px;margin-right:18px}}
p{{font-size:12px;color:var(--dim);max-width:760px}}
</style></head><body>
<h1>tinyæ</h1><div class="tag">one prefix · many instruments · one receipt chain · #opensourceware</div>
<div class="kpi"><div><b>{d['families']}</b><span>FAMILIES</span></div>
 <div><b>{d['green']}</b><span>DOCTORS GREEN NOW</span></div>
 <div><b>{d['not_green']}</b><span>NOT GREEN / UNTESTED</span></div></div>
<table><tbody>{rows}</tbody></table>
<p>Measured at {d['derived_at']} from {d['source']}. This is not a claim copied from a surface —
every row is a doctor gate run for this read.</p>
<div style="margin-top:24px">
 <a href="./tinyrepofilm.html">tinyRepoFilm →</a>
 <a href="./the-film-is-an-instrument.html">the film is an instrument →</a>
 <a href="./tinyae-registry.json">REGISTRY →</a>
 <a href="./homebase.html">homebase →</a></div>
</body></html>'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--html",type=Path);ap.add_argument("--check",action="store_true")
    a=ap.parse_args()
    if a.check:
        cur=json.loads(a.out.read_text(encoding="utf-8"))
        if cur.get("families")!=len(lab_families()):
            print("STALE: family count changed",file=sys.stderr);return 1
        print("OK current:",cur["families"],"families");return 0
    d=derive();a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if a.html: a.html.write_text(html(d),encoding="utf-8")
    print(f"{d['name']}: {d['families']} families · {d['green']} green · {d['not_green']} not green")
    return 0

if __name__=="__main__": sys.exit(main())
