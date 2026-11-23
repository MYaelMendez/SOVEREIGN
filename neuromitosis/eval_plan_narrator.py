#!/usr/bin/env python3
"""Held-out narrator eval. Runs the SAME 5 cases against base or base+adapter.

  python eval_plan_narrator.py --adapter none     # baseline
  python eval_plan_narrator.py --adapter <dir>    # trained

Prints per-case pass/fail and a score. No case was in the training corpus.
"""
from __future__ import annotations

import argparse, json, time
from pathlib import Path

NM = Path('C:/æ/neuromitosis')
BASE = Path('C:/æ/models/gemma-3-4b-it-train')
EVAL = NM / 'plan-narrator/heldout.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--adapter', default='none')
    ap.add_argument('--out', default='')
    ap.add_argument('--case', type=int, default=0, help='1-based case index; 0 = all')
    ap.add_argument('--base', default=str(BASE))
    a = ap.parse_args()
    data = json.loads(EVAL.read_text(encoding='utf-8'))
    cases = data['cases'] if not a.case else [data['cases'][a.case - 1]]

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(a.base)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(a.base, quantization_config=bnb, device_map={'': 0})
    label = 'BASE'
    if a.adapter != 'none':
        model = PeftModel.from_pretrained(model, a.adapter)
        label = 'ADAPTER:' + str(a.adapter).split('/')[-1]
    model.eval()

    results = []
    t0 = time.time()
    for i, c in enumerate(cases):
        prompt = f"<start_of_turn>user\n{c['instruction']}<end_of_turn>\n<start_of_turn>model\n"
        enc = tok(prompt, return_tensors='pt').to(model.device)
        with torch.inference_mode():
            out = model.generate(**enc, max_new_tokens=110, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        text = tok.decode(out[0][enc['input_ids'].shape[1]:], skip_special_tokens=True)
        ok = all(x.lower() in text.lower() for x in c['expect_all']) and \
             not any(x.lower() in text.lower() for x in c['expect_none'])
        results.append({'case': i + 1, 'instruction': c['instruction'], 'pass': ok,
                        'expect_all': c['expect_all'], 'missing': [x for x in c['expect_all'] if x.lower() not in text.lower()],
                        'forbidden': [x for x in c['expect_none'] if x.lower() in text.lower()],
                        'response': text[:600]})

    report = {'schema': 'ae/plan-narrator-eval-result/1', 'model': label,
              'adapter': a.adapter, 'base_model': a.base, 'heldout_sha256': json.loads(EVAL.read_text(encoding='utf-8')) and
              __import__('hashlib').sha256(EVAL.read_bytes()).hexdigest(),
              'score': sum(r['pass'] for r in results), 'total': len(results),
              'seconds': round(time.time() - t0, 1), 'results': results}
    out = Path(a.out) if a.out else NM / f'eval-{label.lower().replace(":", "-")}.json'
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'model': label, 'score': f"{report['score']}/{report['total']}",
                      'seconds': report['seconds'], 'report': str(out),
                      'cases': [(r['case'], r['pass']) for r in results]}, indent=2))


if __name__ == '__main__':
    main()
