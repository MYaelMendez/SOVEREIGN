#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_site_index.py — generate + inject the SITE INDEX and TOOL CHAINS panels
into C:\\æ\\github-pages\\index.html.

Deterministic: walks the surface tree, assigns every .html to exactly one
namespace (first-match), verifies every curated link exists on disk, and only
then injects. Idempotent (skips if the marker is already present).

Usage:
  python C:/æ/scripts/gen_site_index.py            # inject
  python C:/æ/scripts/gen_site_index.py --check    # audit only, no write
"""
import os
import sys
import html as _html

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = r"C:\æ\github-pages"
INDEX = os.path.join(ROOT, "index.html")
MARK = "<!-- \u2550\u2550\u2550 SITE INDEX \u2550\u2550\u2550 -->"
ANCHOR = '  <div class="logshell" id="log">'
NL = "\r\n"

# (title, accent, keywords[], curated links[(path,label)])
CATS = [
    ("LANGUAGE \u00b7 COD\u00c6 / MECH", "rgba(212,175,55,.35)", ["mech"],
     [("mech-os.html", "MECH OS"), ("mech-3d-os.html", "3D OS"),
      ("mechdown.html", "MECHDOWN"), ("mech-education-hub.html", "EDUCATION"),
      ("mech-integration-hub.html", "INTEGRATION"), ("mech-agent-orchestrator.html", "ORCHESTRATOR"),
      ("mech-map-native.html", "MAP NATIVE")]),

    ("MEDIA \u00b7 VID\u00c6O", "rgba(0,234,255,.35)",
     ["video", "videolab", "draw", "factory", "storyboard", "corpus", "multimedia", "aertx"],
     [("video-corpus.html", "VIDEO CORPUS"), ("videolab.html", "VIDEOLAB"),
      ("final-video.html", "FINAL VIDEO"), ("draw-video.html", "DRAW"),
      ("factory.html", "FACTORY"), ("video-vision.mp4", "VIDEO VISION")]),

    ("AEE \u00b7 SILICON", "rgba(0,255,157,.35)", ["cuda", "aee", "ice40", "rtl", "chip", "silicon"],
     [("cuda_IDE_RTX.html", "CUDA IDE"), ("cuda-blueprint.html", "BLUEPRINT"),
      ("cuda-vlc.html", "CUDA\u00b7VLC"), ("glocal-cuda-mesh.html", "CUDA MESH")]),

    ("MESH \u00b7 RUNTIME", "rgba(140,114,255,.35)",
     ["mesh", "fleet", "glocal", "sovereignty", "capability", "constellation", "holomesh"],
     [("mesh-agenti.html", "MESH AGENTI"), ("fleet.html", "FLEET"), ("the-mesh.html", "THE MESH"),
      ("parallel-sovereignty.html", "PARALLEL"), ("capability-mesh.html", "CAPABILITY"),
      ("constellation.html", "CONSTELLATION")]),

    ("STORE \u00b7 COMMERCE", "rgba(212,175,55,.35)",
     ["llm-store", "ae-store", "domain", "rails", "commerce", "store"],
     [("llm-store.html", "LLM STORE"), ("llm-store-4d-atlas.html", "4D ATLAS"),
      ("llm-store-dna-qr.html", "DNA QR"), ("ae-store-digital-twin.html", "DIGITAL TWIN"),
      ("domain-empire.html", "DOMAIN EMPIRE"), ("rails.html", "RAILS")]),

    ("SECRETS \u00b7 PRIVATE", "rgba(212,175,55,.35)", ["vault", "secret", "privateclient", "private-client"],
     [("privateclient/vault.html", "V\u00c6ULT"), ("privateclient/vault-layers.html", "LAYERS"),
      ("privateclient/secret-source-bridge.html", "BRIDGE"), ("privateclient/terminal.html", "TERMINAL"),
      ("privateclient/compute.html", "COMPUTE"), ("privateclient/omnibox.html", "OMNIBOX")]),

    ("QR \u00b7 VERIFICATION", "rgba(0,255,157,.35)", ["qr", "aeqr", "measurement", "cri-"],
     [("aeqr.html", "\u00c6QR"), ("qr-as-skill.html", "QR AS SKILL"),
      ("measurement-index.html", "MEASUREMENT"), ("cri-index.html", "CRI INDEX")]),

    ("THEOLOGY \u00b7 TEOLOGIA.AI", "rgba(212,175,55,.35)", ["teologia", "hauge"],
     [("teologia/index.html", "HUB"), ("teologia/calendario.html", "CALENDARIO"),
      ("teologia/rtx-accelerator.html", "RTX ACCELERATOR"), ("teologia/qr/index.html", "QR FLEET")]),

    ("PROTOCOL \u00b7 INTERFACE", "rgba(0,234,255,.35)",
     ["aaa", "a2ui", "command", "cli", "codex", "googlemcp", "mcpgpt", "webmcp", "webllm",
      "hermes-native", "sovaereign", "aeos", "trinity", "yael", "yarn"],
     [("command-map.html", "COMMAND MAP"), ("aaa-protocol.html", "AAA PROTOCOL"),
      ("webmcp.html", "WEBMCP"), ("webllm.html", "WEBLLM"),
      ("mcpgpt-chat.html", "MCPGPT"), ("hermes-native-demo.html", "HERMES NATIVE")]),

    ("INTERNET OF AGENTS", "rgba(140,114,255,.35)", ["internetofagents"],
     [("internetofagents.html", "IoA"), ("internetofagents-demo.html", "DEMO"),
      ("internetofagents-v2.html", "V2"), ("internetofagents-render.html", "RENDER")]),

    ("ONTOLOGY \u00b7 KNOWLEDGE", "rgba(0,255,157,.35)",
     ["ontology", "neuromitosis", "molt", "zeitgeist", "motlbook", "aggregate", "integration", "brain", "cortex"],
     [("any-ontology-master.html", "ONTOLOGY"), ("neuromitosis.html", "NEUROMITOSIS"),
      ("molt-earth-ultimate-fractal.html", "MOLT EARTH"), ("zeitgeist-4d.html", "ZEITGEIST 4D"),
      ("aggregate.html", "AGGREGATE"), ("integration.html", "INTEGRATION")]),

    ("EDUCATION \u00b7 SKILLS", "rgba(212,175,55,.35)",
     ["skill-guide", "school", "rust-", "nano-", "cri-school", "aea-index", "ael-tv", "cri-teleprompter"],
     [("skill-guide/index.html", "SKILL GUIDE"), ("skill-guide/skill-graph.html", "SKILL GRAPH"),
      ("cri-school-of-hermes.html", "SCHOOL OF HERMES"), ("school-of-hermes-fleet.html", "FLEET"),
      ("rust-territory-tables.html", "RUST TABLES"), ("cri-teleprompter.html", "TELEPROMPTER")]),

    ("PHYSICAL \u00b7 REACHY", "rgba(0,234,255,.35)", ["reachy"],
     [("reachy-clerk.html", "CLERK"), ("reachy-emulator.html", "EMULATOR"),
      ("reachy-face.html", "FACE"), ("reachy-video.html", "VIDEO")]),

    ("OPERATOR \u00b7 META", "rgba(140,114,255,.35)", [],
     [("sovereign-state.html", "SOVEREIGN STATE"), ("keeper.html", "KEEPER"),
      ("droplet.html", "DROPLET"), ("agentic.html", "#STARTABUSINESS"),
      ("demo.html", "DEMO"), ("private-client.html", "PRIVATE CLIENT")]),
]

TOOLCHAINS = [
    ("LANGUAGE", "cod\u00e6 (.mec) \u2192 mechc (Rust) \u2192 WASM \u2192 \u00e6:// runtime"),
    ("VIDEO", "Three.js scene \u2192 __renderFrame(i,total) \u2192 CDP frames \u2192 NVENC \u2192 MP4 \u2192 SupervisorVideo \u2192 QR \u2192 github.io"),
    ("AEE", "SPEC \u2192 RTL (Verilog) \u2192 SIM (iverilog) \u2192 SYNTH (yosys) \u2192 P&R (nextpnr) \u2192 GDS \u2192 FAB \u2192 TEST"),
    ("SECRETS", "browser surface \u2192 secret-source-bridge \u2192 local custody (Victus) \u2192 v\u00e6ult vault \u2192 QR air-gap"),
    ("VERIFY", "artifact \u2192 SHA-256 \u2192 receipt \u2192 hash chain \u2192 k\u00e6nb\u00e6n genesis \u2192 QR badge \u2192 scannable proof"),
    ("CRON", "push content \u2192 webmaster cron \u2192 audit + QR verify + video gate + freshness \u2192 receipt \u2192 fresh"),
    ("MESH", "conductor (teknium) \u2192 MCP\u00b2 broker (droplet) \u2192 reverse tunnel \u2192 Victus leaf \u2192 gpu-mcp \u2192 RTX 3050"),
]


def all_html():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d != ".git"]
        for f in fn:
            if f.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT).replace("\\", "/"))
    return sorted(out)


def assign(files):
    counts = {}
    for f in files:
        low = f.lower()
        for title, _accent, kws, _links in CATS:
            if kws and any(k in low for k in kws):
                counts[title] = counts.get(title, 0) + 1
                break
        else:
            counts["OPERATOR \u00b7 META"] = counts.get("OPERATOR \u00b7 META", 0) + 1
    return counts


def build(counts, total):
    L = []
    L.append("  " + MARK)
    L.append('  <div class="panel panel-primary">')
    L.append('    <div class="panel-head"><span>\u25c8 SITE INDEX \u00b7 %d SURFACES</span>'
             '<span class="tag">%d NAMESPACES</span></div>' % (total, len(CATS)))
    L.append('    <div class="grid-4">')
    for title, accent, _kws, links in CATS:
        n = counts.get(title, 0)
        ok = [(p, lb) for p, lb in links if os.path.exists(os.path.join(ROOT, p))]
        inner = " ".join('<a href="./%s">%s</a>' % (p, _html.escape(lb)) for p, lb in ok)
        L.append('      <div class="card" style="border-color:%s">' % accent)
        L.append('        <div class="name">%s <span class="badge">%d</span></div>' % (title, n))
        L.append('        <div class="row">%s</div>' % inner)
        L.append('      </div>')
    L.append('    </div>')
    extras = []
    for p, lb in [("skill-guide/", "skill guide \u2192"), ("surface-manifest.json", "surface manifest \u2192"),
                  ("sitemap.xml", "sitemap \u2192"), ("manifest.json", "media catalog \u2192")]:
        if os.path.exists(os.path.join(ROOT, p)):
            extras.append('<a href="./%s" class="badge">%s</a>' % (p, lb))
    L.append('    <div class="row" style="margin-top:12px;display:flex;gap:8px">%s</div>' % " ".join(extras))
    L.append('  </div>')
    L.append('')
    L.append('  <!-- \u2550\u2550\u2550 TOOL CHAINS \u2550\u2550\u2550 -->')
    L.append('  <div class="panel">')
    L.append('    <div class="panel-head"><span>\u25c8 TOOL CHAINS</span><span class="tag">COMPOSITION</span></div>')
    L.append('    <div class="logshell" style="font-size:10px">')
    for name, flow in TOOLCHAINS:
        L.append("%-9s %s" % (name, flow))
    L.append('    </div>')
    L.append('    <div class="row" style="margin-top:12px;display:flex;gap:8px">')
    L.append('      <a href="./command-map.html" class="badge">command map \u2192</a>')
    L.append('      <a href="./capability-mesh.html" class="badge">capability mesh \u2192</a>')
    L.append('    </div>')
    L.append('  </div>')
    return NL.join(L)


def audit_links(src):
    import re
    broken = []
    for m in re.finditer(r'href="(\./[^"#?]+)"', src):
        rel = m.group(1)[2:]
        if not os.path.exists(os.path.join(ROOT, rel)):
            broken.append(rel)
    return sorted(set(broken))


def write_sitemap():
    """Regenerate sitemap.xml from the filesystem (never hand-maintained)."""
    import time
    base = "https://myaelmendez.github.io"
    skip = {"404.html"}
    pages = [f for f in all_html() if f not in skip]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for f in pages:
        loc = base + "/" + f
        if f == "index.html":
            loc = base + "/"
        try:
            ts = time.strftime("%Y-%m-%d", time.gmtime(os.path.getmtime(os.path.join(ROOT, f))))
        except OSError:
            ts = time.strftime("%Y-%m-%d")
        pri = "1.0" if f == "index.html" else ("0.8" if "/" not in f else "0.6")
        freq = "weekly" if f == "index.html" else "monthly"
        lines.append("  <url>")
        lines.append("    <loc>%s</loc>" % loc)
        lines.append("    <lastmod>%s</lastmod>" % ts)
        lines.append("    <changefreq>%s</changefreq>" % freq)
        lines.append("    <priority>%s</priority>" % pri)
        lines.append("  </url>")
    lines.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="").write(NL.join(lines))
    return len(pages)


FOOT_ANCHOR = '<a href="./skill-guide/">skills</a>'


def update_footer():
    src = open(INDEX, "r", encoding="utf-8", newline="").read()
    if FOOT_ANCHOR not in src:
        return "anchor missing"
    add = FOOT_ANCHOR + NL + \
          '    <a href="./verify.html">verify://</a>' + NL + \
          '    <a href="./kaenbaen/">k\u00e6nb\u00e6n</a>'
    if 'href="./verify.html"' in src:
        return "already present"
    src = src.replace(FOOT_ANCHOR, add, 1)
    open(INDEX, "w", encoding="utf-8", newline="").write(src)
    return "added verify:// + kaenbaen to footer"


def main():
    check = "--check" in sys.argv
    files = all_html()
    counts = assign(files)
    frag = build(counts, len(files))

    src = open(INDEX, "r", encoding="utf-8", newline="").read()
    print("index.html      : %d bytes" % len(src))
    print("surfaces on disk: %d" % len(files))
    print("has QR badge    : %s" % ("qrserver.com" in src or "qr-badge" in src.lower()))
    broken = audit_links(src)
    print("broken links    : %s" % (broken if broken else "none"))
    print("marker present  : %s" % (MARK in src))
    print()
    for title, _a, _k, _l in CATS:
        print("  %-28s %d" % (title, counts.get(title, 0)))
    print("  %-28s %d" % ("TOTAL", sum(counts.values())))

    if check:
        return
    if MARK in src:
        print("\n[skip] already injected")
    elif ANCHOR not in src:
        print("\n[ERROR] anchor not found: %r" % ANCHOR)
        sys.exit(1)
    else:
        out = src.replace(ANCHOR, frag + NL + ANCHOR, 1)
        open(INDEX, "w", encoding="utf-8", newline="").write(out)
        print("\n[ok] injected %d bytes -> index.html now %d bytes" % (len(frag), len(out)))

    print("[ok] sitemap.xml  : %d pages" % write_sitemap())
    print("[ok] footer       : %s" % update_footer())


if __name__ == "__main__":
    main()
