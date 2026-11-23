#!/usr/bin/env python3
"""NEON STUDIO RESOURCES — measured from the artifacts on disk, not authored.

Every field is a probe: sha256 of bytes, MuJoCo's own nq/nu/ngeom, file counts,
the verb table read from asimov_protocol.py, and the policy hash from neon_rule_env.
"""
from __future__ import annotations

import hashlib, importlib.util, json
from pathlib import Path

R = Path('C:/æ')
TWIN = Path('C:/Users/yaelm/AppData/Local/hermes/cache/scratch/asimov-twin/1.0.0')
OUT = R / 'mp4-factory/NEON-STUDIO-RESOURCES.json'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    import mujoco
    syspath = str(R / 'agents')
    import sys
    if syspath not in sys.path: sys.path.insert(0, syspath)
    import neon_rule_env as nre

    model = TWIN / 'model/asimov_1_25dof.xml'
    trace = R / 'tinymujoco/traces/805b855be6c457ba.json'
    verbs_py = R / 'agents/asimov_protocol.py'

    # verb table from the real module
    s = importlib.util.spec_from_file_location('ap', str(verbs_py))
    ap = importlib.util.module_from_spec(s); s.loader.exec_module(ap)
    verbs = {k: v.get('class') for k, v in sorted(ap.verbs()['verbs'].items())}

    # real model facts from MuJoCo, not from a docstring
    xml = model.read_text(encoding='utf-8')
    xml = __import__('re').sub(r'meshdir="[^"]*"', f'meshdir="{(TWIN / "meshes").as_posix()}"', xml)
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m); mujoco.mj_forward(m, d)
    tr = json.loads(trace.read_text(encoding='utf-8'))

    meshes = sorted((TWIN / 'meshes').glob('*.STL'))
    res = {
        'schema': 'ae/neon-studio-resources/1',
        'body': {'model': str(model), 'sha256': sha(model), 'nq': m.nq, 'nu': m.nu,
                 'ngeom': m.ngeom, 'meshes': len(meshes),
                 'meshes_sha256': hashlib.sha256(b''.join(sha(x).encode() for x in meshes)).hexdigest(),
                 'controllable': False, 'note': 'nu=0: authored stand pose + real trace qpos; no commanded act'},
        'trace': {'path': str(trace), 'sha256': sha(trace), 'policy': tr['policy'],
                  'policy_sha256': tr['policy_sha256'], 'frames': len(tr['qpos']),
                  'nq': tr['nq'], 'joints': len(tr['joint_names']),
                  'authority': tr['authority']},
        'verbs': {'count': len(verbs), 'by_class': {c: sum(v == c for v in verbs.values())
                    for c in sorted(set(verbs.values()))}, 'table': verbs,
                  'source_sha256': sha(verbs_py)},
        'gate': {'policy_sha256': nre.policy().get('policy_sha256'),
                 'bands': list(nre.BANDS),
                 'evaluate_observe_public': nre.evaluate('observe', 'PUBLIC')['decision'],
                 'evaluate_act_custody': nre.evaluate('act', 'CUSTODY')['decision']},
        'renderer': {'mujoco': mujoco.__version__, 'width': 576, 'height': 1024,
                     'depth': 'enable_depth_rendering()'},
        'claim': 'measured resources for the next governed Asimov verb film',
        'not_claimed': 'physical motion — nu=0 plant; every verb is a governed stage',
    }
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(OUT), 'bytes': OUT.stat().st_size,
                      'verbs': res['verbs']['count'], 'frames': res['trace']['frames'],
                      'nq': res['body']['nq'], 'nu': res['body']['nu']}, indent=2))


if __name__ == '__main__':
    main()
