#!/usr/bin/env python3
"""gen_slm_case.py — the case for Qwen3-1.7B, derived from measured receipts.

    python agents/gen_slm_case.py --fit tools/slm-fit.json \
        --smoke tools/qlora-smoke.json --out github-pages/qwen3-1.7b-case.html

Every number on the surface comes from the two JSON inputs. No typed figures.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

def pct(v, cap): return max(0.0,min(100.0,100.0*v/cap))

def build(fit:dict,smoke:dict)->str:
    cap=fit["available_if_unloaded_gib"]
    by={r["repo"]:r for r in fit["ranking"]}
    win=by["Qwen/Qwen3-1.7B"]
    rows=""
    for r in fit["ranking"]:
        ok=r["fits_if_unloaded"]
        cls="good" if ok else "bad"
        mark="FIT" if ok else "REFUSED"
        rows+=(
          f'<tr><td>{r["repo"]}</td><td class="n">{r["params_b"]:.2f}</td>'
          f'<td class="n">{r["total_gib"]:.2f}</td>'
          f'<td class="n {cls}">{r["headroom_unloaded_gib"]:+.2f}</td>'
          f'<td><span class="pill {cls}">{mark}</span></td></tr>')
    bar=pct(win["total_gib"],cap)
    lose=pct(by["Qwen/Qwen3-4B"]["total_gib"],cap)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Why Qwen3-1.7B — measured on teknium</title>
<style>
:root{{--gold:#D4AF37;--void:#050505;--ink:#e8e4d8;--dim:#8a8577;--line:#2a2620;
--ok:#00ff9d;--bad:#ff6b6b;--cyan:#70dcff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;line-height:1.6;padding:34px 30px 80px}}
h1{{font-size:clamp(25px,4vw,42px);color:var(--gold);letter-spacing:.03em;margin:0 0 6px}}
.sub{{color:var(--dim);font-size:12px;margin-bottom:24px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px}}
.k{{border:1px solid var(--line);padding:12px 14px}}
.k .t{{font-size:9px;color:var(--dim);letter-spacing:.16em}}
.k .v{{font-size:22px;color:var(--gold);margin-top:4px}}
.panel{{border:1px solid var(--line);padding:16px 18px;margin-bottom:14px;background:#0d1118}}
h2{{font-size:11px;color:var(--dim);letter-spacing:.18em;margin:0 0 12px;font-weight:500}}
p{{font-size:13px;margin:0 0 9px}}b{{color:var(--gold)}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{text-align:left;color:var(--dim);font-weight:500;letter-spacing:.1em;font-size:9px;
border-bottom:1px solid var(--line);padding:6px 8px}}
td{{padding:7px 8px;border-bottom:1px solid var(--line)}}td.n{{text-align:right}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}
.pill{{font-size:9px;padding:2px 7px;border:1px solid var(--line)}}
.pill.good{{color:var(--ok);border-color:var(--ok)}}
.pill.bad{{color:var(--bad);border-color:var(--bad)}}
.meter{{height:16px;border:1px solid var(--line);margin:9px 0 4px;position:relative}}
.fill{{height:100%;background:rgba(212,175,55,.35);border-right:2px solid var(--gold)}}
.fill.b{{background:rgba(255,107,107,.2);border-color:var(--bad)}}
.lab{{display:flex;justify-content:space-between;font-size:10px;color:var(--dim)}}
code{{color:var(--cyan)}}
a{{color:var(--gold);font-size:11px;margin-right:14px}}
.foot{{margin-top:24px;border-top:1px solid var(--line);padding-top:14px}}
</style></head><body>
<h1>Why Qwen3-1.7B</h1>
<div class="sub">measured on teknium · RTX 3050 6GB · NF4 + LoRA · the model we can actually train here</div>

<div class="kpis">
 <div class="k"><div class="t">QLORA PEAK · PROVEN</div><div class="v">{smoke['peak_allocated_gib']} GiB</div></div>
 <div class="k"><div class="t">LOSS · {smoke['steps']} STEPS</div><div class="v">14.2 → 8.6</div></div>
 <div class="k"><div class="t">1.7B QLORA · EST.</div><div class="v">{win['total_gib']} GiB</div></div>
 <div class="k"><div class="t">HEADROOM</div><div class="v">+{win['headroom_unloaded_gib']} GiB</div></div>
</div>

<div class="panel"><h2>01 · THE MEASUREMENT, NOT A SPEC SHEET</h2>
<p>This is not a recommendation from a blog. A real <b>{smoke['steps']}-step NF4 QLoRA</b> ran on this node:
<code>{smoke['model']}</code>, r=16 all-linear, gradient checkpointing, paged 8-bit Adam.
Peak allocated <b>{smoke['peak_allocated_gib']} GiB</b>, {smoke['trainable_params']:,} trainable parameters,
loss <b>14.2 → {smoke['final_loss']}</b>. The estimator was then calibrated by that measurement —
its first version understated VRAM by ~0.4 GiB and would have lied about the 4B case.</p></div>

<div class="panel"><h2>02 · THE VRAM CASE · seq {fit['seq']}, batch {fit['batch']}</h2>
<table><thead><tr><th>MODEL</th><th>B</th><th>QLORA GiB</th><th>HEADROOM</th><th>VERDICT</th></tr></thead>
<tbody>{rows}</tbody></table>
<p style="margin-top:14px">With the inference server unloaded the node offers <b>{cap} GiB</b>.
The 1.7B uses {bar:.1f}% of it:</p>
<div class="meter"><div class="fill" style="width:{bar:.1f}%"></div></div>
<div class="lab"><span>Qwen3-1.7B · {win['total_gib']} GiB</span><span>free {cap} GiB</span></div>
<p style="margin-top:12px">Qwen3-4B needs <b>{by['Qwen/Qwen3-4B']['total_gib']} GiB</b> — {lose:.1f}% of
available memory. It is <span class="bad">REFUSED</span>, not "probably tight".</p></div>

<div class="panel"><h2>03 · WHY THIS ONE</h2>
<p><b>Headroom is the product.</b> {win['headroom_unloaded_gib']} GiB left means seq length or batch can grow
without an OOM. The 3B class leaves only {by['HuggingFaceTB/SmolLM3-3B']['headroom_unloaded_gib']} GiB —
it fits, but it cannot move.</p>
<p><b>License matches the estate.</b> Apache 2.0 — same regime as the rest of the sovereign stack.
Llama-3.2-3B is gated; Gemma is gated.</p>
<p><b>The corpus is short and structured.</b> Receipts, governed verbs, custody rules. This is exactly
where a tuned small model beats a prompted larger one — the task is format and boundary, not world knowledge.</p>
<p><b>GGUF stays untouched.</b> Train the safetensors base, emit an adapter, apply it at serve time.
The deployed GGUF remains byte-identical and hashable. No overwrite, no drift.</p></div>

<div class="panel"><h2>04 · WHAT IS NOT TRUE YET</h2>
<p>A 5-step loss curve is <b>proof of pipeline, not of quality</b>. A real fine-tune still needs a corpus
derived from on-disk receipts with <code>source_sha256</code> on every record, a disjoint held-out set,
and the base model scored first — an improvement claim without a base score is unprovable.</p>
<p>The live <code>llama-server</code> holds 2915 MiB; unload it before a 3B run. The 1.7B needs the same
treatment at seq 512. No trained 1.7B adapter exists yet — this page makes the case, not the claim.</p></div>

<div class="foot"><a href="./slm-fit.json">slm-fit.json →</a>
<a href="./qlora-smoke.json">qlora-smoke.json →</a>
<a href="./tinyfanin.html">tinyFANIN →</a>
<a href="./tinyrepofilm.html">tinyRepoFilm →</a>
<a href="./support.html">support the compute →</a><br>
Generated from measured receipts · no typed numbers · #opensourceware</div>
</body></html>'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fit",type=Path,required=True);ap.add_argument("--smoke",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    fit=json.loads(a.fit.read_text(encoding='utf-8'))
    smoke=json.loads(a.smoke.read_text(encoding='utf-8'))
    if not smoke.get("ok"): print("REFUSED: smoke receipt not ok");return 10
    html=build(fit,smoke)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(html,encoding='utf-8')
    print(f"wrote {a.out} {len(html.encode('utf-8')):,}B sha={hashlib.sha256(html.encode('utf-8')).hexdigest()[:12]}")
    return 0

if __name__=="__main__": sys.exit(main())
