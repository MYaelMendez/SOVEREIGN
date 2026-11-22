#!/usr/bin/env python3
"""secræt tests — the invariants that matter: values never reach stdout."""
import io
import json
import os
import pathlib
import sys
import tempfile
import contextlib
import unittest

import secraet


class SecraetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.old = (secraet.SECRETS_DIR, secraet.STORE, secraet.KEYS, secraet.AUDIT)
        secraet.SECRETS_DIR = root / "secrets"
        secraet.STORE = secraet.SECRETS_DIR / "secrets.json"
        secraet.KEYS = secraet.SECRETS_DIR / "keys"
        secraet.AUDIT = secraet.SECRETS_DIR / "bridge.audit.log"
        secraet.SECRETS_DIR.mkdir(parents=True)
        self.secret = "sk-live-SECRET-value-0123456789"

    def tearDown(self):
        (secraet.SECRETS_DIR, secraet.STORE, secraet.KEYS, secraet.AUDIT) = self.old
        self.tmp.cleanup()

    def _seal(self, key="KLING", kind="api_key"):
        buf = io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(self.secret + "\n")
        try:
            with contextlib.redirect_stdout(buf):
                rc = secraet.main(["seal", key, "--kind", kind])
        finally:
            sys.stdin = old
        self.assertEqual(rc, 0, buf.getvalue())
        return buf.getvalue()

    def test_seal_writes_store_and_key_file_but_never_prints_value(self):
        out = self._seal()
        self.assertNotIn(self.secret, out)          # stdout stays clean
        self.assertIn("sha256:", out)
        doc = json.loads(secraet.STORE.read_text(encoding="utf-8"))
        self.assertEqual(doc["secrets"][0]["key"], "KLING")
        self.assertEqual(doc["secrets"][0]["value"], self.secret)
        self.assertTrue(secraet._key_file("KLING").is_file())
        self.assertEqual(secraet._key_file("KLING").read_text(encoding="utf-8"), self.secret)

    def test_list_masks_and_never_leaks(self):
        self._seal()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = secraet.main(["list"])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertNotIn(self.secret, out)
        self.assertIn("KLING", out)
        self.assertRegex(out, r"sha256|[0-9a-f]{16}")  # a fingerprint is present

    def test_get_json_carries_value_and_stdout_is_the_result(self):
        self._seal()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = secraet.main(["get", "KLING", "--json"])
        payload = json.loads(buf.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(payload["value"], self.secret)     # carried for the agent
        self.assertNotEqual(payload["preview"], self.secret)
        self.assertEqual(payload["sha256"], secraet.fp(self.secret))

    def test_get_human_writes_0600_temp_file_not_stdout(self):
        self._seal()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            secraet.main(["get", "KLING"])
        out = buf.getvalue()
        self.assertNotIn(self.secret, out)
        path = next((ln.split("value    ", 1)[1].split("  ", 1)[0]
                     for ln in out.splitlines() if ln.startswith("value    ")), None)
        self.assertIsNotNone(path, out)
        self.assertTrue(pathlib.Path(path).is_file())
        self.assertEqual(pathlib.Path(path).read_text(encoding="utf-8"), self.secret)

    def test_resolution_order_env_beats_store(self):
        self._seal()
        os.environ["KLING"] = "from-env"
        try:
            self.assertEqual(secraet.resolve("KLING")["value"], "from-env")
        finally:
            del os.environ["KLING"]
        self.assertEqual(secraet.resolve("KLING")["value"], self.secret)

    def test_unknown_key_returns_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = secraet.main(["get", "NOPE"])
        self.assertEqual(rc, 2)

    def test_fingerprint_is_stable_and_value_independent(self):
        self.assertEqual(secraet.fp("abc"), secraet.fp("abc"))
        self.assertNotEqual(secraet.fp("abc"), secraet.fp("abd"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
