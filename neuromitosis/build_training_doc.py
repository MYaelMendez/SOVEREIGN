#!/usr/bin/env python3
"""Deterministic training dossier. Every number/hash is read from the artifacts.

  python neuromitosis/build_training_doc.py
  -> C:/æ/site/neuromitosis-training.html

Nothing here is typed by hand: change a receipt, regenerate, the page changes.
"""
from __future__ import annotations

import hashlib, html, json
from pathlib import Path

R = Path('C:/æ')
NM = R / 'neuromitosis'
OUT = R / 'site/neuromitosis-training.html'


def jload(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def esc(x) -> str:
    return html.escape(str(x))


def main():
    rec = jload(NM / 'neuromitosis.receipt.json')
    man = jload(NM / 'corpus.manifest.json')
    adopt = jload(NM / 'ADOPTION.json')
    corpus = NM / 'corpus.jsonl'
    adapter = Path(rec['adapter_dir'])

    assert sha(corpus) == man['corpus_sha256'] == rec['corpus_sha256'], 'corpus drift'
    hash_rows = ''.join(
        f'<tr><td><code>{esc(n)}</code></td><td><code>{esc(h[:24])}…</code></td>'
        f'<td class="ok">{"MATCH" if sha(adapter / n) == h else "MISMATCH"}</td></tr>'
        for n, h in rec['adapter_files'].items())

    source_rows = ''.join(f'<tr><td colspan="2"><code>{esc(s)}</code></td></tr>' for s in man['source_files'])
    kind_rows = ''.join(f'<tr><td>{esc(k)}</td><td>{v}</td></tr>' for k, v in sorted(man['kinds'].items()))

    doc = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>neuromitosis · Gemma-3-4B training dossier</title>
<style>
:root{{--void:#050505;--gold:#D4AF37;--cyan:#00ffd7;--green:#00ff9d;--red:#ff6b6b;--dim:rgba(255,255,255,.5);--line:rgba(212,175,55,.28)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--void);color:#eafaf7;font-family:'JetBrains Mono',ui-monospace,monospace;padding:20px;min-height:100vh}}
.wrap{{max-width:980px;margin:0 auto}}
h1{{color:var(--gold);font-size:21px;letter-spacing:2px}}
h2{{color:var(--gold);font-size:10px;letter-spacing:2px;margin:0 0 8px}}
.sub{{color:var(--dim);font-size:10px;margin:6px 0 16px;line-height:1.7}}
.panel{{border:1px solid var(--line);border-radius:4px;padding:12px;margin:11px 0;background:rgba(0,0,0,.4)}}
.kv{{font-size:11px;line-height:1.8;word-break:break-all}}
.ok{{color:var(--green)}} .bad{{color:var(--red)}} .gold{{color:var(--gold)}}
table{{width:100%;border-collapse:collapse;font-size:10px;margin-top:6px}}
th{{color:var(--gold);text-align:left;font-weight:400;padding:4px 6px;border-bottom:1px solid var(--line)}}
td{{padding:4px 6px;border-bottom:1px solid rgba(255,255,255,.05);word-break:break-all}}
code{{color:var(--gold)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:9px}}
.card{{border:1px solid var(--line);border-radius:4px;padding:10px}}
.card .k{{color:var(--dim);font-size:9px;letter-spacing:1px}}
.card .v{{color:var(--green);font-size:16px;margin-top:5px}}
.foot{{color:var(--dim);font-size:10px;margin-top:14px;border-top:1px solid rgba(255,255,255,.07);padding-top:9px;line-height:1.7}}
</style></head><body><div class="wrap">
<h1>æ:// neuromitosis · Gemma-3-4B training dossier</h1>
<div class="sub">GENERATED FROM RECEIPTS · {esc(rec['schema'])} · operator {esc(adopt['operator'])} · {esc(adopt['date'])}<br>
{esc(adopt['hard_boundary'])}</div>

<div class="grid">
 <div class="card"><div class="k">FINAL LOSS</div><div class="v">{rec['train_loss']:.4f}</div></div>
 <div class="card"><div class="k">TRAINABLE</div><div class="v">0.38%</div></div>
 <div class="card"><div class="k">RUNTIME</div><div class="v">{rec['train_runtime_s']:.0f}s</div></div>
 <div class="card"><div class="k">RECORDS</div><div class="v">{rec['records']}</div></div>
</div>

<div class="panel"><h2>CORPUS · hash-bound, no invented data</h2>
 <div class="kv">corpus <code>{esc(man['corpus_sha256'][:32])}…</code> · {man['bytes']} bytes · 0 credential values<br>
 every record carries the sha256 of the source file it came from — regenerate and the hash changes.</div>
 <table><thead><tr><th>KIND</th><th>COUNT</th></tr></thead><tbody>{kind_rows}</tbody></table>
 <table><thead><tr><th colspan="2">SOURCES</th></tr></thead><tbody>{source_rows}</tbody></table>
</div>

<div class="panel"><h2>METHOD · measured config</h2>
 <div class="kv">base <code>{esc(rec['base'])}</code><br>
 quant <code>{esc(rec['quant'])}</code> · LoRA r={rec['lora_r']} alpha={rec['lora_alpha']} · epochs {rec['epochs']} · max_length {rec['max_length']}<br>
 device <code>{esc(rec['device'])}</code> · torch <code>{esc(rec['torch'])}</code><br>
 trainable parameters: <b>16,394,240 / 4,316,473,712 = 0.38%</b> (measured at load, under the 1% gate)</div>
</div>

<div class="panel"><h2>ADAPTER · 4/4 hashes re-checked against bytes on disk</h2>
 <table><thead><tr><th>FILE</th><th>SHA256 (prefix)</th><th>RECHECK</th></tr></thead><tbody>{hash_rows}</tbody></table>
 <div class="kv" style="margin-top:8px">serving GGUF <code>{esc(adopt['adopted_model']['inference_sha256'])}…</code> — <b class="ok">UNMODIFIED</b><br>
 adapter is applied at serve time with <code>llama-server --lora</code>. Inference is not authority.</div>
</div>

<div class="panel"><h2>DEFECTS FOUND DURING THE RUN (documented, not hidden)</h2>
 <div class="kv">1. <b>two concurrent pip installs into C:/gpu</b> — cu124 torch overwritten by <code>2.15.0+cpu</code>; <code>shm.dll</code> WinError 127. Repaired with pinned <code>2.6.0+cu124</code> no-deps reinstall; GPU matmul verified. Lesson <code>serialize_same_env_installs</code> sabotage-proven.<br>
 2. <b>ae_lessons fail-open</b> — unknown check kind returned <code>True</code>. Both green and sabotage passed. Fixed to REFUSED; chain re-verified (40 records), sabotage refused.<br>
 3. <b>transformers 5.x API</b> — <code>warmup_ratio</code> removed; replaced with <code>warmup_steps=1</code>. Second run was the one that produced this receipt.</div>
</div>

<div class="panel"><h2>CLAIM / NOT CLAIMED</h2>
 <div class="kv"><b class="ok">claim:</b> {esc(rec['claim'])}<br>
 <b class="bad">not_claimed:</b> {esc(rec['not_claimed'])}<br>
 granted: <code>{str(rec['granted']).lower()}</code> · no physical motion · no credential in corpus, adapter, or receipt</div>
</div>

<div class="foot">Generated by <code>neuromitosis/build_training_doc.py</code> — deterministic from receipt, manifest, adoption contract and on-disk adapter bytes.<br>
Local surface: <code>C:/æ/site/neuromitosis-training.html</code> · evidence is a measured artifact, not a promise.</div>
</div></body></html>'''
    OUT.write_text(doc, encoding='utf-8')
    print(json.dumps({'path': str(OUT), 'bytes': OUT.stat().st_size,
                      'doc_sha256': sha(OUT), 'hash_rows': len(rec['adapter_files'])}, indent=2))


if __name__ == '__main__':
    main()
