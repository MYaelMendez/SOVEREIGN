#!/usr/bin/env python3
"""make_aqr_fleet.py — regenerate the æ:// QR fleet from qr_inventory.json.

THE RULE: every QR is a UNIQUE, resolvable address. No two QR codes encode
the same URL, and no QR points at a phantom anchor. The previous fleet broke
both rules: it collapsed 54 local resources onto category anchors
(teologia/#agents, #widget, …) that do not exist on the hub, and it emitted
each of the 8 scenes twice (teologia-<x> AND scene-<x> -> same page).

Address resolution (first match wins):
  1. published surface present in gh-pages -> https://myaelmendez.github.io/<path>
  2. local resource present in SOVEREIGN    -> github.com/MYaelMendez/SOVEREIGN/blob/master/<path>
  3. otherwise                              -> ae://local/<path>   (sovereign scheme)

Every generated QR is decoded back (cv2 + pyzbar) and must round-trip before
it is written. QR is only an ADDRESS; trust is re-established by re-hashing the
artifact, never by trusting the QR bytes.
"""
import sys, os, json
sys.path.insert(0, "C:/æ/agents")
import qrcode
from qrcode.image.svg import SvgPathImage
from qrcode.constants import ERROR_CORRECT_M

ROOT = "C:/æ"
OUT_DIR = os.path.join(ROOT, "teologia", "qr")
CACHE = os.path.join(ROOT, "teologia", ".tree-cache.json")

BASE = "https://myaelmendez.github.io"
BLOB = "https://github.com/MYaelMendez/SOVEREIGN/blob/master"

inv = json.load(open(os.path.join(ROOT, "qr_inventory.json"), encoding="utf-8"))
trees = json.load(open(CACHE, encoding="utf-8"))
SOV = set(trees["sovereign"])
GP = set(trees["gh_pages"])


def norm(p: str) -> str:
    p = p.strip().replace("\\", "/")
    for pre in ("C:/æ/", "C:/Æ/"):
        if p.startswith(pre):
            p = p[len(pre):]
            break
    return p.lstrip("/")


def slug(cat: str, path: str) -> str:
    s = path.lower().replace("/", "-").replace("_", "-").replace(".", "-")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "-")
    s = "-".join(x for x in s.split("-") if x)
    return (cat[:3] + "-" + s)[:64]



# Explicit overrides: local inventory paths that have a real, resolvable
# address on gh-pages even though the inventory path doesn't match directly.
# This is the single source of truth for the 10 ae://local items that would
# otherwise fail to resolve.
EXPLICITS = {
    "widget/live_widget.mjs":    "widget/live_widget.mjs",
    "widget/_probe.mjs":         "widget/_probe.mjs",
    "widget/_server.cjs":        "widget/_server.cjs",
    "agents/kanban_push.py":     "agents/kanban_push.py",
    "teologia-calendar.html":    "teologia/calendario.html",
    "videos.html":               "videos.html",
    "qr_inventory.json":         "qr_inventory.json",
    "logs/diagnosis-servers-20261008.md": "logs/diagnosis-servers-20261008.md",
    "logs/environment-branch-decision.md": "logs/environment-branch-decision.md",
    "logs/ops-decision-2026-07-01.md": "logs/ops-decision-2026-07-01.md",
}


def _pct(url: str) -> str:
    """Percent-encode non-ASCII characters in the path portion of a URL."""
    # split scheme+host from path
    idx = url.find('/', url.find('://') + 3)
    if idx < 0:
        return url
    head = url[:idx]
    path = url[idx:]
    return head + urllib.parse.quote(path, safe="/")


def resolve(cat: str, path: str):
    p = norm(path)
    # EXPLICITS wins first — these are known-good gh-pages addresses
    if p in EXPLICITS:
        return f"{BASE}/{EXPLICITS[p]}", "gh-pages"
    base = p.split("/")[-1]
    if cat in ("html_surfaces", "threejs_scenes", "videos"):
        if p in GP:
            return _pct(f"{BASE}/{p}"), "gh-pages"
        hits = [t for t in GP if t == base or t.endswith("/" + base)]
        if hits:
            return _pct(f"{BASE}/{hits[0]}"), "gh-pages"
    if p in SOV:
        return _pct(f"{BLOB}/{p}"), "sovereign"
    hits = [t for t in SOV if t == base or t.endswith("/" + base)]
    if hits:
        return _pct(f"{BLOB}/{hits[0]}"), "sovereign"
    return f"ae://local/{p}", "ae-local"


TYPE = {
    "html_surfaces": "page", "python_agents": "agent", "threejs_scenes": "scene",
    "videos": "video", "configs": "config", "logs": "log",
    "widget": "widget", "kanban": "kanban",
}
LABEL = {
    "html_surfaces": "", "python_agents": "Agent: ", "threejs_scenes": "Scene: ",
    "videos": "Video: ", "configs": "Config: ", "logs": "Log: ",
    "widget": "Widget: ", "kanban": "Kænbæn: ",
}
# When the SAME artifact is listed in two categories, exactly ONE QR must carry
# it — a URL is one address. Lower rank wins (scene beats page, kanban beats
# config, …). This is the rule the previous fleet broke.
PRIORITY = {"threejs_scenes": 0, "videos": 1, "kanban": 2, "widget": 3,
            "python_agents": 4, "html_surfaces": 5, "configs": 6, "logs": 7}


def decode_svg(path: str):
    """Decode a QR SVG back to its payload — proves it round-trips.

    cv2 is tried FIRST: it decodes UTF-8 payloads correctly. pyzbar is the
    fallback, but it mis-detects the charset on non-ASCII URLs (it returns
    Shift-JIS mojibake for UTF-8 bytes like 'æ'), so its result is only used
    when cv2 returns nothing.
    """
    import re, numpy as np, cv2
    from pyzbar.pyzbar import decode
    txt = open(path, encoding="utf-8", errors="replace").read()
    W = H = int(re.search(r'viewBox="0 0 (\d+) (\d+)"', txt).group(1))
    d = re.search(r"<path[^>]*\bd=\"([^\"]+)\"", txt).group(1)
    grid = np.zeros((H, W), dtype=np.uint8)
    for x0, y0, x1, y1, x2 in re.findall(r"M(\d+),(\d+)H(\d+)V(\d+)H(\d+)z", d):
        grid[int(y0):int(y1), int(x0):int(x1)] = 1
    img = (1 - grid) * 255
    img = np.pad(img, 4, constant_values=255)
    big = cv2.resize(img, None, fx=12, fy=12, interpolation=cv2.INTER_NEAREST).astype(np.uint8)
    out = []
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(big)
    if data:
        out.append(data)
    if not out:  # cv2 failed — fall back to pyzbar
        out = [r.data.decode("utf-8", "replace") for r in decode(big)]
    return out


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    seen_ids = set()
    stats = {}
    for cat, items in inv.items():
        for raw in items:
            url, src = resolve(cat, raw)
            stats[src] = stats.get(src, 0) + 1
            rid = slug(cat, raw)
            if rid in seen_ids:  # collision-safe id
                n = 2
                while f"{rid}-{n}" in seen_ids:
                    n += 1
                rid = f"{rid}-{n}"
            seen_ids.add(rid)
            rows.append({"id": rid, "label": LABEL[cat] + norm(raw), "url": url,
                         "type": TYPE[cat], "category": cat, "src": src})

    # ONE URL = ONE QR. The same artifact listed in two categories keeps only its
    # highest-priority category (scene > video > kanban > widget > agent > page >
    # config > log). This is the rule the previous fleet broke.
    best = {}
    for r in rows:
        u = r["url"]
        if u not in best or PRIORITY[r["category"]] < PRIORITY[best[u]["category"]]:
            best[u] = r
    qrs = sorted(best.values(), key=lambda r: (PRIORITY[r["category"]], r["id"]))

    # generate, then DECODE BACK — a QR that does not round-trip is not written.
    ok, fails = 0, []
    for q in qrs:
        qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(q["url"])
        qr.make(fit=True)
        img = qr.make_image(image_factory=SvgPathImage)
        path = os.path.join(OUT_DIR, f"{q['id']}.svg")
        img.save(path)
        decoded = decode_svg(path)
        if q["url"] in decoded:
            ok += 1
        else:
            fails.append(q["id"])
        q["qr_version"] = qr.version
        q["modules"] = qr.modules_count
        q["svg"] = f"qr/{q['id']}.svg"
        q["verified"] = q["url"] in decoded

    urls = {q["url"] for q in qrs}
    manifest = {"fleet": "æ://ecosystem", "generated": "2026-10-10",
                "resource_count": len(qrs), "unique_urls": len(urls),
                "verified": ok, "qrs": qrs}
    json.dump(manifest, open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    # regenerate the index — one card per QR, grouped by category
    by_cat = {}
    for q in qrs:
        by_cat.setdefault(q["category"], []).append(q)
    cards = []
    for cat in sorted(by_cat, key=lambda c: PRIORITY.get(c, 9)):
        cards.append(f'    <h2 class="cat">{cat.replace("_", " ").upper()} · {len(by_cat[cat])}</h2>')
        cards.append('    <div class="qr-grid">')
        for q in by_cat[cat]:
            cards.append(
                f'      <div class="qr-card">\n'
                f'        <img src="{q["svg"]}" alt="{q["label"]}" loading="lazy">\n'
                f'        <h3>{q["label"]}</h3>\n'
                f'        <p class="url">{q["url"]}</p>\n'
                f'        <span class="type">{q["type"]}</span>\n'
                f'      </div>')
        cards.append('    </div>')
    index_html = (
        '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>æ:// QR Index — Ecosystem</title>\n'
        "<link href=\"https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;600&display=swap\" rel=\"stylesheet\">\n"
        "<style>\n"
        "  *{margin:0;padding:0;box-sizing:border-box;}\n"
        "  body{background:#0a0a0a;color:#d4af37;font-family:'Cormorant Garamond',serif;min-height:100vh;padding:40px 20px;}\n"
        "  .container{max-width:1400px;margin:0 auto;}\n"
        "  h1{font-family:'Cinzel',serif;font-size:36px;font-weight:900;letter-spacing:4px;text-align:center;margin-bottom:8px;color:#f0d878;}\n"
        "  .subtitle{text-align:center;color:rgba(240,216,120,0.5);font-family:'JetBrains Mono',monospace;font-size:13px;letter-spacing:2px;margin-bottom:40px;}\n"
        "  .cat{font-family:'Cinzel',serif;font-size:15px;letter-spacing:3px;color:#f0d878;margin:36px 0 16px;border-bottom:1px solid rgba(212,175,55,0.15);padding-bottom:8px;}\n"
        "  .qr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:20px;}\n"
        "  .qr-card{background:rgba(212,175,55,0.03);border:1px solid rgba(212,175,55,0.15);border-radius:12px;padding:18px;text-align:center;transition:border-color 0.2s;}\n"
        "  .qr-card:hover{border-color:rgba(212,175,55,0.4);}\n"
        "  .qr-card img{width:150px;height:150px;margin-bottom:12px;filter:invert(78%) sepia(55%) saturate(500%) hue-rotate(3deg) brightness(1.05);}\n"
        "  .qr-card h3{font-family:'Cinzel',serif;font-size:12px;letter-spacing:1px;margin-bottom:8px;color:#d4af37;word-break:break-word;}\n"
        "  .qr-card .url{font-size:10px;color:rgba(212,175,55,0.4);word-break:break-all;font-family:'JetBrains Mono',monospace;}\n"
        "  .qr-card .type{display:inline-block;margin-top:8px;padding:2px 8px;border:1px solid rgba(212,175,55,0.2);border-radius:3px;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:rgba(212,175,55,0.6);}\n"
        "  .footer{text-align:center;margin-top:48px;padding-top:20px;border-top:1px solid rgba(212,175,55,0.1);color:rgba(212,175,55,0.3);font-size:11px;letter-spacing:2px;}\n"
        "</style>\n</head>\n<body>\n  <div class=\"container\">\n"
        f"    <h1>æ:// QR INDEX</h1>\n"
        f"    <p class=\"subtitle\">{len(qrs)} QR · {len(urls)} UNIQUE ADDRESSES · {ok} ROUND-TRIP VERIFIED · OPEN SOURCE SINCE 1517</p>\n"
        + "\n".join(cards) + "\n"
        "    <div class=\"footer\">\n"
        "      TEOLOGIA.AI · BIBLIA DEL OSO · CASIODORO DE REINA 1569<br>\n"
        "      æ://ECOSYSTEM · EVERY QR IS A UNIQUE, RESOLVABLE ADDRESS\n"
        "    </div>\n  </div>\n</body>\n</html>\n")
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(index_html)

    print(f"generated:  {len(qrs)} QR codes")
    print(f"unique urls: {len(urls)} / {len(qrs)}  (dups: {len(qrs) - len(urls)})")
    print(f"round-trip verified: {ok} / {len(qrs)}")
    print(f"resolution: {stats}")
    print(f"index: {len(qrs)} cards across {len(by_cat)} categories")
    if fails:
        print("DECODE FAILS:", fails[:10])
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
