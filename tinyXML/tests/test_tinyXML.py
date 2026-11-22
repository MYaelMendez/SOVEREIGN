"""tinyXML tests — the refusals are pinned, not just the happy path.

The three that matter: a broken document must report WHERE it broke (ElementTree
does not), an XXE payload must be refused, and the canonical form must be
reproducible — that last one is what lets two parties hash the same document.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "tinyXML.py"
spec = importlib.util.spec_from_file_location("tinyXML", MOD)
tx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tx)

FIX = HERE / "fixtures" / "family.xml"

XXE = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>
<foo>&xxe;</foo>
"""


class TestDoctor(unittest.TestCase):
    def test_measures_the_whole_chain(self):
        d = tx.doctor()
        self.assertTrue(d["ok"], d)
        c = d["checks"]
        self.assertEqual(c["deterministic"], True)
        self.assertEqual(c["xxe_refused"], True)
        self.assertIn("linea", c["error_position"])
        self.assertIn("defusedxml", c["parser"])

    def test_xxe_is_refused(self):
        _, info = tx.parse(XXE, safe=True)
        self.assertIn("error", info)


class TestCheck(unittest.TestCase):
    def test_missing_file(self):
        r = tx.check("C:/definitely-not-here.xml")
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_broken_xml_reports_line_and_column(self):
        """ElementTree gives no position; expat does. That is the point."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.xml"
            p.write_bytes(b"<a>\n  <b></a>\n")
            r = tx.check(p)
            self.assertFalse(r["ok"])
            self.assertIn("linea", r["refusal"])
            self.assertEqual(r["line"], 2)

    def test_html_is_not_xml(self):
        """A surface that is HTML must be refused, not silently parsed."""
        html = HERE.parent.parent / "github-pages" / "tinySVG.html"
        if not html.exists():
            self.skipTest("superficie no presente")
        r = tx.check(html)
        self.assertFalse(r["ok"])

    def test_real_xml_measures_depth_and_namespaces(self):
        r = tx.check(FIX)
        self.assertTrue(r["ok"], r)
        self.assertGreaterEqual(r["depth"], 2)
        self.assertIn("urn:ae", r["namespaces"])


class TestCanonical(unittest.TestCase):
    def test_canonical_form_is_stable(self):
        root, info = tx.parse(FIX.read_bytes())
        self.assertIsNotNone(root, info)
        self.assertEqual(tx.canon(root), tx.canon(root))

    def test_attributes_are_sorted(self):
        """Canonical form must not depend on attribute order in the source."""
        a = b'<r b="2" a="1"/>'
        b = b'<r a="1" b="2"/>'
        ra, _ = tx.parse(a); rb, _ = tx.parse(b)
        self.assertEqual(tx.canon(ra), tx.canon(rb))

    def test_text_is_preserved_exactly(self):
        """Unlike HTML, whitespace IS XML content. A canonicaliser that silently
        normalises it would let two different documents hash the same — so the
        canonical form must keep the text byte for byte."""
        a = b'<r><c> x </c></r>'
        b = b'<r><c>x</c></r>'
        ra, _ = tx.parse(a); rb, _ = tx.parse(b)
        self.assertNotEqual(tx.canon(ra), tx.canon(rb))
        self.assertIn(" x ", tx.canon(ra))

    def test_grade_is_deterministic(self):
        g = tx.grade(FIX)
        self.assertTrue(g["ok"])
        self.assertEqual(g["sha256_a"], g["sha256_b"])


class TestSign(unittest.TestCase):
    def test_signs_the_canonical_form(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "doc.xml"
            f.write_bytes(FIX.read_bytes())
            r = tx.sign(f, key="sovereign-web")
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["canonical_sha256"],
                             hashlib.sha256(tx.canon(tx.parse(FIX.read_bytes())[0]).encode()).hexdigest())
            rec = json.loads(Path(r["receipt"]).read_text(encoding="utf-8"))
            self.assertEqual(rec["canonical_sha256"], r["canonical_sha256"])
            self.assertTrue(rec["public_key"])
            self.assertTrue(rec["signature"])

    def test_sign_refuses_a_broken_document(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "bad.xml"
            f.write_bytes(b"<a><b></a>")
            r = tx.sign(f, key="sovereign-web")
            self.assertFalse(r["ok"])
            self.assertIn("refusal", r)


class TestLedger(unittest.TestCase):
    def test_chain_verifies(self):
        self.assertTrue(tx.ledger_verify()["chain_ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
