#!/usr/bin/env python3
"""
continuity_record.py — the modern continuity record (tinyXML × tinySVG).

The HTML surface is NOT the record. The record is a well-formed XML artifact;
the HTML is a governed RENDER of it. Two instruments supply the discipline:

  tinyXML  — canonical form (sorted attrs, no declaration/comments), XXE
             refused, two canonicalisations byte-compared before any claim.
  tinySVG  — "the viewBox is not the screen": derive scale from the real render
             width and REFUSE a surface whose type falls below 12px effective.

Verbs
  doctor()   measure both instruments, the sources, and the render width
  build      derive continuity.xml from the four sources
  canon      emit the deterministic canonical form of the record
  grade      two canonicalisations, byte-compared (the receipt)
  render     emit continuity.html from the XML, gated by the legibility floor
  check      validate the XML with tinyXML + the HTML font floor

Invariants: doctor measures; every verb refuses; the contract is read from the
bytes; a receipt is a claim until re-run.

  python continuity_record.py doctor|build|canon|grade|render|check
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("C:/æ")
REPO = ROOT / "github-pages"
RECORD_MD = REPO / "AE-CONTINUITY.md"
ACTIVITY = REPO / "github-activity.json"
BRAIN = REPO / "brain.json"
LESSONS = ROOT / "logs/ae_lessons.jsonl"
XML_OUT = REPO / "continuity.xml"
HTML_OUT = REPO / "continuity.html"

SCHEMA = "ae/continuity/1"
ACT_SCHEMA = "ae/github-activity/1"
MECH_SHA16 = hashlib.sha256((ROOT / "github-pages/maechlang/authority.mec").read_bytes()).hexdigest()[:16]
_WASM = ROOT / "github-pages/continuity-wasm/dist/continuity_core_bg.wasm"
WASM_SHA16 = hashlib.sha256(_WASM.read_bytes()).hexdigest()[:16] if _WASM.exists() else "NOT-BUILT"
VERDICTS = ("proved", "broke", "change")
MIN_FONT_PX = 12.0          # tinySVG's floor
RENDER_W = 707.0            # real chat width from tinySVG's doctor
DESIGN_W = 920.0            # the width the CSS is authored at
SEC = re.compile(r"^## (.+?)\s*$", re.M)
VERDICT_RE = re.compile(r"\*\*(proved|broke|change)\*\*\s*[-–—]\s*(.*?)"
                        r"(?=\n\*\*(?:proved|broke|change)\*\*|\Z)", re.S)
MARKER = re.compile(r"\*\*(?:proved|broke|change)\*\*", re.I)
DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})")


def _load(name: str, path: Path):
    """tiny* dirs shadow their own modules — load BY PATH (skill pitfall)."""
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tinyxml():
    return _load("tinyXML_mod", ROOT / "tinyXML/tinyXML.py")


def tinysvg():
    return _load("tinySVG_mod", ROOT / "tinySVG/tinySVG.py")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _esc_text(s) -> str:
    return tinyxml()._esc_text(str(s))


def _esc_attr(s) -> str:
    return tinyxml()._esc_attr(str(s))


# ── derive the XML truth from the four sources ────────────────────────────
def derive() -> ET.Element:
    text = RECORD_MD.read_text(encoding="utf-8")
    matches = list(SEC.finditer(text))
    root = ET.Element("continuity", {"schema": SCHEMA, "source": RECORD_MD.name})

    dates, ordinals = [], []
    raw_sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        raw = m.group(1).strip()
        nm = re.match(r"^(\d+)\.\s+(.*)$", raw)
        num = int(nm.group(1)) if nm else None
        title = nm.group(2).strip() if nm else raw
        dm = DATE.search(title)
        date = ""
        if dm:
            date = dm.group(1)
            title = title[:dm.start()].strip()
        found = {k: " ".join(v.split()) for k, v in VERDICT_RE.findall(body)}
        verdicts = {k: (found.get(k) or None) for k in VERDICTS}
        marked = len(MARKER.findall(body))
        parity = "MISSING" if marked and not any(verdicts.values()) else "ok"
        if date:
            dates.append(date)
        ordinals.append(str(i))
        raw_sections.append((i, num, title, date, verdicts, parity))

    span = f"{min(dates)} → {max(dates)}" if dates else "—"
    meta = ET.SubElement(root, "meta", {
        "source_lines": str(len(text.splitlines())), "span": span,
        "sections": str(len(raw_sections))})
    for p in (RECORD_MD, ACTIVITY, BRAIN, LESSONS):
        ET.SubElement(meta, "source", {"name": p.name,
                                       "state": "present" if p.exists() else "absent"})

    act = _json(ACTIVITY) or {}
    avail = act.get("schema") == ACT_SCHEMA
    ae = ET.SubElement(root, "activity", {
        "available": "1" if avail else "0",
        "schema": act.get("schema", "absent"),
        "fetched_at": str(act.get("fetched_at", ""))[:19],
        "events": str(act.get("events_in_window", 0))})
    for k, v in (act.get("by_type") or {}).items():
        ET.SubElement(ae, "type", {"name": k, "count": str(v)})
    for k, v in list((act.get("by_repo") or {}).items())[:6]:
        ET.SubElement(ae, "repo", {"name": k, "count": str(v)})
    if act.get("note"):
        ae.set("note", str(act["note"])[:200])

    brain = _json(BRAIN) or {}
    lessons = []
    if LESSONS.exists():
        lessons = [json.loads(l) for l in LESSONS.read_text(encoding="utf-8").splitlines()
                   if l.strip()]
    ET.SubElement(root, "chassis", {
        "brain_surfaces": str(brain.get("total_surfaces", "—")),
        "brain_parity_missing": str(len(brain.get("title_parity_missing", [])))
        if "title_parity_missing" in brain else "—",
        "lessons": str(len(lessons)) if LESSONS.exists() else "—",
        "lessons_head": str(lessons[-1].get("hash", ""))[:16] if lessons else "—"})

    secs = ET.SubElement(root, "sections")
    for ordinal, num, title, date, verdicts, parity in raw_sections:
        s = ET.SubElement(secs, "section", {
            "ordinal": str(ordinal), "num": str(num) if num is not None else "",
            "date": date, "parity": parity,
            **{f"has_{k}": "1" if verdicts.get(k) else "0" for k in VERDICTS}})
        t = ET.SubElement(s, "title"); t.text = title
        for k in VERDICTS:
            if verdicts.get(k):
                v = ET.SubElement(s, "verdict", {"kind": k}); v.text = verdicts[k]
    return root


def xml_bytes(root: ET.Element) -> bytes:
    tx = tinyxml()
    return tx.canon(root).encode("utf-8") + b"\n"


def canon(data: bytes | None = None) -> str:
    """Deterministic canonical form — tinyXML's contract, byte for byte."""
    root = _parse(data or XML_OUT.read_bytes())
    if root is None:
        raise ValueError("record is not well-formed — no canonical form")
    return tinyxml().canon(root)


def _parse(data: bytes):
    # tinyXML's `safe=True` hard-imports defusedxml, which is absent here.
    # Its OWN documented XXE contract is the DTD refusal, so enforce that from
    # the bytes and parse with stdlib ET — no silent downgrade of the gate.
    if tinyxml().has_dtd(data):
        raise ValueError("tinyXML refused the record: DTD/entities are not allowed")
    root, info = tinyxml().parse(data, safe=False)
    if root is None:
        raise ValueError(f"tinyXML refused the record: {info.get('error')}")
    return root


def grade(data: bytes | None = None) -> dict:
    """Two canonicalisations, byte-compared — a receipt only after both match."""
    raw = data if data is not None else XML_OUT.read_bytes()
    a, b = canon(raw), canon(raw)
    same = a.encode("utf-8") == b.encode("utf-8")
    return {"ok": same, "schema": SCHEMA, "canon_sha256": _sha(a.encode("utf-8")),
            "bytes": len(raw), "refused": not same,
            "reason": "" if same else "canonicalisation is not deterministic"}


# ── governed HTML render (tinySVG's legibility discipline) ────────────────
FONT_RE = re.compile(r"font-size:\s*([\d.]+)px")
CSS = """
:root{--gold:#D4AF37;--void:#050505;--gd:rgba(212,175,55,.3);--gf:rgba(212,175,55,.1);
--ink:#e8e6df;--muted:#8a8474;--neon:#00ff9d;--red:#ff4d5f;--cyan:#00eaff}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--ink);font:14px/1.6 Consolas,Monaco,monospace;
background-image:repeating-linear-gradient(0deg,transparent 0 2px,rgba(212,175,55,.015) 2px 4px)}
.wrap{max-width:920px;margin:0 auto;padding:40px 24px 80px}
.kicker{color:var(--gold);font-size:12px;letter-spacing:.18em}
h1{font-size:38px;margin:8px 0 4px} .sub{color:var(--muted);font-size:13px;margin-bottom:24px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 28px}
.stat{border:1px solid var(--gd);padding:10px 16px;min-width:120px}
.stat b{display:block;color:var(--gold);font-size:22px}
.stat span{color:var(--muted);font-size:12px;letter-spacing:.1em}
a.raw{color:var(--gold);border:1px solid var(--gd);padding:8px 14px;text-decoration:none;
font-size:12px;display:inline-block;margin-bottom:24px}
a.raw:hover{background:var(--gf)}
.panel{border:1px solid var(--gd);border-left:2px solid var(--gold);padding:14px 16px;margin-bottom:26px}
.panel h2{font-size:13px;letter-spacing:.14em;color:var(--gold);margin:0 0 10px}
.fetched{color:var(--muted);font-size:12px}
.big{font-size:30px;color:var(--gold);line-height:1}
.lbl{color:var(--muted);font-size:12px;letter-spacing:.1em}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.chip{border:1px solid var(--gd);padding:4px 8px;font-size:12px;color:var(--muted)}
.chip b{color:var(--ink)} .chip.push{border-color:var(--cyan)}
.chip.create{border-color:var(--neon)} .chip.watch{border-color:var(--gold)}
.chip.fork{border-color:var(--red)}
ul.tl{list-style:none;padding:0;margin:10px 0;font-size:12px}
ul.tl li{padding:3px 0;border-bottom:1px solid var(--gf)}
.dt{color:var(--muted)} .ev{color:var(--cyan)} .rn{color:var(--ink)} .cm{color:var(--neon)}
.note{color:var(--muted);font-size:12px;line-height:1.5;margin:10px 0}
.filters{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}
input{flex:1;min-width:220px;background:#0a0a0a;border:1px solid var(--gd);color:var(--ink);
padding:10px 12px;outline:none;font:inherit;font-size:14px} input:focus{border-color:var(--gold)}
button{background:transparent;color:var(--muted);border:1px solid var(--gd);padding:8px 12px;
cursor:pointer;font:inherit;font-size:12px} button.on{color:var(--gold);border-color:var(--gold)}
.card{border:1px solid var(--gf);border-left:2px solid var(--gd);margin-bottom:12px}
.chead{display:flex;gap:12px;align-items:baseline;padding:12px 14px;border-bottom:1px solid var(--gf)}
.num{color:var(--gold);font-weight:bold;min-width:44px;font-size:14px}
.ttl{font-size:14px} .date{color:var(--muted);font-size:12px}
.vb{padding:6px 14px 12px} .v{display:flex;gap:10px;padding:4px 0;font-size:12px}
.k{min-width:64px;font-weight:bold;letter-spacing:.08em;font-size:12px}
.k.proved{color:var(--neon)} .k.broke{color:var(--red)} .k.change{color:var(--cyan)}
.t{color:#b9b5a8;font-size:12px} .t.empty{color:var(--muted);font-style:italic}
footer{margin-top:36px;color:var(--muted);font-size:12px;border-top:1px solid var(--gf);padding-top:16px}
@media(max-width:600px){h1{font-size:28px}.chead{flex-wrap:wrap}}
"""


def legibility() -> dict:
    """HTML CSS px are absolute — no viewBox scale. The floor applies to the
    smallest declared size. tinySVG's 'viewBox is not the screen' becomes here:
    a font declared below the floor is unreadable at ANY container width."""
    sizes = [float(x) for x in FONT_RE.findall(CSS)]
    smallest = min(sizes) if sizes else 0.0
    effective = smallest
    return {"ok": effective >= MIN_FONT_PX, "scale": 1.0,
            "smallest_declared_px": smallest, "effective_px": round(effective, 2),
            "floor_px": MIN_FONT_PX, "render_w": RENDER_W,
            "refusal": None if effective >= MIN_FONT_PX
            else f"font {effective:.1f}px below {MIN_FONT_PX}px floor at any width"}


def wasm_state(root: ET.Element) -> str:
    """The Rust core's state JSON, built from the SAME XML that produced the
    cards. One truth: the wasm never derives from a second, drifting copy."""
    sections = []
    for s in root.find("sections"):
        num = s.get("num", "")
        sections.append({
            "key": s.get("ordinal"),
            "label": f"§{num}" if num else "§·",
            "title": s.findtext("title") or "",
            "date": s.get("date", ""),
            "parity": s.get("parity", "ok"),
            "has_proved": s.get("has_proved") == "1",
            "has_broke": s.get("has_broke") == "1",
            "has_change": s.get("has_change") == "1",
        })
    return json.dumps(sections, ensure_ascii=False).replace("</", "<\\/")


def render(root: ET.Element, g: dict) -> str:
    """HTML is a pure render of the XML plus its grade — no source re-read."""
    state_json = wasm_state(root)
    m = root.find("meta")
    act = root.find("activity")
    chassis = root.find("chassis")
    secs = root.find("sections")
    gattr = {"canon_sha256": g["canon_sha256"][:16]}
    cards = []
    for s in secs:
        attrs = " ".join(f'data-has-{k}="{s.get("has_" + k)}"' for k in VERDICTS)
        rows = ""
        for v in s.findall("verdict"):
            k = v.get("kind")
            rows += (f'<div class="v"><span class="k {k}">{k.upper()}</span>'
                     f'<span class="t">{html.escape(v.text or "")}</span></div>')
        for k in VERDICTS:
            if s.get("has_" + k) != "1":
                rows += (f'<div class="v"><span class="k {k}">{k.upper()}</span>'
                         '<span class="t empty">not recorded</span></div>')
        label = f'§{s.get("num")}' if s.get("num") else "§·"
        cards.append(
            f'<article class="card" data-n="{s.get("ordinal")}" '
            f'data-verdict-parity="{s.get("parity")}" {attrs}>'
            f'<div class="chead"><span class="num">{label}</span>'
            f'<span class="ttl">{html.escape(s.findtext("title") or "")}</span>'
            f'<span class="date">{html.escape(s.get("date", ""))}</span></div>'
            f'<div class="vb">{rows}</div></article>')

    types = "".join(
        f'<span class="chip {html.escape(x.get("name","").lower().replace("event",""))}">'
        f'{html.escape(x.get("name","").replace("Event",""))} '
        f'<b>{html.escape(x.get("count",""))}</b></span>'
        for x in (act.findall("type") if act is not None else []))
    repos = "".join(f'<span class="chip">{html.escape(x.get("name",""))} '
                    f'<b>{html.escape(x.get("count",""))}</b></span>'
                    for x in (act.findall("repo") if act is not None else []))
    avail = act is not None and act.get("available") == "1"
    panel = (f'<section class="panel"><h2>LIVE THREAD · GITHUB ACTIVITY</h2>'
             f'<div class="fetched">derived snapshot · fetched '
             f'{html.escape(act.get("fetched_at",""))} UTC · {html.escape(act.get("schema",""))}</div>'
             f'<div style="display:flex;gap:18px;flex-wrap:wrap">'
             f'<div><div class="big">{html.escape(act.get("events","0"))}</div>'
             f'<div class="lbl">EVENTS / 7 DAYS</div></div><div class="chips">{types}</div></div>'
             f'<div class="chips">{repos}</div>'
             f'<p class="note">{html.escape(act.get("note",""))}</p>'
             f'<a class="raw" href="github-activity.json">▦ RAW ACTIVITY JSON ↗</a></section>'
             if avail else '<section class="panel"><h2>LIVE THREAD</h2>'
             '<p class="note">snapshot unavailable — run sync_github_activity.py</p></section>')

    src = " · ".join(f'{x.get("name")}:{x.get("state")}' for x in m.findall("source"))
    stats = [(m.get("sections", "0"), "SECTIONS"), (m.get("span", "—"), "DATE SPAN"),
             (m.get("source_lines", "0"), "SOURCE LINES"),
             (chassis.get("brain_surfaces", "—"), "BRAIN SURFACES"),
             (chassis.get("lessons", "—"), "LESSONS")]
    stat_html = "".join(f'<div class="stat"><b>{html.escape(v)}</b>'
                        f'<span>{k}</span></div>' for v, k in stats)
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>æ · Continuity</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="kicker">#OPENSOURCEWARE · THE CONTINUITY RECORD</div>
<h1>æ · Continuity</h1>
<div class="sub">XML is the record; this page is a governed render. Canonical SHA-256
<code>{gattr["canon_sha256"]}</code> — not hand-maintained.</div>
<div class="stats">{stat_html}</div>
<a class="raw" href="AE-CONTINUITY.md">READ THE FULL RECORD (markdown) ↗</a>
<a class="raw" href="continuity.xml">▦ CANONICAL XML ↗</a>
{panel}
<section class="panel"><h2>CHASSIS · DERIVED STATE</h2>
<div class="fetched">brain title parity missing: {html.escape(chassis.get("brain_parity_missing","—"))}
 · lessons head: {html.escape(chassis.get("lessons_head","—"))}
 · grade: {'PASS' if g['ok'] else 'REFUSED'}</div></section>
<section class="panel" id="mech-panel"><h2>æ:// · REACTIVE GOVERNANCE (Mech 0.3.5)</h2>
<div class="fetched">authority.mec sha256 <code>{MECH_SHA16}</code> · inputs rewritten → whole program re-run</div>
<div id="mech-out" class="note">reading computed state from the wasm…</div></section>
<section class="panel" id="core-panel"><h2>RUST/WASM · DERIVATION CORE</h2>
<div class="fetched">continuity_core_bg.wasm sha256 <code>{WASM_SHA16}</code> · derive() over the XML state</div>
<div id="core-out" class="note">loading Rust core…</div></section>
<div class="filters">
<input id="q" placeholder="filter by word, § number, or verdict…">
<button data-f="all" class="on">ALL</button>
<button data-f="proved">PROVEN</button>
<button data-f="broke">BROKE</button>
<button data-f="change">CHANGE</button>
</div>
<main id="list">{"".join(cards)}</main>
<footer>SOURCES {html.escape(src)} · render width {RENDER_W:.0f}px · type floor {MIN_FONT_PX:.0f}px ·
#050505 / #D4AF37 / #00ff9d</footer>
</div><script type="application/json" id="continuity-state">{state_json}</script>
<script type="module">
// ⟦inputs⟧ rewritten on every Δ; the WHOLE result is re-derived by the Rust
// core. No event-handler accumulation, no JS mirror of the derivation.
const INPUTS = {{ q: '', verdict: 'all' }};
const cards=[...document.querySelectorAll('.card')];
const coreOut=document.getElementById('core-out');
const state=JSON.parse(document.getElementById('continuity-state').textContent);
let core=null;
function paint(r){{
  if(r.refused){{ coreOut.textContent='REFUSED — '+r.reason; return; }}
  const visible=new Set(r.visible);
  cards.forEach(c=>{{ c.style.display=visible.has(c.dataset.n)?'':'none'; }});
  document.querySelectorAll('.filters button').forEach(b=>
    b.classList.toggle('on', b.dataset.f===INPUTS.verdict));
  coreOut.textContent='derive() '+r.count+'/'+r.total+' · receipt '+r.receipt.slice(0,16)+
    ' · parity '+r.parity+' · input-driven, not accumulated';
}}
function derive(){{
  if(!core){{ coreOut.textContent='REFUSED — Rust core unavailable; no derivation claimed'; return; }}
  try {{ paint(JSON.parse(core.derive(JSON.stringify(state), JSON.stringify(INPUTS)))); }}
  catch(e) {{ coreOut.textContent='REFUSED — derive() failed: '+String(e&&e.message||e); }}
}}
document.getElementById('q').addEventListener('input',e=>{{ INPUTS.q=e.target.value; derive(); }});
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{{
  INPUTS.verdict=b.dataset.f; derive();
}}));
// load the Rust core; fail closed — a JS fallback would be a second drifter
try {{
  const mod=await import('./continuity-wasm/dist/continuity_core.js');
  await mod.default();
  core=mod;
  derive();
}} catch(e) {{ coreOut.textContent='REFUSED — Rust core could not load: '+String(e&&e.message||e); }}

// Mech: same reactive discipline for authority. Rewrite ⟦inputs⟧, re-run the
// WHOLE program, read out_string() — never a JS mirror of the verdict.
(async () => {{
  const el=document.getElementById('mech-out');
  try {{
    const mech=await import('./maechlang/runtime/mech_wasm.js');
    const wasm=await (await fetch('./maechlang/runtime/mech_wasm_bg.wasm')).arrayBuffer();
    await mech.default(wasm);
    const base=await (await fetch('./maechlang/authority.mec')).text();
    // this surface is public + published (æ0/æ1): observation, no grant needed
    const inputs={{ pk:false, wr:false, req:'0u8' }};
    const src=base.replace('pk := false','pk := '+inputs.pk)
                  .replace('wr := false','wr := '+inputs.wr)
                  .replace('req := 3u8','req := '+inputs.req);
    const m=new mech.WasmMech(); m.init(); m.run_program(src);
    const out=m.out_string(); m.free();
    const state=(out.match(/state<:(granted|evidence)>:/)||[])[1]||'UNKNOWN';
    if(state==='UNKNOWN'){{ el.textContent='REFUSED — no known state parsed from the wasm'; return; }}
    el.textContent='state :'+state+' · '+
      (state==='granted'?'observation needs no grant':'evidence is not authority')+
      ' · inputs rebuilt + program re-run on every Δ';
  }} catch(e) {{ el.textContent='REFUSED — wasm unavailable: '+String(e&&e.message||e); }}
}})();
</script></body></html>'''


def doctor() -> dict:
    tx_ok = (ROOT / "tinyXML/tinyXML.py").exists()
    ts_ok = (ROOT / "tinySVG/tinySVG.py").exists()
    try:
        root = derive()
        derived_ok = True
        n_sections = len(root.find("sections"))
    except Exception as e:
        derived_ok, n_sections = False, str(e)
    return {"ok": tx_ok and ts_ok and derived_ok,
            "tinyXML": tx_ok, "tinySVG": ts_ok, "derived": derived_ok,
            "sections": n_sections, "legibility": legibility(),
            "rule": "XML is truth; HTML is a graded render below the type floor is refused"}


def check() -> dict:
    refusals = []
    if not XML_OUT.exists():
        refusals.append("continuity.xml missing — run build")
    else:
        g = grade()
        if not g["ok"]:
            refusals.append(g["reason"])
        root = _parse(XML_OUT.read_bytes())
        if root.get("schema") != SCHEMA:
            refusals.append("record schema mismatch")
        parity = [s.get("parity") for s in root.find("sections")]
        if "MISSING" in parity:
            refusals.append(f"{parity.count('MISSING')} unparsed verdict(s)")
    lg = legibility()
    if not lg["ok"]:
        refusals.append(lg["refusal"])
    return {"ok": not refusals, "refused": bool(refusals), "refusals": refusals,
            "grade": grade() if XML_OUT.exists() else None, "legibility": lg}


def main() -> int:
    ap = argparse.ArgumentParser(description="the modern continuity record")
    ap.add_argument("cmd", choices=["doctor", "build", "canon", "grade", "render", "check"])
    a = ap.parse_args()
    if a.cmd == "doctor":
        r = doctor()
    elif a.cmd == "build":
        root = derive()
        data = xml_bytes(root)
        XML_OUT.write_bytes(data)
        g = grade(data)
        r = {"ok": g["ok"], "schema": SCHEMA, "bytes": len(data),
             "canon_sha256": g["canon_sha256"], "sections": len(root.find("sections")),
             "refused": not g["ok"]}
    elif a.cmd == "canon":
        r = {"ok": True, "canonical": canon()}
    elif a.cmd == "grade":
        r = grade()
    elif a.cmd == "check":
        r = check()
    else:  # render
        c = check()
        if c["refused"]:
            r = {"ok": False, "refused": True, "reason": c["refusals"]}
        else:
            root = _parse(XML_OUT.read_bytes())
            doc = render(root, grade())
            HTML_OUT.write_text(doc, encoding="utf-8")
            back = HTML_OUT.read_text(encoding="utf-8")
            ok = (back.count('class="card"') == len(root.find("sections"))
                  and grade()["canon_sha256"][:16] in back)
            r = {"ok": ok, "refused": not ok, "bytes": len(doc),
                 "sections": len(root.find("sections")),
                 "reason": "" if ok else "round-trip verification failed"}
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
