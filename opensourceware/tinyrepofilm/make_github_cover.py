#!/usr/bin/env python3
"""make_github_cover.py — section-cover film about the GitHub institution.

Measured numbers come from the GitHub REST API. Reported numbers come from
public sources and are LABELED as reported on the surface and in the voice.
Nothing here claims authorship of GitHub's work.
"""
from __future__ import annotations
import json, subprocess, sys, wave
from pathlib import Path
R=Path(r"C:/æ/opensourceware/tinyrepofilm")
D=Path(r"C:/æ/tinyfilmmemory/explainer/deliverables/github-cover")
V=R/"github-cover-voice"
D.mkdir(parents=True,exist_ok=True);V.mkdir(parents=True,exist_ok=True)
f=json.loads(Path(r"C:/æ/github-pages/github-institution.json").read_text(encoding='utf-8'))
m=f['measured'];rp=f['reported']
# measured timeline bars: service 2008, acquisition 2018, 1B repos 2025, agent era 2026
html='''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#0e1c2e;color:#e8e4d8;font-family:'JetBrains Mono',monospace;padding:34px 40px}
h1{color:#D4AF37;font-size:38px;letter-spacing:.1em;margin:0 0 4px}
.sub{color:#8a8577;font-size:13px;margin-bottom:18px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}
.k{border:1px solid #3a3520;padding:12px;background:#132338}.k .t{font-size:10px;color:#8a8577;letter-spacing:.12em}
.k .v{font-size:26px;color:#D4AF37}.k .s{font-size:9px;color:#70dcff}
.panel{border:1px solid #3a3520;padding:14px;margin-bottom:10px;background:#132338}
h3{font-size:10px;color:#8a8577;letter-spacing:.16em;margin:0 0 12px}
.ev{display:grid;grid-template-columns:80px 1fr;gap:10px;font-size:13px;padding:4px 0;border-bottom:1px solid #243449}
.yr{color:#D4AF37}.reported{color:#ffd166}
#scan{position:absolute;top:0;width:2px;height:100%;background:#D4AF37;box-shadow:0 0 18px #D4AF37;opacity:.6}
.bar{height:24px;background:linear-gradient(90deg,#D4AF37,#6b5718);margin:6px 0;transition:none}
</style></head><body><div id="scan"></div>
<h1 id="title">github:// — the institution</h1>
<div class="sub" id="sub">measured by REST · reported labelled · no authorship claimed</div>
<div class="kpis">
<div class="k"><div class="t">ORG REPOS</div><div class="v" id="a">__REPOS__</div><div class="s">MEASURED</div></div>
<div class="k"><div class="t">FOLLOWERS</div><div class="v" id="b">__FOLLOWERS__</div><div class="s">MEASURED</div></div>
<div class="k"><div class="t">DOCS STARS</div><div class="v" id="c">__STARS__</div><div class="s">MEASURED</div></div>
<div class="k"><div class="t">DOCS FORKS</div><div class="v" id="d">__FORKS__</div><div class="s">MEASURED</div></div>
</div>
<div class="panel"><h3>THE RECORD · MEASURED WHERE POSSIBLE</h3>
<div class="ev"><span class="yr">2008</span><span>service launches · company formed 2007</span></div>
<div class="ev"><span class="yr">2018</span><span>Microsoft acquires GitHub for $7.5B · <span class="reported">REPORTED</span></span></div>
<div class="ev"><span class="yr">2025</span><span>one billion repositories · <span class="reported">REPORTED</span></span></div>
<div class="ev"><span class="yr">2026</span><span>the agent era · <span class="reported">REPORTED</span></span></div>
</div>
<div class="panel"><h3>AN INSTITUTION, NOT AN AUTHOR</h3>
<div class="bar" data-h="22" style="width:22%"></div>
<div class="bar" data-h="48" style="width:48%"></div>
<div class="bar" data-h="78" style="width:78%"></div>
<div class="bar" data-h="100" style="width:100%"></div>
</div>
<script>window.__setTime=function(t){{
 var ph=.5+.5*Math.sin(t*1.7);
 var s=document.getElementById('scan');s.style.left=((t%2)/2*100)+'%';
 [].forEach.call(document.querySelectorAll('.bar'),function(b){{
   var h=b.dataset.h;b.style.width=(parseFloat(h)*(.6+.55*ph))+'%';}});
 var i=Math.min(3,Math.floor(t/4));
 var ids=['a','b','c','d'];
 [].forEach.call(document.querySelectorAll('.k'),function(k){{k.style.outline='none'}});
 var e=document.getElementById(ids[i]);if(e)e.closest('.k').style.outline='2px solid #D4AF37';
}};window.__ready=true;</script></body></html>'''
html=(html.replace('__REPOS__',f"{m['org_public_repos']:,}").replace('__FOLLOWERS__',f"{m['org_followers']:,}")
      .replace('__STARS__',f"{m['docs_stars']:,}").replace('__FORKS__',f"{m['docs_forks']:,}"))
(D/'studio.html').write_text(html,encoding='utf-8')

lines=[("M2",f"github dot com. {m['org_public_repos']} official repositories. {m['org_followers']:,} followers."),
       ("F2",f"The docs repository: {m['docs_stars']:,} stars, {m['docs_forks']:,} forks. Measured today."),
       ("M2","Founded two thousand seven. Acquired by Microsoft in two thousand eighteen for seven point five billion. Reported."),
       ("F2","One billion repositories in two thousand twenty five. Reported, not measured here."),
       ("M2","An institution that hosts the work. It is not the work itself."),
       ("F2","We film the platform. We never claim authorship of it.")]
HEAD=("import sys,os,pathlib;"
 "[os.environ.pop(k,None) for k in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')];"
 "sys.path.insert(0,r'C:/æ/osw-voice-lab');import det_voice;")
segs=[];t0=0.0
for i,(v,txt) in enumerate(lines):
    wav=V/f"seg_{i:02d}_{v}.wav"
    code=HEAD+f"det_voice.synth_wav({txt!r},pathlib.Path({str(wav)!r}),voice={v!r},seed=42)"
    r=subprocess.run(['C:/gpu/Scripts/python.exe','-c',code],capture_output=True,text=True,timeout=300,encoding='utf-8',errors='replace')
    if r.returncode!=0 or not wav.exists(): print("REFUSED voice",i,(r.stdout+r.stderr)[-200:],file=sys.stderr);sys.exit(1)
    with wave.open(str(wav),'rb') as w: d=w.getnframes()/w.getframerate()
    segs.append({"i":i,"voice":v,"text":txt,"file":wav.name,"duration_s":round(d,3),"t0":round(t0,3)});t0+=d
(V/'voice-manifest.json').write_text(json.dumps({"segments":segs,"total_s":round(t0,3)},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
cl=[]
for sg in segs: cl += [f"file '{V / sg['file']}'", f"duration {sg['duration_s']:.6f}"]
(V/'concat.txt').write_text('\n'.join(cl)+'\n',encoding='utf-8')
ff=r"C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe"
subprocess.run([ff,'-y','-f','concat','-safe','0','-i',str(V/'concat.txt'),'-af','apad=pad_dur=0.4','-c:a','pcm_s16le',str(V/'padded.wav')],capture_output=True,timeout=300)
with wave.open(str(V/'padded.wav'),'rb') as w: total=w.getnframes()/w.getframerate()
print(f"studio {(D/'studio.html').stat().st_size:,}B · {len(segs)} segs {t0:.3f}s · padded {total:.3f}s")
