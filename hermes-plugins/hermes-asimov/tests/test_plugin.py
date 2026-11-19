"""Safety regression tests for the hermes-asimov plugin and the æ:// entry resolver.

These encode the laws of the protocol. A regression here is a safety bug:

  * handlers must accept the POSITIONAL arg the host passes (handler(*a, **kw))
  * motion plans require approval (ACT-001); read verbs are allowed
  * exec without confirm is refused; the grant tool NEVER grants
  * unknown verbs / phrases are refusals (results), never exceptions
  * the entry resolver opens addresses, never executions; cli:// is allowlisted
  * canonical voice:// and cli:// resolve; 'say <text>' keeps its verb

Run:  C:/gpu/Scripts/python.exe -m pytest <this file> -q
Modules are loaded with importlib.util.spec_from_file_location and the resolver
is copied to an ASCII scratch dir first (the 'æ' path corrupts subprocess argv).
Tests skip gracefully when an engine or model is absent.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

PLUGIN_DIR = Path('C:/Users/yaelm/AppData/Local/hermes/plugins/hermes-asimov')
AGENTS_DIR = Path('C:/æ/agents')  # Unicode source path: read in-process only
SCRATCH = Path('C:/Users/yaelm/AppData/Local/hermes/cache/scratch')
HERMES_HOME = Path(os.environ.get('HERMES_HOME', 'C:/Users/yaelm/AppData/Local/hermes'))
VERB_ENGINE = HERMES_HOME / 'plugins' / 'hermes-ae' / 'scripts' / 'ae_verbs.py'
POLICY_FILE = HERMES_HOME / 'plugins' / 'hermes-ae' / 'ae-policy.json'
PROTOCOL = PLUGIN_DIR / 'scripts' / 'asimov_protocol.py'

EXPECTED_TOOLS = {'asimov_status', 'asimov_verbs', 'asimov_plan',
                  'asimov_exec', 'asimov_sim', 'asimov_grant'}


# --------------------------------------------------------------------------- fixtures

@pytest.fixture(scope='session')
def workdir():
    """ASCII scratch dir: resolver copies + redirected receipt ledgers.

    Ledgers are redirected so the tests never append to the operator's real
    hash-chained receipts. Everything a subprocess receives is an ASCII path.
    """
    SCRATCH.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix='asimov_tests_', dir=str(SCRATCH)))
    old = {k: os.environ.get(k) for k in ('HERMES_AE_LEDGER', 'HERMES_ASIMOV_LEDGER')}
    os.environ['HERMES_AE_LEDGER'] = str(d / 'ae-receipts.jsonl')
    os.environ['HERMES_ASIMOV_LEDGER'] = str(d / 'asimov-protocol.jsonl')
    yield d
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='session')
def plugin(workdir):
    if not (PLUGIN_DIR / '__init__.py').exists():
        pytest.skip(f'plugin missing: {PLUGIN_DIR}')
    return _load('hermes_asimov_under_test', PLUGIN_DIR / '__init__.py')


@pytest.fixture(scope='session')
def entry(workdir):
    """Copy the resolver + sibling protocols to ASCII scratch, then import.

    ae_entry.dispatch() imports asimov_protocol / voice_protocol / cli_protocol
    by name from its own directory, so the siblings must sit next to the copy.
    """
    src = AGENTS_DIR / 'ae_entry.py'
    if not src.exists():
        pytest.skip(f'entry resolver missing: {src}')
    for name in ('ae_entry.py', 'asimov_protocol.py', 'voice_protocol.py', 'cli_protocol.py'):
        p = AGENTS_DIR / name
        if p.exists():
            shutil.copy2(str(p), str(workdir / name))
    return _load('ae_entry_under_test', workdir / 'ae_entry.py')


# --------------------------------------------------------------------------- helpers

def _j(s):
    """Every handler returns a JSON STRING — never a dict, never an exception."""
    assert isinstance(s, str), f'handler must return a JSON string, got {type(s)}'
    return json.loads(s)


def _skip_if_engine_absent(out):
    reason = str(out.get('reason') or out.get('error') or '')
    if out.get('refused') and ('missing' in reason or 'unavailable' in reason):
        pytest.skip(f'engine absent: {reason}')


def _engine_present():
    return PROTOCOL.exists() and VERB_ENGINE.exists() and POLICY_FILE.exists()


class _Ctx:
    """Minimal stand-in for the Hermes plugin context."""

    def __init__(self):
        self.tools = {}
        self.sections = []

    def register_tool(self, **kw):
        self.tools[kw['name']] = kw

    def register_system_prompt_section(self, **kw):
        self.sections.append(kw)


# --------------------------------------------------------------------------- 1. host call shape

def test_handlers_accept_positional_args(plugin):
    """LAW: the host calls handler(*a, **kw). A **kw-only lambda raises
    TypeError and breaks every tool. Positional calls must not raise."""
    ctx = _Ctx()
    plugin.register(ctx)
    assert EXPECTED_TOOLS <= set(ctx.tools), f'missing tools: {EXPECTED_TOOLS - set(ctx.tools)}'
    for name, spec in ctx.tools.items():
        handler = spec['handler']
        requires_verb = 'verb' in spec['schema']['function']['parameters'].get('required', [])
        args = ('stand',) if requires_verb else ()
        try:
            out = handler(*args)  # positional, exactly as the host passes it
        except TypeError as exc:
            pytest.fail(f'{name} handler rejects positional args (host call shape): {exc}')
        _j(out)  # must still be a JSON string result
    # keyword form must keep working too
    _j(ctx.tools['asimov_plan']['handler'](verb='stand'))


# --------------------------------------------------------------------------- 2-3. policy decisions

def test_plan_stand_requires_approval(plugin):
    """LAW: motion is privileged. stand -> require_approval, ACT-001, no act."""
    if not _engine_present():
        pytest.skip('verb engine / policy absent')
    out = _j(plugin.asimov_plan('stand'))
    _skip_if_engine_absent(out)
    assert out.get('decision') == 'require_approval', out
    assert out.get('allowed') is False, out
    assert out.get('executed') is False, out
    assert 'ACT-001' in json.dumps(out.get('rules', [])), out


def test_plan_state_is_allowed_read(plugin):
    """LAW: read verbs are allowed without approval."""
    if not _engine_present():
        pytest.skip('verb engine / policy absent')
    out = _j(plugin.asimov_plan('state'))
    _skip_if_engine_absent(out)
    assert out.get('decision') == 'allow', out
    assert out.get('executed') is False, out


# --------------------------------------------------------------------------- 4-5. execution & grant gates

def test_exec_without_confirm_refused(plugin):
    """LAW: actuation is EXTERNAL. No confirm=true -> refusal mentioning confirm."""
    out = _j(plugin.asimov_exec('stand'))
    assert out.get('ok') is False, out
    assert out.get('refused') is True, out
    assert 'confirm' in str(out.get('reason', '')).lower(), out


def test_grant_never_grants(plugin):
    """LAW: the tool MUST NEVER GRANT. Only HUMAN://ROOT signs."""
    if not PROTOCOL.exists():
        pytest.skip('protocol engine absent')
    out = _j(plugin.asimov_grant('stand'))
    _skip_if_engine_absent(out)
    assert out.get('grants') is False, f'asimov_grant granted authority: {out}'


# --------------------------------------------------------------------------- 6. unknown verb

@pytest.mark.parametrize('tool', ['asimov_plan', 'asimov_sim'])
def test_unknown_verb_refused_not_exception(plugin, tool):
    """LAW: a refusal is a RESULT. Unknown verb -> refused JSON, no exception."""
    out = _j(getattr(plugin, tool)('definitely_not_a_verb'))
    assert out.get('refused') is True, out
    assert out.get('executed') is not True, out


def test_unknown_verb_exec_not_executed(plugin):
    """Even with confirm=true an unknown verb must not execute anything."""
    out = _j(plugin.asimov_exec('definitely_not_a_verb', confirm=True))
    assert out.get('success') is False or out.get('refused') is True, out
    assert out.get('executed') is not True, out


# --------------------------------------------------------------------------- 7-8. entry resolver

@pytest.mark.parametrize('raw', [
    'asimov protocol', 'BOT://', '🤖', '💬', 'robot', '机器人', 'ロボット', 'робот',
])
def test_entry_aliases_resolve_to_asimov(entry, raw):
    """LAW: ordinary words, any language, emoji or friendly scheme -> asimov://."""
    addr, how = entry.resolve(raw)
    assert addr is not None, f'{raw!r} refused: {how}'
    assert addr.startswith('asimov://'), (raw, addr, how)


def test_robot_stand_resolves_to_plan_never_exec(entry):
    """LAW: resolution opens an address, not a permission. Motion -> PLAN."""
    addr, how = entry.resolve('robot stand')
    assert addr == 'asimov://plan stand', (addr, how)
    assert 'exec' not in addr
    d = entry.dispatch('robot stand')
    assert d['ok'] is True, d
    assert d['resolved'] == 'asimov://plan stand', d
    assert d['grants'] is False, d
    # the protocol result itself must never report an executed act
    assert d.get('result', {}).get('executed') is not True, d


# --------------------------------------------------------------------------- 9. unknown phrase

def test_sandwich_refused_and_lists_reachable(entry):
    """LAW: an unknown phrase is a refusal that lists what IS reachable."""
    addr, _ = entry.resolve('make me a sandwich')
    assert addr is None
    d = entry.dispatch('make me a sandwich')
    assert d['ok'] is False, d
    assert d['refused'] is True, d
    reachable = d.get('reachable')
    assert isinstance(reachable, list) and reachable, d
    joined = ' '.join(reachable)
    for scheme in ('asimov://', 'voice://', 'cli://'):
        assert scheme in joined, (scheme, reachable)


# --------------------------------------------------------------------------- 10. cli allowlist

@pytest.mark.parametrize('raw', ['cli://rm -rf', '⌨ delete everything'])
def test_cli_allowlist_refuses_unnamed_verbs(entry, raw):
    """LAW: cli:// is an allowlist, not a shell. Destructive text -> refused."""
    d = entry.dispatch(raw)
    res = d.get('result', {})
    assert res.get('refused') is True, (raw, d)
    assert res.get('success') is False, (raw, d)
    assert 'allowlist' in res, (raw, res)


# --------------------------------------------------------------------------- 11. canonical schemes

@pytest.mark.parametrize('raw', ['voice://', 'cli://'])
def test_canonical_schemes_resolve(entry, raw):
    """REGRESSION: canonical voice:// and cli:// must resolve (a past bug
    refused them while the emoji worked)."""
    addr, how = entry.resolve(raw)
    assert addr == raw, (raw, addr, how)
    d = entry.dispatch(raw)
    assert d['ok'] is True, (raw, d)
    assert d['resolved'] == raw, (raw, d)
    # status/caps are pure introspection: no model or robot required
    assert d.get('result', {}).get('success') is True, (raw, d)


# --------------------------------------------------------------------------- 12. verb preservation

def test_say_keeps_verb_and_text(entry):
    """REGRESSION: 'say hello world' -> voice://say hello world.
    The verb must not be dropped (past bug)."""
    addr, how = entry.resolve('say hello world')
    assert addr == 'voice://say hello world', (addr, how)


def test_speak_and_talk_keep_verb(entry):
    """Same law for the other verb-is-the-route words."""
    for raw, want in (('speak hello world', 'voice://speak hello world'),
                      ('talk to me', 'voice://talk to me')):
        addr, how = entry.resolve(raw)
        assert addr == want, (raw, addr, how)
