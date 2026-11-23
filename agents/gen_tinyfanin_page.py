#!/usr/bin/env python3
"""gen_tinyfanin_page.py — present tinyFANIN from its own derived truth.

    python gen_tinyfanin_page.py --truth <truth.json> --out tinyfanin.html

No numbers typed by hand: every value comes from the folded receipt record.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

def build(d:dict)->str:
    rows="".join(
      f'<div class="r"><span class="f">{m["file"]}</span>'
      f'<span class="d">{m["digest"][:16]}</span>'
      f'<span class="v">{m["verdict"]}</span>'
      f'<span class="c">{m.get("chain","")[:16]}</span></div>'
      for m in d.get("receipts",[]))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tinyFANIN — N receipts → ONE truth</title><style>
:root{{--gold:#D4AF37;--void:#050505;--ink:#e8e4d8;--dim:#8a8577;--line:#2a2620;--ok:#00ff9d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;padding:32px 30px 70px;line-height:1.5}}
h1{{font-size:30px;color:var(--gold);letter-spacing:.06em;margin:0}}
.sub{{font-size:12px;color:var(--dim);margin-bottom:22px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}}
.k{{border:1px solid var(--line);padding:12px}}.k .t{{font-size:9px;color:var(--dim);letter-spacing:.14em}}
.k .v{{font-size:23px;color:var(--gold);margin-top:4px}}
.panel{{border:1px solid var(--line);padding:14px 16px;margin-bottom:12px}}
h3{{font-size:10px;color:var(--dim);letter-spacing:.18em;margin:0 0 10px;font-weight:500}}
.r{{display:grid;grid-template-columns:1fr 150px 90px 150px;gap:10px;font-size:11px;padding:5px 0;border-bottom:1px solid var(--line)}}
.f{{color:var(--ink)}}.d{{color:var(--gold)}}.v{{color:var(--dim)}}.c{{color:#70dcff}}
.tag{{font-size:11px;color:var(--dim)}}b{{color:var(--gold)}}
a{{color:var(--gold);font-size:11px;margin-right:14px}}
</style></head><body>
<h1>tinyFANIN</h1>
<div class="sub">N receipts → ONE truth · the number one skill, executable · no member skipped</div>
<div class="kpis">
 <div class="k"><div class="t">MEMBERS FOLDED</div><div class="v">{d.get('members')}</div></div>
 <div class="k"><div class="t">VERDICTS</div><div class="v">{len(d.get('verdicts',[]))}</div></div>
 <div class="k"><div class="t">HEAD</div><div class="v">{str(d.get('head',''))[:12]}</div></div>
 <div class="k"><div class="t">SCHEMA</div><div class="v">{str(d.get('schema','')).split('/')[-1]}</div></div>
</div>
<div class="panel"><h3>INTENT</h3><div class="tag">{d.get('intent')} · source {d.get('source')}</div></div>
<div class="panel"><h3>THE FOLDED RECEIPTS · HASH CHAIN IN ORDER</h3>{rows}</div>
<div class="panel"><h3>THE RULE</h3>
<div class="tag">A receipt without a measured digest is <b>REFUSED</b>, never skipped. A tampered digest fails <b>verify</b> with exit 10 and names the broken members. The head is the only truth; everything else is evidence.</div></div>
<div style="margin-top:16px">
 <a href="./tiny.html">constellation →</a><a href="./tinyae.html">registry →</a>
 <a href="./tinyrepofilm.html">tinyRepoFilm →</a><a href="./ae-protocol.html">æ protocol →</a>
 <a href="./tinyfanin-truth.json">truth JSON →</a></div>
</body></html>'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--truth",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    d=json.loads(a.truth.read_text(encoding="utf-8"))
    html=build(d)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(html,encoding="utf-8")
    body=html.encode("utf-8")
    print(f"wrote {a.out} {len(body):,}B sha={hashlib.sha256(body).hexdigest()[:12]} "
          f"members={d.get('members')} head={str(d.get('head'))[:12]}")
    return 0

if __name__=="__main__": sys.exit(main())
