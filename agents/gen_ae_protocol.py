#!/usr/bin/env python3
"""gen_ae_protocol.py — the protocol surface is DERIVED, never hand-maintained.

    python gen_ae_protocol.py --facts ae-protocol-facts.json --out ae-protocol.html
    python gen_ae_protocol.py --facts ... --out ... --check

Every number comes from ae-protocol-facts.json (itself derived from
væult_chain verify + tinyae registry + tinyfilmmemory.verify). The attached
context kept showing 13/12/15/12 while reality moved — this ends that drift.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

LINKS=[("vault","custody","where the secret lives"),
 ("envelope","format","how anything crosses a boundary"),
 ("supervision","gate","is the artifact real, or a picture of one"),
 ("signing","authority","who may act, and until when"),
 ("pledge","contract","what an agent has promised"),
 ("kanban","dispatch","how a physical card moves the board"),
 ("push","publish","how a fleet pushes without colliding"),
 ("transport","delivery","how a sealed envelope reaches a person"),
 ("sms","delivery","one more door to the same envelope"),
 ("alias","reach","can a person actually open this path"),
 ("teach","adoption","is every agent taught to use this chain")]

def build(d:dict)->str:
    rows="".join(f'<div class="link"><span class="ix">{i+1:02d}</span><span class="nm">{n}</span>'
                 f'<span class="rl">{r}</span><span class="an">{a}</span></div>'
                 for i,(n,r,a) in enumerate(LINKS))
    ex=d['exit_codes']
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>æ:// PROTOCOL — from first principles</title><style>
:root{{--gold:#D4AF37;--void:#0e1c2e;--ink:#e8e4d8;--dim:#8a8577;--line:#3a3520}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;padding:26px 34px}}
h1{{font-size:26px;color:var(--gold);letter-spacing:.16em;margin:0 0 4px}}
.tag{{font-size:11px;color:var(--dim);margin-bottom:12px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:12px}}
.kpi{{border:1px solid var(--line);padding:10px 12px;background:#132338}}
.kpi .k{{font-size:9px;color:var(--dim);letter-spacing:.14em}}.kpi .v{{font-size:22px;color:var(--gold)}}
.panel{{border:1px solid var(--line);padding:12px 14px;margin-bottom:10px;background:#132338}}
h3{{font-size:10px;color:var(--dim);letter-spacing:.16em;margin:0 0 10px;font-weight:500}}
.link{{display:grid;grid-template-columns:32px 110px 76px 1fr;gap:10px;font-size:11px;padding:3px 0;border-bottom:1px solid #243449}}
.ix{{color:var(--dim)}}.nm{{color:var(--gold)}}.rl{{color:#70dcff}}.an{{color:var(--ink)}}
.foot{{font-size:9px;color:var(--dim);margin-top:10px}}
a{{color:var(--gold);font-size:11px;margin-right:14px}}
</style></head><body>
<h1>æ:// PROTOCOL</h1>
<div class="tag" id="scene-title">CUSTODY · where the secret lives</div>
<div class="tag">{d['links_detail']} · derived from the chain itself, not from a surface</div>
<div class="kpis">
 <div class="kpi"><div class="k">LINKS HEALTHY</div><div class="v" id="s-links">{d['links_healthy']}</div></div>
 <div class="kpi"><div class="k">TINYÆ FAMILIES</div><div class="v" id="s-fam">{d['tinyae_families']}</div></div>
 <div class="kpi"><div class="k">DOCTORS GREEN</div><div class="v" id="s-green">{d['doctors_green']}/{d['doctors_total']}</div></div>
 <div class="kpi"><div class="k">FILM CHAIN</div><div class="v" id="s-chain">{d['film_chain']}</div></div>
 <div class="kpi"><div class="k">REFUSE / BLOCKED</div><div class="v" id="s-exit">{ex['REFUSED']} / {ex['BLOCKED']}</div></div>
</div>
<div class="panel"><h3>THE ELEVEN LINKS · {d['links_healthy']} HEALTHY</h3>{rows}</div>
<div class="panel"><h3>FILM MEMORY · {d['films']} FILMS · DRIFT {d['drift_shown']} SHOWN · OPEN DRIFT {len(d['open_drift'])}</h3>
<div class="tag">{d['doctors_note']}</div></div>
<div class="foot">HUMAN://ROOT → custody → format → gate → authority → contract → dispatch → publish → delivery → adoption</div>
<div style="margin-top:14px">
 <a href="./ae-protocol-facts.json">FACTS JSON →</a>
 <a href="./deploy-status.json">DEPLOY STATUS →</a>
 <a href="./tinyrepofilm.html">tinyRepoFilm →</a>
 <a href="./homebase.html">homebase →</a></div>
</body></html>'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--facts',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--check',action='store_true')
    a=ap.parse_args()
    d=json.loads(a.facts.read_text(encoding='utf-8'))
    html=build(d)
    if a.check:
        if not a.out.exists(): print('MISSING',file=sys.stderr);return 1
        cur=a.out.read_text(encoding='utf-8')
        if cur!=html:
            print('STALE: surface differs from derived facts',file=sys.stderr);return 1
        print('OK current: surface == facts')
        return 0
    a.out.write_text(html,encoding='utf-8')
    body=html.encode('utf-8')
    print(f"wrote {a.out}: {len(body):,}B sha={hashlib.sha256(body).hexdigest()[:12]} "
          f"links={d['links_healthy']} families={d['tinyae_families']} "
          f"doctors={d['doctors_green']}/{d['doctors_total']} chain={d['film_chain']} films={d['films']}")
    return 0

if __name__=='__main__': sys.exit(main())
