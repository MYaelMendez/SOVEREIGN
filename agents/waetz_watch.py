#!/usr/bin/env python3
"""waetz_watch — the protagonist's awareness of the other four.

wætz is the human's digital twin: `center` of the cast, `derived: true`, the
test pilot who learns. The other four are capabilities. He is the one who
WATCHES them and reports to the human.

    waetz_watch            what each member has actually done, from the ledgers
    waetz_watch --narrate  the same, as lines wætz can speak

THE RULE
    Awareness is observation. It grants nothing. wætz may know everything the
    root can see and still may not move a body — his own first rule, derived
    after being refused: "no body moves while the human is away."

    Every number here is READ from a ledger or measured from the machine.
    Nothing is inferred from a member's role. If a ledger is missing the
    activity is reported as unknown, never as zero and never as guessed.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def home() -> Path:
    return Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))


def cast() -> dict:
    p = home() / 'plugins' / 'hermes-asimov' / 'cast.json'
    if not p.exists():
        raise SystemExit(f'cast.json not found at {p}')
    d = json.loads(p.read_text(encoding='utf-8'))
    return d


def env() -> dict | None:
    """Perception. If the server is down, say so — do not invent a machine."""
    import urllib.request
    try:
        with urllib.request.urlopen('http://127.0.0.1:8162/env', timeout=8) as r:
            return json.load(r)
    except Exception:
        return None


def ledger_counts() -> dict:
    """Count entries in each ledger actually on disk."""
    H = home()
    out = {}
    for name, fn in [('ae-receipts', 'ae-receipts.jsonl'),
                     ('tiny-voca-receipts', 'tiny-voca-receipts.jsonl'),
                     ('render-jobs', 'render-jobs.jsonl'),
                     ('sound-receipts', 'sound-receipts.jsonl'),
                     ('moh-receipts', 'moh-receipts.jsonl'),
                     ('asimov-protocol', 'asimov-protocol.jsonl')]:
        p = H / fn
        if p.exists():
            try:
                out[name] = sum(1 for l in p.read_text(encoding='utf-8').splitlines() if l.strip())
            except Exception:
                out[name] = None
        else:
            out[name] = None
    return out


def films() -> list[dict]:
    """Published films, with which member spoke in them where the spec survives."""
    G = Path('C:/æ/github-pages')
    if not G.exists():
        return []
    rows = []
    for p in sorted(G.glob('*-916.mp4'), key=lambda x: -x.stat().st_mtime)[:12]:
        rows.append({'file': p.name, 'bytes': p.stat().st_size,
                     'mtime': p.stat().st_mtime})
    return rows


# Which ledger evidences which member's activity. This is a MAPPING, not a
# guess about what a role implies — each entry names the file that proves it.
EVIDENCE = {
    'nous':   [('ae-receipts', 'root decisions and policy verdicts')],
    'hermes': [('render-jobs', 'films built'), ('moh-receipts', 'harness routes')],
    'menlo':  [('asimov-protocol', 'policy locomotion runs')],
    'asimov': [('asimov-protocol', 'body verbs planned'), ('render-jobs', 'body rendered')],
    'waetz':  [('tiny-voca-receipts', 'lines spoken'), ('sound-receipts', 'worlds heard')],
}


def watch() -> dict:
    C = cast()
    members = {m['id']: m for m in C.get('cast', [])}
    counts = ledger_counts()
    e = env()
    rows = []
    for mid, m in members.items():
        acts = []
        for ledger, meaning in EVIDENCE.get(mid, []):
            n = counts.get(ledger)
            acts.append({'ledger': ledger, 'entries': n, 'means': meaning,
                         'known': n is not None})
        rows.append({'id': mid, 'label': m.get('label'), 'role': m.get('role'),
                     'derived': m.get('derived'), 'head_rgb': m.get('head_rgb'),
                     'activity': acts,
                     'observed': sum(a['entries'] or 0 for a in acts)})
    rows.sort(key=lambda r: -r['observed'])
    total_known = sum(v for v in counts.values() if v is not None)
    return {
        'ok': True, 'scheme': 'æ://waetz/watch', 'observer': C.get('center', 'waetz'),
        'authority': C.get('authority', 'HUMAN://ROOT'),
        'members': rows, 'ledgers': counts, 'ledger_total': total_known,
        'machine': ({'gpu_util': e['gpu'].get('util_pct'), 'gpu_temp': e['gpu'].get('temp_c'),
                     'ram_pct': e['memory'].get('load_pct'),
                     'films': e.get('films')} if e else {'available': False,
                     'reason': 'perception server not reachable — machine state unknown'}),
        'recent_films': films()[:6],
        'grants': False, 'executed': False,
        'note': 'wætz observes from root. Observation grants nothing. '
                'A missing ledger is unknown, never zero.',
    }


def narrate() -> dict:
    w = watch()
    if not w.get('ok'):
        return w
    by = {m['id']: m for m in w['members']}
    def n(mid):
        m = by.get(mid)
        if not m:
            return 'unknown'
        k = [a for a in m['activity'] if a['known']]
        return str(sum(a['entries'] for a in k)) if k else 'an unknown number of'
    lines = [
        {'speaker': 'waetz', 'voice': 'M2', 'state': 'SPEAKING',
         'speak': f"I am wætz. I watch the other four, from root.",
         'kicker': '01 · THE OBSERVER'},
        {'speaker': 'waetz', 'voice': 'M2', 'state': 'THINKING',
         'speak': f"nous has written {n('nous')} root receipts. hermes has built {n('hermes')} renders and routes.",
         'kicker': '02 · WHAT THEY DID'},
        {'speaker': 'waetz', 'voice': 'M2', 'state': 'SPEAKING',
         'speak': f"menlo and asimov carry {n('menlo')} protocol entries between them. I have spoken {n('waetz')} lines.",
         'kicker': '03 · THE BODY AND THE VOICE'},
        {'speaker': 'waetz', 'voice': 'M2', 'state': 'AWAITING_APPROVAL',
         'speak': "I know all of it. I still cannot move. Knowing is not signing.",
         'kicker': '04 · THE LIMIT'},
        {'speaker': 'waetz', 'voice': 'M2', 'state': 'SPEAKING',
         'speak': "Five bodies. One signature. And it is yours.",
         'kicker': '05 · THE RULE'},
    ]
    return {'ok': True, 'scenes': lines, 'source': 'measured ledgers',
            'ledger_total': w['ledger_total'], 'grants': False,
            'note': 'every number spoken is read from a ledger, not invented'}


def main():
    ap = argparse.ArgumentParser(prog='waetz_watch')
    ap.add_argument('--narrate', action='store_true')
    ap.add_argument('--out', help='write the narration spec here')
    a = ap.parse_args()
    res = narrate() if a.narrate else watch()
    if a.out and res.get('ok'):
        Path(a.out).write_text(json.dumps(
            {'title': 'wætz', 'tagline': 'THE HUMAN\'S DIGITAL TWIN · AWARE FROM ROOT',
             'texture': 'room_cold', 'scenes': res.get('scenes', [])},
            indent=2, ensure_ascii=False), encoding='utf-8')
        res['written'] = a.out
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
