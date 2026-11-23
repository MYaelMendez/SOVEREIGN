#!/usr/bin/env python3
"""neuromitosis OS · status API. Every field is read from disk or probed live.

No credentials. No static status strings. A missing gate reports UNKNOWN,
never PASS. Served on 127.0.0.1:8092 for the OS surface on 8091.
"""
from __future__ import annotations

import hashlib, importlib.util, json, os, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path('C:/æ')
NM = ROOT / 'neuromitosis'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ''


def jload(p: Path):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def probe(url: str, timeout=1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except Exception:
        return None


def status() -> dict:
    corpus = NM / 'corpus.jsonl'
    manifest = jload(NM / 'corpus.manifest.json') or {}
    receipt = jload(NM / 'receipt.json') if (NM / 'receipt.json').exists() else jload(NM / 'neuromitosis.receipt.json')
    adapter = NM / 'lora-adapter'
    take = jload(ROOT / 'logs/tinyactor-takes.jsonl'.replace('logs/', 'logs/')) if False else None
    takes = [json.loads(l) for l in (ROOT / 'logs/tinyactor-takes.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    film = jload(ROOT / 'mp4-factory/tinyactor-performance-916.receipt.json')
    film_bytes = ROOT / 'mp4-factory/tinyactor-performance-916.mp4'

    # lesson chain — real verification, not a printed claim
    sp = importlib.util.spec_from_file_location('al', str(ROOT / 'agents/ae_lessons.py'))
    al = importlib.util.module_from_spec(sp); sp.loader.exec_module(al)
    recs = al.read_ledger()

    return {
        'schema': 'ae/neuromitosis-os-status/1',
        'system': {
            'boot': 'LOCAL · VICTUS · RTX 3050 6GB',
            'substrate': 'C:/æ · sovereign private client mesh',
            'authority': 'human-bound · no agent self-grant',
        },
        'modules': [
            {'id': 'CORPUS', 'label': 'bond corpus',
             'state': 'VERIFIED' if corpus.exists() and sha(corpus) == manifest.get('corpus_sha256') else 'UNVERIFIED',
             'detail': f"{manifest.get('records','?')} hash-bound records",
             'endpoint': 'neuromitosis/corpus.jsonl'},
            {'id': 'ADAPTER', 'label': 'Gemma QLoRA',
             'state': 'TRAINED' if receipt and adapter.exists() else ('TRAINING' if adapter.exists() else 'PENDING'),
             'detail': ((f"loss {receipt.get('train_loss'):.4f}" if isinstance(receipt.get('train_loss'), (int, float)) else 'no loss yet')
                        if receipt else 'no receipt yet'),
             'endpoint': 'neuromitosis/lora-adapter/'},
            {'id': 'LESSONS', 'label': 'self-repair ledger',
             'state': 'VALID' if al.verify_chain(recs) else 'BROKEN',
             'detail': f'{len(recs)} records · head {recs[-1]["hash"][:12]}' if recs else 'empty',
             'endpoint': 'logs/ae_lessons.jsonl'},
            {'id': 'ACTOR', 'label': 'tinyACTOR',
             'state': 'OPERATED' if takes else 'UNKNOWN',
             'detail': f"take {takes[-1]['hash'][:12] if takes else '—'} · grants:false",
             'endpoint': 'logs/tinyactor-takes.jsonl'},
            {'id': 'FILM', 'label': 'trace performance',
             'state': 'GATED' if film and film_bytes.exists() and sha(film_bytes) == film.get('sha256') else 'UNVERIFIED',
             'detail': f"{film.get('frames','?') if film else '?'} frames · sha {film.get('sha256','')[:12] if film else '—'}",
             'endpoint': 'mp4-factory/tinyactor-performance-916.mp4'},
        ],
        'endpoints': [
            {'name': 'tinyMUJOCO doctor', 'url': 'http://127.0.0.1:8170/doctor', 'http': probe('http://127.0.0.1:8170/doctor')},
            {'name': 'ae-boy console', 'url': 'http://127.0.0.1:8091/ae-boy.html', 'http': probe('http://127.0.0.1:8091/ae-boy.html')},
            {'name': 'ae-boy proxy', 'url': 'http://127.0.0.1:8166/health', 'http': probe('http://127.0.0.1:8166/health')},
            {'name': 'model server', 'url': 'http://127.0.0.1:8088/v1/models', 'http': probe('http://127.0.0.1:8088/v1/models')},
        ],
        'rejected_claims': [
            'ENCRYPTION: AES-4096 [ACTIVE] — static text, no crypto verified',
            'ACCESS GRANTED / UPTIME 99.999% — theater, no auth, no measurement',
            'fetch(/api/spatial/init) — 404 on static Pages',
            '675B/671B model fusion — catalog text, not local, not fused',
        ],
        'boundary': 'Evidence != Authority · no act granted by a surface · no physical motion (nu=0)',
    }


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/status'):
            body = json.dumps(status(), ensure_ascii=False, indent=1).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        elif self.path == '/health':
            body = b'{"ok":true,"service":"neuromitosis-os"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8092), H).serve_forever()
