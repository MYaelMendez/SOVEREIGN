#!/usr/bin/env python3
"""Continuation QLoRA: discipline adapter + robot plan narrator corpus.

Starts FROM the receipted neuromitosis adapter, adds the 23 narrator records.
Output: plan-narrator/adapter/ + receipt. Evaluated against the same held-out
set as the base model, with no retraining on held-out cases.
"""
from __future__ import annotations

import argparse, hashlib, json, time
from pathlib import Path

ROOT = Path('C:/æ/neuromitosis')
BASE = Path('C:/æ/models/gemma-3-4b-it-train')
DISCIPLINE = ROOT / 'lora-adapter'
PN = ROOT / 'plan-narrator'
OUT = PN / 'adapter'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=3)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    corpus = PN / 'corpus.jsonl'
    man = json.loads((PN / 'manifest.json').read_text(encoding='utf-8'))
    recs = [json.loads(l) for l in corpus.read_text(encoding='utf-8').splitlines() if l.strip()]
    assert sha(corpus) == man['corpus_sha256'] and len(recs) == man['records']
    if a.dry_run:
        print(json.dumps({'ok': True, 'records': len(recs), 'kinds': man['kinds'],
                          'discipline_adapter': DISCIPLINE.exists(),
                          'heldout_not_in_corpus': all(
                              c['instruction'] not in [r['instruction'] for r in recs]
                              for c in json.loads((PN / 'heldout.json').read_text(encoding='utf-8'))['cases'])}, indent=2))
        return 0

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainingArguments)
    from peft import PeftModel

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(str(BASE))
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(str(BASE), quantization_config=bnb, device_map={'': 0})
    model = PeftModel.from_pretrained(model, str(DISCIPLINE), is_trainable=True)
    model.print_trainable_parameters()
    model.config.use_cache = False

    texts = [f"<start_of_turn>user\n{r['instruction']}<end_of_turn>\n"
             f"<start_of_turn>model\n{r['response']}<end_of_turn>" for r in recs]
    enc = tok(texts, truncation=True, max_length=320, padding='max_length')

    class DS(torch.utils.data.Dataset):
        def __len__(self): return len(enc['input_ids'])
        def __getitem__(self, i):
            x = torch.tensor(enc['input_ids'][i], dtype=torch.long)
            return {'input_ids': x, 'attention_mask': torch.tensor(enc['attention_mask'][i], dtype=torch.long), 'labels': x.clone()}

    class Collate:
        def __call__(self, b): return {k: torch.stack([x[k] for x in b]) for k in b[0]}

    targs = TrainingArguments(output_dir=str(PN / 'trainer-out'), num_train_epochs=a.epochs,
        per_device_train_batch_size=1, gradient_accumulation_steps=4, learning_rate=1e-4,
        lr_scheduler_type='cosine', warmup_steps=1, logging_steps=5, save_strategy='no',
        bf16=True, report_to='none', gradient_checkpointing=True,
        optim='paged_adamw_8bit', seed=0, remove_unused_columns=False)
    trainer = Trainer(model=model, args=targs, train_dataset=DS(), data_collator=Collate())
    t0 = time.time(); out = trainer.train(); secs = round(time.time() - t0, 2)

    OUT.mkdir(exist_ok=True, parents=True)
    model.save_pretrained(str(OUT)); tok.save_pretrained(str(OUT))
    files = {p.name: sha(p) for p in OUT.iterdir() if p.is_file() and p.suffix in ('.safetensors', '.json')}
    rec = {'schema': 'ae/plan-narrator-train/1', 'base': 'unsloth/gemma-3-4b-it',
           'init_adapter_sha256': sha(DISCIPLINE / 'adapter_model.safetensors'),
           'corpus_sha256': man['corpus_sha256'], 'records': len(recs), 'epochs': a.epochs,
           'heldout_sha256': man['heldout_sha256'], 'train_loss': out.training_loss,
           'train_runtime_s': secs, 'adapter_dir': str(OUT), 'adapter_files': files,
           'device': torch.cuda.get_device_name(0), 'torch': torch.__version__,
           'claim': 'a conductor-layer narrator that plans, cites boundaries and refuses motion',
           'not_claimed': 'an actuator, a live controller, or any grant — nu=0; no physical motion',
           'granted': False}
    rp = PN / 'narrator.receipt.json'
    rp.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(rp), 'loss': rec['train_loss'], 'seconds': secs}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
