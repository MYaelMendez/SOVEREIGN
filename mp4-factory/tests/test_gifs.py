"""
test_gifs.py — tests for the two GIF capabilities in this estate.

1. agentic_ontology_gif.py  — deterministic authoring (full tests, no deps
   beyond Pillow, which the renderer already requires).
2. gif-search skill         — Tenor search/download via curl + jq. Its live
   calls skip with an explicit reason when TENOR_API_KEY is absent; the
   static-contract tests always run so a broken/missing SKILL.md is caught.

Run:  python -m pytest C:/ae/mp4-factory/tests/test_gifs.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MP4_FACTORY = Path("C:/æ/mp4-factory")
RENDERER = MP4_FACTORY / "agentic_ontology_gif.py"
GIF_OUT = MP4_FACTORY / "agentic_ontology.gif"
SKILL = Path("C:/Users/yaelm/AppData/Local/hermes/skills/media/gif-search/SKILL.md")


def load_renderer():
    spec = importlib.util.spec_from_file_location("agentic_ontology_gif", RENDERER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 1. deterministic authoring ──────────────────────────────────────────────

def test_renderer_module_imports():
    mod = load_renderer()
    assert len(mod.CATS) == 9
    assert mod.OSW == ["DISCOVER", "FORK", "CONNECT", "ORCHESTRATE", "VERIFY"]


def test_frame_is_exact_9x16_rgb():
    mod = load_renderer()
    img = mod.frame(0, mod.FRAMES)
    assert img.size == (576, 1024)
    assert img.mode == "RGB"


def test_frames_are_deterministic():
    """Same (k, total) must produce byte-identical pixels — the core claim."""
    mod = load_renderer()
    a = mod.frame(13, mod.FRAMES).tobytes()
    b = mod.frame(13, mod.FRAMES).tobytes()
    assert a == b


def test_animation_advances():
    """The pulse must actually move; 60 identical frames is not an animation."""
    mod = load_renderer()
    a = mod.frame(0, mod.FRAMES).tobytes()
    b = mod.frame(20, mod.FRAMES).tobytes()
    assert a != b


def test_pulse_is_bounded_and_wraps():
    mod = load_renderer()
    for k in range(0, 60, 5):
        for i in range(len(mod.CATS)):
            p = mod.pulse(k / 60, i, len(mod.CATS))
            assert 0.0 <= p <= 1.0
    # visiting node 0 at phase 0 is full; node 4 is not
    assert mod.pulse(0.0, 0, 9) == pytest.approx(1.0)
    assert mod.pulse(0.0, 4, 9) < 1.0


def test_ledger_taxonomy_unchanged():
    """The renderer must not drift from brain_index.py's category set."""
    mod = load_renderer()
    names = {c[0] for c in mod.CATS}
    expected = {"CHASSIS", "AGENT", "COMPUTE", "MEDIA", "CUSTODY",
                "ECONOMY", "KNOWLEDGE", "INFRA", "SURFACE"}
    assert names == expected


@pytest.mark.skipif(not GIF_OUT.exists(), reason="run agentic_ontology_gif.py first")
def test_encoded_gif_contract():
    from PIL import Image, ImageChops
    im = Image.open(GIF_OUT)
    assert im.format == "GIF"
    assert im.size == (576, 1024)
    assert im.n_frames == 60
    assert im.info.get("loop") == 0  # infinite loop
    im.seek(0); f0 = im.convert("RGB").copy()
    im.seek(30); f30 = im.convert("RGB").copy()
    assert ImageChops.difference(f0, f30).getbbox() is not None


# ── 2. gif-search skill contract ────────────────────────────────────────────

@pytest.mark.skipif(not SKILL.exists(), reason="gif-search skill not installed")
def test_gif_search_skill_contract():
    """Pin the real commands so the skill cannot silently rot."""
    txt = SKILL.read_text(encoding="utf-8")
    assert "tenor.googleapis.com/v2/search" in txt
    assert ".media_formats.gif.url" in txt
    assert ".media_formats.tinygif.url" in txt
    assert "TENOR_API_KEY" in txt
    assert "curl" in txt and "jq" in txt
    assert "limit" in txt and "media_filter" in txt and "contentfilter" in txt


@pytest.mark.skipif(not SKILL.exists(), reason="gif-search skill not installed")
def test_gif_search_frontmatter_hardline():
    """Hermes skill-authoring rules: lowercase name, Hermes author, <=60 desc."""
    txt = SKILL.read_text(encoding="utf-8")
    fm = txt.split("---", 2)[1]
    assert "name: gif-search" in fm
    assert "author: Hermes" in fm
    line = next(l for l in fm.splitlines() if l.strip().startswith("description:"))
    desc = line.split("description:", 1)[1].strip().strip('"')
    assert len(desc) <= 60, f"description is {len(desc)} chars, over the 60-char cap"
    assert desc.endswith(".")


@pytest.mark.skipif(not shutil.which("jq"), reason="jq not installed")
@pytest.mark.skipif(not shutil.which("curl"), reason="curl not installed")
@pytest.mark.skipif(not os.getenv("TENOR_API_KEY"), reason="TENOR_API_KEY not set")
def test_gif_search_live_returns_gif_urls():
    """Live call: proves the documented endpoint works with a real key."""
    key = os.environ["TENOR_API_KEY"]
    url = ("https://tenor.googleapis.com/v2/search?q=thumbs+up&limit=1"
           f"&key={key}")
    out = subprocess.run(
        ["curl", "-s", url], capture_output=True, text=True, timeout=30, check=True
    ).stdout
    urls = subprocess.run(
        ["jq", "-r", ".results[].media_formats.gif.url"],
        input=out, capture_output=True, text=True, timeout=10, check=True
    ).stdout.strip().splitlines()
    assert urls and all(u.startswith("https://") for u in urls)


def test_gif_search_missing_key_is_a_refusal_not_a_fallback():
    """Refusal path: with no key the skill documents no anonymous fallback."""
    txt = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    assert "TENOR_API_KEY" in txt            # credential is declared
    assert "Get a free API key" in txt       # and the user is told how to get one
    # The documented endpoint always carries key=<TENOR_API_KEY>; there is no
    # keyless URL in the skill, so absence of the key must stop the caller.
    assert "key=${TENOR_API_KEY}" in txt
    # The only placeholder key mention is inside the .env setup block, not a
    # usable request URL — so there is no documented anonymous request path.
    setup_block = txt.split("## Search for GIFs")[0]
    assert "TENOR_API_KEY=your_key_here" in setup_block
    assert "tenor.googleapis.com" not in setup_block