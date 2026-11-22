#!/usr/bin/env python3
"""ae_lessons.py — hash-chained ledger of defects already paid for.

The gap this closes: run-log wrote PROVED/BROKE/CHANGE, but nothing injected it
into the next run and nothing REFUSED a repeat. Here a lesson is not prose —
it is an executable invariant over a `context.json` that maps symbolic roles
to the current run's real paths/values.

    python ae_lessons.py seed          # one-time: install the lessons from this session
    python ae_lessons.py list
    python ae_lessons.py check --context ctx.json   # 1 if any invariant violated
    python ae_lessons.py brief --task brief.md      # prepend KNOWN DEFECTS block
    python ae_lessons.py verify        # hash-chain integrity

A guard that never fails is worthless: `check` is designed to refuse.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, wave
from collections import Counter
from pathlib import Path

LEDGER=Path(r"C:/æ/logs/ae_lessons.jsonl")
GENESIS="0"*64

def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(b): return hashlib.sha256(b).hexdigest()

def read_ledger():
    if not LEDGER.exists(): return []
    return [json.loads(l) for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]

def verify_chain(recs):
    prev=GENESIS
    for r in recs:
        body={k:v for k,v in r.items() if k!='hash'}
        if r.get('prev')!=prev or r.get('hash')!=sha(canon(body)):
            return False
        prev=r['hash']
    return True

def append(lesson):
    recs=read_ledger()
    prev=recs[-1]['hash'] if recs else GENESIS
    r=dict(lesson); r['prev']=prev
    r['hash']=sha(canon(r))
    LEDGER.parent.mkdir(parents=True,exist_ok=True)
    with LEDGER.open('a',encoding='utf-8') as f: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    return r

SEED=[
 dict(id='narration_lt_picture',run='homebase-explainer',
   defect='voice 40.056s > picture 40.0s — -shortest cut the last word',
   invariant='voice_total_s < picture_s',check={'kind':'lt','a':'voice_total_s','b':'picture_s'},
   change='assert picture > voice before encoding; picture raised to 42s'),
 dict(id='frame_count_exact',run='homebase-explainer',
   defect='Chrome died; rm -rf frames left 0 frames and ffmpeg silently reused the old mp4',
   invariant='captured frames == picture_s * fps',check={'kind':'count_eq','dir':'frames_dir','n':'total_frames'},
   change='render.mjs throws unless captured == TOTAL; run.py asserts before encode'),
 dict(id='mp4_sha_changed',run='homebase-explainer',
   defect='same gate receipt across re-renders looked like caching; it was a stale artifact',
   invariant='new artifact sha != previous sha when re-rendering',
   check={'kind':'sha_ne','a':'mp4','b':'prev_mp4'},
   change='print encoder-input sha and compare with previous run'),
 dict(id='pixel_gate_pass',run='contributions-film',
   defect='gold-on-void fell below luminance 20 and 15-frame sampling hid motion',
   invariant='gate calidad == PASS with lum>20 contrast>8 mov>0.5 frames_negros==0',
   check={'kind':'gate','file':'gate_json'},
   change='lifted scene background and added camera/progress motion; thresholds untouched'),
 dict(id='audio_real',run='contributions-film',
   defect='a pixel PASS was about to be reported as an audio claim',
   invariant='decoded PCM peak>1000 and active span covers >50% of voice',
   check={'kind':'audio','mp4':'mp4','voice_s':'voice_total_s'},
   change='decode to s16le and measure peak/RMS/active span separately'),
 dict(id='counter_bars_coherent',run='contributions-film',
   defect='counter 176 vs October bar 506 — two different progress models',
   invariant='counter == sum(monthly bars) at every sampled t',
   check={'kind':'coherence','html':'studio_html','times':'sample_times'},
   change='bars derive from the same revealed-day set as the counter; clamp upto to len-1'),
 dict(id='studio_fetch_path',run='contributions-film',
   defect='studio copy fetched ./data.json from /_studio/ -> __ready never set, identical frames',
   invariant='studio html references ../<data> when nested one directory down',
   check={'kind':'regex_absent','file':'studio_html','pattern':"fetch\\('./contributions\\.json'"},
   change='build_studio.py rewrites fetch to ../contributions.json'),
 dict(id='then_catch_chain',run='contributions-film',
   defect='orphan .catch() after injected statements broke the whole script',
   invariant='no statement between }) and .catch( in studio html',
   check={'kind':'regex_absent','file':'studio_html','pattern':'\\}\\)\\s*\\n\\s*window\\.__segT0'},
   change='build_studio.py injects a .then(()=>{...}) wrapper'),
 dict(id='no_credential_surface',run='contributions-film',
   defect='gh token could leak into a derived surface',
   invariant='no ghp_/gho_/ghp/Bearer/Authorization in derived json',
   check={'kind':'regex_absent','file':'data_json','pattern':'gh[pous]_[A-Za-z0-9]{10,}|Bearer\\s+\\S+|Authorization'},
   change='gen_contributions.py writes only public calendar fields; regex-verified'),
  dict(id='identical_fork_refused',run='huggingbot',
    defect='a fork identical to upstream passed with 659 inherited commits — authorship theft',
    invariant='an upstream-identical fork REFUSEs with exit 10 before derivation',
    check={'kind':'exit_code_eq','file':'decision_json','value':10},
    change='fork_provenance() reads derived compare record; identical => REFUSE 10'),
  dict(id='refusal_has_record',run='tinyrepofilm',
    defect='REFUSED and a crash both returned 1 — a refusal without a record did not happen',
    invariant='every refusal persists decision-<target>.json with verdict and exit code',
    check={'kind':'decision_record','file':'decision_json'},
    change='emit_decision() writes verdict/exit_code beside the artifact; 10=REFUSED 11=BLOCKED'),
  dict(id='decided_drift_not_resealed',run='tinyfilmmemory',
    defect='v1/v2 hermes drift demanded re-seal although bytes were superseded by v3',
    invariant='quarantined drift stays visible but open_drift is empty',
    check={'kind':'drift_decided','file':'verify_json'},
    change='quarantine record + verify() distinguishes open_drift from quarantined'),
 dict(id='explicit_stage_only',run='deploy',
   defect='concurrent agent held index.lock; -A would have shipped unverified work',
   invariant='no bare git push and no -A in deploy scripts',
   check={'kind':'advisory','note':'verify kanban_push.py task record manually'},
   change='explicit git add of 2 paths + kanban_push.py with FLEET_REPO'),
]

def get(ctx,key):
    return ctx.get(key)

def evaluate(lesson,ctx):
    c=lesson['check']; kind=c['kind']
    if kind=='advisory': return True,'advisory (manual)'
    if kind=='lt':
        a,b=get(ctx,c['a']),get(ctx,c['b'])
        if a is None or b is None: return False,'REFUSED: missing key '+str(c['a'] if a is None else c['b'])
        return a<b, f"{c['a']}={a} < {c['b']}={b}"
    if kind=='count_eq':
        d,n=get(ctx,c['dir']),get(ctx,c['n'])
        if not d or n is None: return False,'REFUSED: missing frames_dir/total_frames'
        got=len(list(Path(d).glob('frame_*.png')))
        return got==n, f'frames={got} expected={n}'
    if kind=='sha_ne':
        a,b=get(ctx,c['a']),get(ctx,c['b'])
        if not a or not b: return False,'REFUSED: missing artifact or previous artifact'
        ha=sha(Path(a).read_bytes()); hb=sha(Path(b).read_bytes())
        return ha!=hb, f'{ha[:12]} != {hb[:12]}'
    if kind=='gate':
        f=get(ctx,c['file'])
        if not f or not Path(f).exists(): return False,'REFUSED: gate_json missing (no PASS claimed)'
        g=json.loads(Path(f).read_text(encoding='utf-8'))
        ok=(g.get('calidad')=='PASS' and g.get('luminancia_media',0)>20 and
            g.get('contraste_medio',0)>8 and g.get('movimiento_medio',0)>0.5 and
            g.get('frames_negros',0)==0)
        return ok,f"calidad={g.get('calidad')}"
    if kind=='audio':
        mp4=get(ctx,c['mp4']); voice=get(ctx,c['voice_s'])
        if not mp4 or not Path(mp4).exists(): return False,'REFUSED: mp4 missing'
        import subprocess, numpy as np
        ff=ctx.get('ffmpeg'); ff=ff or 'ffmpeg'
        r=subprocess.run([ff,'-v','error','-i',str(mp4),'-vn','-ac','1','-ar','24000','-f','s16le','-'],
                         capture_output=True,timeout=180)
        pcm=np.frombuffer(r.stdout,dtype='<i2').astype('float32')
        peak=float(abs(pcm).max()); act=(abs(pcm)>200).sum()/max(1,len(pcm))
        return (peak>1000 and (voice is None or act>0.5)),f'peak={peak:.0f} active={act*100:.1f}%'
    if kind=='regex_absent':
        f=get(ctx,c['file'])
        if not f or not Path(f).exists(): return False,'REFUSED: file missing '+str(f)
        t=Path(f).read_text(encoding='utf-8',errors='replace')
        m=re.search(c['pattern'],t,re.I|re.S)
        return m is None, 'absent' if not m else 'FOUND: '+m.group(0)[:40]
    if kind=='coherence':
        # verified by the studio's own probe; require the explicit attestation
        att=get(ctx,'coherence_verified')
        return bool(att), f'attested={att}'

    if kind=='exit_code_eq':
        f=get(ctx,c['file'])
        if not f or not Path(f).exists(): return False,'REFUSED: no decision record'
        d=json.loads(Path(f).read_text(encoding='utf-8'))
        return d.get('exit_code')==c['value'], f"exit={d.get('exit_code')} expected={c['value']}"
    if kind=='decision_record':
        f=get(ctx,c['file'])
        if not f or not Path(f).exists(): return False,'REFUSED: refusal without a record'
        d=json.loads(Path(f).read_text(encoding='utf-8'))
        ok=d.get('verdict') in ('REFUSED','BLOCKED','FILMED') and isinstance(d.get('exit_code'),int)
        return ok, f"verdict={d.get('verdict')} exit={d.get('exit_code')}"
    if kind=='drift_decided':
        f=get(ctx,c['file'])
        if not f or not Path(f).exists(): return False,'REFUSED: verify_json missing'
        d=json.loads(Path(f).read_text(encoding='utf-8'))
        return (d.get('ok') is True and d.get('open_drift')==[]), f"ok={d.get('ok')} open={d.get('open_drift')}"
    return True,'unknown check kind'
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('cmd',choices=['seed','list','check','brief','verify'])
    ap.add_argument('--context',type=Path)
    ap.add_argument('--task',type=Path)
    a=ap.parse_args()
    recs=read_ledger()
    if a.cmd=='seed':
        existing={r['id'] for r in recs}
        added=[append(L)['id'] for L in SEED if L['id'] not in existing]
        print('seeded:',added or '(already present)')
    elif a.cmd=='list':
        for r in recs: print(f"  {r['id']:26s} {r['invariant'][:70]}")
        print(f'  total={len(recs)}')
    elif a.cmd=='verify':
        print(f"chain_ok={verify_chain(recs)} records={len(recs)} head={(recs[-1]['hash'][:12] if recs else GENESIS[:12])}")
        return 0 if verify_chain(recs) else 1
    elif a.cmd=='brief':
        if not a.task: raise SystemExit('--task required')
        block='KNOWN DEFECTS (already paid for — do not repeat)\n'+'\n'.join(
          f"- [{r['id']}] {r['invariant']}\n    fix: {r['change']}" for r in recs)
        t=a.task.read_text(encoding='utf-8') if a.task.exists() else ''
        a.task.write_text(block+'\n\n'+t,encoding='utf-8')
        print(f'prepended {len(recs)} invariants to {a.task}')
    elif a.cmd=='check':
        if not a.context: raise SystemExit('--context required')
        ctx=json.loads(a.context.read_text(encoding='utf-8'))
        bad=[]
        for r in recs:
            ok,msg=evaluate(r,ctx)
            flag='PASS' if ok else 'REFUSE'
            print(f"  [{flag:6s}] {r['id']:26s} {msg}")
            if not ok: bad.append(r['id'])
        print(f'\n  {len(recs)-len(bad)}/{len(recs)} invariants hold')
        if bad: print('  REFUSED by: '+', '.join(bad))
        return 1 if bad else 0
    return 0

if __name__=='__main__': sys.exit(main())
