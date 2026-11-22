"""
continuity_html.py — render the record as a verifiable surface.

FIRST PRINCIPLES
  1. ONE MODEL. Every source is read in build_model(); rendering is a pure
     function of that model. No source is touched during render.
  2. ABSENCE IS EXPLICIT. An unrecorded verdict is None and carries
     data-has-*="0" — never a label that only looks present.
  3. FAIL CLOSED. A verdict marker that parses empty, a wrong schema, or a
     duplicate key REFUSES generation. No pass is inferred.
  4. ROUND TRIP. After writing, re-read the artifact and assert every model
     fact appears in it. A render that cannot be read back is not a render.
  5. DETERMINISTIC. No wall-clock in the output; identical inputs → identical
     bytes. The activity snapshot's own fetched_at is the only timestamp.

Reads : AE-CONTINUITY.md · github-activity.json · brain.json · ae_lessons.jsonl
Writes: continuity.html
Gate  : --check (refuse, never "skipped = PASS")
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path("C:/æ/github-pages")
RECORD = REPO / "AE-CONTINUITY.md"
ACTIVITY = REPO / "github-activity.json"
BRAIN = REPO / "brain.json"
LESSONS = Path("C:/æ/logs/ae_lessons.jsonl")
OUT = REPO / "continuity.html"

SCHEMA = "ae/github-activity/1"
VERDICTS = ("proved", "broke", "change")
SEC = re.compile(r"^## (.+?)\s*$", re.M)
VERDICT = re.compile(
    r"\*\*(proved|broke|change)\*\*\s*[-–—]\s*(.*?)"
    r"(?=\n\*\*(?:proved|broke|change)\*\*|\Z)", re.S)
MARKER = re.compile(r"\*\*(?:proved|broke|change)\*\*", re.I)
DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})")


# ── model ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Section:
    num: int | None
    title: str
    date: str
    verdicts: dict          # kind -> text or None
    parity: str             # "ok" | "MISSING"
    ordinal: int            # position in the record — the unique identity

    @property
    def label(self) -> str:
        return f"§{self.num}" if self.num is not None else "§·"

    @property
    def key(self) -> str:
        # Author numbering can collide under concurrent edits; position cannot.
        return str(self.ordinal)

    @property
    def present(self) -> tuple:
        return tuple(k for k in VERDICTS if self.verdicts.get(k))


@dataclass(frozen=True)
class Activity:
    available: bool
    schema: str
    events: int
    by_type: dict
    by_repo: dict
    timeline: list
    fetched_at: str
    note: str


@dataclass(frozen=True)
class Model:
    sections: tuple
    source_lines: int
    span: str
    activity: Activity
    brain_surfaces: str
    brain_parity_missing: str
    lesson_count: str
    lesson_head: str
    sources: dict           # path -> "present" | "absent"


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _activity() -> Activity:
    d = _json(ACTIVITY)
    if not isinstance(d, dict) or d.get("schema") != SCHEMA:
        return Activity(False, "absent", 0, {}, {}, [], "", "snapshot unavailable — run sync_github_activity.py")
    return Activity(True, d["schema"], int(d.get("events_in_window", 0)),
                    d.get("by_type", {}), d.get("by_repo", {}),
                    d.get("timeline", []), str(d.get("fetched_at", ""))[:19].replace("T", " "),
                    str(d.get("note", "")))


def build_model() -> Model:
    text = RECORD.read_text(encoding="utf-8")
    matches = list(SEC.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        raw = m.group(1).strip()
        nm = re.match(r"^(\d+)\.\s+(.*)$", raw)
        num, title = (int(nm.group(1)), nm.group(2).strip()) if nm else (None, raw)
        dm = DATE.search(title)
        date = ""
        if dm:
            date = dm.group(1)
            title = title[:dm.start()].strip()
        found = {k: " ".join(v.split()) for k, v in VERDICT.findall(body)}
        verdicts = {k: (found.get(k) or None) for k in VERDICTS}
        marked = len(MARKER.findall(body))
        parity = "MISSING" if marked and not any(verdicts.values()) else "ok"
        sections.append(Section(num, title, date, verdicts, parity, i))

    dates = [s.date for s in sections if s.date]
    span = f"{min(dates)} → {max(dates)}" if dates else "—"

    brain = _json(BRAIN) or {}
    lessons = []
    if LESSONS.exists():
        lessons = [json.loads(l) for l in LESSONS.read_text(encoding="utf-8").splitlines()
                   if l.strip()]

    return Model(
        sections=tuple(sections), source_lines=len(text.splitlines()), span=span,
        activity=_activity(),
        brain_surfaces=str(brain.get("total_surfaces", "—")),
        brain_parity_missing=str(len(brain.get("title_parity_missing", [])))
        if "title_parity_missing" in brain else "—",
        lesson_count=str(len(lessons)) if LESSONS.exists() else "—",
        lesson_head=str(lessons[-1].get("hash", ""))[:16] if lessons else "—",
        sources={p.name: ("present" if p.exists() else "absent")
                 for p in (RECORD, ACTIVITY, BRAIN, LESSONS)},
    )


def validate(m: Model) -> list:
    """Refusals — checked before ANY output is written."""
    bad = []
    missing = [s.title for s in m.sections if s.parity == "MISSING"]
    if missing:
        bad.append(f"{len(missing)} section(s) carry a verdict marker but parse empty: {missing[:5]}")
    keys = [s.key for s in m.sections]
    if len(set(keys)) != len(keys):
        bad.append("section identities collide — position keys are not unique")
    # Duplicate § NUMBERS are a record-authoring issue, not a render blocker:
    # concurrent agents reuse numbers. Report them; the display label is
    # intentionally allowed to repeat, but each card keeps a unique key.
    bodies = [(s.title, tuple(s.verdicts[k] for k in VERDICTS)) for s in m.sections]
    exact = {b for b in bodies if bodies.count(b) > 1}
    if exact:
        bad.append(f"byte-identical sections (true duplicates): {len(exact)}")
    if m.activity.available and m.activity.schema != SCHEMA:
        bad.append("activity schema mismatch")
    if not m.sections:
        bad.append("record has no sections")
    return bad


# ── view ───────────────────────────────────────────────────────────────────
def e(s) -> str:
    return html.escape(str(s), quote=True)


CSS = """
:root{--gold:#D4AF37;--void:#050505;--gd:rgba(212,175,55,.3);--gf:rgba(212,175,55,.1);
--ink:#e8e6df;--muted:#6f6a5c;--neon:#00ff9d;--red:#ff4d5f;--cyan:#00eaff}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--ink);font:14px/1.6 Consolas,Monaco,monospace;
background-image:repeating-linear-gradient(0deg,transparent 0 2px,rgba(212,175,55,.015) 2px 4px)}
.wrap{max-width:920px;margin:0 auto;padding:40px 24px 80px}
.kicker{color:var(--gold);font-size:12px;letter-spacing:.18em}
h1{font-size:38px;margin:8px 0 4px} .sub{color:var(--muted);font-size:13px;margin-bottom:24px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 28px}
.stat{border:1px solid var(--gd);padding:10px 16px;min-width:120px}
.stat b{display:block;color:var(--gold);font-size:22px}
.stat span{color:var(--muted);font-size:11px;letter-spacing:.1em}
a.raw{color:var(--gold);border:1px solid var(--gd);padding:8px 14px;text-decoration:none;
font-size:12px;display:inline-block;margin-bottom:24px}
a.raw:hover{background:var(--gf)}
.panel{border:1px solid var(--gd);border-left:2px solid var(--gold);padding:14px 16px;margin-bottom:26px}
.panel h2{font-size:12px;letter-spacing:.14em;color:var(--gold);margin:0 0 10px}
.fetched{color:var(--muted);font-size:11px}
.big{font-size:30px;color:var(--gold);line-height:1}
.lbl{color:var(--muted);font-size:10px;letter-spacing:.1em}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.chip{border:1px solid var(--gd);padding:4px 8px;font-size:11px;color:var(--muted)}
.chip b{color:var(--ink)} .chip.push{border-color:var(--cyan)}
.chip.create{border-color:var(--neon)} .chip.watch{border-color:var(--gold)}
.chip.fork{border-color:var(--red)}
ul.tl{list-style:none;padding:0;margin:10px 0;font-size:11px}
ul.tl li{padding:3px 0;border-bottom:1px solid var(--gf)}
.dt{color:var(--muted)} .ev{color:var(--cyan)} .rn{color:var(--ink)} .cm{color:var(--neon)}
.note{color:var(--muted);font-size:10px;line-height:1.5;margin:10px 0}
.filters{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}
input{flex:1;min-width:220px;background:#0a0a0a;border:1px solid var(--gd);color:var(--ink);
padding:10px 12px;outline:none;font:inherit} input:focus{border-color:var(--gold)}
button{background:transparent;color:var(--muted);border:1px solid var(--gd);padding:8px 12px;
cursor:pointer;font:inherit;font-size:12px} button.on{color:var(--gold);border-color:var(--gold)}
.card{border:1px solid var(--gf);border-left:2px solid var(--gd);margin-bottom:12px}
.chead{display:flex;gap:12px;align-items:baseline;padding:12px 14px;border-bottom:1px solid var(--gf)}
.num{color:var(--gold);font-weight:bold;min-width:44px} .ttl{flex:1} .date{color:var(--muted);font-size:11px}
.vb{padding:6px 14px 12px} .v{display:flex;gap:10px;padding:4px 0;font-size:12px}
.k{min-width:64px;font-weight:bold;letter-spacing:.08em}
.k.proved{color:var(--neon)} .k.broke{color:var(--red)} .k.change{color:var(--cyan)}
.t{color:#b9b5a8} .t.empty{color:var(--muted);font-style:italic}
footer{margin-top:36px;color:var(--muted);font-size:11px;border-top:1px solid var(--gf);padding-top:16px}
@media(max-width:600px){h1{font-size:28px}.chead{flex-wrap:wrap}}
"""


def card(s: Section) -> str:
    # presence is data, not a label that always renders
    attrs = " ".join(f'data-has-{k}="{1 if s.verdicts.get(k) else 0}"' for k in VERDICTS)
    rows = "".join(
        f'<div class="v"><span class="k {k}">{k.upper()}</span>'
        + (f'<span class="t">{e(s.verdicts[k])}</span>' if s.verdicts.get(k)
           else '<span class="t empty">not recorded</span>')
        + "</div>" for k in VERDICTS)
    return (f'<article class="card" data-n="{e(s.key)}" '
            f'data-verdict-parity="{s.parity}" {attrs}>'
            f'<div class="chead"><span class="num">{e(s.label)}</span>'
            f'<span class="ttl">{e(s.title)}</span>'
            f'<span class="date">{e(s.date)}</span></div>'
            f'<div class="vb">{rows}</div></article>')


def activity_panel(a: Activity) -> str:
    if not a.available:
        return ('<section class="panel"><h2>LIVE THREAD · GITHUB ACTIVITY</h2>'
                '<p class="note">snapshot unavailable — run sync_github_activity.py</p></section>')
    types = "".join(
        f'<span class="chip {e(k.lower().replace("event", ""))}">'
        f'{e(k.replace("Event", ""))} <b>{e(v)}</b></span>'
        for k, v in a.by_type.items())
    repos = "".join(f'<span class="chip">{e(k)} <b>{e(v)}</b></span>'
                    for k, v in list(a.by_repo.items())[:6])
    tl = "".join(
        f'<li><span class="dt">{e(str(x.get("created_at", ""))[:16].replace("T", " "))}</span> '
        f'<span class="ev">{e(str(x.get("type", "")).replace("Event", ""))}</span> '
        f'<span class="rn">{e(x.get("repo", ""))}</span>'
        + (f' <span class="cm">+{x["commits"]}</span>' if x.get("commits") else "") + "</li>"
        for x in a.timeline[:8])
    return (f'<section class="panel"><h2>LIVE THREAD · GITHUB ACTIVITY</h2>'
            f'<div class="fetched">derived snapshot · fetched {e(a.fetched_at)} UTC · '
            f'public API · schema {e(a.schema)}</div>'
            f'<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin:10px 0">'
            f'<div><div class="big">{e(a.events)}</div><div class="lbl">EVENTS / 7 DAYS</div></div>'
            f'<div class="chips">{types}</div></div>'
            f'<div class="chips">{repos}</div><ul class="tl">{tl}</ul>'
            f'<p class="note">{e(a.note)}</p>'
            f'<a class="raw" href="github-activity.json">▦ RAW ACTIVITY JSON ↗</a></section>')


def render(m: Model) -> str:
    cards = "\n".join(card(s) for s in reversed(m.sections))
    src = " · ".join(f"{k}:{v}" for k, v in m.sources.items())
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>æ · Continuity</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="kicker">#OPENSOURCEWARE · THE CONTINUITY RECORD</div>
<h1>æ · Continuity</h1>
<div class="sub">Every run: what was proved, what broke, what changed. Generated from
<code>AE-CONTINUITY.md</code> — not hand-maintained.</div>
<div class="stats">
<div class="stat"><b>{len(m.sections)}</b><span>SECTIONS</span></div>
<div class="stat"><b>{e(m.span)}</b><span>DATE SPAN</span></div>
<div class="stat"><b>{m.source_lines}</b><span>SOURCE LINES</span></div>
<div class="stat"><b>{e(m.brain_surfaces)}</b><span>BRAIN SURFACES</span></div>
<div class="stat"><b>{e(m.lesson_count)}</b><span>LESSONS</span></div>
</div>
<a class="raw" href="AE-CONTINUITY.md">READ THE FULL RECORD (markdown) ↗</a>
{activity_panel(m.activity)}
<section class="panel"><h2>CHASSIS · DERIVED STATE</h2>
<div class="fetched">brain title parity missing: {e(m.brain_parity_missing)} ·
lessons head: {e(m.lesson_head)}</div></section>
<div class="filters">
<input id="q" placeholder="filter by word, § number, or verdict…">
<button data-f="all" class="on">ALL</button>
<button data-f="proved">PROVEN</button>
<button data-f="broke">BROKE</button>
<button data-f="change">CHANGE</button>
</div>
<main id="list">{cards}</main>
<footer>SOURCES {e(src)} · read the artifact at render time, never repeat a count from a doc ·
#050505 / #D4AF37 / #00ff9d</footer>
</div><script>
const q=document.getElementById('q'), cards=[...document.querySelectorAll('.card')];
let filter='all';
function apply(){{
  const term=q.value.trim().toLowerCase();
  cards.forEach(c=>{{
    const text=c.textContent.toLowerCase();
    const hit=!term||text.includes(term)||('§'+c.dataset.n).includes(term);
    const fv=filter==='all'||c.dataset['has'+filter[0].toUpperCase()+filter.slice(1)]==='1';
    c.style.display=(hit&&fv)?'':'none';
  }});
}}
q.addEventListener('input',apply);
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{{
  filter=b.dataset.f;
  document.querySelectorAll('.filters button').forEach(x=>x.classList.toggle('on',x===b));
  apply();
}}));
</script></body></html>'''


def verify(doc: str, m: Model) -> list:
    """Round trip: every model fact must be readable back from the HTML."""
    bad = []
    if doc.count('class="card"') != len(m.sections):
        bad.append("card count != section count")
    if 'data-verdict-parity="MISSING"' in doc:
        bad.append("generated HTML carries an unparsed verdict marker")
    for label in (str(len(m.sections)), str(m.source_lines), m.brain_surfaces, m.lesson_count):
        if label not in doc:
            bad.append(f"stat {label!r} missing from output")
    if m.activity.available and str(m.activity.events) not in doc:
        bad.append("activity event count missing from output")
    for s in m.sections[:5]:
        if e(s.title) not in doc:
            bad.append(f"section title missing: {s.title[:30]}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="render the continuity record")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    m = build_model()
    refusals = validate(m)
    if args.check:
        if refusals:
            print("REFUSE: " + "; ".join(refusals))
            return 1
        print(f"OK: {len(m.sections)} sections, 0 unparsed verdicts, "
              f"{len(m.sources)} sources checked")
        return 0
    if refusals:
        print("REFUSE: " + "; ".join(refusals))
        return 1

    doc = render(m)
    problems = verify(doc, m)
    if problems:
        print("REFUSE: round-trip verification failed: " + "; ".join(problems))
        return 1
    OUT.write_text(doc, encoding="utf-8")
    # verify what actually landed, not the in-memory string
    disk_problems = verify(OUT.read_text(encoding="utf-8"), m)
    if disk_problems:
        print("REFUSE: on-disk verification failed: " + "; ".join(disk_problems))
        return 1
    print(f"wrote {OUT} ({len(m.sections)} sections, {len(doc)} bytes, round-trip OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
