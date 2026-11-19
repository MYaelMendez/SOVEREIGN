"""hermes-asimov — asimov:// as a first-class Hermes plugin.

Governed command and control for the Asimov humanoid. Wraps the official Menlo
SDK verb surface with æ Policy and hash-chained receipts. Adds one transport the
SDK does not ship: `sim`, so the same C2 path runs on a laptop with no robot.

    HUMAN://ROOT → æ POLICY → asimov:// → menlo.asimov.Robot → RECEIPT

An address is not a permission. A refusal is a RESULT, not an exception.
Nothing here grants authority; only the human signs.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HERMES_HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
PROTOCOL = ROOT / 'scripts' / 'asimov_protocol.py'
PY = os.environ.get('HERMES_AE_PYTHON', sys.executable)

VERB_ENUM = ['status', 'state', 'get_state', 'check', 'stand', 'damp', 'balance',
             'set_velocity', 'trajectory', 'set_joints', 'photo', 'capture_clip',
             'record_audio', 'play_pcm']


def _out(obj):
    return json.dumps(obj, ensure_ascii=False)


def _run(address):
    """Dispatch through the protocol engine. Never reimplement its rules."""
    if not PROTOCOL.exists():
        return {'ok': False, 'refused': True,
                'reason': f'protocol engine missing: {PROTOCOL}'}
    env = dict(os.environ)
    # a contaminated PYTHONPATH breaks the child interpreter on this host
    for k in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        env.pop(k, None)
    env['HERMES_HOME'] = str(HERMES_HOME)
    env.setdefault('HERMES_AE_PYTHON', PY)
    try:
        p = subprocess.run([PY, str(PROTOCOL), address],
                           capture_output=True, text=True, encoding='utf-8',
                           timeout=180, env=env)
    except Exception as exc:
        return {'ok': False, 'refused': True, 'reason': f'{type(exc).__name__}: {exc}'}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {'ok': False, 'refused': True,
                'reason': (p.stderr or p.stdout or 'no output')[-400:]}


def asimov_status(**kw):
    """Protocol status: SDK version, robot presence, transports, verb count."""
    return _out(_run('asimov://status'))


def asimov_verbs(**kw):
    """The canonical verb set, mapped to official Menlo SDK calls."""
    return _out(_run('asimov://verbs'))


def asimov_plan(verb=None, **kw):
    """Policy-evaluated plan. Returns the exact SDK call. NEVER connects."""
    if not verb:
        return _out({'ok': False, 'refused': True, 'reason': 'verb required',
                     'available': VERB_ENUM})
    return _out(_run(f'asimov://plan {verb}'))


def asimov_exec(verb=None, confirm=False, **kw):
    """Execute a verb. Dry-run unless HERMES_AE_SDK_LIVE=1 AND confirm=true.

    Motion still requires a bound human approval or an armed deadman; this
    tool cannot supply either.
    """
    if not verb:
        return _out({'ok': False, 'refused': True, 'reason': 'verb required',
                     'available': VERB_ENUM})
    if not confirm:
        return _out({'ok': False, 'refused': True, 'verb': verb,
                     'reason': 'execution requires confirm=true',
                     'note': 'Robot actuation is an EXTERNAL effect. Use asimov_plan first.'})
    return _out(_run(f'asimov://exec {verb}'))


def asimov_sim(verb=None, **kw):
    """Plan against the simulation transport (MuJoCo). Requires no robot."""
    if not verb:
        return _out({'ok': False, 'refused': True, 'reason': 'verb required',
                     'available': VERB_ENUM})
    return _out(_run(f'asimov://sim {verb}'))


def asimov_grant(verb=None, **kw):
    """Report the approval shape a verb requires. GRANTS NOTHING."""
    if not verb:
        return _out({'ok': False, 'refused': True, 'reason': 'verb required'})
    return _out(_run(f'asimov://grant {verb}'))


def _verb_schema(name, desc, requires_verb, extra=None):
    props = {}
    required = []
    if requires_verb:
        props['verb'] = {'type': 'string', 'enum': VERB_ENUM,
                         'description': 'Official Menlo verb. Motion verbs need human approval or a deadman.'}
        required.append('verb')
    if extra:
        props.update(extra)
    return {'type': 'function', 'function': {'name': name, 'description': desc,
            'parameters': {'type': 'object', 'properties': props, 'required': required}}}


SECTION = """## asimov:// — governed robot command and control

`asimov://` is the OpenSourceWare C2 protocol for the Asimov humanoid. It wraps
the official Menlo SDK; it invents no wire synonyms. Motion names are Menlo's own.

    HUMAN://ROOT → æ POLICY → asimov:// → menlo.asimov.Robot → RECEIPT

Tools: `asimov_status`, `asimov_verbs`, `asimov_plan`, `asimov_exec`,
`asimov_sim`, `asimov_grant`.

Rules that bind every agent using them:

1. **An address is not a permission.** Resolving a verb produces a plan, never
   an act. `asimov_plan` is the default safe path; it never connects.
2. **Motion requires a human.** `stand`, `damp`, `balance`, `set_velocity`,
   `trajectory`, `set_joints` return `require_approval` (ACT-001) until a bound
   human approval or an armed deadman exists. You cannot supply either.
3. **Never self-grant.** `asimov_grant` reports the required approval shape and
   returns `grants: false`. Do not fabricate an approval object.
4. **A refusal is a result.** `{"ok": false, "refused": true, "reason": ...}`
   is a correct answer, not an error to retry around. Report it; do not route
   around the gate.
5. **`sim` is not hardware.** The simulation transport is specified, not yet
   implemented. Never report a simulated act as a physical one.
6. **Execution is EXTERNAL.** `asimov_exec` needs `confirm=true` and stays
   dry-run unless `HERMES_AE_SDK_LIVE=1`. Ask the operator first.

The SDK is a client of Asimov Edge and its safety layer, never a bypass.
Nothing in the SDK is an emergency stop. This protocol adds governance, not
physical safety.
"""


def register(ctx):
    ctx.register_tool(name='asimov_status', toolset='hermes-asimov',
                      schema=_verb_schema('asimov_status',
                          'asimov:// protocol status: Menlo SDK version, robot presence, transports, verb count.', False),
                      handler=lambda *a, **kw: asimov_status(**kw),
                      description='asimov:// protocol status', emoji='🤖')
    ctx.register_tool(name='asimov_verbs', toolset='hermes-asimov',
                      schema=_verb_schema('asimov_verbs',
                          'List the canonical asimov:// verbs mapped to official Menlo SDK calls, with class and gate.', False),
                      handler=lambda *a, **kw: asimov_verbs(**kw),
                      description='asimov:// canonical verbs', emoji='🤖')
    ctx.register_tool(name='asimov_plan', toolset='hermes-asimov',
                      schema=_verb_schema('asimov_plan',
                          'Policy-evaluate a verb and return the exact SDK call. NEVER connects to a robot. The default safe path.', True),
                      handler=lambda *a, **kw: asimov_plan(**kw),
                      description='asimov:// plan (no connection)', emoji='🤖')
    ctx.register_tool(name='asimov_exec', toolset='hermes-asimov',
                      schema=_verb_schema('asimov_exec',
                          'Execute a verb. Requires confirm=true; stays dry-run unless HERMES_AE_SDK_LIVE=1. Motion still needs human approval or an armed deadman.',
                          True, {'confirm': {'type': 'boolean',
                                 'description': 'Must be true. Robot actuation is an EXTERNAL effect.'}}),
                      handler=lambda *a, **kw: asimov_exec(**kw),
                      description='asimov:// execute (gated)', emoji='🤖')
    ctx.register_tool(name='asimov_sim', toolset='hermes-asimov',
                      schema=_verb_schema('asimov_sim',
                          'Plan a verb against the MuJoCo simulation transport. Requires no robot. Transport is specified, not yet implemented.', True),
                      handler=lambda *a, **kw: asimov_sim(**kw),
                      description='asimov:// sim transport', emoji='🤖')
    ctx.register_tool(name='asimov_grant', toolset='hermes-asimov',
                      schema=_verb_schema('asimov_grant',
                          'Report the approval shape a verb requires. GRANTS NOTHING — only HUMAN://ROOT signs.', True),
                      handler=lambda *a, **kw: asimov_grant(**kw),
                      description='asimov:// approval shape (no grant)', emoji='🤖')
    try:
        ctx.register_system_prompt_section(id='asimov-protocol', content=SECTION,
                                           position='after_memory')
    except Exception:
        pass
    # integration layer: the front door, MoH, voice and introspection as tools
    try:
        from .integration import register_extra
    except ImportError:
        import importlib.util as _u
        _p = ROOT / 'integration.py'
        if _p.exists():
            _s = _u.spec_from_file_location('hermes_asimov_integration', _p)
            _m = _u.module_from_spec(_s)
            _s.loader.exec_module(_m)
            register_extra = _m.register_extra
        else:
            register_extra = None
    if register_extra:
        try:
            register_extra(ctx)
        except Exception:
            pass
