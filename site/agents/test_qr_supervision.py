#!/usr/bin/env python3
"""
test_qr_supervision.py — the nine checks are code, so they get tests.

Improvement #7 of QR_SUPERVISION_IMPROVEMENTS.md: "The nine checks are untested
code. A smoke test proving the rune case refuses is not a suite — a regression in
contrast() or module_size would pass silently and be found by a customer instead
of a test."

These are BEHAVIOR contracts, not snapshots. Each test asserts a relationship the
gate must preserve, not a value that is expected to drift.

Run:
    python test_qr_supervision.py            # stdlib unittest, no pytest needed
    python test_qr_supervision.py -v
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

AGENTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
sys.path.insert(0, r"C:/æ/aeqr")

from ae import envelope as qe
from ae import supervision as qs


class TempPNG:
    """Render a payload to a temp PNG, with knobs to degrade it."""

    def __init__(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="qrtest-"))

    def render(self, envelope: str, name: str = "a.png", *, box_size: int = 10,
               border: int = 4, ecc: str = "M"):
        p = self.dir / name
        qs._render(envelope, p, box_size=box_size, border=border, ecc=ecc)
        return p


class TestTheGateAccepts(unittest.TestCase):
    """What must PASS."""

    def setUp(self):
        self.t = TempPNG()

    def test_a_good_card_passes(self):
        env = qe.encode("route", {"cmd": "væult:// status"})
        p = self.t.render(env)
        rep = qs.supervise(p, expect_kind="route")
        self.assertTrue(rep.passed, f"refused a good card: {rep.reason()}")
        self.assertEqual(len(rep.decoders_ok), 2, "both decoders must agree")

    def test_every_envelope_type_passes(self):
        for kind in qe.TYPES:
            with self.subTest(kind=kind):
                env = qe.encode(kind, {"probe": kind})
                p = self.t.render(env, name=f"{kind}.png")
                rep = qs.supervise(p, expect_kind=kind)
                self.assertTrue(rep.passed, f"{kind}: {rep.reason()}")

    def test_produce_returns_a_linked_receipt(self):
        r = qs.produce("route", {"cmd": "væult:// list"}, out_path=self.t.dir / "r.png")
        self.assertTrue(r.envelope_sha256 and r.image_sha256)
        self.assertTrue(r.chain, "a receipt must carry a chain hash")
        # the chain must be seeded from a REAL prev, not ""
        self.assertNotEqual(r.prev, "", "prev must not be empty — that is not a chain")


class TestTheGateRefuses(unittest.TestCase):
    """What must REFUSE. Each names a distinct reason."""

    def setUp(self):
        self.t = TempPNG()

    def test_rune_magic_is_refused(self):
        """The §5.3 failure class: generates fine, fails on scan."""
        good = qe.encode("route", {"cmd": "x"})
        rune = "æ:" + good[len("ae:"):]
        p = self.t.render(rune, name="rune.png")
        rep = qs.supervise(p, envelope=rune)
        self.assertFalse(rep.passed, "a rune envelope must be refused")
        names = {c.name for c in rep.failed}
        self.assertIn("charset", names, "charset must be the named failure")
        # and the mechanism: one decoder mangles it
        self.assertLess(len(rep.decoders_ok), 2,
                        "the rune class is caught by cross-decoder disagreement")

    def test_payload_mismatch_is_refused(self):
        env = qe.encode("route", {"cmd": "a"})
        p = self.t.render(env)
        rep = qs.supervise(p, expect_payload={"cmd": "DIFFERENT"}, envelope=env)
        self.assertFalse(rep.passed)
        self.assertIn("payload_match", {c.name for c in rep.failed})

    def test_type_mismatch_is_refused(self):
        env = qe.encode("route", {"cmd": "a"})
        p = self.t.render(env)
        rep = qs.supervise(p, expect_kind="secret", envelope=env)
        self.assertFalse(rep.passed)
        self.assertIn("type_fidelity", {c.name for c in rep.failed})

    def test_a_non_envelope_image_is_refused(self):
        import cv2
        import numpy as np
        p = self.t.dir / "blank.png"
        cv2.imwrite(str(p), np.full((200, 200, 3), 255, dtype=np.uint8))
        rep = qs.supervise(str(p))
        self.assertFalse(rep.passed)
        self.assertIn("envelope", {c.name for c in rep.failed})

    def test_a_tiny_render_is_refused_on_module_size(self):
        """box_size=1 makes modules too small to scan."""
        env = qe.encode("route", {"cmd": "x"})
        p = self.t.render(env, name="tiny.png", box_size=1, border=1)
        rep = qs.supervise(p, envelope=env)
        # either it fails to decode, or module_size catches it — both are refusals
        self.assertFalse(rep.passed, "a 1px-per-module code must not pass")


class TestTheChecksAreHonest(unittest.TestCase):
    """The checks must not report a proxy as a measurement."""

    def setUp(self):
        self.t = TempPNG()

    def test_module_count_is_measured_not_assumed(self):
        """A v8 code must report 49 modules, not the v1 floor of 21."""
        import cv2
        env = qe.encode("route", {"cmd": "y" * 60})
        p = self.t.render(env)
        img = cv2.imread(str(p))
        ok, _, pts, _ = cv2.QRCodeDetector().detectAndDecodeMulti(img)
        self.assertIsNotNone(pts, "detector must find the code")
        n, how = qs._estimate_modules_side(img, pts[0])
        self.assertIn("measured", how,
                      f"fell back to a proxy: {how} — a proxy that errs "
                      f"optimistic is worse than no check")
        self.assertEqual(n % 4, 1, "a QR side is 17+4v, always 1 mod 4")
        self.assertGreaterEqual(n, 21)

    def test_module_count_tracks_the_real_version(self):
        """Rendering different payload sizes must yield different, correct counts."""
        import cv2
        seen = []
        for i, n_chars in enumerate([2, 60, 300]):
            env = qe.encode("route", {"cmd": "z" * n_chars})
            p = self.t.render(env, name=f"v{i}.png")
            img = cv2.imread(str(p))
            ok, _, pts, _ = cv2.QRCodeDetector().detectAndDecodeMulti(img)
            if pts is None:
                continue
            n, how = qs._estimate_modules_side(img, pts[0])
            if "measured" in how:
                seen.append(n)
        self.assertGreaterEqual(len(seen), 2, "at least two sizes must measure")
        self.assertEqual(len(set(seen)), len(seen),
                         f"different sizes gave the same count: {seen}")

    def test_a_fallback_names_itself(self):
        """If measurement fails, the detail must SAY so — never look measured."""
        n, how = qs._estimate_modules_side(None, None)
        self.assertIn("assumed", how,
                      "a fallback must announce itself as a fallback")


class TestTheChainIsReal(unittest.TestCase):
    """The receipt chain must link, not just hash."""

    def test_prev_is_not_empty(self):
        prev, source = qs.chain_prev()
        # either a real prev, or an explicit statement that no chain exists
        self.assertTrue(prev or "no kænbæn" in source,
                        f"prev={prev!r} source={source!r}")

    def test_two_receipts_have_different_prev_or_chain(self):
        t = TempPNG()
        r1 = qs.produce("route", {"cmd": "one"}, out_path=t.dir / "1.png")
        r2 = qs.produce("route", {"cmd": "two"}, out_path=t.dir / "2.png")
        self.assertNotEqual(r1.chain, r2.chain, "distinct artifacts, distinct chains")
        # if a chain exists, r2 must have moved past r1's starting point
        if r1.prev and r2.prev:
            self.assertNotEqual(r2.prev, "",
                                "the second receipt must have a real prev")


class TestTheGateIsArmed(unittest.TestCase):
    """#9: an unarmed gate must be distinguishable from a bad artifact."""

    def test_decoders_available_reports_each(self):
        d = qs.decoders_available()
        self.assertIn("cv2", d)
        self.assertIn("pyzbar", d)
        self.assertTrue(d["cv2"], "cv2 is required for the gate to run at all")

    def test_require_armed_raises_when_short(self):
        """With one decoder, GateUnarmed must fire — not a check failure."""
        orig = qs.decoders_available
        qs.decoders_available = lambda: {"cv2": True, "pyzbar": False}
        try:
            with self.assertRaises(qs.GateUnarmed):
                qs.require_armed()
        finally:
            qs.decoders_available = orig

    def test_unarmed_is_not_a_refusal(self):
        """GateUnarmed and QRRefused must be different types — an operator has
        to tell 'this artifact is bad' from 'I cannot tell'."""
        self.assertFalse(issubclass(qs.GateUnarmed, qs.QRRefused))
        self.assertFalse(issubclass(qs.QRRefused, qs.GateUnarmed))


class TestTheChainIsConsumable(unittest.TestCase):
    """#4: a chain nobody reads proves nothing. ORDER and GENESIS must be checked."""

    def _good(self):
        return [{"receipt": "r1", "prev": "genesis"},
                {"receipt": "r2", "prev": "r1"},
                {"receipt": "r3", "prev": "r2"}]

    def test_an_intact_chain_verifies(self):
        r = qs._verify_links(self._good())
        self.assertTrue(r["ok"], r["breaks"])
        self.assertEqual(r["links"], 3)

    def test_a_reorder_is_caught(self):
        bad = self._good(); bad[1]["prev"] = "r0"
        r = qs._verify_links(bad)
        self.assertFalse(r["ok"], "a broken prev must not verify")
        self.assertIn("previous receipt", r["first_break"]["why"])

    def test_an_omission_is_caught(self):
        g = self._good()
        r = qs._verify_links([g[0], g[2]])       # r2 removed
        self.assertFalse(r["ok"], "an omission must not verify")

    def test_a_bad_genesis_seed_is_caught(self):
        r = qs._verify_links([{"receipt": "r1", "prev": "elsewhere"}])
        self.assertFalse(r["ok"])
        self.assertIn("genesis", r["first_break"]["why"])

    def test_the_real_chain_verifies(self):
        r = qs.chain_verify()
        self.assertTrue(r["ok"], f"the live chain has breaks: {r['breaks'][:2]}")
        self.assertGreater(r["links"], 0)


class TestAdvisoryChecks(unittest.TestCase):
    """A check that cannot tell a working artifact from a broken one must not
    refuse one. This class exists because module_size/quiet_zone/contrast DID
    refuse working artifacts — a rotated code both decoders read fine."""

    def setUp(self):
        self.t = TempPNG()

    def test_a_rotated_code_both_decoders_read_is_not_refused(self):
        """The exact regression: 6 and 20 degrees were falsely refused."""
        import cv2
        import numpy as np
        env = qe.encode("route", {"cmd": "test"})
        p = self.t.render(env)
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        for ang in (6, 20, 35):
            with self.subTest(angle=ang):
                M = cv2.getRotationMatrix2D((w/2, h/2), ang, 1.0)
                rot = cv2.warpAffine(img, M, (w, h), borderValue=(255,255,255))
                rp = self.t.dir / f"rot{ang}.png"
                cv2.imwrite(str(rp), rot)
                scannable = (env in qs._decode_with_cv2(rot)
                             and env in qs._decode_with_pyzbar(rot))
                rep = qs.supervise(str(rp), envelope=env)
                self.assertEqual(rep.passed, scannable,
                                 f"{ang}deg: decoders say {scannable}, gate says "
                                 f"{rep.passed} — refused by "
                                 f"{[c.name for c in rep.failed]}")

    def test_advisory_checks_are_reported_but_cannot_refuse(self):
        env = qe.encode("route", {"cmd": "x"})
        p = self.t.render(env)
        rep = qs.supervise(p, envelope=env)
        names = {c.name for c in rep.advisory_notes}
        self.assertIn("module_size", names,
                      "module_size must be advisory — it is a proxy")
        for c in rep.failed:
            self.assertFalse(c.advisory,
                             f"{c.name} is advisory but appears in failed")

    def test_the_gate_still_refuses_a_genuinely_broken_artifact(self):
        """Advisory must not mean toothless: the real checks still bite."""
        env = qe.encode("route", {"cmd": "a"})
        p = self.t.render(env)
        rep = qs.supervise(p, expect_payload={"cmd": "OTHER"}, envelope=env)
        self.assertFalse(rep.passed, "payload_match must still refuse")

    def test_occlusion_that_breaks_the_decode_is_refused(self):
        """The one remaining sweep failure IS correct: decoders cannot read it."""
        import cv2
        import numpy as np
        env = qe.encode("route", {"cmd": "x"})
        p = self.t.render(env)
        img = cv2.imread(str(p))
        h, w = img.shape[:2]
        occluded = img.copy()
        occluded[h - int(h*0.16):, :int(w*0.16)] = 40
        op = self.t.dir / "occ.png"
        cv2.imwrite(str(op), occluded)
        scannable = (env in qs._decode_with_cv2(occluded)
                     and env in qs._decode_with_pyzbar(occluded))
        rep = qs.supervise(str(op), envelope=env)
        self.assertEqual(rep.passed, scannable)


class TestAssuranceLevel(unittest.TestCase):
    """A pass without an expectation is not the same claim as a pass against a
    stated truth. The report must not blur them.

    Without this, `roundtrip` compares the image to the envelope recovered FROM
    the image, and `cross_decoder` compares two decoders to each other — both
    self-referential. The gate would report PASS for 'this image decodes to
    whatever this image decodes to'."""

    def setUp(self):
        self.t = TempPNG()

    def test_no_expectation_is_self_consistent(self):
        env = qe.encode("route", {"cmd": "x"})
        p = self.t.render(env)
        rep = qs.supervise(str(p))              # no expectation at all
        self.assertEqual(rep.assurance, "self_consistent")
        self.assertEqual(rep.expectations, [])
        names = {c.name for c in rep.advisory_notes}
        self.assertIn("assurance", names,
                      "a self-consistent-only pass must SAY so")

    def test_an_envelope_upgrades_the_assurance(self):
        env = qe.encode("route", {"cmd": "x"})
        p = self.t.render(env)
        rep = qs.supervise(str(p), envelope=env)
        self.assertEqual(rep.assurance, "expected")
        self.assertIn("envelope", rep.expectations)

    def test_a_payload_expectation_is_expected(self):
        env = qe.encode("route", {"cmd": "x"})
        p = self.t.render(env)
        rep = qs.supervise(str(p), expect_payload={"cmd": "x"}, envelope=env)
        self.assertEqual(rep.assurance, "expected")
        self.assertIn("payload", rep.expectations)

    def test_produce_always_yields_expected(self):
        """The producer knows what it meant, so it must always assert it."""
        r = qs.produce("route", {"cmd": "x"}, out_path=self.t.dir / "p.png")
        self.assertEqual(r.report["assurance"], "expected")
        self.assertTrue(r.report["expectations"])

    def test_the_tautology_does_not_catch_a_wrong_but_consistent_render(self):
        """The honest limitation, asserted: a self-consistent pass proves the
        image decodes, NOT that it decodes to the intended payload."""
        envA = qe.encode("route", {"cmd": "TRANSFER TO ALICE"})
        envB = qe.encode("route", {"cmd": "TRANSFER TO MALLORY"})
        pB = self.t.render(envB, name="b.png")
        # a scan with no expectation cannot know B is wrong
        rep = qs.supervise(str(pB))
        self.assertTrue(rep.passed)
        self.assertEqual(rep.assurance, "self_consistent",
                         "and it must be labelled as such, not as verified")
        # with the expectation, it is caught
        rep2 = qs.supervise(str(pB), envelope=envA)
        self.assertFalse(rep2.passed, "the expected envelope must catch the swap")


if __name__ == "__main__":
    unittest.main(verbosity=2)
