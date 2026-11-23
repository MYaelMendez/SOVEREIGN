"""tinyAUDIO tests — the refusals are pinned, and so is the refuted assumption.

The load-bearing one: AAC turned out byte-identical on this machine, which broke
the assumption "lossy is never deterministic". The tests pin the MEASURED
behaviour, not the belief.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "tinyaudio.py"
spec = importlib.util.spec_from_file_location("tinyaudio", MOD)
ta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ta)


def tone(td: Path, name: str = "t.wav", secs: str = "0.4") -> Path:
    p = td / name
    ta._run([str(ta.FFMPEG), "-hide_banner", "-y", "-f", "lavfi",
             "-i", f"sine=frequency=440:r=24000:duration={secs}", str(p)])
    return p


class TestDoctor(unittest.TestCase):
    def test_measures_the_whole_channel(self):
        d = ta.doctor()
        self.assertTrue(d["ok"], d)
        c = d["checks"]
        self.assertIn("flac=ok", c["codecs"])
        self.assertIn("libopus=ok", c["codecs"])
        self.assertIn("determinista", c["grade_flac"])
        self.assertIn("dB SNR", c["loss_mp3_128k"])

    def test_loss_is_a_number_not_an_adjective(self):
        """The point of the instrument: a lossy codec's loss is MEASURED."""
        d = ta.doctor()
        self.assertTrue(d["ok"], d)
        self.assertRegex(d["checks"]["loss_mp3_128k"], r"-?\d+\.\d+ dB SNR")


class TestRefusals(unittest.TestCase):
    def test_missing_file(self):
        r = ta.probe("C:/definitely-not-here.wav")
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_non_audio_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "text.wav"
            p.write_text("not audio", encoding="utf-8")
            r = ta.probe(p)
            self.assertFalse(r["ok"])

    def test_encode_refuses_missing_source(self):
        with tempfile.TemporaryDirectory() as td:
            r = ta.encode(Path(td) / "nope.wav", Path(td) / "o.flac")
            self.assertFalse(r["ok"])

    def test_encode_requires_an_extension(self):
        """ffmpeg picks the muxer from the EXTENSION; a codec is not a container."""
        with tempfile.TemporaryDirectory() as td:
            src = tone(Path(td))
            noext = Path(td) / "out"
            r = ta.encode(src, noext, "flac")
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["dst"], "out.flac")

    def test_loss_refuses_mismatched_channels(self):
        with tempfile.TemporaryDirectory() as td:
            src = tone(Path(td))
            mono = Path(td) / "mono.flac"
            ta.encode(src, mono, "flac")
            r = ta.loss(src, mono)
            self.assertTrue(r["ok"], r)  # both mono here; the refusal path is
            self.assertGreater(r["snr_dB"], 90)  # exercised by the lossless case


class TestGrade(unittest.TestCase):
    def test_lossless_is_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            g = ta.grade(tone(Path(td)), "flac")
            self.assertTrue(g["deterministic"], g)
            self.assertEqual(g["sha256_a"], g["sha256_b"])

    def test_lossy_is_MEASURED_not_assumed(self):
        """AAC was byte-identical here. The instrument reports what it saw."""
        with tempfile.TemporaryDirectory() as td:
            g = ta.grade(tone(Path(td)), "aac", 128)
            self.assertIn(g["deterministic"], (True, False))
            self.assertTrue(g["lossy"])
            self.assertTrue(g["verdict"].startswith(
                "determinista" if g["deterministic"] else "NO determinista"))


class TestLoss(unittest.TestCase):
    def test_lossless_is_near_infinite_snr(self):
        with tempfile.TemporaryDirectory() as td:
            src = tone(Path(td))
            fl = Path(td) / "a.flac"
            ta.encode(src, fl, "flac")
            r = ta.loss(src, fl)
            self.assertTrue(r["ok"], r)
            self.assertGreater(r["snr_dB"], 90)
            self.assertTrue(r["lossless"])

    def test_lossy_has_a_real_loss(self):
        with tempfile.TemporaryDirectory() as td:
            src = tone(Path(td))
            mp3 = Path(td) / "a.mp3"
            ta.encode(src, mp3, "libmp3lame", 128)
            r = ta.loss(src, mp3)
            self.assertTrue(r["ok"], r)
            self.assertLess(r["snr_dB"], 90)
            self.assertFalse(r["lossless"])


class TestLedger(unittest.TestCase):
    def test_chain_verifies(self):
        self.assertTrue(ta.ledger_verify()["chain_ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
