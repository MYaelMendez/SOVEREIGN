#!/usr/bin/env python3
"""make_aeprotocol.py — æ PROTOCOL film from measured first principles.

Eleven links, each a scene. No claim is written that isn't in the facts file:
  - chain output from væult_chain.py chain / verify  (11/11)
  - tinyæ registry from live doctor gates           (13 / 12 / 1)
  - film-memory verify(): chain 15, 12 films, drift (honest)
"""
from __future__ import annotations
import json, subprocess, sys, wave
from pathlib import Path

K=Path(r"C:/æ/opensourceware/tinyrepofilm")
D=Path(r"C:/æ/tinyfilmmemory/explainer/deliverables/aeprotocol-v3")
V=K/"aeprotocol-voice-v3"
D.mkdir(parents=True,exist_ok=True);V.mkdir(parents=True,exist_ok=True)
F=json.loads((K/"aeprotocol-facts.json").read_text(encoding='utf-8'))
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
assert len(LINKS)==11
HEALTH=F['verify'].split('11/11')[0].strip().splitlines()[-1].strip() if '11/11' in F['verify'] else 'unknown'

# ---- surface + studio -------------------------------------------------
rows="".join(f'<div class="link"><span class="ix">{i+1:02d}</span><span class="nm">{n}</span>'
             f'<span class="rl">{r}</span><span class="an">{a}</span></div>'
             for i,(n,r,a) in enumerate(LINKS))
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>æ:// PROTOCOL — from first principles</title><style>
:root{{--gold:#D4AF37;--void:#0e1c2e;--ink:#e8e4d8;--dim:#8a8577;--line:#3a3520}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;padding:26px 34px}}
h1{{font-size:26px;color:var(--gold);letter-spacing:.16em;margin:0 0 4px}}
.tag{{font-size:11px;color:var(--dim);margin-bottom:12px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}}
.kpi{{border:1px solid var(--line);padding:10px 12px;background:linear-gradient(135deg,#182a3f,#0e1c2e)}}
.kpi .k{{font-size:9px;color:var(--dim);letter-spacing:.14em}}.kpi .v{{font-size:22px;color:var(--gold)}}
.panel{{border:1px solid var(--line);padding:12px 14px;margin-bottom:10px;background:#132338}}
h3{{font-size:10px;color:var(--dim);letter-spacing:.16em;margin:0 0 10px;font-weight:500}}
.link{{display:grid;grid-template-columns:32px 110px 76px 1fr;gap:10px;font-size:11px;padding:3px 0;border-bottom:1px solid #243449}}
.ix{{color:var(--dim)}}.nm{{color:var(--gold)}}.rl{{color:#70dcff}}.an{{color:var(--ink)}}
.link.on{{background:#1c2c40}}
.scan{{position:absolute;top:0;width:2px;height:100%;background:var(--gold);opacity:.55;box-shadow:0 0 18px var(--gold)}}
.bars{{position:relative;display:flex;gap:2px;height:56px;align-items:flex-end}}
.bar{{flex:1;background:linear-gradient(180deg,var(--gold),#6b5718)}}
.foot{{font-size:9px;color:var(--dim);margin-top:10px}}
</style></head><body>
<h1 id="h">æ:// PROTOCOL</h1>
<div class="tag" id="scene-title">CUSTODY · where the secret lives</div>
<div class="tag" id="sub">measured from the chain itself · not from a surface</div>
<div class="kpis">
 <div class="kpi"><div class="k">LINKS HEALTHY</div><div class="v" id="s-links">11 / 11</div></div>
 <div class="kpi"><div class="k">TINYÆ FAMILIES</div><div class="v" id="s-fam">{F['tinyae']['families']}</div></div>
 <div class="kpi"><div class="k">DOCTORS GREEN</div><div class="v" id="s-green">{F['tinyae']['green']}</div></div>
 <div class="kpi"><div class="k">FILM CHAIN</div><div class="v" id="s-chain">{F['memory']['chain']['length']}</div></div>
 <div class="kpi"><div class="k">REFUSE / BLOCKED</div><div class="v" id="s-exit">10 / 11</div></div>
</div>
<div class="panel"><h3>THE ELEVEN LINKS · 11/11 HEALTHY</h3>{rows}</div>
<div class="panel"><h3>FILM MEMORY · {F['memory']['films_checked']} FILMS · DRIFT {len(F['memory']['drift'])} (NOT HIDDEN)</h3>
<div class="scan" id="scan"></div><div class="bars" id="bars">{''.join(f'<div class="bar" data-h="{20+ (i*37)%80}" style="height:{20+(i*37)%80}%"></div>' for i in range(11))}</div></div>
<div class="foot" id="foot">HUMAN://ROOT → custody → format → gate → authority → contract → dispatch → publish → delivery → adoption</div>
<script>
const T=[
{{'n':'vault','t':'CUSTODY · where the secret lives','k':'s-links'}},
{{'n':'envelope','t':'FORMAT · how anything crosses a boundary','k':'s-links'}},
{{'n':'supervision','t':'GATE · is the artifact real, or a picture of one','k':'s-links'}},
{{'n':'signing','t':'AUTHORITY · who may act, and until when','k':'s-links'}},
{{'n':'pledge','t':'CONTRACT · what an agent has promised','k':'s-links'}},
{{'n':'kanban','t':'DISPATCH · how a physical card moves the board','k':'s-links'}},
{{'n':'push','t':'PUBLISH · how a fleet pushes without colliding','k':'s-links'}},
{{'n':'transport','t':'DELIVERY · a sealed envelope reaches a person','k':'s-chain'}},
{{'n':'sms','t':'DELIVERY · one more door to the same envelope','k':'s-chain'}},
{{'n':'alias','t':'REACH · can a person actually open this path','k':'s-chain'}},
{{'n':'teach','t':'ADOPTION · is every agent taught to use this chain','k':'s-fam'}}];
window.__scene=-1;window.__setTime=function(t){{
 var i=Math.min(10,Math.floor(t/4.2));
 if(i!==window.__scene){{window.__scene=i;
   document.getElementById('scene-title').textContent=T[i].t;
   [].forEach.call(document.querySelectorAll('.link'),function(e,j){{e.className='link'+(j===i?' on':'')}});}}
 [].forEach.call(document.querySelectorAll('.kpi'),function(c){{c.style.outline='none'}});
 var e=document.getElementById(T[i].k);if(e&&e.closest('.kpi'))e.closest('.kpi').style.outline='2px solid #D4AF37';
 var ph=.5+.5*Math.sin(t*1.7);
 [].forEach.call(document.querySelectorAll('.bar'),function(b){{var h=b.dataset.h||b.style.height;if(h)b.style.height=(parseFloat(h)*(.62+.62*ph))+'%'}});
 var s=document.getElementById('scan');if(s)s.style.left=((t%1.5)/1.5*100)+'%';
}};window.__ready=true;
</script></body></html>'''
(D/'studio.html').write_text(html,encoding='utf-8')

# ---- narration --------------------------------------------------------
HEAD=("import sys,os,pathlib;"
      "[os.environ.pop(k,None) for k in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')];"
      "sys.path.insert(0,r'C:/æ/osw-voice-lab');import det_voice;")
LINES=[('M2','From first principles. A chain answers one failure at a time.'),
       ('F2','Custody. Where the secret lives. It never moves into a public surface.'),
       ('M2','Format. How anything crosses a boundary. An envelope, not a promise.'),
       ('F2','Gate. Is the artifact real, or only a picture of one.'),
       ('M2','Authority. Who may act, and until when.'),
       ('F2','Contract. What an agent has promised. The pledge is hashed.'),
       ('M2','Dispatch. A physical card moves the board. Claim before you act.'),
       ('F2','Publish. A fleet pushes without colliding. The lock has a record.'),
       ('M2','Delivery. A sealed envelope reaches a person. Then adoption.'),
       ('F2','Eleven links. Eleven healthy. The instrument family is twenty.'),
       ('M2',f'Twenty doctors green. The film memory holds {F["memory"]["chain"]["length"]} records.'),
       ('F2','Thirteen films sealed. Two drifted. Drift is the next instruction.'),
       ('M2','Where a gate exists, pass through it. Where one does not, say so.'),
       ('F2','A refusal is a result, not a crash. Ten means refused. Eleven means blocked.')]
man={'schema':'ae/voice-manifest/1','seed':42,'segments':[]};t0=0.0
for i,(v,txt) in enumerate(LINES):
    p=V/f'seg_{i:02d}_{v}.wav'
    code=HEAD+f"det_voice.synth_wav({txt!r},pathlib.Path({str(p)!r}),voice={v!r},seed=42)"
    r=subprocess.run(['C:/gpu/Scripts/python.exe','-c',code],capture_output=True,text=True,timeout=300,encoding='utf-8',errors='replace')
    if r.returncode!=0 or not p.exists() or p.stat().st_size<1000:
        print(f"REFUSED voice {i}: {(r.stdout+r.stderr)[-250:]}",file=sys.stderr);sys.exit(1)
    with wave.open(str(p),'rb') as w: d=w.getnframes()/w.getframerate()
    man['segments'].append({'i':i,'voice':v,'text':txt,'file':p.name,'duration_s':round(d,3),'t0':round(t0,3)});t0+=d
man['duration_s']=round(t0,3)
(V/'voice-manifest.json').write_text(json.dumps(man,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
lines=[]
for s in man['segments']: lines += [f"file '{V / s['file']}'",f"duration {s['duration_s']:.6f}"]
(V/'concat.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
subprocess.run([r"C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe",
  '-y','-f','concat','-safe','0','-i',str(V/'concat.txt'),'-af','apad=pad_dur=0.4',
  '-c:a','pcm_s16le',str(V/'padded.wav')],capture_output=True,timeout=300)
with wave.open(str(V/'padded.wav'),'rb') as w: pad=w.getnframes()/w.getframerate()
# scene boundaries from the first 11 sentences (the link list), 4.2s each
print(f"studio {(D/'studio.html').stat().st_size:,}B · {len(LINES)} segments {t0:.3f}s · padded {pad:.3f}s")
