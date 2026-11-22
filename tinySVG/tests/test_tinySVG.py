"""tinySVG tests — the refusals are pinned, not just the happy path.

The whole instrument exists because a 20-node constellation was published with
11.93 px labels. These tests pin that failure mode and the geometry rules.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent / "tinySVG.py"
spec = importlib.util.spec_from_file_location("tinySVG", MOD)
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


class TestDoctor(unittest.TestCase):
    def test_measures_the_render_not_the_viewbox(self):
        d = ts.doctor()
        self.assertTrue(d["ok"], d)
        c = d["checks"]
        self.assertEqual(c["nodes"], 20)
        self.assertEqual(c["small_labels"], 0)
        self.assertEqual(c["overflow"], 0)
        self.assertEqual(c["overlaps"], 0)
        self.assertGreaterEqual(c["font_effective_px"], ts.MIN_FONT_PX)

    def test_viewBox_is_derived_from_the_render_width(self):
        # a narrower render must yield a narrower viewBox, or the type shrinks
        self.assertLess(ts.viewBox_for(707.0, 27.0), ts.viewBox_for(1280.0, 27.0))
        # the deployed surface measured 11.93 px at viewBox 1600 — under the floor
        self.assertLess(27.0 * 707.0 / 1600.0, ts.MIN_FONT_PX)
        self.assertGreaterEqual(27.0 * 707.0 / ts.viewBox_for(707.0, 27.0), ts.MIN_FONT_PX)


class TestRefusals(unittest.TestCase):
    def test_missing_file(self):
        r = ts.check_svg("C:/definitely-not-here.svg")
        self.assertFalse(r["ok"])
        self.assertIn("refusal", r)

    def test_html_wrapper_is_unwrapped(self):
        """A surface is HTML around an SVG; the artifact must still be measured."""
        svg = ts.constellation(["a", "b"], render_w=707.0)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "page.html"
            p.write_text(f"<!DOCTYPE html><html><body>{svg}</body></html>", encoding="utf-8")
            r = ts.check_svg(p, render_w=707.0)
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["nodes"], 2)

    def test_surfaces_without_viewBox_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "novb.svg"
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle r="5"/></svg>', encoding="utf-8")
            r = ts.check_svg(p)
            self.assertFalse(r["ok"])
            self.assertIn("viewBox", r["refusal"])

    def test_unparseable_svg_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.svg"
            p.write_bytes(b"\x00\x01\x02 not xml")
            r = ts.check_svg(p)
            self.assertFalse(r["ok"])

    def test_small_type_is_a_refusal(self):
        # emit a layout whose viewBox is too wide for the render width
        svg = ts.constellation(["a", "b", "c"], render_w=707.0)
        import re
        svg = re.sub(r'viewBox="0 0 [\d.]+ [\d.]+"', 'viewBox="0 0 4000 2600"', svg, count=1)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wide.svg"
            p.write_text(svg, encoding="utf-8")
            r = ts.check_svg(p, render_w=707.0)
            self.assertFalse(r["ok"])
            self.assertTrue(r["small_labels"])


class TestGrade(unittest.TestCase):
    def test_deterministic(self):
        g = ts.grade(707.0)
        self.assertTrue(g["ok"])
        self.assertEqual(g["sha256_a"], g["sha256_b"])


class TestLedger(unittest.TestCase):
    def test_chain_verifies(self):
        v = ts.ledger_verify()
        self.assertTrue(v["chain_ok"])


class TestGeometry(unittest.TestCase):
    def test_inner_node_clears_the_hub(self):
        pts = ts.positions(20, 1590, 1033, node_r=58.0, hub_r=128.0)
        d = min(((x - 795) ** 2 + (y - 516.5) ** 2) ** 0.5 for x, y in pts)
        self.assertGreaterEqual(d, 128.0 + 58.0 + ts.HUB_CLEARANCE - 1)

    def test_no_two_nodes_overlap(self):
        pts = ts.positions(20, 1590, 1033, node_r=58.0, hub_r=128.0)
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                self.assertGreaterEqual(
                    ((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2) ** 0.5,
                    58.0 * 2 - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
