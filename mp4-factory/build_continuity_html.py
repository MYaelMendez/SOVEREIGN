"""
build_continuity_html.py — generate continuity.html from AE-CONTINUITY.md.

Deterministic: parses the numbered sections and their proved/broke/change
verdicts from the markdown, emits a single self-contained gold-on-void index.
No runtime fetch, no drift: regenerate after every edit to the record.

Reads:  C:/æ/github-pages/AE-CONTINUITY.md
Writes: C:/æ/github-pages/continuity.html
"""
from __future__ import annotations

import html
import re
from pathlib import Path

SRC = Path("C:/æ/github-pages/AE-CONTINUITY.md")
OUT = Path("C:/æ/github-pages/continuity.html")
ACTIVITY = Path("C:/æ/github-pages/github-activity.json")

SEC = re.compile(r"^## (.+?)\s*$", re.M)
VERDICT = re.compile(r"\*\*(proved|broke|change)\*\*\s*[-–—]\s*(.*?)(?=\n\*\*(?:proved|broke|change)\*\*|\Z)", re.S)


def parse():
    text = SRC.read_text(encoding="utf-8")
    matches = list(SEC.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        raw = m.group(1).strip()
        nm = re.match(r"^(\d+)\.\s+(.*)$", raw)
        if nm:
            num, title = int(nm.group(1)), nm.group(2).strip()
        else:
            num, title = None, raw
        date = ""
        dm = re.search(r"\((\d{4}-\d{2}-\d{2})", title)
        if dm:
            date = dm.group(1)
            title = title[:dm.start()].strip()
        v = {k: " ".join(val.split()) for k, val in VERDICT.findall(body)}
        markers = len(re.findall(r"\*\*(?:proved|broke|change)\*\*", body, re.I))
        sections.append({"num": num, "title": title, "date": date,
                         "markers": markers,
                         "parity": "MISSING" if markers and not any(v.values()) else "ok",
                         "proved": v.get("proved", ""), "broke": v.get("broke", ""),
                         "change": v.get("change", "")})
    return sections, len(text.splitlines())


def activity_block():
    """Bake the derived GitHub snapshot into the page as static, honest HTML."""
    if not ACTIVITY.exists():
        return ("<div class='act-empty'>GitHub activity not synced — "
                "run <code>sync_github_activity.py</code> then regenerate.</div>")
    import json as _json
    d = _json.loads(ACTIVITY.read_text(encoding="utf-8"))
    types = "".join(
        f"<span class='tp {k.lower().replace('event','')}'>{esc(k.replace('Event',''))} <b>{v}</b></span>"
        for k, v in d.get("by_type", {}).items())
    repos = "".join(
        f"<span class='rp'>{esc(k)} <b>{v}</b></span>"
        for k, v in list(d.get("by_repo", {}).items())[:6])
    tl = "".join(
        f"<li><span class='dt'>{esc(str(e.get('created_at',''))[:16].replace('T',' '))}</span> "
        f"<span class='ev'>{esc(str(e.get('type','')).replace('Event',''))}</span> "
        f"<span class='rn'>{esc(e.get('repo',''))}</span>"
        + (f" <span class='cm'>+{e['commits']}</span>" if e.get("commits") else "")
        + "</li>"
        for e in d.get("timeline", [])[:8])
    fetched = esc(str(d.get("fetched_at", ""))[:19].replace("T", " "))
    return f"""<section class="activity">
<div class="act-head"><span class="kicker">LIVE THREAD · GITHUB ACTIVITY</span>
<span class="fetched">synced {fetched} UTC · public API</span></div>
<div class="act-main">
<div class="act-stat"><b>{d.get('events_in_window', 0)}</b><span>EVENTS / 7 DAYS</span></div>
<div class="act-types">{types}</div>
</div>
<div class="repos">{repos}</div>
<ul class="tl">{tl}</ul>
<div class="act-note">{esc(d.get('note',''))}</div>
<a class="raw" href="github-activity.json">▦ RAW ACTIVITY JSON ↗</a>
</section>"""


def esc(s):
    return html.escape(s, quote=True)


def card(s):
    verdicts = "".join(
        f'<div class="v"><span class="k {k}">{k.upper()}</span>'
        f'<span class="t">{esc(s[k]) or "<em>not recorded</em>"}</span></div>'
        for k in ("proved", "broke", "change")
    )
    label = f'§{s["num"]}' if s["num"] is not None else '§·'
    key = str(s["num"]) if s["num"] is not None else s["title"]
    return (f'<article class="card" data-n="{esc(key)}" data-verdict-parity="{s["parity"]}">'
            f'<div class="chead"><span class="num">{label}</span>'
            f'<span class="ttl">{esc(s["title"])}</span>'
            f'<span class="date">{esc(s["date"])}</span></div>'
            f'<div class="vb">{verdicts}</div></article>')


def main():
    import sys
    sections, lines = parse()
    missing = [s["title"] for s in sections if s["parity"] == "MISSING"]
    if "--check" in sys.argv:
        if missing:
            print(f"REFUSE: {len(missing)} section(s) carry a verdict marker "
                  f"but parsed empty: {missing[:5]}")
            sys.exit(1)
        # executable lesson continuity_verdict_parity: fail closed on a
        # generated artifact that still carries an unparsed verdict marker.
        if OUT.exists() and 'data-verdict-parity="MISSING"' in OUT.read_text(encoding="utf-8"):
            print("REFUSE: generated HTML carries data-verdict-parity=MISSING "
                  "(lesson continuity_verdict_parity)")
            sys.exit(1)
        print(f"OK: {len(sections)} sections, 0 unparsed verdicts")
        return
    if missing:
        print(f"REFUSE: {len(missing)} section(s) carry a verdict marker "
              f"but would render 'not recorded': {missing[:5]}")
        sys.exit(1)
    cards = "\n".join(card(s) for s in reversed(sections))
    dates = [s["date"] for s in sections if s["date"]]
    span = f"{dates[-1]} → {dates[0]}" if dates else "—"
    doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>æ · Continuity</title>
<style>
:root{{--gold:#D4AF37;--void:#050505;--gold-dim:rgba(212,175,55,.3);
--gold-faint:rgba(212,175,55,.1);--ink:#e8e6df;--muted:#6f6a5c;
--neon:#00ff9d;--red:#ff4d5f;--cyan:#00eaff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--void);color:var(--ink);
font:14px/1.6 Consolas,Monaco,monospace;
background-image:repeating-linear-gradient(0deg,transparent 0 2px,rgba(212,175,55,.015) 2px 4px)}}
.wrap{{max-width:920px;margin:0 auto;padding:40px 24px 80px}}
.kicker{{color:var(--gold);font-size:12px;letter-spacing:.18em}}
h1{{font-size:38px;margin:8px 0 4px;color:var(--ink)}}
.sub{{color:var(--muted);font-size:13px;margin-bottom:24px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 28px}}
.stat{{border:1px solid var(--gold-dim);padding:10px 16px;min-width:120px}}
.stat b{{display:block;color:var(--gold);font-size:22px}}
.stat span{{color:var(--muted);font-size:11px;letter-spacing:.1em}}
a.raw{{color:var(--gold);border:1px solid var(--gold-dim);padding:8px 14px;
text-decoration:none;font-size:12px;display:inline-block;margin-bottom:24px}}
a.raw:hover{{background:var(--gold-faint)}}
.activity{{border:1px solid var(--gold-dim);border-left:2px solid var(--gold);
padding:14px 16px;margin-bottom:26px;background:rgba(212,175,55,.03)}}
.act-head{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
border-bottom:1px solid var(--gold-faint);padding-bottom:8px;margin-bottom:12px}}
.fetched{{color:var(--muted);font-size:11px}}
.act-main{{display:flex;gap:18px;align-items:center;flex-wrap:wrap}}
.act-stat b{{font-size:30px;color:var(--gold);display:block;line-height:1}}
.act-stat span{{color:var(--muted);font-size:10px;letter-spacing:.1em}}
.act-types{{display:flex;gap:6px;flex-wrap:wrap}}
.tp{{border:1px solid var(--gold-dim);padding:4px 8px;font-size:11px;color:var(--muted)}}
.tp b{{color:var(--ink)}}
.tp.push{{border-color:var(--cyan)}} .tp.create{{border-color:var(--neon)}}
.tp.watch{{border-color:var(--gold)}} .tp.fork{{border-color:var(--red)}}
.repos{{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}}
.rp{{font-size:11px;color:#b9b5a8;border-bottom:1px dotted var(--gold-dim);padding-bottom:2px}}
.rp b{{color:var(--gold)}}
.tl{{list-style:none;padding:0;margin:10px 0;font-size:11px}}
.tl li{{padding:3px 0;border-bottom:1px solid var(--gold-faint)}}
.dt{{color:var(--muted)}} .ev{{color:var(--cyan)}} .rn{{color:var(--ink)}}
.cm{{color:var(--neon)}}
.act-note{{color:var(--muted);font-size:10px;line-height:1.5;margin:10px 0}}
.act-empty{{border:1px dashed var(--gold-dim);padding:14px;margin-bottom:26px;color:var(--muted);font-size:12px}}
.filters{{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}}
input,filters button{{font:inherit}}
input{{flex:1;min-width:220px;background:#0a0a0a;border:1px solid var(--gold-dim);
color:var(--ink);padding:10px 12px;outline:none}}
input:focus{{border-color:var(--gold)}}
button{{background:transparent;color:var(--muted);border:1px solid var(--gold-dim);
padding:8px 12px;cursor:pointer;font-size:12px}}
button.on{{color:var(--gold);border-color:var(--gold)}}
.card{{border:1px solid var(--gold-faint);border-left:2px solid var(--gold-dim);
margin-bottom:12px;background:rgba(212,175,55,.02)}}
.chead{{display:flex;gap:12px;align-items:baseline;padding:12px 14px;
border-bottom:1px solid var(--gold-faint)}}
.num{{color:var(--gold);font-weight:bold;min-width:44px}}
.ttl{{flex:1;color:var(--ink)}}
.date{{color:var(--muted);font-size:11px}}
.vb{{padding:6px 14px 12px}}
.v{{display:flex;gap:10px;padding:4px 0;font-size:12px}}
.k{{min-width:64px;font-weight:bold;letter-spacing:.08em}}
.k.proved{{color:var(--neon)}} .k.broke{{color:var(--red)}} .k.change{{color:var(--cyan)}}
.t{{color:#b9b5a8}}
em{{color:var(--muted)}}
footer{{margin-top:36px;color:var(--muted);font-size:11px;
border-top:1px solid var(--gold-faint);padding-top:16px}}
@media(max-width:600px){{h1{{font-size:28px}}.chead{{flex-wrap:wrap}}}}
</style>
</head>
<body>
<div class="wrap">
<div class="kicker">#OPENSOURCEWARE · THE CONTINUITY RECORD</div>
<h1>æ · Continuity</h1>
<div class="sub">Every run: what was proved, what broke, what changed. Generated from <code>AE-CONTINUITY.md</code> — not hand-maintained.</div>
<div class="stats">
<div class="stat"><b>{len(sections)}</b><span>SECTIONS</span></div>
<div class="stat"><b>{span}</b><span>DATE SPAN</span></div>
<div class="stat"><b>{lines}</b><span>SOURCE LINES</span></div>
</div>
<a class="raw" href="AE-CONTINUITY.md">READ THE FULL RECORD (markdown) ↗</a>
{activity_block()}
<div class="filters">
<input id="q" placeholder="filter by word, § number, or verdict…">
<button data-f="all" class="on">ALL</button>
<button data-f="proved">PROVEN</button>
<button data-f="broke">BROKE</button>
<button data-f="change">CHANGE</button>
</div>
<main id="list">
{cards}
</main>
<footer>SOURCE github-pages/AE-CONTINUITY.md · generated by build_continuity_html.py · read the artifact at render time, never repeat a count from a doc · #050505 / #D4AF37 / #00ff9d</footer>
</div>
<script>
const q=document.getElementById('q'), cards=[...document.querySelectorAll('.card')];
let filter='all';
function apply(){{
  const term=q.value.trim().toLowerCase();
  cards.forEach(c=>{{
    const text=c.textContent.toLowerCase();
    const n=c.dataset.n;
    const hit=(!term||text.includes(term)||('§'+n).includes(term));
    const fv=filter==='all'||c.querySelector('.k.'+filter);
    c.style.display=(hit&&fv)?'':'none';
  }});
}}
q.addEventListener('input',apply);
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{{
  filter=b.dataset.f;
  document.querySelectorAll('.filters button').forEach(x=>x.classList.toggle('on',x===b));
  apply();
}}));
</script>
</body>
</html>'''
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT} ({len(sections)} sections, {len(doc)} bytes)")


if __name__ == "__main__":
    main()
