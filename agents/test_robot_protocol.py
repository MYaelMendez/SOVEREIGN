#!/usr/bin/env python3
"""robot:// tests — the fleet receipt must actually exist and chain."""
import hashlib
import json
import os
import pathlib
import tempfile
import unittest

import robot_protocol as rp


class RobotProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.old = (rp.LEDGER, rp.HERMES_HOME)
        rp.LEDGER = root / "robot-protocol.jsonl"
        rp.HERMES_HOME = root
        # dialect ledgers the fleet anchor will read
        for name in rp.ROBOTS:
            (root / f"{name}-protocol.jsonl").write_text("", encoding="utf-8")

    def tearDown(self):
        (rp.LEDGER, rp.HERMES_HOME) = self.old
        self.tmp.cleanup()

    def _lines(self):
        if not rp.LEDGER.exists():
            return []
        return [l for l in rp.LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_every_dispatch_writes_a_fleet_receipt(self):
        before = len(self._lines())
        out = rp.dispatch("robot://")
        self.assertIn("fleet_receipt", out)
        after = self._lines()
        self.assertEqual(len(after), before + 1)
        rec = json.loads(after[-1])
        self.assertEqual(rec["hash"], out["fleet_receipt"])
        self.assertEqual(rec["action"], "dispatch")
        self.assertEqual(rec["detail"]["address"], "robot://")

    def test_receipt_hash_matches_canonical_body(self):
        out = rp.dispatch("robot://robots")
        rec = json.loads(self._lines()[-1])
        body = {k: rec[k] for k in ("ts", "action", "authority", "detail", "prev")}
        self.assertEqual(hashlib.sha256(rp._canonical(body).encode()).hexdigest(), rec["hash"])

    def test_ledger_is_hash_linked(self):
        rp.dispatch("robot://")
        rp.dispatch("robot://robots")
        a, b = (json.loads(l) for l in self._lines())
        self.assertEqual(b["prev"], a["hash"])

    def test_refusal_is_still_recorded(self):
        out = rp.dispatch("robot://nosuchbot")
        self.assertFalse(out["success"])
        self.assertTrue(out["refused"])
        rec = json.loads(self._lines()[-1])
        self.assertFalse(rec["detail"]["success"])
        self.assertTrue(rec["detail"]["refused"])

    def test_fleet_ledger_anchors_every_dialect_plus_the_fleet(self):
        rp.dispatch("robot://asimov")
        led = rp.fleet_ledger()
        self.assertIn("robot", led["ledgers"])
        for name in list(rp.ROBOTS) + ["robot"]:
            self.assertIn(name, led["ledgers"])
        self.assertEqual(len(led["combined_sha256"]), 64)
        self.assertEqual(led["ledgers"]["robot"]["receipts"], 1)

    def test_fleet_ledger_route_is_not_self_recorded(self):
        n = len(self._lines())
        rp.dispatch("robot://fleet/ledger")
        self.assertEqual(len(self._lines()), n)   # no self-reference

    def test_parse_routes_the_first_segment(self):
        self.assertEqual(rp.parse("robot://asimov/plan stand"), ("asimov", ["plan", "stand"]))
        self.assertEqual(rp.parse("robot://fleet/ledger"), ("fleet", ["ledger"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
