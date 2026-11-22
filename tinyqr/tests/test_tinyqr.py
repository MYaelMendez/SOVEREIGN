"""tinyqr tests — the refusals are pinned, not just the happy path.

Two refusals matter most here:
  * a signature that does not verify (the identity claim fails)
  * a QR that cannot be read back (the chip is a picture of a chip)
Plus the regression that cost real time: cv2 cannot read a non-ASCII path.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "tinyqr.py"
spec = importlib.util.spec_from_file_location("tinyqr", MOD)
tq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tq)


class TestDoctor(unittest.TestCase):
    def test_signs_for_real_end_to_end(self):
        d = tq.doctor()
        self.assertTrue(d["ok"], d)
        for step in ("modules", "keypair", "sign", "verify", "encode", "decode", "artifact_verifies"):
            self.assertIn(step, d["checks"])
        self.assertNotIn("REFUSED", str(d["checks"]))

    def test_artifact_verifies_is_the_load_bearing_check(self):
        """A QR that decodes but does not verify is a picture of a signature."""
        d = tq.doctor()
        self.assertEqual(d["checks"].get("artifact_verifies"), "ok")


class TestRefusals(unittest.TestCase):
    def test_verify_refuses_a_forged_signature(self):
        import hashlib
        pk = "ab" * 32
        r = tq.verify(pk, "m", hashlib.sha256(b"x").hexdigest())
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_decode_refuses_a_missing_file(self):
        r = tq.decode("C:/definitely-not-here.png")
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_decode_refuses_a_non_qr_image(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "blank.png"
            Image.new("RGB", (120, 120), (255, 255, 255)).save(p)
            r = tq.decode(p)
            self.assertFalse(r["ok"])

    def test_sign_refuses_an_unknown_key(self):
        r = tq.sign("no_such_key_xyz", "m")
        self.assertFalse(r["ok"])

    def test_seal_signs_the_artifact_and_the_qr_reads_back(self):
        """The whole point: sign a file, read the QR, verify the signature."""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "artifact.html"
            f.write_text("<html>tiny</html>", encoding="utf-8")
            r = tq.seal(f, key="sovereign-web")
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["sha256"], hashlib.sha256(f.read_bytes()).hexdigest())
            # the QR carries the short URL; the signature lives in the receipt
            d = tq.decode(r["png"])
            self.assertTrue(d["ok"], d)
            self.assertIn("verify.html?a=artifact.html", str(d["data"]))
            rec = json.loads(Path(r["receipt"]).read_text(encoding="utf-8"))
            v = tq.verify(rec["public_key"], rec["sha256"], rec["signature"])
            self.assertTrue(v["ok"], v)


class TestGrade(unittest.TestCase):
    def test_qr_is_reproducible(self):
        payload = {"a": 1, "b": "tinyqr"}
        g = tq.grade(payload)
        self.assertTrue(g["ok"])
        self.assertEqual(g["sha256_a"], g["sha256_b"])


class TestLedger(unittest.TestCase):
    def test_chain_verifies(self):
        v = tq.ledger_verify()
        self.assertTrue(v["chain_ok"])

    def test_tamper_breaks_the_chain(self):
        recs = tq.ledger_read()
        if not recs:
            self.skipTest("ledger vacio")
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "l.jsonl"
            t = dict(recs[-1]); t["decision"] = "forged"
            body = {k: v for k, v in t.items() if k != "hash"}
            self.assertNotEqual(t["hash"], tq._sha(tq._canon(body)))
            fake.write_text(json.dumps(t, ensure_ascii=False) + "\n", encoding="utf-8")
            prev = recs[-2]["hash"] if len(recs) > 1 else tq.GENESIS
            self.assertEqual(t["prev"], prev)


class TestUnicodePath(unittest.TestCase):
    """The regression that broke the chip: cv2.imread cannot read C:\\æ\\... ."""

    def test_supervision_reads_a_unicode_path(self):
        import sys
        sys.path.insert(0, r"C:\æ\agents")
        import qr_supervision as qs
        pngs = sorted(Path(r"C:\æ\secrets\keys\qr").glob("*.png"))
        if not pngs:
            self.skipTest("sin QR en disco")
        img = qs._imread(pngs[0])
        self.assertIsNotNone(img, "cv2.imread falla con paths no-ASCII; _imread debe leerlos")


if __name__ == "__main__":
    unittest.main(verbosity=2)
