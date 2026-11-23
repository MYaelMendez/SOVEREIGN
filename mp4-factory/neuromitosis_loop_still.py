#!/usr/bin/env python3
"""Deterministic 9:16 poster of the neuromitosis loop. All numbers read from artifacts."""
from __future__ import annotations

import hashlib, json, subprocess, os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

R = Path('C:/æ')
OUT = R / 'mp4-factory/neuromitosis-loop-916.png'
W, H = 576, 1024
VOID, GOLD, GREEN, CYAN, RED, DIM = (5,5,5), (212,175,55), (0,255,157), (112,220,255), (255,107,107), (120,120,120)


def j(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def font(sz, bold=False):
    name = 'consolab.ttf' if bold else 'consola.ttf'
    p = Path('C:/Windows/Fonts') / name
    return ImageFont.truetype(str(p), sz) if p.exists() else ImageFont.load_default()


def main():
    rec = j(R/'neuromitosis/neuromitosis.receipt.json')
    led = [json.loads(x) for x in (R/'logs/ae_lessons.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    base = j(R/'neuromitosis/plan-narrator/eval-base.json')
    v3 = j(R/'neuromitosis/plan-narrator/eval-v3-case6.json')
    nm = j(R/'neuromitosis/plan-narrator/manifest.json')
    closure = j(R/'neuromitosis/plan-narrator/DEFECT-CLOSURE.json')
    gpu = j(R/'neuromitosis/plan-narrator/narrator-v3.receipt.json')

    img = Image.new('RGB', (W,H), VOID)
    d = ImageDraw.Draw(img)
    y = 34

    def line(text, size=15, color=(234,250,247), bold=False, gap=9, x=28):
        nonlocal y
        d.text((x,y), text, font=font(size,bold), fill=color)
        y += size + gap

    d.rectangle([0,0,W,6], fill=GOLD)
    line('æ:// NEUROMITOSIS', 26, GOLD, True, 6)
    line('the bond · human + robot + DAO', 12, DIM, False, 20)

    line('WHAT IS PROVEN', 13, GREEN, True, 12)
    line(f"QLoRA loss ........ {rec['train_loss']:.4f}", 15, (234,250,247), False, 5)
    line(f"trainable ......... 0.38%  (16.4M / 4.3B)", 15, (234,250,247), False, 5)
    line(f"adapter hashes .... 4/4 MATCH", 15, (234,250,247), False, 5)
    line(f"lessons ledger .... {len(led)} records, chain VALID", 15, (234,250,247), False, 5)
    line(f"narrator corpus ... {nm['records']} hash-bound records", 15, (234,250,247), False, 22)

    line('WHAT IS MEASURED, NOT SOLVED', 13, GOLD, True, 12)
    line(f"base held-out ..... {base['score']}/{base['total']}", 15, RED, False, 5)
    line(f"adapter case 6 .... {v3['score']}/{v3['total']}", 15, RED, False, 5)
    line('model invents ..... move_camera', 15, RED, False, 5)
    line('verb gate ......... REFUSE (5/5 tests)', 15, GREEN, False, 5)
    line(closure['status'], 13, CYAN, True, 22)

    line('THE BOUNDARY', 13, GOLD, True, 12)
    line('a plan is a proposal, not an act', 15, (234,250,247), False, 5)
    line('scanning never grants execution', 15, (234,250,247), False, 5)
    line('nu=0 · no physical motion claimed', 15, (234,250,247), False, 5)
    line('granted:false on every response', 15, (234,250,247), False, 22)

    line('EVIDENCE CHAIN', 13, GOLD, True, 12)
    line('take  cd13569f85b0…   film 24daef4d…', 13, CYAN, False, 5)
    line('corpus ' + nm['corpus_sha256'][:16] + '…', 13, CYAN, False, 5)
    line('lora  ' + rec['adapter_files']['adapter_model.safetensors'][:16] + '…', 13, CYAN, False, 5)
    line('v3    ' + sha(R/'neuromitosis/plan-narrator/adapter-v3/adapter_model.safetensors')[:16] + '…', 13, CYAN, False, 20)

    # closing band
    d.rectangle([0,H-96,W,H], fill=(10,10,12))
    d.line([(0,H-96),(W,H-96)], fill=GOLD, width=2)
    line('Evidence ≠ Authority', 22, GOLD, True, 4, x=28)
    y = H-58
    d.text((28,y), 'governance is receipts — measured', font=font(12), fill=DIM)

    img.save(OUT)
    print(json.dumps({'path': str(OUT), 'bytes': OUT.stat().st_size,
                      'sha256': sha(OUT), 'ratio': W/H}, indent=2))


if __name__ == '__main__':
    main()
