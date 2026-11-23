#!/usr/bin/env python3
"""qlora_smoke.py — prove QLoRA works on this 6GB node with a measured receipt.

5 steps, Qwen3-0.6B, NF4 + LoRA r16. Records a JSON receipt with live VRAM.
Never writes weights into git; adapter goes to --out dir (scratch by default).
"""
from __future__ import annotations
import argparse, hashlib, inspect, json, sys, time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

RECORDS = [
    {"instruction":"What is tinyFANIN?","response":"tinyFANIN folds N receipts into ONE truth via a SHA-256 hash chain. A receipt without a measured digest is REFUSED, never skipped."},
    {"instruction":"When does verify refuse?","response":"verify recomputes the chain from live fields. A tampered digest returns exit 10 and names the broken members. A cached chain_input would let sabotage pass — never cache it."},
    {"instruction":"Where do secrets live?","response":"Custody stays on the local node at C:\\æ\\secrets. Never move a credential into a transcript, surface or log. A public surface is truth, not a secret store."},
    {"instruction":"What is the gate rule?","response":"Where a gate exists, pass through it. Where one does not, say the check is missing rather than report a pass. A thing not checked back is not a thing."},
    {"instruction":"How does kanban push work?","response":"Use kanban_push.py, never bare git push. Claim before you act: a shared read-modify-write window needs a lock and a record."},
]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",default="Qwen/Qwen3-0.6B")
    ap.add_argument("--out",default="C:/Users/yaelm/AppData/Local/hermes/cache/scratch/qlora-smoke/adapter")
    ap.add_argument("--steps",type=int,default=5)
    a=ap.parse_args()
    t0=time.time()
    torch.cuda.reset_peak_memory_stats()
    free0,total=torch.cuda.mem_get_info()

    tok=AutoTokenizer.from_pretrained(a.model)
    tok.pad_token=tok.eos_token
    bnb=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=True)
    base=AutoModelForCausalLM.from_pretrained(a.model,quantization_config=bnb,device_map={"":0})
    base=prepare_model_for_kbit_training(base)
    lora=LoraConfig(r=16,lora_alpha=32,lora_dropout=0.05,target_modules="all-linear",task_type="CAUSAL_LM")
    model=get_peft_model(base,lora)
    trainable=sum(p.numel() for p in model.parameters() if p.requires_grad)

    texts=[f"### Instruction:\n{r['instruction']}\n\n### Response:\n{r['response']}" for r in RECORDS]*4
    enc=tok(texts,truncation=True,max_length=256,padding="max_length",return_tensors="pt")
    class DS(torch.utils.data.Dataset):
        def __len__(self): return enc["input_ids"].shape[0]
        def __getitem__(self,i):
            ids=enc["input_ids"][i]
            return {"input_ids":ids,"attention_mask":enc["attention_mask"][i],"labels":ids.clone()}
    def collate(features):
        k=features[0].keys()
        return {x:torch.stack([f[x] for f in features]) for x in k}

    sig=inspect.signature(TrainingArguments.__init__).parameters
    kw=dict(output_dir=a.out,max_steps=a.steps,per_device_train_batch_size=1,
        gradient_accumulation_steps=2,gradient_checkpointing=True,learning_rate=2e-4,
        bf16=True,logging_steps=1,save_strategy="no",report_to=[],optim="paged_adamw_8bit")
    if "warmup_ratio" in sig: kw["warmup_ratio"]=0.03
    else: kw["warmup_steps"]=1
    args=TrainingArguments(**kw)
    trainer=Trainer(model=model,args=args,train_dataset=DS(),data_collator=collate)
    out=trainer.train()

    peak=torch.cuda.max_memory_allocated()/2**30
    reserved=torch.cuda.memory_reserved()/2**30
    rec={"model":a.model,"steps":a.steps,"trainable_params":trainable,
         "peak_allocated_gib":round(peak,2),"peak_reserved_gib":round(reserved,2),
         "free_before_gib":round(free0/2**30,2),"total_gib":round(total/2**30,2),
         "final_loss":round(float(out.training_loss),4),"seconds":round(time.time()-t0,1),
         "ok":True}
    model.save_pretrained(a.out)
    p=Path(a.out)/"receipt.json"; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(rec,indent=2),encoding="utf-8")
    print("RECEIPT",json.dumps(rec))
    return 0

if __name__=="__main__": sys.exit(main())
