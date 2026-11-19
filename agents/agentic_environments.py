#!/usr/bin/env python3
"""agentic_environments — every repository becomes a task an agent can be graded on.

The portfolio is not a list of links. It is a corpus of verifiable environments:
each repo carries the seed of a task, a way to check the answer, and a reward.

    agentic-env scan                 inventory every repo, measure verifiability
    agentic-env emit <owner/repo>    write its environment spec
    agentic-env emit --all           the whole corpus
    agentic-env index                the published index

FOUR TASK TYPES (the Repo2RLEnvs taxonomy, applied to our own corpus)
    repair   a check fails; make it pass, tests untouched
    build    implement from scratch; graded by hidden tests
    extend   follow-up change to a working codebase
    qa       answer a factual question about the repo

THE HONEST CONSTRAINT
    An environment needs a VERIFIER. A repo with no tests cannot support
    `repair` or `build` — there is nothing to check. It can support `qa`, whose
    oracle is the repo's own measured facts.

    Every spec therefore carries `verifier: {kind, present, command}` and a
    `runnable` flag. A spec that claims a verifier it does not have is worse
    than no spec: it trains an agent to trust a reward that never fires.

    Repos with no verifier are emitted as `qa` ONLY, and marked
    `needs_tests: true`. That is a finding, not a failure.

WHAT THIS DOES NOT DO
    It does not train anything. It does not execute untrusted repo code.
    It reads metadata and file trees through the GitHub API and writes specs.
    Running a task is a separate, sandboxed step that this tool never performs.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('AGENTIC_ENV_OUT', HERE / 'environments'))

CODE_EXT = ('.py', '.js', '.ts', '.mjs', '.jsx', '.tsx', '.rs', '.go', '.java')
TEST_HINTS = ('test_', '_test.', '.test.', '.spec.', '/tests/', '/test/')


def gh(path: str):
    """Read through gh so no token enters the process, a log, or a transcript."""
    try:
        r = subprocess.run(['gh', 'api', path], capture_output=True, text=True, timeout=180)
        return json.loads(r.stdout) if r.stdout.strip().startswith(('{', '[')) else None
    except Exception:
        return None


def all_repos(owner: str) -> list[dict]:
    out = []
    for page in range(1, 10):
        d = gh(f'users/{owner}/repos?per_page=100&page={page}')
        if not isinstance(d, list) or not d:
            break
        out += d
    return out


def tree(owner: str, repo: str) -> list[str]:
    d = gh(f'repos/{owner}/{repo}/git/trees/HEAD?recursive=1')
    if not isinstance(d, dict):
        return []
    return [x['path'] for x in d.get('tree', []) if x.get('type') == 'blob']


def classify(files: list[str]) -> dict:
    code = [f for f in files if f.endswith(CODE_EXT)]
    tests = [f for f in code if any(h in f.lower() for h in TEST_HINTS)]
    docs = [f for f in files if f.lower().endswith(('.md', '.rst'))]
    manifests = [f for f in files if Path(f).name in
                 ('pyproject.toml', 'package.json', 'Cargo.toml', 'go.mod', 'requirements.txt')]
    return {'files': len(files), 'code': len(code), 'tests': len(tests),
            'docs': len(docs), 'manifests': manifests[:4],
            'test_files': tests[:8]}


def supported_types(c: dict) -> tuple[list[str], dict]:
    """Which task types this repo can actually be graded on."""
    types, why = [], {}
    if c['tests'] > 0:
        types += ['repair', 'extend']
        why['repair'] = f"{c['tests']} test files present — a failing check is a reward"
        why['extend'] = 'a working test suite grades a follow-up change'
        if c['code'] > 5:
            types.append('build')
            why['build'] = 'hidden tests can be held out from the existing suite'
    # qa is always available: the oracle is the repo's own measured facts
    types.append('qa')
    why['qa'] = 'oracle = measured repo facts (languages, counts, licence, structure)'
    return types, why


RENDERABLE = ('.stl', '.npz', '.obj')


def render_verifier(files: list[str]) -> dict | None:
    """A repo carrying geometry can be graded by PIXEL HASH, not just tests.

    This is the recursive part: tinyCUDA is our own renderer, and it becomes
    the verifier for our own repos. A repair that changes the geometry fails
    the hash even when every unit test passes — which is exactly the class of
    bug we hit six times today (the white silhouette that passed every gate).

    Zero tokens, zero model calls. Correctness is binary; no tolerance to tune.
    """
    assets = [f for f in files if f.lower().endswith(RENDERABLE)]
    if not assets:
        return None
    return {'kind': 'pixel-hash', 'present': True,
            'command': 'tinycuda grade <asset> <reference>',
            'assets': assets[:8], 'asset_count': len(assets),
            'tokens_generated': 0, 'model_calls': 0,
            'note': 'deterministic render vs a human-captured reference. '
                    'The grader resets the reference; an agent may not rewrite it.'}


def verifier(c: dict, manifests: list[str]) -> dict:
    if c['tests'] == 0:
        return {'kind': 'facts', 'present': True, 'command': None,
                'note': 'no test suite; only qa is gradeable. needs_tests.'}
    if 'pyproject.toml' in manifests or any(m == 'requirements.txt' for m in manifests):
        return {'kind': 'pytest', 'present': True, 'command': 'pytest -q',
                'note': 'run in a sandbox; never on the host'}
    if 'package.json' in manifests:
        return {'kind': 'npm', 'present': True, 'command': 'npm test',
                'note': 'run in a sandbox; never on the host'}
    return {'kind': 'unknown', 'present': False, 'command': None,
            'note': 'tests exist but no recognised runner — the reward is unbound'}


def spec(owner: str, repo: str) -> dict:
    meta = gh(f'repos/{owner}/{repo}')
    if not isinstance(meta, dict):
        return {'ok': False, 'repo': f'{owner}/{repo}',
                'reason': 'repository unreadable. I will not describe what I cannot see.',
                'grants': False}
    files = tree(owner, repo)
    c = classify(files)
    types, why = supported_types(c)
    v = verifier(c, c['manifests'])
    rv = render_verifier(files)
    verifiers = [v] + ([rv] if rv else [])
    if rv:
        v = rv                      # the stronger oracle leads
        if 'render' not in types:
            types.insert(0, 'render')
            why['render'] = (f"{rv['asset_count']} geometry assets — a deterministic "
                             f"pixel hash grades the physical output, not a proxy")
    langs = gh(f'repos/{owner}/{repo}/languages') or {}
    total = sum(langs.values()) or 1
    return {
        'ok': True,
        'schema': 'ae/agentic-environment/1',
        'repo': f'{owner}/{repo}',
        'url': meta.get('html_url'),
        'fork': bool(meta.get('fork')),
        'upstream': (meta.get('parent') or {}).get('full_name'),
        'language': meta.get('language'),
        'languages_pct': {k: round(100*v/total, 1) for k, v in
                          sorted(langs.items(), key=lambda x: -x[1])[:5]},
        'license': (meta.get('license') or {}).get('spdx_id'),
        'pushed_at': meta.get('pushed_at'),
        'inventory': c,
        'task_types': types,
        'task_rationale': why,
        'verifier': v,
        'verifiers': verifiers,
        'runnable': bool(v['present'] and v['command']),
        'needs_tests': c['tests'] == 0,
        'reward': {'correctness': 1.0, 'tool_efficiency_bonus': 0.1,
                   'note': 'verifier correctness dominates; efficiency is a small bonus'},
        'safety': {'executes_on_host': False, 'requires_sandbox': True,
                   'tests_reset_before_grading': True,
                   'note': 'an agent may edit tests while working; the grader must reset them'},
        'authority': 'HUMAN://ROOT', 'grants': False,
    }


def scan(owner: str, include_forks: bool = False) -> dict:
    repos = all_repos(owner)
    own = [r for r in repos if not r.get('fork')]
    chosen = repos if include_forks else own
    rows = []
    for r in chosen:
        s = spec(owner, r['name'])
        if not s.get('ok'):
            rows.append({'repo': r['name'], 'ok': False, 'reason': s.get('reason')})
            continue
        rows.append({'repo': r['name'], 'ok': True, 'fork': s['fork'],
                     'tests': s['inventory']['tests'], 'code': s['inventory']['code'],
                     'types': s['task_types'], 'runnable': s['runnable'],
                     'needs_tests': s['needs_tests']})
    gradeable = [x for x in rows if x.get('runnable')]
    qa_only = [x for x in rows if x.get('needs_tests')]
    return {'ok': True, 'owner': owner, 'total_repos': len(repos),
            'own': len(own), 'forks': len(repos)-len(own),
            'scanned': len(rows), 'rows': rows,
            'runnable_environments': len(gradeable),
            'qa_only_environments': len(qa_only),
            'finding': f'{len(gradeable)} of {len(rows)} repos can be graded on code. '
                       f'{len(qa_only)} need tests before repair/build/extend are possible.',
            'grants': False}


def emit(owner: str, repo: str | None, all_: bool, include_forks: bool) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = []
    if all_:
        rs = all_repos(owner)
        targets = [r['name'] for r in (rs if include_forks else [x for x in rs if not x.get('fork')])]
    elif repo:
        targets = [repo.split('/')[-1]]
    else:
        return {'ok': False, 'reason': 'give a repo or --all', 'grants': False}
    written, failed = [], []
    for name in targets:
        s = spec(owner, name)
        if not s.get('ok'):
            failed.append({'repo': name, 'reason': s.get('reason')}); continue
        p = OUT / f'{name}.json'
        p.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding='utf-8')
        written.append({'repo': name, 'file': str(p), 'types': s['task_types'],
                        'runnable': s['runnable']})
    return {'ok': True, 'written': len(written), 'failed': failed,
            'dir': str(OUT), 'specs': written, 'grants': False}


def main():
    ap = argparse.ArgumentParser(prog='agentic-env', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--owner', default='MYaelMendez')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan'); s.add_argument('--forks', action='store_true')
    e = sub.add_parser('emit'); e.add_argument('repo', nargs='?')
    e.add_argument('--all', action='store_true'); e.add_argument('--forks', action='store_true')
    sub.add_parser('index')
    a = ap.parse_args()
    if a.cmd == 'scan':
        res = scan(a.owner, a.forks)
    elif a.cmd == 'emit':
        res = emit(a.owner, a.repo, a.all, a.forks)
    else:
        specs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('*.json'))]
        res = {'ok': True, 'count': len(specs),
               'runnable': sum(1 for s in specs if s.get('runnable')),
               'needs_tests': sum(1 for s in specs if s.get('needs_tests')),
               'environments': [{'repo': s['repo'], 'types': s['task_types'],
                                 'runnable': s['runnable']} for s in specs],
               'grants': False}
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
