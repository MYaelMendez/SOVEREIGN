#!/usr/bin/env python3
"""doctor for tinyvoca — delegates to the real det_voice engine in osw-voice-lab."""
import json, sys, os, importlib.util
from pathlib import Path
ENGINE=Path(r"C:/æ/osw-voice-lab/det_voice.py")
def doctor():
    if not ENGINE.exists(): return {"ok":False,"error":"det_voice.py missing"}
    spec=importlib.util.spec_from_file_location("det_voice",str(ENGINE))
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    import inspect
    sig=str(inspect.signature(m.synth_wav))
    ok="voice" in sig and "seed" in sig and "out" in sig
    return {"ok":ok,"engine":str(ENGINE),"signature":sig,
      "voices":getattr(m,"VOICE_IDS",None)}
if __name__=="__main__": print(json.dumps(doctor(),ensure_ascii=False,default=str))
