#!/usr/bin/env python3
"""studio_proxy — let a browser reach VLC and the ledgers without lying about it.

VLC's HTTP interface sends no CORS headers, so a page at :8161 cannot fetch
:8081 even when VLC is listening. The studio reported "VLC not reachable" —
which was false. This proxy makes the reachability real and adds the headers.

    GET /vlc/requests/status.json   → VLC, with CORS
    GET /ledgers                    → counts read from disk, with CORS

Local only. Binds 127.0.0.1. No credential is accepted from the client; the
VLC password is read from the environment or the local default, never echoed.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import base64, json, os, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get('STUDIO_PROXY_PORT', '8164'))
VLC = 'http://127.0.0.1:8081'
VLC_PASS = os.environ.get('VLC_HTTP_PASS', 'asimov')
AUTH = 'Basic ' + base64.b64encode(f':{VLC_PASS}'.encode()).decode()


def home() -> Path:
    return Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))


def ledgers() -> dict:
    H = home()
    out = {}
    for name in ('ae-receipts', 'tiny-voca-receipts', 'render-jobs',
                 'sound-receipts', 'moh-receipts', 'asimov-protocol'):
        p = H / f'{name}.jsonl'
        if p.exists():
            try:
                out[name] = sum(1 for l in p.read_text(encoding='utf-8').splitlines() if l.strip())
            except Exception:
                out[name] = None
        else:
            out[name] = None
    return {'ok': True, 'ledgers': out,
            'total': sum(v for v in out.values() if v is not None),
            'grants': False,
            'note': 'read from disk. A missing file is null, never zero.'}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/ledgers':
            return self._send(200, ledgers())
        if u.path == '/health':
            return self._send(200, {'ok': True, 'proxy': 'studio', 'grants': False})
        if u.path.startswith('/vlc/'):
            target = VLC + u.path[4:] + (('?' + u.query) if u.query else '')
            try:
                r = urllib.request.urlopen(
                    urllib.request.Request(target, headers={'Authorization': AUTH}), timeout=10)
                return self._send(200, json.load(r))
            except Exception as exc:
                # report the FAILURE KIND, not a guess about VLC's state
                return self._send(502, {'ok': False, 'upstream': 'vlc',
                                        'error': f'{type(exc).__name__}: {exc}',
                                        'note': 'the proxy could not reach VLC. This is '
                                                'a proxy-side failure, not proof VLC is down.'})
        return self._send(404, {'ok': False, 'routes': ['/ledgers', '/health', '/vlc/...']})

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    print(f'  studio proxy on 127.0.0.1:{PORT} — /ledgers /health /vlc/...')
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
