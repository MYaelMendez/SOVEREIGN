#!/usr/bin/env python3
"""render_film.py — the wired render stage for tinyRepoFilm.

One input (facts + story already gated) → voice → CDP frames → NVENC →
vidæo gate (frame + byte receipt) → tinyfilmmemory seal → decision record.

Every stage fails closed with an explicit exit code:
    0 FILMED · 10 REFUSED · 11 BLOCKED
"""
from __future__ import annotations
import json, os, socket, subprocess, sys, time, urllib.request, wave
from pathlib import Path

ROOT=Path(r"C:/æ")
KITS=ROOT/"opensourceware"
EXIT_OK, EXIT_REFUSED, EXIT_BLOCKED = 0, 10, 11

def refuse(reason, code=EXIT_REFUSED):
    return {"verdict":"REFUSED" if code==EXIT_REFUSED else "BLOCKED",
            "reason":reason,"exit_code":code}

def render_film(target:str, story:list, facts:dict, out:Path,
                voice_py:str, gate_py:str) -> tuple[int,dict]:
    work=out/f"film-{target.replace('/','_')}"
    work.mkdir(parents=True,exist_ok=True)
    voice=work/"voice"; voice.mkdir(exist_ok=True)
    frames=work/"frames"; frames.mkdir(exist_ok=True)

    # 0) OPTIONAL HyperFrames gate — fails closed, never silently skipped.
    composition=os.environ.get("HF_COMPOSITION")
    if composition:
        gate=ROOT/"agents/hf_runtime.py"
        if not Path(composition).exists() or not gate.exists():
            return EXIT_BLOCKED,refuse("HF gate: composition or adapter missing",EXIT_BLOCKED)
        r=subprocess.run([sys.executable,str(gate),"validate",composition],
          capture_output=True,text=True,timeout=600,encoding="utf-8",errors="replace")
        if r.returncode!=0:
            return EXIT_REFUSED,refuse(f"HyperFrames validate failed: {(r.stdout+r.stderr)[-180:]}")
        print("  HF gate: PASS (No console errors)")

    # 1) deterministic narration, every number bound to the derived record
    lines=[("M2",f"From public GitHub. {target}. {facts['total_stars']:,} stars, {facts['total_forks']:,} forks."),
           ("F2",f"{facts['commits_52w']:,} commits across fifty two weeks."),
           ("M2","Every number here is bound to the derived record.")]
    head=("import sys,os,pathlib;"
      "[os.environ.pop(k,None) for k in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')];"
      "sys.path.insert(0,r'C:/æ/osw-voice-lab');import det_voice;")
    segs=[];t0=0.0
    for i,(v,txt) in enumerate(lines):
        wav=voice/f"seg_{i:02d}_{v}.wav"
        code=head+f"det_voice.synth_wav({txt!r},pathlib.Path({str(wav)!r}),voice={v!r},seed=42)"
        r=subprocess.run([voice_py,'-c',code],capture_output=True,text=True,timeout=300,encoding='utf-8',errors='replace')
        if r.returncode!=0 or not wav.exists() or wav.stat().st_size<1000:
            return EXIT_BLOCKED,refuse(f"voice stage {i}: {(r.stdout+r.stderr)[-160:]}",EXIT_BLOCKED)
        with wave.open(str(wav),'rb') as w: d=w.getnframes()/w.getframerate()
        segs.append({"i":i,"voice":v,"text":txt,"file":wav.name,"duration_s":round(d,3),"t0":round(t0,3)});t0+=d
    concat=[]
    for sg in segs:
        concat += [f"file '{voice / sg['file']}'", f"duration {sg['duration_s']:.6f}"]
    (voice/'concat.txt').write_text('\n'.join(concat)+'\n',encoding='utf-8')
    ffdir=Path(r"C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin")
    ffmpeg=ffdir/'ffmpeg.exe'
    if not ffmpeg.exists(): return EXIT_BLOCKED,refuse("ffmpeg 7.1 nvenc missing",EXIT_BLOCKED)
    r=subprocess.run([str(ffmpeg),'-y','-f','concat','-safe','0','-i',str(voice/'concat.txt'),
       '-af','apad=pad_dur=0.4','-c:a','pcm_s16le',str(voice/'padded.wav')],
       capture_output=True,text=True,timeout=300)
    if r.returncode!=0: return EXIT_BLOCKED,refuse("audio concat failed",EXIT_BLOCKED)
    with wave.open(str(voice/'padded.wav'),'rb') as w: total=w.getnframes()/w.getframerate()
    total_frames=round(total*24)

    # 2) studio with deterministic __setTime bound to measured voice boundaries
    bounds=[0.0]
    for sg in segs: bounds.append(round(bounds[-1]+sg['duration_s'],2))
    html='''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#0e1c2e;color:#e8e4d8;font-family:monospace;padding:40px}
h1{color:#D4AF37;font-size:34px}.k{border:1px solid #3a3520;padding:14px;margin:10px 0;background:#132338}
.v{color:#D4AF37;font-size:26px}.t{color:#8a8577;font-size:13px}</style></head><body>
<h1 id="title">ae:// __TARGET__</h1>
<div class="k"><div class="t">STARS</div><div class="v" id="a">__STARS__</div></div>
<div class="k"><div class="t">FORKS</div><div class="v" id="b">__FORKS__</div></div>
<div class="k"><div class="t">COMMITS / 52W</div><div class="v" id="c">__COMMITS__</div></div>
<div id="scan" style="position:absolute;top:0;width:3px;height:100%;background:#D4AF37;box-shadow:0 0 20px #D4AF37"></div>
<div id="bars" style="display:flex;gap:3px;height:90px;align-items:flex-end;margin-top:20px">
<div class="bar" data-h="30" style="height:30%;flex:1;background:linear-gradient(180deg,#D4AF37,#6b5718)"></div>
<div class="bar" data-h="80" style="height:80%;flex:1;background:linear-gradient(180deg,#D4AF37,#6b5718)"></div>
<div class="bar" data-h="55" style="height:55%;flex:1;background:linear-gradient(180deg,#D4AF37,#6b5718)"></div>
<div class="bar" data-h="95" style="height:95%;flex:1;background:linear-gradient(180deg,#D4AF37,#6b5718)"></div>
<div class="bar" data-h="40" style="height:40%;flex:1;background:linear-gradient(180deg,#D4AF37,#6b5718)"></div>
</div>
<script>const B=__BOUNDS__;window.__setTime=function(t){
 var i=0;while(i<B.length-1&&t>=B[i+1])i++;
 var ids=['a','b','c'];[].forEach.call(document.querySelectorAll('.k'),function(k){k.style.outline='none'});
 var e=document.getElementById(ids[Math.min(i,2)]);if(e)e.closest('.k').style.outline='2px solid #D4AF37';
 document.getElementById('title').textContent='ae:// __TARGET__ · scene '+(i+1);
 var ph=0.5+0.5*Math.sin(t*1.7);
 [].forEach.call(document.querySelectorAll('.bar'),function(b){
   var h=b.dataset.h||b.style.height;b.style.height=(parseFloat(h)*(0.62+0.62*ph))+'%';});
 var s=document.getElementById('scan');s.style.left=((t%1.5)/1.5*100)+'%';s.style.height=(60+40*ph)+'%';
};window.__ready=true;</script></body></html>'''
    html=(html.replace('__TARGET__',target).replace('__STARS__',f"{facts['total_stars']:,}")
              .replace('__FORKS__',f"{facts['total_forks']:,}")
              .replace('__COMMITS__',f"{facts['commits_52w']:,}")
              .replace('__BOUNDS__',json.dumps(bounds)))
    (work/'studio.html').write_text(html,encoding='utf-8')

    # 3) CDP frames via the proven render.mjs harness
    chrome=Path(r"C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.exists(): return EXIT_BLOCKED,refuse("Chrome missing",EXIT_BLOCKED)
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
    srv=subprocess.Popen([sys.executable,'-m','http.server',str(port)],cwd=str(work),
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    cdp=9200+port%500
    ch=subprocess.Popen([str(chrome),'--headless=new','--force_high_performance_gpu','--use-angle=d3d11',
        f'--remote-debugging-port={cdp}','--window-size=1920,1080','--no-first-run','--disable-extensions',
        f'--user-data-dir={work/"chrome"}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(25):
            try: urllib.request.urlopen(f'http://127.0.0.1:{cdp}/json',timeout=1);break
            except Exception: time.sleep(1)
        env=os.environ.copy();env.update({"CDP_URL":f"http://127.0.0.1:{cdp}",
          "PAGE_URL":f"http://127.0.0.1:{port}/studio.html","FRAMES":str(frames),
          "TOTAL_FRAMES":str(total_frames),"FPS":"24","WIDTH":"1920","HEIGHT":"1080"})
        r=subprocess.run(['node',str(KITS/'hermes-contributions-film'/'render.mjs')],
          capture_output=True,text=True,timeout=1800,encoding='utf-8',errors='replace',env=env)
        if r.returncode!=0 or 'CAPTURED=' not in r.stdout:
            return EXIT_BLOCKED,refuse(f"CDP capture: {(r.stdout+r.stderr)[-180:]}",EXIT_BLOCKED)
    finally:
        ch.terminate();srv.terminate()

    # 4) encode → gate (frame + byte receipt) → seal
    silent=work/'silent.mp4';film=work/'film.mp4'
    r=subprocess.run([str(ffmpeg),'-y','-framerate','24','-i',str(frames/'frame_%05d.png'),
      '-c:v','h264_nvenc','-preset','p5','-b:v','6M','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)],
      capture_output=True,text=True,timeout=900)
    if r.returncode!=0: return EXIT_BLOCKED,refuse("NVENC encode failed",EXIT_BLOCKED)
    r=subprocess.run([str(ffmpeg),'-y','-i',str(silent),'-i',str(voice/'padded.wav'),
      '-c:v','copy','-c:a','aac','-b:a','128k','-t',f'{total:.2f}',str(film)],
      capture_output=True,text=True,timeout=300)
    if r.returncode!=0: return EXIT_BLOCKED,refuse("mux failed",EXIT_BLOCKED)
    env=os.environ.copy()
    for k in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'): env.pop(k,None)
    r=subprocess.run([gate_py,str(ROOT/'vidæo'/'vidæo.py'),'verify',str(film)],
      capture_output=True,text=True,timeout=600,encoding='utf-8',errors='replace',env=env)
    txt=r.stdout or r.stderr;i=txt.find('{')
    if i<0 or r.returncode!=0: return EXIT_BLOCKED,refuse(f"gate unavailable: {txt[-160:]}",EXIT_BLOCKED)
    rep=json.loads(txt[i:])
    if rep.get('calidad')!='PASS': return EXIT_REFUSED,refuse(f"gate: {rep.get('razones')}")
    # tinyfilmmemory cites the FILE STEM. A generic "film.mp4" would seal as
    # æ://film/film and collide with every other auto-render. Name it first.
    named=work/(target.replace('/','_')+'.mp4')
    named.write_bytes(film.read_bytes())
    sys.path.insert(0,str(ROOT/'tinyfilmmemory'))
    import tinyfilmmemory as tfm
    rec=tfm.record(named,tfm.DEFAULT_LEDGER,
      abstract=f"tinyRepoFilm auto-render: {target} · byte {rep.get('byte_receipt','')[:12]}")
    return EXIT_OK,{"verdict":"FILMED","artifact":str(named),"citation":rec["citation"],
                    "receipt":rep.get("receipt"),"byte_receipt":rep.get("byte_receipt"),
                    "frames":total_frames,"duration_s":round(total,3)}
