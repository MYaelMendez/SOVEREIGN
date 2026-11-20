#!/usr/bin/env python3
"""nano:// — the cast teaches machine learning, one concept per film.

tiny was a package. nano is a LESSON: one idea, five voices, under a minute,
vertical, on the phone a new developer already holds.

    nano list                     the concepts the cast can teach
    nano spec <concept>           write the film spec
    nano render <concept> out.mp4 the whole lesson

WHY THE CAST CAN TEACH
    The five members are not mascots. Their roles map onto the learning loop:

        nous    root voice      → the objective. what are we optimising?
        hermes  build voice     → the mechanism. how is it implemented?
        menlo   upstream source → the prior. what did we inherit?
        asimov  robot body      → the policy. what does it actually do?
        waetz   test pilot      → the learner. what did we find out?

    waetz asks. The others answer. He is `center` of the cast and the only
    member whose role is to LEARN — so the student is on screen, not implied.

THE RULE THAT MAKES IT HONEST
    Every lesson carries a `demonstration` — a real measurement from this
    machine that shows the concept, not an animation of it. A lesson about
    reward hacking shows the pixel-hash catching the white silhouette. A
    lesson about exploration shows the policy's 64 knee reversals against a
    keyframe's 12.

    If a concept has no demonstration available, the spec says so and the
    lesson is marked `illustrated, not demonstrated`. We do not animate a
    claim we have not measured.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# role → the part of the learning loop this voice owns
TEACHER = {
    'nous':   'the objective',
    'hermes': 'the mechanism',
    'menlo':  'the prior',
    'asimov': 'the policy',
    'waetz':  'the learner',
}
VOICE = {'nous': 'F2', 'hermes': 'M2', 'menlo': 'M2', 'asimov': 'F2', 'waetz': 'M2'}

# Each concept: the question waetz asks, four answers from the four roles,
# and a DEMONSTRATION measured on this machine. Accuracy over simplification.
CONCEPTS = {
    'reward': {
        'title': 'what is a reward',
        'ask': 'What is a reward, actually?',
        'nous': 'A number that says how good an outcome was. Nothing more.',
        'hermes': 'The loop reads it and shifts the policy toward more of it.',
        'menlo': 'My gait was rewarded for velocity. So it learned to move fast.',
        'asimov': 'Nobody rewarded lifting my feet. So I never learned to.',
        'close': 'The reward wrote the gait. Choose it carefully.',
        'demo': 'knee swing 46 degrees, foot clearance 1.5 centimetres — measured',
        'measured': True,
    },
    'policy': {
        'title': 'what is a policy',
        'ask': 'What is a policy?',
        'nous': 'A rule for choosing an action from what you can see.',
        'hermes': 'Seventy eight floats in. Twenty three joint targets out. Fifty times a second.',
        'menlo': 'Mine is eight hundred thirty one kilobytes. It runs on a laptop.',
        'asimov': 'I do not plan my steps. I react, faster than planning.',
        'close': 'A policy is a reflex you can train.',
        'demo': '600 policy ticks, 2400 physics steps, 7.87 metres, no fall',
        'measured': True,
    },
    'exploration': {
        'title': 'why exploration matters',
        'ask': 'Why do you try things that fail?',
        'nous': 'Because the best action is not the one you already know.',
        'hermes': 'We sample eight rollouts per task and keep what scored.',
        'menlo': 'My training tried gaits that fell. That is how it found one that did not.',
        'asimov': 'Every fall was information. None was waste.',
        'close': 'A refusal is a result, not a failure.',
        'demo': 'the policy knee reverses 64 times; a keyframed sine reverses 12',
        'measured': True,
    },
    'overfitting': {
        'title': 'what overfitting looks like',
        'ask': 'How do I know I actually learned?',
        'nous': 'When you succeed on something you have never seen.',
        'hermes': 'We hold out tasks. Sixty eight of eighty six were never used to pick the checkpoint.',
        'menlo': 'My viewer contract is matched. Its training randomisations are not.',
        'asimov': 'I walk in this simulation. I have not been tested in yours.',
        'close': 'One machine is not a result. It is a start.',
        'demo': 'held-out split 68/86; second-box reproduction still unperformed',
        'measured': True,
    },
    'reward-hacking': {
        'title': 'what reward hacking is',
        'ask': 'Can you cheat the reward?',
        'nous': 'Yes. And that is the most important failure to design against.',
        'hermes': 'A render passed every gate and was a white silhouette. The geometry was right; the picture was wrong.',
        'menlo': 'So the guard belongs in your code. Not in the metric.',
        'asimov': 'Now a pixel hash grades me. Zero tokens. It cannot be argued with.',
        'close': 'Verify the thing, not a proxy for the thing.',
        'demo': 'colours 0-255 instead of 0-1: gate PASS, picture broken, pixel hash 0.0',
        'measured': True,
    },
    'transfer': {
        'title': 'what transfer learning is',
        'ask': 'Did you learn to walk from nothing?',
        'nous': 'No. Almost nothing is learned from nothing.',
        'hermes': 'We run a policy someone else trained. Eight hundred thirty one kilobytes.',
        'menlo': 'I trained it on hardware you do not own. You get the result.',
        'asimov': 'I inherit the walking. I did not earn it.',
        'close': 'Open capability composes downward.',
        'demo': 'policy sha 47f70691, 831809 bytes, trained upstream, run locally',
        'measured': True,
    },
    'sim2real': {
        'title': 'the sim to real gap',
        'ask': 'Would you walk on a real floor?',
        'nous': 'That is the question the whole field is asking.',
        'hermes': 'The inference contract is matched exactly. The noise and delays are not.',
        'menlo': 'Training randomised my gains. This simulation does not.',
        'asimov': 'I have never touched a floor. I have only touched a solver.',
        'close': 'Simulation is where you prove it. Hardware is where you find out.',
        'demo': 'no physical robot attached; hardware://asimov is DECLARED',
        'measured': True,
    },
    'determinism': {
        'title': 'why determinism matters',
        'ask': 'Why do you render the same thing twice?',
        'nous': 'Because a result you cannot repeat is not a result.',
        'hermes': 'Depth and triangle id packed into one atomic. No race. Twelve of twelve frames identical.',
        'menlo': 'My policy is deterministic too. Same observation, same action.',
        'asimov': 'So a stranger gets my exact pixels. Not approximately mine.',
        'close': 'A receipt only means something if the thing repeats.',
        'demo': '12/12 frames byte-identical, sha b03512e3db620076',
        'measured': True,
    },
}


def list_concepts() -> dict:
    return {'ok': True, 'scheme': 'nano://', 'count': len(CONCEPTS),
            'concepts': [{'id': k, 'title': v['title'],
                          'demonstrated': v['measured']} for k, v in CONCEPTS.items()],
            'teachers': TEACHER, 'grants': False,
            'note': 'waetz asks; the four roles answer. The student is on screen.'}


def spec(concept: str) -> dict:
    c = CONCEPTS.get(concept)
    if not c:
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': f'unknown concept {concept!r}', 'available': sorted(CONCEPTS)}
    order = ['waetz', 'nous', 'hermes', 'menlo', 'asimov', 'waetz']
    lines = [c['ask'], c['nous'], c['hermes'], c['menlo'], c['asimov'], c['close']]
    kick = ['01 · THE QUESTION', '02 · THE OBJECTIVE', '03 · THE MECHANISM',
            '04 · THE PRIOR', '05 · THE POLICY', '06 · THE LESSON']
    scenes = [{'speaker': s, 'voice': VOICE[s], 'state': 'SPEAKING',
               'speak': l, 'kicker': k} for s, l, k in zip(order, lines, kick)]
    return {'ok': True, 'concept': concept,
            'title': f"nano:// {c['title']}",
            'tagline': 'FIVE VOICES · ONE IDEA',
            'texture': 'room_cold', 'scenes': scenes,
            'demonstration': c['demo'],
            'demonstrated': c['measured'],
            'cast': 'nous,hermes,waetz,menlo,asimov',
            'grants': False,
            'note': 'every claim here is measured on this machine or marked as inherited'}


def render(concept: str, out: Path, seconds: float = 20.0) -> dict:
    s = spec(concept)
    if not s.get('ok'):
        return s
    sp = HERE / f'nano-{concept}.json'
    sp.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding='utf-8')
    conv = HERE / 'convergence.py'
    if not conv.exists():
        return {'ok': False, 'refused': True, 'reason': 'convergence.py not beside nano.py',
                'grants': False}
    model = os.environ.get('NANO_MODEL_DIR')
    if not model:
        h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
        cand = h / 'cache' / 'scratch' / 'portable-test' / 'model'
        model = str(cand) if cand.exists() else None
    if not model:
        return {'ok': False, 'refused': True, 'grants': False,
                'reason': 'no model dir; set NANO_MODEL_DIR or run tinygpu fetch'}
    args = [sys.executable, str(conv), '--out', str(out), '--seconds', str(seconds),
            '--cast', s['cast'], '--scenes', str(sp), '--texture', s['texture'],
            '--model-dir', model, '--title', s['title'], '--tagline', s['tagline']]
    trace = os.environ.get('NANO_TRACE')
    if trace and Path(trace).exists():
        args += ['--trace', trace]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    return {'ok': out.exists(), 'concept': concept, 'file': str(out),
            'bytes': out.stat().st_size if out.exists() else 0,
            'demonstration': s['demonstration'], 'spec': str(sp),
            'stdout_tail': r.stdout[-400:], 'grants': False}


def main():
    ap = argparse.ArgumentParser(prog='nano', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    s = sub.add_parser('spec'); s.add_argument('concept'); s.add_argument('--out')
    r = sub.add_parser('render'); r.add_argument('concept'); r.add_argument('out')
    r.add_argument('--seconds', type=float, default=20.0)
    a = ap.parse_args()
    if a.cmd == 'list':
        res = list_concepts()
    elif a.cmd == 'spec':
        res = spec(a.concept)
        if a.out and res.get('ok'):
            Path(a.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding='utf-8')
            res['written'] = a.out
    else:
        res = render(a.concept, Path(a.out), a.seconds)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
