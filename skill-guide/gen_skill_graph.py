#!/usr/bin/env python3
"""gen_skill_graph.py — regenerate the sovereign skill graph from the live library.

The library grows organically: a new SKILL.md -> a new node + edges. This script
reads ~/.hermes/skills/ and writes graph.json + sovereign-graph.json, so the
graph is never a stale snapshot.

Edge signals (semantic weight):
  related_skills frontmatter  -> w3  (declared, intentional)
  shared tags                 -> w2  (semantic kin)
  prose backtick mention      -> w1  (weak)

Run:  python gen_skill_graph.py
"""
from __future__ import annotations

import colorsys
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else r"C:\Users\yaelm\AppData\Local\hermes\skills")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else r"C:\æ\skill-guide")

ALIAS = {
    "startabusiness": "agentic-entrepreneurship", "gguf": "gguf-quantization",
    "browser": "computer-use", "hermes-video": "hyperframes", "vllm": "tensorrt-llm",
    "mlops/cuda": "cuda", "concept-diagrams": "architecture-diagram",
    "trl-fine-tuning": "fine-tuning-with-trl", "audiocraft": "audiocraft-audio-generation",
    "rss-feeds": "blogwatcher", "reddit-reading": "blogwatcher",
}
SOV_TAGS = {"sovereign", "ae", "æ", "pc-inference", "glocal"}
FLEET = {"claude-code", "codex", "opencode", "agentic-interpreter"}


def _fm(txt: str) -> str:
    if not txt.startswith("---"):
        return ""
    m = re.search(r"\n---\s*\n", txt[3:])
    return txt[3:m.start() + 3] if m else ""


def _field(txt: str, f: str) -> str:
    m = re.search(rf"^{f}:\s*(.+)$", txt, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def _list(txt: str, f: str) -> list[str]:
    m = re.search(rf"^{f}:\s*\[(.*?)\]", txt, re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def _related(fm: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"related_skills:\s*\[(.*?)\]", fm, re.S):
        out |= {x.strip().strip('"').strip("'") for x in m.group(1).split(",") if x.strip()}
    for m in re.finditer(r"related_skills:\s*\n((?:\s*-\s*.+\n?)+)", fm):
        out |= {re.sub(r"^\s*-\s*", "", l).strip().strip('"').strip("'")
                for l in m.group(1).splitlines() if l.strip()}
    return out


def build(root: pathlib.Path) -> dict:
    nodes: dict[str, dict] = {}
    texts: dict[str, str] = {}
    for sk in root.rglob("SKILL.md"):
        if ".archive" in sk.parts:
            continue
        txt = sk.read_text(encoding="utf-8", errors="replace")
        rel = sk.parent.relative_to(root)
        name = _field(txt, "name") or rel.parts[-1]
        nodes[name] = {
            "dir": str(rel).replace("\\", "/"),
            "cat": "single" if len(rel.parts) == 1 else rel.parts[0],
            "tags": _list(txt, "tags"),
            "desc": _field(txt, "description"),
            "lines": txt.count("\n") + 1,
        }
        texts[name] = txt

    names = set(nodes)
    edges: dict[tuple, int] = defaultdict(int)
    kinds: dict[tuple, set] = defaultdict(set)

    for n, txt in texts.items():
        fm = _fm(txt)
        body = txt[len(fm) + 3:] if fm else txt
        for r in _related(fm):
            r = ALIAS.get(r, r)
            if r in names and r != n:
                e = tuple(sorted((n, r)))
                edges[e] += 3
                kinds[e].add("declared")
        for m in re.finditer(r"`([a-z0-9][a-z0-9\-_]{2,})`", body):
            t = m.group(1)
            if t in names and t != n:
                e = tuple(sorted((n, t)))
                edges[e] += 1
                kinds[e].add("mention")

    tagmap: dict[str, list[str]] = defaultdict(list)
    for n, meta in nodes.items():
        for t in meta["tags"]:
            tagmap[t.lower()].append(n)
    for ns in tagmap.values():
        if 1 < len(ns) <= 5:
            for i in range(len(ns)):
                for j in range(i + 1, len(ns)):
                    e = tuple(sorted((ns[i], ns[j])))
                    if "declared" not in kinds[e]:
                        edges[e] += 2
                        kinds[e].add("tag")

    deg = Counter()
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    mx = max(deg.values()) if deg else 1

    groups = sorted({m["cat"] for m in nodes.values()})
    base_hue = {"sovereign": 45, "hermes": 52, "software-development": 190,
                "autonomous-ai-agents": 160, "business": 20, "creative": 280, "mlops": 120}
    hues = {g: base_hue.get(g, (i * 47) % 360) for i, g in enumerate(groups)}

    def col(g: str) -> str:
        r, gg, b = colorsys.hls_to_rgb(hues.get(g, 45) / 360, 0.58, 0.70)
        return "#%02x%02x%02x" % (int(r * 255), int(gg * 255), int(b * 255))

    sov = {n for n, m in nodes.items()
           if m["cat"] == "sovereign" or any(t.lower() in SOV_TAGS for t in m["tags"])}

    payload = {
        "nodes": [{
            "id": n, "g": m["cat"], "col": col(m["cat"]),
            "deg": deg[n], "sz": round(3 + (deg[n] / mx) ** 0.6 * 10, 2),
            "sov": n in sov, "fleet": n in FLEET, "ln": m["lines"],
            "tags": m["tags"][:6],
        } for n, m in nodes.items()],
        "edges": [{"s": a, "t": b, "w": w, "k": sorted(kinds[(a, b)])}
                  for (a, b), w in edges.items()],
        "groups": [{"key": g, "label": g, "col": col(g),
                    "count": sum(1 for m in nodes.values() if m["cat"] == g)} for g in groups],
        "stats": {"nodes": len(nodes), "edges": len(edges),
                  "declared": sum(1 for v in kinds.values() if "declared" in v),
                  "tag": sum(1 for v in kinds.values() if "tag" in v),
                  "mention": sum(1 for v in kinds.values() if "mention" in v),
                  "sov": len(sov), "fleet": len(FLEET & names)},
    }
    return payload


def main() -> None:
    payload = build(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "graph.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    # Emit the widget too: inject the payload into the template so the surface
    # and the data can never drift apart. Falls back to a "regenerate" nudge if
    # the template is absent.
    tpl = OUT / "skill-graph.template.html"
    if tpl.exists():
        html = tpl.read_text(encoding="utf-8").replace(
            "const G = __DATA__;", "const G = " + json.dumps(payload, ensure_ascii=False) + ";")
        (OUT / "skill-graph.html").write_text(html, encoding="utf-8")
        widget = f"widget -> skill-graph.html ({len(html):,} chars)"
    else:
        widget = "template missing; widget not regenerated"

    s = payload["stats"]
    print(f"skill-graph: {s['nodes']} nodes, {s['edges']} edges, {len(payload['groups'])} groups")
    print(f"  declared={s['declared']} tag={s['tag']} mention={s['mention']} "
          f"sovereign={s['sov']} fleet={s['fleet']}")
    print(f"  {widget}")


if __name__ == "__main__":
    main()
