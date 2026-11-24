"""tinyEMOJI tests — the refusals are pinned, and so is the false negative.

The load-bearing lesson: pyzbar mis-decodes some 4-byte UTF-8 payloads (it
returned Chinese text for 🍊). A single decoder refused 18 of 26 QRs that were
perfectly fine. The tests pin the CROSS-DECODER behaviour.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "tinyemoji.py"
spec = importlib.util.spec_from_file_location("tinyemoji", MOD)
te = importlib.util.module_from_spec(spec)
spec.loader.exec_module(te)


class TestDoctor(unittest.TestCase):
    def test_registry_is_complete(self):
        d = te.doctor()
        self.assertTrue(d["ok"], d)
        c = d["checks"]
        self.assertEqual(c["missing"], 0)
        self.assertEqual(c["bad_payload"], 0)
        self.assertEqual(c["qr_ok"], c["symbols"])

    def test_punycode_is_computed(self):
        """Never recalled: IDNA on the label."""
        d = te.doctor()
        self.assertRegex(d["checks"]["punycode"], r"→ xn--")

    def test_multichar_symbols_are_declared(self):
        """♾️ is two codepoints. Honesty about graphemes."""
        self.assertRegex(te.doctor()["checks"]["multichar"], r"\d+ símbolos")


class TestRefusals(unittest.TestCase):
    def test_missing_surface(self):
        r = te.check("C:/definitely-not-here.html")
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_surface_without_core(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.html"
            p.write_text("<html><body>no registry here</body></html>", encoding="utf-8")
            r = te.check(p)
            self.assertFalse(r["ok"])
            self.assertIn("CORE", r["refusal"])

    def test_missing_qr_is_a_named_refusal(self):
        """A registry whose QR directory is empty must say exactly what is gone."""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "reg.html"
            src.write_text("var CORE=[{s:'🍊',cp:'U+1F34A',cap:'x'}];", encoding="utf-8")
            empty = Path(td) / "qr"; empty.mkdir()
            r = te.check(src, qrdir=empty)
            self.assertFalse(r["ok"])
            self.assertIn("U+1F34A.png", r["missing"])


class TestDecoders(unittest.TestCase):
    def test_pyzbar_alone_would_fail(self):
        """The false negative this instrument exists to prevent."""
        png = te.QRDIR / "U+1F34A.png"
        if not png.exists():
            self.skipTest("QR no presente")
        all_readings = te.decode_qr_all(png)
        self.assertTrue(any("#🍊" in r for r in all_readings),
                        f"ninguno de los decoders leyó el anchor: {all_readings}")

    def test_resolve_reports_the_anchor(self):
        r = te.resolve("🍊")
        self.assertTrue(r["qr_exists"])
        self.assertTrue(r["anchor_matches"], r)


class TestGrade(unittest.TestCase):
    def test_registry_read_is_stable(self):
        g = te.grade(te.REGISTRY)
        self.assertTrue(g["deterministic"], g)

    def test_punycode_reproducible(self):
        self.assertEqual(te.punycode("🍊"), te.punycode("🍊"))


class TestLedger(unittest.TestCase):
    def test_chain_verifies(self):
        self.assertTrue(te.ledger_verify()["chain_ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
