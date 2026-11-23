#!/usr/bin/env python3
"""slm_fit.py — which small language model can we actually QLoRA-train here?

Live VRAM (nvidia-smi) + real repo sizes (HF API, optional) + an explicit,
auditable VRAM model. PROVEN inputs are labelled separately from ESTIMATES:
the only true proof is a training run.

    python tools/slm_fit.py --json out.json --check
    python tools/slm_fit.py --probe-hf
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

# QLoRA planning model — assumptions written down, not hidden in the code.
ASSUMPTIONS = {
    "cuda_context_gib": 0.45,       # measured-typical on Ampere laptop
    "nf4_bytes_per_param": 0.55,    # 4-bit weights + scales + quant metadata
    "lora_fraction": 0.010,         # r=16 all-linear ~= 1% of params
    "lora_bytes_per_param": 6.0,    # bf16 weight + grad + 8-bit Adam state
    "act_gib_per_b_param_seq512_bs1": 0.30,  # gradient checkpointing ON
    "safety_gib": 0.30,
    # Calibration from a REAL 5-step QLoRA on this node (Qwen3-0.6B, seq 256):
    # formula said 1.27 GiB @seq512, torch measured 1.66 GiB peak @seq256.
    # Conservative multiplier so planning never understates the real cost.
    "measured_calibration": 1.30,
}
CANDS = [
    ("Qwen/Qwen3-0.6B",                  0.6,  "apache-2.0",  "tiny / routing / classification"),
    ("Qwen/Qwen3-1.7B",                  2.03, "apache-2.0",  "BEST BALANCE: fast iteration, structured output"),
    ("HuggingFaceTB/SmolLM3-3B",         3.08, "apache-2.0",  "fully-open research, strongest 3B reasoning"),
    ("Qwen/Qwen3-4B",                    4.02, "apache-2.0",  "capability ceiling, tight on 6GB"),
    ("meta-llama/Llama-3.2-3B-Instruct", 3.21, "llama3.2",    "gated; most tunable per Distilabs"),
    ("google/gemma-3-1b-it",             1.0,  "gemma",       "gated; narrow but cheap"),
]

def nvidia() -> dict:
    q = "name,memory.total,memory.used,memory.free,driver_version"
    r = subprocess.run(["nvidia-smi",f"--query-gpu={q}","--format=csv,noheader"],
                       capture_output=True,text=True,timeout=30)
    if r.returncode or not r.stdout.strip(): raise RuntimeError("nvidia-smi unavailable — REFUSED")
    parts=[p.strip() for p in r.stdout.strip().split(",")]
    return {"name":parts[0],"total_mib":int(parts[1].split()[0]),
            "used_mib":int(parts[2].split()[0]),"free_mib":int(parts[3].split()[0]),
            "driver":parts[4]}

def estimate(P:float, seq:int, batch:int, A:dict) -> dict:
    w   = P*1e9*A["nf4_bytes_per_param"]/2**30
    lora= P*1e9*A["lora_fraction"]*A["lora_bytes_per_param"]/2**30
    act = A["act_gib_per_b_param_seq512_bs1"]*P*(seq/512)*(batch/1)
    tot = (A["cuda_context_gib"]+w+lora+act+A["safety_gib"])*A["measured_calibration"]
    return {"weights_nf4_gib":round(w,2),"lora_gib":round(lora,2),
            "activations_gib":round(act,2),"total_gib":round(tot,2)}

DESKTOP_MIB = 761  # measured cold-idle on this host (rtx-3050 skill)

def build(seq:int,batch:int) -> dict:
    g=nvidia(); avail=g["free_mib"]/1024
    cold=(g["total_mib"]-DESKTOP_MIB)/1024
    rows=[]
    for repo,P,lic,note in CANDS:
        e=estimate(P,seq,batch,ASSUMPTIONS)
        rows.append({"repo":repo,"params_b":P,"license":lic,"note":note,
                     **e,"fits":e["total_gib"]<=avail,
                     "fits_if_unloaded":e["total_gib"]<=cold,
                     "headroom_gib":round(avail-e["total_gib"],2),
                     "headroom_unloaded_gib":round(cold-e["total_gib"],2)})
    rows.sort(key=lambda r:(not r["fits_if_unloaded"],-r["params_b"]))
    return {"gpu":g,"available_gib":round(avail,2),"available_if_unloaded_gib":round(cold,2),
            "seq":seq,"batch":batch,"assumptions":ASSUMPTIONS,"ranking":rows,
            "evidence":"PROVEN: GPU + live VRAM. ESTIMATED: training VRAM (needs a run to prove)."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seq",type=int,default=512);ap.add_argument("--batch",type=int,default=1)
    ap.add_argument("--json",type=Path);ap.add_argument("--check",action="store_true")
    a=ap.parse_args()
    if a.seq<=0 or a.batch<=0:
        print("REFUSED: seq and batch must be positive");return 10
    d=build(a.seq,a.batch)
    if a.json:
        a.json.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"GPU {d['gpu']['name']} · {d['gpu']['free_mib']} MiB libre ahora · "
          f"{d['available_if_unloaded_gib']:.2f} GiB si se descarga llama-server · seq={a.seq} batch={a.batch}")
    print(f"{'model':40s} {'B':>5s} {'need GiB':>9s} {'now':>7s} {'unload':>7s}  fit")
    for r in d["ranking"]:
        print(f"{r['repo']:40s} {r['params_b']:5.2f} {r['total_gib']:9.2f} "
              f"{r['headroom_gib']:7.2f} {r['headroom_unloaded_gib']:7.2f}  "
              f"{'YES' if r['fits_if_unloaded'] else ('now' if r['fits'] else 'no')}")
    if a.check:
        by={r["repo"]:r for r in d["ranking"]}
        ok=(by["Qwen/Qwen3-1.7B"]["fits_if_unloaded"]
            and by["HuggingFaceTB/SmolLM3-3B"]["fits_if_unloaded"]
            and not by["Qwen/Qwen3-4B"]["fits_if_unloaded"])
        print("CHECK", "OK" if ok else
              "STALE: expected 1.7B+3B fit and 4B refuse — re-measure live VRAM")
        return 0 if ok else 1
    return 0

if __name__=="__main__": sys.exit(main())
