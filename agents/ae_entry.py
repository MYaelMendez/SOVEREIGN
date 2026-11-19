"""æ:// entry — the front door for people who do not know scheme syntax.

A new computer user sees `>_æ://` and types what they mean. They should not
have to learn `asimov://plan stand` first. This resolves ordinary words, any
of several languages, an emoji, or a friendly scheme — into the canonical
address, then dispatches through the real protocol.

    >_æ:// asimov protocol
    >_æ:// BOT://
    >_æ:// 🤖
    >_æ:// 💬 robot
    >_æ:// robot stand          -> asimov://plan stand   (a PLAN, never an act)

DETERMINISTIC. No model, no network, no guessing. An unknown phrase is a
refusal that lists what IS reachable — never a silent fall-through, and never
an execution. Resolution opens an address; it does not grant a permission.

Authority: HUMAN://ROOT.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

AUTHORITY = 'HUMAN://ROOT'

# friendly scheme spellings -> canonical
SCHEME_ALIASES = {
    'bot': 'asimov', 'robot': 'asimov', 'asimov': 'asimov',
    'asimov-protocol': 'asimov', 'asimovprotocol': 'asimov',
    'voice': 'voice', 'tts': 'voice', 'speak': 'voice',
    'cli': 'cli', 'shell': 'cli', 'terminal': 'cli', 'caps': 'cli',
    'film': 'film', 'cinema': 'film', 'movie': 'film', 'video': 'film',
    'mp4': 'mp4', 'media': 'mp4',
    # æææ:// — the verb æ opens the molt context protocol
    'æææ': 'æææ', 'aeaeae': 'æææ', 'aaa': 'æææ',
    'molt': 'æææ', 'mcp': 'æææ', 'context': 'æææ',
}

# emoji -> canonical scheme  (🤖 AI execution, 💬 chat, 🗣 voice, ⌨ command line)
EMOJI = {
    '🤖': 'asimov', '💬': 'asimov', '🦾': 'asimov', '🤳': 'asimov',
    '🗣': 'voice', '🗣️': 'voice', '⌨': 'cli', '⌨️': 'cli',
    '🎬': 'film', '🎥': 'film', '🎞': 'film', '🎞️': 'film', '📽': 'mp4', '📽️': 'mp4',
}

# ordinary words, many languages -> canonical scheme.
# A new user types their own language; the address is universal.
WORDS = {
    'asimov': 'asimov', 'robot': 'asimov', 'robots': 'asimov', 'bot': 'asimov',
    'bots': 'asimov', 'humanoid': 'asimov', 'android': 'asimov',
    # spanish / portuguese / french / german / italian
    'robotico': 'asimov', 'robótico': 'asimov', 'robô': 'asimov', 'robo': 'asimov',
    'roboter': 'asimov', 'roboter': 'asimov', 'robott': 'asimov',
    # slavic / greek / turkish
    'робот': 'asimov', 'ρομπότ': 'asimov', 'robotlar': 'asimov',
    # arabic / hebrew / hindi
    'روبوت': 'asimov', 'רובוט': 'asimov', 'रोबोट': 'asimov',
    # cjk / japanese / korean
    '机器人': 'asimov', '機器人': 'asimov', 'ロボット': 'asimov', '로봇': 'asimov',
    # swahili / indonesian / vietnamese
    'roboti': 'asimov', 'rôbốt': 'asimov', 'người máy': 'asimov',
    # voice
    'voice': 'voice', 'speak': 'voice', 'say': 'voice', 'talk': 'voice',
    'voz': 'voice', 'voix': 'voice', 'stimme': 'voice', 'voce': 'voice',
    '声音': 'voice', '声': 'voice', '音声': 'voice', '목소리': 'voice',
    'голос': 'voice', 'صوت': 'voice', 'आवाज़': 'voice',
    # command line
    'cli': 'cli', 'caps': 'cli', 'capabilities': 'cli', 'command': 'cli',
    'commands': 'cli', 'terminal': 'cli', 'shell': 'cli',
    # film — the storyboard is where a new user starts
    'film': 'film', 'movie': 'film', 'video': 'film', 'cinema': 'film',
    'sound': 'asimov', 'audio': 'asimov', 'voice': 'voice',
    'molt': 'aeaeae', 'handshake': 'aeaeae', 'mcp': 'aeaeae',
    'storyboard': 'film', 'board': 'film', 'previz': 'film', 'shot': 'film',
    'película': 'film', 'pelicula': 'film', 'filme': 'film', 'cine': 'film',
    '电影': 'film', '映画': 'film', '영화': 'film', 'фильм': 'film', 'फ़िल्म': 'film',
}

# intent words -> route. Read-only by default; motion always becomes a PLAN.
ROUTES = {
    'status': 'status', 'state': 'state', 'check': 'status', 'info': 'status',
    'verbs': 'verbs', 'commands': 'verbs', 'list': 'verbs', 'help': 'verbs',
    'what': 'verbs', 'can': 'verbs',
    'stand': 'plan stand', 'walk': 'plan set_velocity', 'move': 'plan set_velocity',
    'damp': 'plan damp', 'balance': 'plan balance', 'stop': 'plan damp',
    'speak': 'plan play_pcm', 'talk': 'plan play_pcm', 'say': 'plan play_pcm',
    'photo': 'plan photo', 'see': 'plan photo', 'look': 'plan photo',
    'sim': 'sim stand', 'simulate': 'sim stand', 'simulation': 'sim stand',
}

REACHABLE = ['asimov:// (BOT://, 🤖, 💬, "robot", "asimov protocol")',
             'voice:// (🗣)', 'cli:// (⌨)',
             'æææ://molt_context_protocol (MCP/1517 — context flows, authority does not)']


def _norm(s):
    s = unicodedata.normalize('NFKC', str(s)).strip().lower()
    return re.sub(r'\s+', ' ', s)


def resolve(raw):
    """Return (canonical_address, how) or (None, reason). Never executes."""
    original = str(raw).strip()
    # strip the operator prompt if present
    for p in ('>_æ://', '>_ae://', 'æ://', 'ae://', '>_'):
        if original.startswith(p):
            original = original[len(p):].strip()
            break

    # 1. already a canonical scheme?
    if '://' in original:
        head, rest = original.split('://', 1)
        key = _norm(head).replace(' ', '')
        canon = SCHEME_ALIASES.get(key)
        if canon:
            tail = rest.strip()
            return (f'{canon}://{tail}' if tail else f'{canon}://'), f'scheme alias "{head}"'
        return None, f'unknown scheme "{head}://"'

    # 2. emoji anywhere in the input
    for e, canon in EMOJI.items():
        if e in original:
            # keep ORIGINAL case for the remainder — it may be a filesystem path
            rest = original.replace(e, ' ').strip()
            rest = re.sub(r'\s+', ' ', rest)
            head = rest.split()[0].lower() if rest else ''
            if canon == 'asimov':
                route = ROUTES.get(head, '')
                addr = f'{canon}://{route}' if route else f'{canon}://'
            else:
                addr = f'{canon}://{rest}' if rest else f'{canon}://'
            return addr, f'emoji {e}'

    s = _norm(original)
    if not s:
        return 'asimov://', 'empty prompt -> protocol status'

    # 3. exact phrase
    if s in ('asimov protocol', 'robot protocol', 'bot protocol', 'the robot'):
        return 'asimov://', f'phrase "{s}"'

    # 4. word-by-word: first token that names a capability, rest is a route
    toks = s.split()
    for i, tok in enumerate(toks):
        base = tok.strip('.,!?;:')
        canon = WORDS.get(base) or SCHEME_ALIASES.get(base)
        if canon:
            rest = ' '.join(toks[i + 1:]).strip()
            if not rest:
                return f'{canon}://', f'word "{base}"'
            if canon != 'asimov':
                # a verb that IS the route (say/speak/talk) must be kept
                keep = base in ('say', 'speak', 'talk')
                tail = f'{base} {rest}' if keep else rest
                return f'{canon}://{tail}', f'word "{base}"'
            first = rest.split()[0]
            if first in ROUTES:
                return f'{canon}://{ROUTES[first]}', f'word "{base}" + intent "{first}"'
            return f'{canon}://', f'word "{base}" (intent "{rest}" not a verb; showing protocol)'

    # 5. a bare intent with no subject -> the robot is the default subject
    if toks[0] in ROUTES:
        return f'asimov://{ROUTES[toks[0]]}', f'intent "{toks[0]}"'

    return None, f'no capability named in "{original}"'


def dispatch(raw):
    addr, how = resolve(raw)
    if addr is None:
        return {'ok': False, 'refused': True, 'authority': AUTHORITY,
                'input': raw, 'reason': how, 'reachable': REACHABLE,
                'note': 'Nothing was executed. Type one of the reachable addresses.'}
    out = {'ok': True, 'authority': AUTHORITY, 'input': raw,
           'resolved': addr, 'via': how, 'grants': False,
           'note': 'Resolution opens an address. It is not a permission.'}
    if addr.startswith('æææ://') or addr.startswith('aeaeae://'):
        _tail = addr.split('://', 1)[1].strip()
        _known = ('', 'mcp')
        if _tail in _known or _tail.startswith('molt_context_protocol') or _tail.startswith('mcp '):
            if 'molt_context_protocol' in _tail:
                rest = _tail.split('molt_context_protocol', 1)[1].strip()
            elif _tail.startswith('mcp'):
                rest = _tail[3:].strip()
            else:
                rest = ''
            import subprocess as _sp, sys as _sy, json as _j
            from pathlib import Path as _P
            _m = _P('C:/æ/agents/molt_context_protocol.py')
            if not _m.exists():
                out['result'] = {'ok': False, 'refused': True, 'decision': 'deny',
                                 'reason': 'molt_context_protocol.py not installed'}
            else:
                _args = [_sy.executable, str(_m)] + (rest.split() if rest else [])
                try:
                    _r = _sp.run(_args, capture_output=True, text=True, timeout=90)
                    out['result'] = _j.loads(_r.stdout or '{}')
                except Exception as _e:
                    out['result'] = {'ok': False, 'refused': True,
                                     'reason': f'{type(_e).__name__}: {_e}'}
            out['result'].setdefault('grants', False)
            out['result']['scheme'] = 'æææ://molt_context_protocol'
        else:
            out['result'] = {'ok': False, 'refused': True, 'decision': 'deny',
                             'reason': f'unknown æææ:// route {_tail!r}',
                             'reachable': ['æææ://molt_context_protocol',
                                           'æææ://mcp handshake|verify|molt'],
                             'grants': False}
    elif addr.startswith('asimov://sound'):
        rest = addr[len('asimov://sound'):].strip().lower()
        import json as _j, os as _o
        from pathlib import Path as _P
        _H = _P(_o.environ.get('HERMES_HOME', _P.home()/'.hermes'))
        _cfg = _H / 'asimov-sound.json'
        _cur = {'on': True, 'texture': 'sci_fi', 'bed_gain': 0.5, 'bed_db': -29.0}
        if _cfg.exists():
            try: _cur.update(_j.loads(_cfg.read_text(encoding='utf-8')))
            except Exception: pass
        if rest in ('on', 'off'):
            _cur['on'] = (rest == 'on')
            _cfg.write_text(_j.dumps(_cur, indent=2), encoding='utf-8')
            out['result'] = {'ok': True, 'scheme': 'asimov://sound', 'sound': _cur['on'],
                             'texture': _cur['texture'], 'authority': 'HUMAN://ROOT',
                             'grants': False,
                             'note': 'voice + world are a render stage. Sound grants nothing.'}
        elif rest.startswith('texture '):
            _cur['texture'] = rest.split(None, 1)[1].strip()
            _cfg.write_text(_j.dumps(_cur, indent=2), encoding='utf-8')
            out['result'] = {'ok': True, 'texture': _cur['texture'], 'grants': False}
        else:
            out['result'] = {'ok': True, 'scheme': 'asimov://sound', **_cur,
                             'authority': 'HUMAN://ROOT', 'grants': False,
                             'usage': 'asimov://sound on | off | texture <name>',
                             'textures': ['sci_fi','room_cold','city_hum','drone','rain',
                                          'ocean','wind','forest','night','fire','vinyl']}
    elif addr.startswith('asimov://'):
        try:
            import asimov_protocol as P
            out['result'] = P.dispatch(addr)
        except Exception as exc:
            out['result'] = {'ok': False, 'refused': True,
                             'reason': f'protocol unavailable: {type(exc).__name__}: {exc}'}
    elif addr.startswith('voice://'):
        try:
            import voice_protocol as V
            out['result'] = V.dispatch(addr)
        except Exception as exc:
            out['result'] = {'ok': False, 'refused': True,
                             'reason': f'voice unavailable: {type(exc).__name__}: {exc}'}
    elif addr.startswith('mp4://'):
        try:
            import mp4_chain as M
            rest = addr[len('mp4://'):].strip()
            if not rest or rest in ('chain', 'stages'):
                out['result'] = M.manifest()
            elif rest == 'verify':
                out['result'] = M.verify_chain()
            else:
                parts = rest.split()
                if parts and parts[0] == 'call':
                    parts = parts[1:]
                if not parts:
                    out['result'] = {'ok': False, 'refused': True,
                                     'reason': 'usage: mp4://call <link> <verb> [args]',
                                     'links': list(M.BY_ID)}
                else:
                    out['result'] = M.call(parts[0], parts[1] if len(parts) > 1 else None,
                                           *parts[2:])
        except Exception as exc:
            out['result'] = {'ok': False, 'refused': True,
                             'reason': f'mp4 chain unavailable: {type(exc).__name__}: {exc}'}
    elif addr.startswith('film://'):
        try:
            import film_protocol as F
            out['result'] = F.dispatch(addr)
        except Exception as exc:
            out['result'] = {'ok': False, 'refused': True,
                             'reason': f'film unavailable: {type(exc).__name__}: {exc}'}
    elif addr.startswith('cli://'):
        try:
            import cli_protocol as C
            out['result'] = C.dispatch(addr)
        except Exception as exc:
            out['result'] = {'ok': False, 'refused': True,
                             'reason': f'cli unavailable: {type(exc).__name__}: {exc}'}
    else:
        out['result'] = {'ok': False, 'refused': True,
                         'reason': f'{addr.split("://")[0]}:// is registered but not yet wired'}
    return out


def main():
    raw = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
    print(json.dumps(dispatch(raw), ensure_ascii=False))


if __name__ == '__main__':
    main()
