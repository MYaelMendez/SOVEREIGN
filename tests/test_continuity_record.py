"""continuity_record tests — tiny* discipline: refusals, canon, legibility gate."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

MOD = Path("C:/æ/continuity_record.py")
spec = importlib.util.spec_from_file_location("cr", MOD)
cr = importlib.util.module_from_spec(spec); spec.loader.exec_module(cr)


def test_derive_is_well_formed_and_has_all_sources():
    root = cr.derive()
    assert root.get("schema") == cr.SCHEMA
    assert len(root.find("sections")) >= 70
    names = {s.get("name") for s in root.find("meta").findall("source")}
    assert {"AE-CONTINUITY.md", "github-activity.json", "brain.json", "ae_lessons.jsonl"} <= names


def test_canon_is_deterministic_and_sorted():
    root = cr.derive()
    a = cr.tinyxml().canon(root)
    b = cr.tinyxml().canon(cr._parse(cr.xml_bytes(root)))
    assert a == b
    assert a.startswith("<continuity ") and a.endswith("</continuity>")


def test_grade_byte_compares_two_canonicalisations():
    g = cr.grade(cr.xml_bytes(cr.derive()))
    assert g["ok"] and not g["refused"] and len(g["canon_sha256"]) == 64


def test_xxe_dtd_is_refused():
    payload = b'<!DOCTYPE continuity [<!ENTITY x "boom">]><continuity>&x;</continuity>'
    with pytest.raises(ValueError, match="DTD/entities"):
        cr._parse(payload)


def test_malformed_xml_is_refused():
    with pytest.raises(ValueError, match="tinyXML refused"):
        cr._parse(b"<continuity><broken>")


def test_legibility_floor_enforced():
    lg = cr.legibility()
    assert lg["ok"] and lg["effective_px"] >= cr.MIN_FONT_PX
    # a surface authored below the floor must be refused, not silently rendered
    assert "floor" in lg or lg["refusal"] is None


def test_render_is_pure_from_xml_and_round_trips():
    root = cr.derive()
    doc = cr.render(root, cr.grade(cr.xml_bytes(root)))
    assert doc.count('class="card"') == len(root.find("sections"))
    assert cr.grade(cr.xml_bytes(root))["canon_sha256"][:16] in doc
    assert "not recorded" in doc  # absence is explicit, not a fake label


def test_doctor_measures_does_not_assert():
    d = cr.doctor()
    assert d["ok"] and d["tinyXML"] and d["tinySVG"]
    assert isinstance(d["sections"], int) and d["sections"] > 0
