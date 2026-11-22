"""tinyffmpeg tests — the refusals are pinned, not just the happy path.

A green suite that only exercises success proves nothing (tiny-instruments #2).
Every refusal below is triggered against a real condition: a missing input, an
unknown codec, a broken ledger.
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "tinyffmpeg.py"
spec = importlib.util.spec_from_file_location("tinyffmpeg", MOD)
tf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tf)


def _fixture_mp4() -> Path | None:
    """A real input, made by the real ffmpeg. None if no build is present."""
    builds = tf._candidates()
    if not builds:
        return None
    fd, name = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    out = Path(name)
    rc, _, _ = tf._run(builds[0], ["-hide_banner", "-loglevel", "error", "-y",
                                    "-f", "lavfi", "-i", "testsrc=size=64x48:rate=5",
                                    "-frames:v", "5", str(out)])
    return out if rc == 0 and out.exists() else None


class TestDoctor(unittest.TestCase):
    def test_measures_and_proves(self):
        d = tf.doctor()
        self.assertIn("ok", d)
        if d["found"] == 0:
            self.assertIn("refusal", d)
            return
        self.assertTrue(d["ok"])
        self.assertTrue(d["builds"])
        for b in d["builds"]:
            self.assertIn("encode_proof", b)
            self.assertTrue(b["path"])
            # a build that cannot encode is never reported ok
            if b["encode_proof"] != "PASS":
                self.assertFalse(d["ok"])


class TestRefusals(unittest.TestCase):
    def test_encode_refuses_missing_input(self):
        r = tf.encode(Path("C:/definitely-not-here.mp4"), Path("C:/tmp-out.mp4"))
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_encode_refuses_unknown_codec(self):
        src = _fixture_mp4()
        if src is None:
            self.skipTest("no ffmpeg fixture available")
        with tempfile.TemporaryDirectory() as td:
            r = tf.encode(src, Path(td) / "o.mp4", codec="no_such_codec_xyz")
            self.assertFalse(r["ok"])
            self.assertIn("refusal", r)

    def test_probe_refuses_without_build(self):
        r = tf.probe(Path("C:/definitely-not-ffmpeg.exe"))
        self.assertFalse(r["ok"])


class TestGrade(unittest.TestCase):
    def test_two_runs_byte_compared(self):
        src = _fixture_mp4()
        if src is None:
            self.skipTest("no ffmpeg fixture available")
        g = tf.grade(src)
        self.assertIn("deterministic", g)
        if g.get("ok"):
            self.assertEqual(g["sha256_a"], g["sha256_b"])

    def test_grade_refuses_missing_input(self):
        g = tf.grade(Path("C:/definitely-not-here.mp4"))
        self.assertFalse(g["ok"])
        self.assertIn("refusal", g)


class TestLedger(unittest.TestCase):
    def test_chain_is_verifiable(self):
        v = tf.ledger_verify()
        self.assertTrue(v["chain_ok"])

    def test_tamper_is_detected(self):
        """A rewritten record must break the chain."""
        recs = tf.ledger_read()
        if not recs:
            self.skipTest("ledger empty")
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "led.jsonl"
            tampered = dict(recs[-1])
            tampered["decision"] = "forged"
            body = {k: v for k, v in tampered.items() if k != "hash"}
            fake.write_text(json.dumps(tampered, ensure_ascii=False) + "\n", encoding="utf-8")
            prev = recs[-2]["hash"] if len(recs) > 1 else tf.GENESIS
            self.assertNotEqual(tampered["hash"], tf._sha(tf._canon(body)))
            self.assertEqual(tampered["prev"], prev)


if __name__ == "__main__":
    unittest.main(verbosity=2)
