#!/usr/bin/env python3
"""Live conductor proxy: Gemma-3-4B + v3 LoRA through the deterministic verb gate.

The model may propose a plan. The gate decides whether it is namable.
No act is granted. Served on 127.0.0.1:8093 for the neuromitosis OS.
"""
from __future__ import annotations

import importlib.util, json, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path('C:/æ')
UPSTREAM = 'http://127.0.0.1:8088/v1/chat/completions'

sp = importlib.util.spec_from_file_location('g', str(ROOT / 'agents/plan_verb_gate.py'))
g = importlib.util.module_from_spec(sp); sp.loader.exec_module(g)


def ask(prompt: str) -> dict:
    body = json.dumps({'model': 'gemma', 'messages': [{'role': 'user', 'content': prompt}],
                       'temperature': 0, 'max_tokens': 160, 'stream': False}).encode()
    req = urllib.request.Request(UPSTREAM, data=body, headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    text = d['choices'][0]['message']['content']
    return {'plan': text, 'gate': g.gate(text), 'seconds': round(time.time() - t0, 2),
            'completion_tokens': d.get('usage', {}).get('completion_tokens'),
            'prompt_tokens': d.get('usage', {}).get('prompt_tokens'),
            'granted': False}


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path == '/health':
            self._send(200, {'ok': True, 'service': 'neuromitosis-conductor',
                             'gate': 'plan_verb_gate', 'granted': False})
        else:
            self._send(404, {'ok': False})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if self.path != '/plan':
            self._send(404, {'ok': False}); return
        try:
            n = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(n) or b'{}')
            prompt = str(data.get('prompt', ''))[:800]
            if not prompt:
                self._send(400, {'ok': False, 'reason': 'empty prompt', 'granted': False}); return
            self._send(200, {'ok': True, **ask(prompt)})
        except Exception as e:
            self._send(502, {'ok': False, 'reason': str(e)[:180], 'granted': False})

    def log_message(self, *a): pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8093), H).serve_forever()
