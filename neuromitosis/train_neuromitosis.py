#!/usr/bin/env python3
"""
neuromitosis QLoRA — train the adoptive Gemma on estate receipts only.

Base:  unsloth/gemma-3-4b-it (trainable safetensors)
Data:  neuromitosis/corpus.jsonl (44 records, every one hash-bound to a source)
Out:   neuromitosis/lora-adapter/ + receipt with hashes

The GGUF that serves the æ boy is NEVER modified. The adapter is applied at
serve time with llama-server --lora. Inference ≠ authority.
"""
from __future__ import annotations

import argparse, hashlib, json, time
from pathlib import Path

ROOT = Path('C:/æ/neuromitosis')
BASE = Path('C:/æ/models/gemma-3-4b-it-train')
CORPUS = ROOT / 'corpus.jsonl'
OUT = ROOT / 'lora-adapter'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_records():
    recs = [json.loads(l) for l in CORPUS.read_text(encoding='utf-8').splitlines() if l.strip()]
    m = json.loads((ROOT / 'corpus.manifest.json').read_text(encoding='utf-8'))
    assert len(recs) == m['records'], 'corpus drifted from manifest'
    assert sha(CORPUS) == m['corpus_sha256'], 'corpus hash mismatch'
    return recs, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=2)
    ap.add_argument('--max-length', type=int, default=384)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    recs, manifest = load_records()
    if a.dry_run:
        print(json.dumps({'ok': True, 'records': len(recs), 'kinds': manifest['kinds'],
                          'corpus_sha256': manifest['corpus_sha256'],
                          'base_exists': BASE.exists()}, indent=2))
        return 0

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainingArguments)
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training

    print('torch', torch.__version__, 'cuda', torch.cuda.is_available(),
          torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU', flush=True)
    if not torch.cuda.is_available():
        print('REFUSING: QLoRA on CPU is not the tested path; no device claim made')
        return 2

    tok = AutoTokenizer.from_pretrained(str(BASE))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(str(BASE), quantization_config=bnb,
                                                 device_map={'': 0})
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lcfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=16, lora_dropout=0.05,
                      target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj',
                                      'gate_proj', 'up_proj', 'down_proj'], bias='none')
    model = get_peft_model(model, lcfg)
    model.print_trainable_parameters()

    texts = []
    for r in recs:
        texts.append(f"<start_of_turn>user\n{r['instruction']}<end_of_turn>\n"
                     f"<start_of_turn>model\n{r['response']}<end_of_turn>")
    enc = tok(texts, truncation=True, max_length=a.max_length, padding='max_length')

    class DS(torch.utils.data.Dataset):
        def __len__(self): return len(enc['input_ids'])
        def __getitem__(self, i):
            x = torch.tensor(enc['input_ids'][i], dtype=torch.long)
            mask = torch.tensor(enc['attention_mask'][i], dtype=torch.long)
            return {'input_ids': x, 'attention_mask': mask, 'labels': x.clone()}

    targs = TrainingArguments(
        output_dir=str(ROOT / 'trainer-out'), num_train_epochs=a.epochs,
        per_device_train_batch_size=1, gradient_accumulation_steps=4,
        learning_rate=2e-4, lr_scheduler_type='cosine', warmup_steps=1,
        logging_steps=5, save_strategy='no', bf16=True, report_to='none',
        gradient_checkpointing=True, optim='paged_adamw_8bit', seed=0,
        remove_unused_columns=False)

    class Collate:
        def __call__(self, batch):
            return {k: torch.stack([b[k] for b in batch]) for k in batch[0]}

    trainer = Trainer(model=model, args=targs, train_dataset=DS(), data_collator=Collate())
    t0 = time.time()
    train_out = trainer.train()
    secs = round(time.time() - t0, 2)

    OUT.mkdir(exist_ok=True, parents=True)
    model.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT))
    files = sorted(p.name for p in OUT.iterdir() if p.is_file())
    adapter_files = {p.name: sha(p) for p in OUT.iterdir() if p.is_file() and p.suffix in ('.safetensors', '.json')}
    rec = {'schema': 'ae/neuromitosis-train/1', 'base': 'unsloth/gemma-3-4b-it',
           'base_dir': str(BASE), 'corpus_sha256': manifest['corpus_sha256'],
           'records': len(recs), 'epochs': a.epochs, 'max_length': a.max_length,
           'lora_r': 8, 'lora_alpha': 16, 'quant': 'nf4-4bit-double',
           'trainable_parameters': getattr(model, '_trainable_params', None),
           'train_loss': train_out.training_loss, 'train_runtime_s': secs,
           'adapter_dir': str(OUT), 'adapter_files': adapter_files,
           'device': torch.cuda.get_device_name(0), 'torch': torch.__version__,
           'claim': 'a receipt-bearing LoRA adapter trained on estate receipts, never on secrets',
           'not_claimed': 'a new authority — adapter does not grant acts, change policy, or move a robot',
           'granted': False}
    rp = ROOT / 'neuromitosis.receipt.json'
    rp.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(rp), 'loss': rec['train_loss'], 'seconds': secs,
                      'files': files}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
