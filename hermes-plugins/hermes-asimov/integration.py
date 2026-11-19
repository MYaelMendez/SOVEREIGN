"""Integration layer — today's standalone modules as first-class Hermes tools.

The front door, MoH routing, voice and the robot studio were built as scripts
under C:/æ/agents/. An agent in a fresh session could not call them. This
registers them, so capability is addressable by tool name rather than by
remembering a path.

Every handler:
  * accepts the POSITIONAL arg the host passes (lambda *a, **kw)
  * returns a JSON string
  * reports a refusal as a structured result, never an exception
  * probes the real module and says so plainly when it is absent
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

H = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
AGENTS = Path(os.environ.get('AE_AGENTS', r'C:\æ\agents'))
HERE = Path(__file__).resolve().parent
PY = os.environ.get('HERMES_AE_PYTHON', sys.executable)


def _out(o):
    return json.dumps(o, ensure_ascii=False)


def _env():
    e = dict(os.environ)
    e['HERMES_HOME'] = str(H)
    e.setdefault('HERMES_AE_PYTHON', PY)
    e.setdefault('TINY_VOCA_HOME', str(H / 'tiny-voca'))
    for k in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        e.pop(k, None)
    return e


def _run(script: Path, arg: str, timeout: int = 240):
    """Run a module by NATIVE path.

    Only stage when the path contains non-ASCII ('æ' corrupts subprocess argv).
    Staging a module that resolves siblings relative to __file__ breaks it, so
    ASCII-path modules run in place.
    """
    if not script.exists():
        return {'ok': False, 'refused': True, 'reason': f'module missing: {script}'}
    target = script
    cwd = str(script.parent)
    try:
        str(script).encode('ascii')
    except UnicodeEncodeError:
        stage = H / 'cache' / 'scratch' / 'ae-tools'
        stage.mkdir(parents=True, exist_ok=True)
        target = stage / script.name
        try:
            target.write_bytes(script.read_bytes())
            for sib in ('asimov_protocol.py', 'voice_protocol.py', 'cli_protocol.py',
                        'robot_face2.py', 'robot_face.py'):
                s = script.parent / sib
                if s.exists():
                    (stage / sib).write_bytes(s.read_bytes())
        except Exception as exc:
            return {'ok': False, 'refused': True, 'reason': f'staging failed: {exc}'}
        cwd = str(stage)
    try:
        p = subprocess.run([PY, str(target), arg], capture_output=True, text=True,
                           encoding='utf-8', timeout=timeout, env=_env(), cwd=cwd)
    except Exception as exc:
        return {'ok': False, 'refused': True, 'reason': f'{type(exc).__name__}: {exc}'}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {'ok': False, 'refused': True,
                'reason': (p.stderr or p.stdout or 'no output')[-400:]}


# ── the front door ────────────────────────────────────────────────────────
def ae_resolve(text=None, **kw):
    """Resolve ordinary words / an emoji into a governed address. Never grants."""
    if not text:
        return _out({'ok': False, 'refused': True, 'reason': 'text required',
                     'examples': ['asimov protocol', 'BOT://', '🤖', 'robot stand',
                                  '🗣 say hello', '⌨ ledger']})
    return _out(_run(AGENTS / 'ae_entry.py', text))


# ── mixture of harnesses ──────────────────────────────────────────────────
def _moh(arg):
    return _run(HERE / 'scripts' / 'moh.py', arg)


def moh_status(**kw):
    return _out(_moh('moh://'))


def moh_agents(**kw):
    return _out(_moh('moh://agents'))


def moh_route(agent=None, harness=None, scale=None, **kw):
    if not agent or not harness:
        return _out({'ok': False, 'refused': True,
                     'reason': 'agent and harness required',
                     'usage': 'moh_route(agent="waetz", harness="voice")'})
    return _out(_moh(f'moh://route {agent} {harness}' + (f' {scale}' if scale else '')))


def moh_delegate(source=None, target=None, harness=None, **kw):
    if not (source and target and harness):
        return _out({'ok': False, 'refused': True,
                     'reason': 'source, target and harness required'})
    return _out(_moh(f'moh://delegate {source} {target} {harness}'))


# ── voice ─────────────────────────────────────────────────────────────────
def voice_speak(text=None, actor=None, **kw):
    if not text:
        return _out({'ok': False, 'refused': True, 'reason': 'text required',
                     'cast': ['nous', 'hermes', 'waetz', 'menlo', 'asimov']})
    who = actor or 'hermes'
    return _out(_run(AGENTS / 'voice_protocol.py', f'voice://say {who} {text}'))


def voice_cast(**kw):
    return _out(_run(AGENTS / 'voice_protocol.py', 'voice://voices'))


# ── introspection ─────────────────────────────────────────────────────────
def ae_ledger(**kw):
    return _out(_run(AGENTS / 'cli_protocol.py', 'cli://ledger'))


def ae_caps(**kw):
    return _out(_run(AGENTS / 'cli_protocol.py', 'cli://caps'))


def _schema(name, desc, props=None, required=None):
    return {'type': 'function', 'function': {
        'name': name, 'description': desc,
        'parameters': {'type': 'object', 'properties': props or {},
                       'required': required or []}}}


CAST_ENUM = ['nous', 'hermes', 'waetz', 'menlo', 'asimov']
HARNESS_ENUM = ['voice', 'ffmpeg', 'control', 'physics', 'viewport', 'robot',
                'publish', 'course', 'ledger']
SCALE_ENUM = ['cpu://teknium', 'gpu://teknium', 'vps://backbone', 'hardware://asimov']

TOOLS = [
    ('ae_resolve', ae_resolve, 'æ:// front door — resolve ordinary words or an emoji '
     'into a governed address. Deterministic, offline. Motion words become PLANS, never acts.',
     {'text': {'type': 'string', 'description': 'e.g. "asimov protocol", "BOT://", "🤖", '
               '"robot stand", "🗣 say hello", "⌨ ledger"'}}, ['text'], '🍊'),
    ('moh_status', moh_status, 'moh:// registry overview — agents, harnesses, scales, principles.',
     None, None, '⚙'),
    ('moh_agents', moh_agents, 'moh:// the five orchestrators, their harness mixes, scales and '
     'delegation rights. wætz conducts.', None, None, '⚙'),
    ('moh_route', moh_route, 'moh:// route a harness to a compute scale. An unmeasured scale '
     'returns the fallback and a MOH://DEGRADED receipt. Never grants.',
     {'agent': {'type': 'string', 'enum': CAST_ENUM},
      'harness': {'type': 'string', 'enum': HARNESS_ENUM},
      'scale': {'type': 'string', 'enum': SCALE_ENUM}}, ['agent', 'harness'], '⚙'),
    ('moh_delegate', moh_delegate, 'moh:// may one agent ask another to run a harness? '
     'Reports permitted; GRANTS NOTHING. Motion still needs HUMAN://ROOT.',
     {'source': {'type': 'string', 'enum': CAST_ENUM},
      'target': {'type': 'string', 'enum': CAST_ENUM},
      'harness': {'type': 'string', 'enum': HARNESS_ENUM}},
     ['source', 'target', 'harness'], '⚙'),
    ('voice_speak', voice_speak, 'Speak with a cast member using their own derived timbre. '
     'Local tinyVOCA ONNX, CPU, no cloud. Receipted.',
     {'text': {'type': 'string'}, 'actor': {'type': 'string', 'enum': CAST_ENUM}},
     ['text'], '🗣'),
    ('voice_cast', voice_cast, 'The five voices and their derivation parameters, with measured '
     'spectral centroids proving they differ.', None, None, '🗣'),
    ('ae_ledger', ae_ledger, 'Every receipt ledger: entries, chain integrity, head hash. '
     'Read-only.', None, None, '🧾'),
    ('ae_caps', ae_caps, 'The capability front doors and the cli:// allowlist.', None, None, '⌨'),
]


def register_extra(ctx):
    for name, fn, desc, props, req, emoji in TOOLS:
        ctx.register_tool(name=name, toolset='hermes-asimov',
                          schema=_schema(name, desc, props, req),
                          handler=lambda *a, _f=fn, **kw: _f(**kw),
                          description=desc[:90], emoji=emoji)
    # the studio as a non-blocking job capability
    try:
        import importlib.util as _u
        _p = HERE / 'render_jobs.py'
        if _p.exists():
            _s = _u.spec_from_file_location('hermes_asimov_render_jobs', _p)
            _r = _u.module_from_spec(_s)
            _s.loader.exec_module(_r)

            def _launch(**kw):
                return _out(_r.launch(**kw))

            def _status(**kw):
                return _out(_r.status(**kw))

            def _list(**kw):
                return _out(_r.listing(**kw))

            ctx.register_tool(
                name='robot_render', toolset='hermes-asimov',
                schema=_schema('robot_render',
                    'Launch a robot film render as a BACKGROUND JOB. Returns a handle '
                    'immediately; a five-body film takes ~30 min. Poll robot_render_status. '
                    'The gate runs on completion and its verdict is recorded.',
                    {'scene': {'type': 'string', 'enum': ['charging_bay', 'studio3', 'studio'],
                               'description': 'charging_bay = docked cast sharing prompts/responses'},
                     'spec': {'type': 'string', 'description': 'absolute path to the spec JSON'},
                     'name': {'type': 'string'},
                     'smoke': {'type': 'integer',
                               'description': 'render only the first N scenes (composition check)'}},
                    ['scene', 'spec']),
                handler=lambda *a, **kw: _launch(**kw),
                description='Launch a robot film render (non-blocking)', emoji='🎬')
            ctx.register_tool(
                name='robot_render_status', toolset='hermes-asimov',
                schema=_schema('robot_render_status',
                    'Poll a render job: state, frames/expect, bytes, elapsed, and the '
                    'SupervisorVideo gate verdict once encoded.',
                    {'job_id': {'type': 'string'}}, ['job_id']),
                handler=lambda *a, **kw: _status(**kw),
                description='Poll a render job + gate', emoji='🎬')
            ctx.register_tool(
                name='robot_render_list', toolset='hermes-asimov',
                schema=_schema('robot_render_list', 'List recent render jobs and their gate verdicts.',
                               {'limit': {'type': 'integer'}}, []),
                handler=lambda *a, **kw: _list(**kw),
                description='List render jobs', emoji='🎬')
    except Exception:
        pass
