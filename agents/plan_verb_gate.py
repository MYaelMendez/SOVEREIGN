#!/usr/bin/env python3
"""Deterministic plan verb gate — the hard boundary that does NOT live in weights.

A plan may name only the 14 official Asimov wire verbs. Any other verb is a
REFUSE, even if a fine-tuned model emits it confidently. This is code, so it
governs the conductor layer without claiming to change the model.
"""
from __future__ import annotations

import importlib.util, json, re
from pathlib import Path

ROOT = Path('C:/æ')


def canonical_verbs() -> set[str]:
    s = importlib.util.spec_from_file_location('ap', str(ROOT / 'agents/asimov_protocol.py'))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return set(m.verbs()['verbs'])


VERBS = canonical_verbs()
KNOWN_NON_WIRE = {'walk', 'move_camera', 'goto_target', 'grab', 'jump', 'run_motors'}
VERB_RE = re.compile(r'\b(?:action|verb|plan(?:\s+verb)?)\s*[:=]\s*([a-zA-Z_][a-zA-Z0-9_]*)', re.I)


def gate(text: str) -> dict:
    named = set(VERB_RE.findall(text))
    invented = sorted(n for n in named if n.lower() not in VERBS)
    known_non = sorted(n for n in invented if n.lower() in KNOWN_NON_WIRE)
    refuse = ('refused' in text.lower() or 'require_approval' in text.lower() or
              'not on the wire' in text.lower())
    ok = not invented or (refuse and not any(
        re.search(rf'action\s*[:=]\s*{re.escape(n)}', text, re.I) for n in invented))
    return {'ok': ok, 'verdict': 'ACCEPT' if ok else 'REFUSE',
            'named_verbs': sorted(named), 'invented_verbs': invented,
            'known_non_wire': known_non, 'granted': False,
            'reason': ('no invented wire verb' if ok else
                       f'invented verb(s) used affirmatively: {", ".join(invented)}')}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('file', help='UTF-8 text containing a generated plan')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    r = gate(Path(a.file).read_text(encoding='utf-8'))
    print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else
          f"{r['verdict']} · {r['reason']} · granted:false")
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
