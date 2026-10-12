"""
brain_index.py — the neuromitosis brain index.

Scans every surface on the site and produces a live index the neuromitosis page
renders. This is the site's brain: what exists, what it is, how it is classified.

The classification is the AGENTIC ENGINEERING ONTOLOGY — the pivot. Every
surface is placed by what it *is* in the agentic stack, not by when it was made.

Ontology (the pivot):
  CHASSIS      the language/runtime layer (schemes, routers, interpreters)
  AGENT        agents, fleets, orchestration, the human loop
  COMPUTE      GPU, CUDA, inference, the RTX node
  MEDIA        video, audio, image — production and verification
  CUSTODY      secrets, vault, authority, grants
  ECONOMY      DAO LLC, rails, funding, the market tape
  KNOWLEDGE    curricula, indices, research, schools
  SURFACE      the HTML viewports themselves (index/entry/terminal)
  INFRA        droplet, mesh, DNS, deployment

Output: brain.json + brain.js (const BRAIN = {...})
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

SITE = Path(r"C:\æ\github-pages")

# ── the ontology: keyword → category ──
# Order matters: first match wins, so specific before generic.
ONTOLOGY = [
    ("CUSTODY", ["vault", "væult", "vaeult", "secret", "privateclient", "vault-layers",
                 "authority", "grant", "passkey", "qr-key", "key-manager", "glocal-secret"]),
    ("MEDIA", ["video", "mp4", "media", "audio", "teleprompt", "render", "cuda-vlc",
               "videolab", "factory", "storyboard", "zeitgeist", "vlc", "podcast",
               "aertx", "cdp", "constellation", "holomesh"]),
    ("COMPUTE", ["cuda", "gpu", "rtx", "inference", "llama", "monaco", "mech-3d",
                 "mech-4d", "kernel", "tensor", "matmul", "cuda-ide", "pc-inference"]),
    ("ECONOMY", ["dao", "doola", "rails", "funding", "market", "index", "cri", "stripe",
                 "revenue", "llc", "letterspace", "store", "llm-store", "price"]),
    ("KNOWLEDGE", ["school", "curricul", "lesson", "course", "research", "wiki",
                   "teologia", "hauge", "biblioteca", "hermes-native", "education",
                   "molt", "learning"]),
    ("CHASSIS", ["chassis", "scheme", "router", "protocol", "basic", "baesic", "bæsic",
                 "interpreter", "a2ui", "ontology", "mech", "æææ", "aaa", "cli-4d",
                 "semantic-key", "code-mode", "compose", "ae-cli", "aeos"]),
    ("AGENT", ["agent", "fleet", "loop", "human", "neuromitosis", "orchestrat",
               "swarm", "keeper", "hermes", "codex", "interpreter", "subagent"]),
    ("INFRA", ["droplet", "mesh", "glocal", "deploy", "nginx", "tunnel", "dns",
               "vps", "node", "telemetry", "vscoder", "vscode", "bridge"]),
    ("SURFACE", ["index", "home", "demo", "404", "entry", "hub", "root", "map",
                 "guide", "banner", "dashboard"]),
]

CATEGORY_META = {
    "CHASSIS":   {"glyph": "⌘", "role": "the language/runtime layer — schemes, routers, interpreters"},
    "AGENT":     {"glyph": "◈", "role": "agents, fleets, orchestration — the human loop"},
    "COMPUTE":   {"glyph": "▤", "role": "GPU, CUDA, inference — the RTX node"},
    "MEDIA":     {"glyph": "▶", "role": "video, audio, image — production and verification"},
    "CUSTODY":   {"glyph": "🔒", "role": "secrets, vault, authority — grants and revocation"},
    "ECONOMY":   {"glyph": "$", "role": "DAO LLC, rails, funding — the market tape"},
    "KNOWLEDGE": {"glyph": "✎", "role": "curricula, indices, schools — teaching early"},
    "INFRA":     {"glyph": "⬡", "role": "droplet, mesh, DNS — deployment and telemetry"},
    "SURFACE":   {"glyph": "□", "role": "the HTML viewports — entry, index, terminal"},
    "OTHER":     {"glyph": "·", "role": "unclassified surfaces"},
}


def classify(name: str, title: str) -> str:
    hay = (name + " " + title).lower()
    for cat, keys in ONTOLOGY:
        if any(k in hay for k in keys):
            return cat
    return "OTHER"


def title_of(path: Path) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", txt, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:90]
    m = re.search(r"<h1[^>]*>(.*?)</h1>", txt, re.S | re.I)
    if m:
        return re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip()[:90]
    return ""


def desc_of(path: Path) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', txt, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:160]
    return ""


def build() -> dict:
    surfaces = []
    for f in sorted(SITE.glob("*.html")):
        name = f.stem
        if name in ("404",):
            continue
        title = title_of(f)
        desc = desc_of(f)
        cat = classify(name, title + " " + desc)
        surfaces.append({
            "file": f.name,
            "name": name,
            "title": title or name,
            "desc": desc,
            "category": cat,
            "size_kb": round(f.stat().st_size / 1024, 1),
        })

    # subdirectory surfaces (aipodcast_me, etc.)
    for d in sorted(p for p in SITE.iterdir() if p.is_dir() and not p.name.startswith(".")):
        idx = d / "index.html"
        if idx.exists():
            surfaces.append({
                "file": f"{d.name}/index.html",
                "name": d.name,
                "title": title_of(idx) or d.name,
                "desc": desc_of(idx),
                "category": classify(d.name, title_of(idx)),
                "size_kb": round(idx.stat().st_size / 1024, 1),
            })

    by_cat: dict = {}
    for s in surfaces:
        by_cat.setdefault(s["category"], []).append(s)

    # order categories by the ontology order, then OTHER
    order = [c for c, _ in ONTOLOGY] + ["OTHER"]
    categories = []
    for c in order:
        if c in by_cat:
            meta = CATEGORY_META.get(c, CATEGORY_META["OTHER"])
            categories.append({
                "id": c, "glyph": meta["glyph"], "role": meta["role"],
                "count": len(by_cat[c]),
                "surfaces": sorted(by_cat[c], key=lambda x: x["name"]),
            })

    return {
        "brain": "neuromitosis.com",
        "kind": "site brain index · agentic engineering ontology",
        "generated": "2026-10-05",
        "total_surfaces": len(surfaces),
        "total_categories": len(categories),
        "categories": categories,
    }


if __name__ == "__main__":
    b = build()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else SITE / "brain.json"
    out.write_text(json.dumps(b, indent=2, ensure_ascii=False), encoding="utf-8")
    (out.parent / "brain.js").write_text(
        "// generated by brain_index.py — the site brain, do not hand-edit\n"
        "const BRAIN = " + json.dumps(b, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in b.items() if k != "categories"}, indent=2))
    print(f"\nwrote {out} + brain.js\n")
    for c in b["categories"]:
        print(f"  {c['glyph']} {c['id']:10} {c['count']:>3}  {c['role'][:56]}")
