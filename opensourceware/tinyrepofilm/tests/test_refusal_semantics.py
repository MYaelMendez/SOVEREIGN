#!/usr/bin/env python3
"""Refusal semantics are RESULTS, not crashes.

    python -m pytest tests/test_refusal_semantics.py -q

Three distinct exit codes; every refusal persists a decision record.
Sabotage tests prove each path is executable, not merely declared.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

CLI=Path(r"C:/æ/opensourceware/tinyrepofilm/tinyrepofilm.py")
SCRATCH=Path(r"C:/Users/yaelm/AppData/Local/hermes/cache/scratch/trf-refusal-tests")
PY=r"C:/gpu/Scripts/python.exe"
KIT=CLI.parent
ENV=None
def _env():
    global ENV
    if ENV is None:
        ENV=os.environ.copy()
        for k in ("PYTHONPATH","PYTHONHOME","VIRTUAL_ENV"): ENV.pop(k,None)
        ENV["PATH"]=str(KIT)+os.pathsep+ENV.get("PATH","")
    return ENV
import os

def run(target:str, *flags) -> tuple[int,str,Path]:
    out=SCRATCH/target.replace('/','_')
    r=subprocess.run([PY,str(CLI),'--target',target,'--out',str(out),*flags],
      capture_output=True,text=True,timeout=300,encoding='utf-8',errors='replace',cwd=str(KIT),env=_env())
    return r.returncode,(r.stdout or r.stderr),out

def test_refused_identical_fork_is_exit_10_with_decision():
    """Sabotage: a fork byte-identical to upstream must REFUSE, never film."""
    rc,txt,out=run('MYaelMendez/HuggingBot','--derive-only')
    assert rc==10, txt[-400:]
    assert 'identical to upstream' in txt
    d=out/'decision-MYaelMendez_HuggingBot.json'
    assert d.exists(), "a refusal without a record did not happen"
    rec=json.loads(d.read_text(encoding='utf-8'))
    assert rec['verdict']=='REFUSED' and rec['exit_code']==10

def test_blocked_missing_browser_is_exit_11():
    """Sabotage: no Chrome binary -> infrastructure BLOCKED, not a verdict."""
    sys.path.insert(0,str(KIT))
    import render_film
    from pathlib import Path as P
    original=render_film.Path
    class NoChrome:
        def __init__(self,s): self.s=str(s)
        def exists(self): return 'chrome.exe' not in self.s.lower()
        def __truediv__(self,x): return original(self.s)/x
        def __str__(self): return self.s
    render_film.Path=NoChrome
    try:
        code,dec=render_film.render_film('x/y',[],{'total_stars':1,'total_forks':0,'commits_52w':0},
                                         SCRATCH/'blocked',PY,PY)
    finally:
        render_film.Path=original
    assert code==11, dec
    assert dec['verdict']=='BLOCKED' and 'Chrome' in dec['reason']

def test_control_non_fork_passes():
    """Control: a real repo must NOT be caught by the provenance guard."""
    rc,txt,_=run('openclaw/openclaw','--derive-only')
    assert rc==0, txt[-400:]
    assert 'gate: PASS' in txt
