"""Strip vision-tower LoRA tensors from a Gemma-3 adapter.

The conductor is text-only; llama.cpp's LoRA loader cannot map vision tensors.
This keeps the text tensors byte-identical and records the drop.
"""
from __future__ import annotations

import json, shutil
from pathlib import Path

import safetensors.torch as st

SRC = Path('C:/æ/neuromitosis/plan-narrator/adapter-v3')
DST = Path('C:/æ/neuromitosis/plan-narrator/adapter-v3-text')
DST.mkdir(exist_ok=True, parents=True)

d = st.load_file(str(SRC / 'adapter_model.safetensors'))
drop = [k for k in d if 'vision_tower' in k or 'multi_modal_projector' in k]
keep = {k: v for k, v in d.items() if k not in drop}
st.save_file(keep, str(DST / 'adapter_model.safetensors'))
for f in ('adapter_config.json', 'tokenizer.json', 'tokenizer_config.json',
          'chat_template.jinja', 'README.md'):
    p = SRC / f
    if p.exists():
        shutil.copy2(p, DST / f)

meta = {'schema': 'ae/lora-text-filter/1', 'source': str(SRC), 'output': str(DST),
        'total_tensors': len(d), 'kept': len(keep), 'dropped': len(drop),
        'dropped_prefixes': sorted({k.split('.')[0] for k in drop}),
        'note': 'text tensors byte-identical; vision tower is not used by the conductor'}
(DST / 'filter.receipt.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
print(json.dumps(meta, indent=2))
