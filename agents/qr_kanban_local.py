#!/usr/bin/env python
"""Local-first k\u00e6nb\u00e6n card mint+decode using ONLY on-disk resources:
  qrcode (pure python) + PIL + cv2.QRCodeDetector (NO pyzbar, NO supervision)."""
import argparse, json, os, sys, time
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFont
import cv2


def _imread(path):
    """cv2.imread cannot read a non-ASCII path on Windows (C:\æ\... -> None)."""
    import cv2
    import numpy as np
    buf = np.fromfile(str(path), dtype=np.uint8)
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)

VERBS = {"claim":"claim a task","complete":"mark task done","block":"mark blocked","unblock":"clear block","archive":"archive","inspect":"show","list":"print board","init":"create db"}

def make_payload(v,t):
    return json.dumps({"cmd":f"kanban://{v} {t}" if t else f"kanban://{v}","verb":v,"task_id":t},separators=(",",":"))

def sign(p):
    from hashlib import sha256
    return "sha256:"+sha256((os.environ.get("HERMES_KANBAN_SIG","\u00e6-local-default")+p).encode()).hexdigest()[:32]

def mint_card(v,t,out):
    assert v in VERBS, f"unknown verb {v!r}"
    p=make_payload(v,t); sig=sign(p)
    img=qrcode.make(p,box_size=10,border=3).convert("RGB")
    W,H=img.size
    canvas=Image.new("RGB",(W,H+48),(5,5,5))
    canvas.paste(img,(0,0,W,H))  # 4-item box — was the bug
    d=ImageDraw.Draw(canvas)
    label=f"{v.upper()}  {t or chr(8212)}  ::  \u00e6://kanban[{sig[:7]}]"
    try: font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",15)
    except Exception: font=ImageFont.load_default()
    d.text((10,H+12),label,fill=(212,175,55),font=font)
    d.text((10,H+28),p[:64]+"...",fill=(111,106,92),font=font)
    Path(out).parent.mkdir(parents=True,exist_ok=True); canvas.save(out,"PNG")
    return out

def scan_card(path):
    img=_imread(path)
    if img is None: return {"path":path,"ok":False,"error":"unreadable"}
    up=cv2.resize(img,None,fx=1.6,fy=1.6,interpolation=cv2.INTER_CUBIC)
    data,pts,_=cv2.QRCodeDetector().detectAndDecode(up)
    r={"path":path,"ok":bool(data)}
    if data:
        try:
            o=json.loads(data); r["payload"]=o; r["verb"]=o.get("verb"); r["task_id"]=o.get("task_id"); r["cmd"]=o.get("cmd")
        except Exception as e: r["decode_error"]=str(e)
    r["points"]=None if pts is None else pts.shape[0]
    return r

def main(argv):
    ap=argparse.ArgumentParser(prog="qr_kanban_local"); sub=ap.add_subparsers(dest="cmd",required=True)
    pc=sub.add_parser("card"); pc.add_argument("verb",choices=sorted(VERBS)); pc.add_argument("task_id",nargs="?"); pc.add_argument("--out",default="card.png")
    ps=sub.add_parser("scan"); ps.add_argument("path")
    pv=sub.add_parser("verbs")
    a=ap.parse_args(argv)
    if a.cmd=="card":
        out=mint_card(a.verb,a.task_id,a.out)
        print(json.dumps({"ok":True,"verb":a.verb,"task_id":a.task_id,"out":out,"payload_keys":list(json.loads(make_payload(a.verb,a.task_id)).keys())},indent=2))
    elif a.cmd=="scan": print(json.dumps(scan_card(a.path),indent=2))
    elif a.cmd=="verbs": print(json.dumps(VERBS,indent=2))

if __name__=="__main__": main(sys.argv[1:])