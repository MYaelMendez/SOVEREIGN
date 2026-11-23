"""Determinism and safety gates for the neuromitosis corpus.

Run: python -m pytest neuromitosis/test_corpus.py -q
"""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path('C:/æ')
TOOL = ROOT / 'neuromitosis/build_corpus.py'
CORPUS = ROOT / 'neuromitosis/corpus.jsonl'
MANIFEST = ROOT / 'neuromitosis/corpus.manifest.json'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_manifest_matches_bytes():
    m = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert sha(CORPUS) == m['corpus_sha256']
    assert len(CORPUS.read_text(encoding='utf-8').splitlines()) == m['records'] == 44


def test_every_record_hash_binds_to_its_source():
    for line in CORPUS.read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        src = ROOT / r['source']
        assert src.exists(), r['source']
        assert sha(src) == r['source_sha256'], r['source']
        assert r['instruction'] and r['response']


def test_no_credential_values():
    import re
    text = CORPUS.read_text(encoding='utf-8')
    assert not re.search(r'gh[pousr]_[A-Za-z0-9]{20,}|Bearer [A-Za-z0-9._-]{20,}|sk-[A-Za-z0-9]{20,}', text)


def test_regeneration_is_deterministic(tmp_path):
    before = sha(CORPUS)
    subprocess.run([sys.executable, str(TOOL)], check=True, capture_output=True)
    assert sha(CORPUS) == before, 'corpus is not deterministic'
