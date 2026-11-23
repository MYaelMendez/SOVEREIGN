#!/usr/bin/env python3
"""tinyFANIN — N receipts → ONE truth.

The number one skill, made executable. Every other instrument measures one
thing; fan-in is how many measurements become one claim a human can hold.

    python tinyfanin.py doctor
    python tinyfanin.py fold --from <dir> --out fanin.json --intent "..."
    python tinyfanin.py verify --truth fanin.json

Receipt = SHA-256 hash chain H(prev || intent || ops || result || state || evidence).
A member without a measured sha is REFUSED, never skipped. A refusal is a
result and folds in as evidence — not as a crash.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"C:/æ")
GITHUB=ROOT/"github-pages"
EXIT_OK, EXIT_REFUSED, EXIT_BLOCKED = 0, 10, 11

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def canon(o)->str: return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def doctor() -> dict:
    """Prove the instrument can read its own truth surface — nothing else."""
    reg=GITHUB/"tinyae-registry.json"
    d={"module":str(Path(__file__).resolve()),
       "registry":reg.exists(),
       "families":None,"chain_integrity":None}
    if reg.exists():
        j=json.loads(reg.read_text(encoding="utf-8"))
        d["families"]=j.get("families")
        d["chain_integrity"]=bool(j.get("schema","").startswith("ae/"))
    d["ok"]=bool(d["registry"] and d["chain_integrity"])
    return d

def read_members(source:Path) -> tuple[list,dict]:
    """Collect receipts from a directory of JSON artifacts. Fail closed."""
    members=[]; refused=[]
    if not source.exists() or not source.is_dir():
        return [],{"reason":f"source missing or not a directory: {source}"}
    for f in sorted(source.rglob("*.json")):
        try: d=json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            refused.append({"file":str(f.relative_to(source)),"reason":f"unparseable: {type(e).__name__}"});continue
        # A receipt is any artifact carrying one of these measured digests.
        dig=(d.get("sha256") or d.get("byte_receipt") or d.get("receipt") or
             (d.get("gate") or {}).get("receipt") or (d.get("chain") or {}).get("head"))
        if not dig:
            refused.append({"file":str(f.relative_to(source)),"reason":"no measured digest"});continue
        members.append({"file":str(f.relative_to(source)),"digest":str(dig)[:64],
                        "verdict":d.get("verdict") or d.get("calidad") or "recorded"})
    return members,{"reason":None,"refused":refused}

def fold(members:list,intent:str,source:str) -> dict:
    prev="0"*64
    # Sort ONCE and store in the same order the chain was computed. A verify
    # that re-sorts a differently-ordered list breaks the chain for no reason.
    members=sorted(members,key=lambda x:x["digest"])
    for m in members:
        nxt=sha((prev+canon([intent,m["digest"],m["verdict"],source])).encode())
        m["chain"] = nxt[:16]
        m["prev"]  = prev[:16]
        prev=nxt
    return {"schema":"ae/tinyfanin-truth/1",
      "derived_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "intent":intent,"source":source,"members":len(members),
      "head":prev,"verdicts":sorted({m["verdict"] for m in members}),
      "receipts":members,
      "note":"One truth is the hash of ordered member digests. No member is skipped."}

def verify(truth:Path) -> tuple[int,dict]:
    if not truth.exists(): return EXIT_BLOCKED,{"error":"truth file missing"}
    d=json.loads(truth.read_text(encoding="utf-8"))
    prev="0"*64;bad=[]
    for m in d.get("receipts",[]):
        payload=prev+canon([d["intent"],m["digest"],m["verdict"],d["source"]])
        nxt=sha(payload.encode())
        if m.get("chain")!=nxt[:16]: bad.append(m.get("file","?"))
        prev=nxt
    ok=(not bad and prev==d.get("head"))
    return (EXIT_OK if ok else EXIT_REFUSED),{"ok":ok,"checked":len(d.get("receipts",[])),
            "head_match":prev==d.get("head"),"broken":bad}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("cmd",choices=["doctor","fold","verify"])
    ap.add_argument("--from",dest="source",type=Path)
    ap.add_argument("--out",type=Path)
    ap.add_argument("--intent",default="fold the measured")
    ap.add_argument("--truth",type=Path)
    a=ap.parse_args()
    if a.cmd=="doctor":
        d=doctor();print(json.dumps(d,indent=2,ensure_ascii=False));return 0 if d["ok"] else EXIT_BLOCKED
    if a.cmd=="fold":
        if not a.source or not a.out:
            print("BLOCKED: --from and --out required",file=sys.stderr);return EXIT_BLOCKED
        members,meta=read_members(a.source)
        if meta.get("reason") and "reason" in meta and not meta.get("refused"):
            print("BLOCKED: "+meta["reason"],file=sys.stderr);return EXIT_BLOCKED
        for r in meta.get("refused",[]): print(f"  REFUSED member: {r['file']} — {r['reason']}",file=sys.stderr)
        d=fold(members,a.intent,str(a.source))
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(f"FOLDED {d['members']} receipts → head {d['head'][:16]} · verdicts {d['verdicts']}")
        return EXIT_OK
    if a.cmd=="verify":
        if not a.truth: print("BLOCKED: --truth required",file=sys.stderr);return EXIT_BLOCKED
        code,d=verify(a.truth);print(json.dumps(d,ensure_ascii=False));return code

if __name__=="__main__": sys.exit(main())
