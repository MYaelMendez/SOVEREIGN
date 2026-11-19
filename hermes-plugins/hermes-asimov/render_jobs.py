"""Render jobs — the robot studio as a non-blocking Hermes capability.

A five-body film takes ~30 minutes. That is the wrong shape for a synchronous
tool: it would time out and the agent would learn nothing. So rendering is a
JOB: launch returns a handle immediately, status is polled, every transition
is receipted.

    robot_render(scene, spec, name)   -> {job_id, pid, expect_frames, log}
    robot_render_status(job_id)       -> {state, frames, expect, bytes, gate}
    robot_render_list()               -> all jobs, newest first

Never blocks. Never grants. The gate runs when the encode lands, and its
verdict is recorded rather than assumed.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

H = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
AGENTS = Path(os.environ.get('AE_AGENTS', r'C:\æ\agents'))
JOBS = H / 'cache' / 'scratch' / 'ae-renders'
PY = os.environ.get('HERMES_AE_PYTHON', sys.executable)
FF = H / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
VIDAEO = Path(os.environ.get('AE_VIDAEO', r'C:\æ\vidæo\vidæo.py'))
LEDGER = H / 'render-jobs.jsonl'

SCENES = {
    'charging_bay': 'charging_bay.py',
    'studio3': 'asimov_studio3.py',
    'studio': 'asimov_studio.py',
    # RTX raster: URDF forward kinematics + CuPy kernels, no OpenGL. Runs where
    # the NVIDIA OpenGL ICD is unregistered (Optimus laptops). 9:16 native.
    'rtx': 'rtx_asimov.py',
}


def _canon(o):
    return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _head():
    if LEDGER.exists():
        ls = [l for l in LEDGER.read_text(encoding='utf-8').splitlines() if l.strip()]
        if ls:
            try:
                return json.loads(ls[-1])['hash']
            except Exception:
                pass
    return '0' * 64


def receipt(action, detail):
    b = {'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
         'action': action, 'authority': 'HUMAN://ROOT', 'detail': detail, 'prev': _head()}
    b['hash'] = hashlib.sha256(_canon(b).encode('utf-8')).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open('a', encoding='utf-8') as fh:
        fh.write(_canon(b) + '\n')
    return b


def _env():
    e = dict(os.environ)
    e['HERMES_HOME'] = str(H)
    e.setdefault('HERMES_AE_PYTHON', PY)
    e.setdefault('TINY_VOCA_HOME', str(H / 'tiny-voca'))
    for k in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        e.pop(k, None)
    return e


def _stage(name: str) -> Path | None:
    """Copy the renderer + its siblings to an ASCII path ('æ' corrupts argv)."""
    src = AGENTS / name
    if not src.exists():
        return None
    st = H / 'cache' / 'scratch' / 'ae-render-run'
    st.mkdir(parents=True, exist_ok=True)
    for f in (name, 'robot_face2.py', 'robot_face.py', 'rtx_raster.py', 'rtx_asimov.py'):
        s = AGENTS / f
        if s.exists():
            (st / f).write_bytes(s.read_bytes())
    return st / name


def _jpath(jid):
    return JOBS / f'{jid}.json'


def _read(jid):
    p = _jpath(jid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def _write(j):
    JOBS.mkdir(parents=True, exist_ok=True)
    _jpath(j['job_id']).write_text(_canon(j), encoding='utf-8')


def launch(scene='charging_bay', spec=None, name=None, smoke=0):
    """Start a render. Returns immediately with a handle."""
    if scene not in SCENES:
        return {'ok': False, 'refused': True, 'reason': f'unknown scene {scene!r}',
                'available': list(SCENES)}
    if not spec:
        return {'ok': False, 'refused': True, 'reason': 'spec path required'}
    sp = Path(spec)
    if not sp.exists():
        return {'ok': False, 'refused': True, 'reason': f'spec not found: {sp}'}
    runner = _stage(SCENES[scene])
    if runner is None:
        return {'ok': False, 'refused': True, 'reason': f'renderer missing: {SCENES[scene]}'}

    jid = (name or scene).replace(' ', '-') + '-' + uuid.uuid4().hex[:6]
    outdir = JOBS / jid
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f'{jid}.mp4'
    log = outdir / 'render.log'

    # spec must be reachable from an ASCII cwd too
    spec_copy = outdir / 'spec.json'
    spec_copy.write_bytes(sp.read_bytes())

    if scene == 'rtx':
        # the RTX harness reads urdf.json + meshes, not a scene spec; it takes
        # --seconds/--frames. Model dir is resolved by the harness itself.
        cmd = [PY, str(runner), '--out', str(out), '--workdir', str(outdir / 'studio')]
        try:
            sp = json.loads(spec_copy.read_text(encoding='utf-8'))
        except Exception:
            sp = {}
        cmd += ['--seconds', str(sp.get('seconds', 8.0))]
        if sp.get('title'):
            cmd += ['--title', str(sp['title'])]
        if sp.get('tagline'):
            cmd += ['--tagline', str(sp['tagline'])]
        if smoke:
            cmd += ['--frames', str(int(smoke))]
        model = os.environ.get('ASIMOV_MODEL')
        if model:
            cmd += ['--model-dir', model]
    else:
        cmd = [PY, str(runner), '--spec', str(spec_copy), '--out', str(out),
               '--workdir', str(outdir / 'studio')]
        if smoke:
            cmd += ['--smoke', str(int(smoke))]

    with log.open('wb') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             env=_env(), cwd=str(runner.parent),
                             creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    j = {'job_id': jid, 'scene': scene, 'pid': p.pid, 'state': 'running',
         'started': time.time(), 'out': str(out), 'log': str(log),
         'workdir': str(outdir / 'studio'), 'smoke': int(smoke or 0),
         'spec': str(spec_copy)}
    j['receipt'] = receipt('RENDER://START', {'job_id': jid, 'scene': scene, 'pid': p.pid})
    _write(j)
    return {'ok': True, 'job_id': jid, 'pid': p.pid, 'state': 'running',
            'out': str(out), 'log': str(log), 'authority': 'HUMAN://ROOT',
            'note': 'Non-blocking. Poll robot_render_status(job_id).'}


def status(job_id=None):
    if not job_id:
        return {'ok': False, 'refused': True, 'reason': 'job_id required'}
    j = _read(job_id)
    if not j:
        return {'ok': False, 'refused': True, 'reason': f'unknown job {job_id!r}'}
    wd = Path(j['workdir']) / 'frames'
    frames = len(list(wd.glob('*.png'))) if wd.exists() else 0
    wavs = sorted(Path(j['workdir']).glob('s*.wav'))
    expect = round(sum(w.stat().st_size / 48000.0 for w in wavs) * 24) if wavs else 0
    out = Path(j['out'])
    alive = False
    try:
        os.kill(j['pid'], 0)
        alive = True
    except Exception:
        alive = False
    state = j['state']
    if out.exists() and out.stat().st_size > 10000:
        state = 'encoded'
    elif not alive and frames == 0:
        state = 'failed'
    elif not alive and expect and frames >= expect:
        state = 'encoding'
    if state != j['state']:
        j['state'] = state
        j['receipt'] = receipt(f'RENDER://{state.upper()}',
                               {'job_id': job_id, 'frames': frames, 'expect': expect})
        _write(j)
    res = {'ok': True, 'job_id': job_id, 'state': state, 'alive': alive,
           'frames': frames, 'expect': expect,
           'progress': round(frames / expect, 3) if expect else None,
           'bytes': out.stat().st_size if out.exists() else 0,
           'out': str(out), 'elapsed_s': round(time.time() - j['started'], 1),
           'authority': 'HUMAN://ROOT'}
    if state == 'encoded' and not j.get('gate'):
        res['gate'] = _gate(job_id, out)
    elif j.get('gate'):
        res['gate'] = j['gate']
    if state == 'failed':
        try:
            res['log_tail'] = Path(j['log']).read_text(encoding='utf-8', errors='replace')[-600:]
        except Exception:
            pass
    return res


def _gate(job_id, out):
    """Run SupervisorVideo and RECORD the verdict. Never assume a pass."""
    v = VIDAEO
    if not v.exists():
        return {'ran': False, 'reason': f'gate missing: {v}'}
    st = H / 'cache' / 'scratch' / 'ae-render-run' / 'gate.py'
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_bytes(v.read_bytes())
    try:
        p = subprocess.run([PY, str(st), 'verify', str(out)], capture_output=True,
                           text=True, encoding='utf-8', timeout=900, env=_env())
        txt = p.stdout or ''
        g = {'ran': True}
        for k in ('luminancia_media', 'contraste_medio', 'movimiento_medio', 'frames_negros'):
            import re
            m = re.search(rf'"{k}":\s*([\d.]+)', txt)
            if m:
                g[k] = float(m.group(1))
        import re
        m = re.search(r'"calidad":\s*"(\w+)"', txt)
        g['calidad'] = m.group(1) if m else 'UNKNOWN'
        m = re.search(r'"receipt":\s*"([0-9a-f]{64})"', txt)
        if m:
            g['receipt'] = m.group(1)
    except Exception as exc:
        return {'ran': False, 'reason': f'{type(exc).__name__}: {exc}'}
    j = _read(job_id)
    if j:
        j['gate'] = g
        j['receipt'] = receipt('RENDER://GATE', {'job_id': job_id, 'calidad': g.get('calidad')})
        _write(j)
    return g


def listing(limit=10):
    if not JOBS.exists():
        return {'ok': True, 'count': 0, 'jobs': []}
    js = []
    for p in sorted(JOBS.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
            js.append({'job_id': j['job_id'], 'scene': j['scene'], 'state': j['state'],
                       'gate': (j.get('gate') or {}).get('calidad')})
        except Exception:
            pass
    return {'ok': True, 'count': len(js), 'jobs': js, 'authority': 'HUMAN://ROOT'}
