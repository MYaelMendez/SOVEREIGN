#!/usr/bin/env python3
"""
neuromitosis corpus — deterministic SFT records built ONLY from receipts already
on disk. No invented facts, no secrets, no authority claims.

Each record carries source_sha256 (hash of the file it was derived from) so a
trainer can prove what it was taught. Identity is served by the proxy at runtime;
these records teach the *discipline*, not a fabricated persona.
"""
from __future__ import annotations

import hashlib, json
from pathlib import Path

ROOT = Path('C:/æ')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rec(instruction: str, response: str, source: Path, kind: str) -> dict:
    return {'schema': 'ae/sft/1', 'kind': kind, 'instruction': instruction.strip(),
            'response': response.strip(), 'source': str(source.relative_to(ROOT)).replace('\\', '/'),
            'source_sha256': sha(source)}


def build() -> list[dict]:
    out = []

    # 1. Lessons: defect -> invariant -> change. The estate's own learned law.
    p = ROOT / 'logs/ae_lessons.jsonl'
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        l = json.loads(line)
        out.append(_rec(
            f"A build produced the defect: {l['defect']} What invariant prevents it?",
            f"invariant: {l['invariant']}\nchange: {l['change']}\ncheck: {json.dumps(l['check'], ensure_ascii=False)}",
            p, 'lesson'))

    # 2. Takes: what a human-bound action actually looks like.
    p = ROOT / 'logs/tinyactor-takes.jsonl'
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        out.append(_rec(
            f"Describe the authorization of the {t['scene']} scene action.",
            (f"verb={t['verb']} scene={t['scene']} camera={t['camera']} "
             f"action_sha256={t['action_sha256']} card_sha256={t['card_sha256']}. "
             f"granted={t['granted']} grants={t['grants']} — the take bounds a turn, "
             f"it is not self-authorization. receipt={t['hash']}"), p, 'take'))

    # 3. Identity discipline: what the æ boy may and may not claim.
    p = ROOT / 'agents/ae-boy-identity.txt'
    txt = p.read_text(encoding='utf-8')
    out.append(_rec('What is the æ boy and what may it claim?',
                    txt, p, 'identity'))

    # 4. Receipt honesty boundaries: claim / not_claimed.
    for rel in ('mp4-factory/tinyactor-performance-916.receipt.json',
                'mp4-factory/neon-holomesh-916.receipt.json'):
        p = ROOT / rel
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        out.append(_rec(f"What does the artifact {p.name} prove, and what does it not prove?",
                        f"claim: {d.get('claim','')}\nnot_claimed: {d.get('not_claimed','')}\n"
                        f"sha256: {d.get('sha256','')}\ngranted: {d.get('granted')}", p, 'receipt'))

    # 5. Policy: the actual bound-human governance contract.
    p = ROOT / 'github-pages/ae-policy.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    out.append(_rec('State the authority policy for machines and agents.',
                    json.dumps(d, ensure_ascii=False, indent=1), p, 'policy'))
    return out


def main():
    recs = build()
    out = ROOT / 'neuromitosis/corpus.jsonl'
    out.parent.mkdir(exist_ok=True)
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in recs), encoding='utf-8')
    manifest = {'schema': 'ae/neuromitosis-corpus/1', 'records': len(recs),
                'kinds': {k: sum(r['kind'] == k for r in recs) for k in sorted({r['kind'] for r in recs})},
                'corpus_sha256': sha(out), 'bytes': out.stat().st_size,
                'source_files': sorted({r['source'] for r in recs})}
    mp = out.with_name('corpus.manifest.json')
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
