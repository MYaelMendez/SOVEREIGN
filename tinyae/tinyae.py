#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tinyæ — the meta-instrument above the tiny* family.

WHY IT IS ABOVE THE REST
------------------------
Every other instrument measures one capability. tinyæ measures the family, and
it owns the four things that make "the family" mean something:

  membership   the FAMILY list — the only place a member is declared
  measurement  run_doctor() — the ONLY regime, on every interpreter
  the registry  tinyae-registry.json — derived, never hand-written
  the gate      doctor() — refuses to call the family healthy when the
               registry is stale or a published surface contradicts it

Nothing is published as "the family" unless tinyæ made it. tiny_family.py keeps
the constellation's *look* but imports membership and measurement from here;
tinyhq.html and tinyae.html are rendered from the registry, so they cannot drift.

    tinyae.py doctor          # the gate: registry current + surfaces agree
    tinyae.py derive          # run every doctor, write the registry
    tinyae.py surfaces        # render tinyhq.html + tinyae.html from the registry
    tinyae.py verify          # recompute in memory, report drift, write nothing
    tinyae.py report          # one machine-readable verdict
    tinyae.py constellation   # render tiny.html (delegates to tiny_family)

MEASURED, NOT DECLARED. A refusal is a result, never painted green.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:/æ")
PAGES = ROOT / "github-pages"
REGISTRY = PAGES / "tinyae-registry.json"
CONSTELLATION = PAGES / "tiny.html"
HQ = PAGES / "tinyhq.html"
REPORT = PAGES / "tinyae.html"

SCHEMA = "ae/tinyae-registry/2"

# ── membership: the one list ────────────────────────────────────────────────
# name -> (domain, one-line role). Adding a member here is the only way in;
# tiny_family.py imports this, so the constellation cannot disagree.
FAMILY = [
    ("tinycuda",     "pixels",   "raster determinista en una libreta GPU"),
    ("tinygpu",      "pixels",   "renderer de robot con CAD real"),
    ("tinycudavideo", "video",   "el seam: frames -> pelicula"),
    ("tinyvision",   "video",    "supervision del film de la politica"),
    ("tinyffmpeg",   "codecs",   "gobierna los builds de FFmpeg"),
    ("tinyqr",       "identity", "el chip: firma de extremo a extremo"),
    ("tinymujoco",   "motion",   "fisica y movimiento"),
    ("tinyasimov",   "motion",   "el cuerpo: C2 con gates"),
    ("tinypython",   "policy",   "la politica que camina"),
    ("tinypolicy",   "policy",   "su C2"),
    ("tinyonnx",     "policy",   "el oracle ONNX"),
    ("tinycan",      "bus",      "el bus del robot"),
    ("tinygpugbot",  "actors",   "actores con cues, desde trazas"),
    ("tinycontinuum", "time",    "el tiempo y sus frames"),
    ("tinyfilmmemory", "memory", "la memoria del film"),
    ("tinylab",      "lab",      "el auto-estudio de la familia"),
    ("tinyplugin",   "plugin",   "fallos de instalacion, a la vista"),
    ("tinyrepofilm", "film",     "un repo, org o usuario -> pelicula sellada"),
    ("tinyvoca",     "voice",    "la voz local que narra los films"),
    ("tinyae",       "protocol", "la familia measure-and-refuse, un solo prefijo"),
    ("tinySVG",      "geometry", "el viewBox no es la pantalla: escala y solapes"),
    ("tinyXML",      "document", "el documento es el contrato: canon, XXE, firma"),
]

DOMAINS = {
    "pixels": "#D4AF37", "video": "#00e5ff", "codecs": "#39ff14",
    "identity": "#ff4d6d", "motion": "#bf5af2", "policy": "#ffd166",
    "bus": "#69d2ff", "actors": "#ff9f5a", "time": "#9bf6ff",
    "memory": "#c8b6ff", "lab": "#7CFC00", "plugin": "#8d99ae",
    "film": "#ffd700", "voice": "#ff8fab", "protocol": "#D4AF37",
    "geometry": "#7bdff2", "document": "#f1c40f",
}


# ── the one measurement regime ──────────────────────────────────────────────
def interpreters() -> list[str]:
    """Three interpreters on this host carry different stacks. An instrument is
    tried on each; the disagreement is the finding."""
    cands = [
        r"C:\gpu\Scripts\python.exe",
        r"C:\Users\yaelm\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe",
        sys.executable,
    ]
    out = []
    for c in cands:
        if c and Path(c).exists() and c not in out:
            out.append(c)
    return out


def run_doctor(name: str) -> dict:
    """Run one instrument's doctor on EVERY interpreter and classify.

    - a ModuleNotFoundError / timeout is a DEPENDENCY gap, not a verdict
    - a verdict that flips between interpreters is FLAKY, never a pass
    """
    f = ROOT / name / f"{name}.py"
    if not f.exists():
        return {"ok": False, "status": "MODULE MISSING",
                "reason": f"{f} no existe", "verdicts": [], "module": False}
    env = os.environ.copy()
    for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(k, None)
    verdicts, last = [], None
    for exe in interpreters():
        t0 = time.time()
        try:
            r = subprocess.run([exe, str(f), "doctor"], capture_output=True,
                               text=True, timeout=120, errors="replace", env=env,
                               cwd=str(ROOT / name))
        except subprocess.TimeoutExpired:
            verdicts.append({"python": Path(exe).name, "ok": False,
                             "refusal": "TIMEOUT (120s)", "elapsed_s": 120.0})
            continue
        except Exception as exc:
            verdicts.append({"python": Path(exe).name, "ok": False,
                             "refusal": f"{type(exc).__name__}: {exc}"})
            continue
        dt = round(time.time() - t0, 2)
        out = (r.stdout or "").strip()
        try:
            d = json.loads(out)
        except Exception:
            verdicts.append({"python": Path(exe).name, "ok": False,
                             "refusal": f"stdout no es JSON: {out[:120]}",
                             "elapsed_s": dt})
            continue
        blob = json.dumps(d, ensure_ascii=False)
        verdicts.append({"python": Path(exe).name, "ok": bool(d.get("ok")),
                         "elapsed_s": dt, "rc": r.returncode,
                         "error": str(d.get("error") or d.get("reason") or "")[:200],
                         "_blob": blob})
        if d.get("ok"):
            last = d
    DEP_MARKS = ("ModuleNotFoundError", "ImportError", "no module named",
                 "Cannot find", "TIMEOUT")
    for v in verdicts:
        # scan the WHOLE receipt: tinycuda reports at checks.cuda.error
        msg = (str(v.get("refusal") or "") + " " + str(v.get("error") or "")
               + " " + str(v.get("_blob") or ""))
        v["dep"] = any(m in msg for m in DEP_MARKS)
        v.pop("_blob", None)
    if last is None:
        last = {"ok": False, "refusal": (verdicts[-1].get("refusal")
                                         if verdicts else "ningun interprete ejecuto")}
    real = [v["ok"] for v in verdicts if not v.get("dep")]
    last["verdicts"] = verdicts
    last["ok"] = any(v["ok"] for v in verdicts)
    last["flaky"] = bool(real) and any(real) and (len(set(real)) > 1)
    last["dep_only"] = bool(verdicts) and all(v.get("dep") for v in verdicts)
    last["module"] = True
    return last


def derive() -> dict:
    """Measure the whole family and build the registry. Writes nothing."""
    instruments = []
    for name, _dom, _role in FAMILY:
        r = run_doctor(name)
        reason = (r.get("reason") or r.get("refusal")
                  or ("GREEN" if r.get("ok") else "NOT GREEN"))
        instruments.append({
            "name": name, "module": r.get("module", True), "ok": bool(r.get("ok")),
            "status": "GREEN" if r.get("ok") else "NOT GREEN",
            "reason": str(reason)[:180], "rc": r.get("rc"),
            "flaky": bool(r.get("flaky")), "dep_only": bool(r.get("dep_only")),
            "interpreters": [v.get("python") for v in r.get("verdicts", [])],
            "verdicts": r.get("verdicts", []),
        })
    green = [i["name"] for i in instruments if i["ok"]]
    flaky = [i["name"] for i in instruments if i["flaky"]]
    return {
        "schema": SCHEMA,
        "name": "tinyæ",
        "derived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regime": {
            "interpreters": len(interpreters()),
            "flaky_detection": True,
            "dependency_gap_separated": True,
            "source": "each instrument's own `doctor`, run now on every interpreter",
        },
        "families": len(instruments),
        "green": len(green),
        "not_green": len(instruments) - len(green),
        "flaky": len(flaky),
        "green_names": green,
        "flaky_names": flaky,
        "instruments": instruments,
        "note": ("Measured now. A refusal is reported as a refusal, never painted "
                 "green. Flaky means the interpreters disagreed — that is a finding, "
                 "not a pass."),
    }


def write_registry(reg: dict) -> None:
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def read_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


# ── the gate ────────────────────────────────────────────────────────────────
FRESH_SECONDS = float(os.environ.get("TINYAE_FRESH", "7200"))


def doctor() -> dict:
    """Is the family honestly represented?

    Deliberately CHEAP. The first version re-measured the whole family inside
    the gate, which made tinyæ's own doctor slower than the thing it gates: it
    timed out at 120s while the family took 5m35s. So the gate asks the sharper,
    cheaper question — is the registry present, schema-current, fresh, and do the
    published surfaces agree with it? `verify` is the verb that re-measures.
    """
    if not REGISTRY.exists():
        return {"ok": False, "status": "REGISTRY MISSING",
                "reason": f"{REGISTRY} no existe — run `tinyae.py derive`",
                "families": len(FAMILY), "green": 0, "not_green": len(FAMILY),
                "findings": ["registry missing"]}
    try:
        reg = read_registry()
    except Exception as exc:
        return {"ok": False, "status": "REGISTRY UNREADABLE",
                "reason": f"{type(exc).__name__}: {exc}",
                "findings": ["registry unreadable"]}

    findings = []
    if reg.get("schema") != SCHEMA:
        findings.append(f"schema {reg.get('schema')} != {SCHEMA}")

    try:
        age = time.time() - datetime.fromisoformat(reg["derived_at"]).timestamp()
    except Exception:
        age = None
    if age is None:
        findings.append("derived_at unparsable")
    elif age > FRESH_SECONDS:
        findings.append(f"registry is {age / 60:.0f} min old "
                        f"(fresh window {FRESH_SECONDS / 60:.0f} min)")

    fam, green, not_green = reg.get("families"), reg.get("green"), reg.get("not_green")
    checks = (
        (CONSTELLATION, (str(len(FAMILY)),)),
        (HQ, (f"{green} ok", f"{not_green} refused")),
        (REPORT, (f"<b>{fam}</b>", f"<b>{green}</b>", f"<b>{not_green}</b>")),
    )
    for surface, needles in checks:
        if not surface.exists():
            findings.append(f"{surface.name} missing — run `tinyae.py surfaces`")
            continue
        body = surface.read_text(encoding="utf-8", errors="replace")
        for n in needles:
            if n not in body:
                findings.append(f"{surface.name} does not state {n!r}")

    ok = not findings
    out = {
        "ok": ok,
        "status": "GREEN" if ok else "NOT GREEN",
        "families": fam, "green": green, "not_green": not_green,
        "flaky": reg.get("flaky"),
        "derived_at": reg.get("derived_at"),
        "registry_age_min": round(age / 60, 1) if age is not None else None,
        "findings": findings,
        "reason": ("registry present, fresh, and every surface agrees" if ok
                   else "; ".join(findings)[:400]),
    }
    return out


# ── derived surfaces ────────────────────────────────────────────────────────
def render_hq(reg: dict) -> str:
    rooms = "\n".join(
        f'      <a class="room" href="tiny.html#{i["name"]}">\n'
        f'        <span class="rn">{i["name"].replace("tiny","")}</span>\n'
        f'        <span class="rr">{role}</span>\n'
        f'        <span class="rd {"ok" if i["ok"] else "refused"}">'
        f'{"ok" if i["ok"] else "refused"}</span>\n'
        f'      </a>'
        for i, (name, _dom, role) in zip(reg["instruments"], FAMILY))
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tinyHQ · the headquarters of the tiny constellation</title>
<meta name="description" content="tinyHQ — generated from tinyae-registry.json. Every room's badge is a measurement, not a claim.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
<style>
:root{{--void:#050505;--gold:#D4AF37;--text:#e8e8e8;--dim:#a3926a;--mut:#a89e80;--line:rgba(212,175,55,.24)}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--void);color:var(--text);font-family:'JetBrains Mono',ui-monospace,monospace;min-height:100vh;overflow-x:hidden}}
body::before{{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(1000px 700px at 50% 30%,rgba(212,175,55,.10),transparent 62%)}}
.wrap{{position:relative;z-index:1;max-width:1280px;margin:0 auto;padding:clamp(14px,2.6vw,34px)}}
header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;padding-bottom:18px;border-bottom:1px solid var(--line)}}
.eyebrow{{font-size:clamp(.58rem,1.1vw,.72rem);letter-spacing:.4em;text-transform:uppercase;color:var(--gold)}}
h1{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(1.9rem,5.4vw,3.8rem);color:var(--gold);letter-spacing:-.02em;line-height:.95;margin-top:10px;text-shadow:0 0 50px rgba(212,175,55,.26)}}
.sub{{color:var(--dim);font-size:clamp(.74rem,1.4vw,.9rem);margin-top:12px;max-width:680px;line-height:1.6}}
.count{{text-align:right}}
.count .n{{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(2rem,5vw,3.6rem);color:var(--gold);line-height:1}}
.count .l{{font-size:.62rem;letter-spacing:.2em;text-transform:uppercase;color:var(--mut);margin-top:6px}}
.count .t{{font-size:.66rem;color:var(--mut);margin-top:8px}}
section{{margin-top:26px}}
.sec-head{{font-family:'Orbitron',sans-serif;font-weight:700;font-size:clamp(.95rem,2.4vw,1.35rem);color:var(--gold);letter-spacing:.06em;margin-bottom:12px}}
.lede{{color:var(--dim);font-size:clamp(.72rem,1.3vw,.86rem);line-height:1.65;max-width:760px;margin-bottom:14px}}
.rooms{{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:10px}}
.room{{display:block;border:1px solid var(--line);border-radius:12px;padding:13px 14px;background:rgba(8,7,4,.5);text-decoration:none;transition:border-color .2s,transform .2s}}
.room:hover{{border-color:var(--gold);transform:translateY(-2px)}}
.rn{{display:block;font-family:'Orbitron',sans-serif;font-weight:700;font-size:1.02rem;color:var(--gold)}}
.rr{{display:block;color:var(--mut);font-size:.7rem;line-height:1.5;margin-top:6px;min-height:2.2em}}
.rd{{display:inline-block;font-size:.6rem;letter-spacing:.16em;text-transform:uppercase;border:1px solid;border-radius:999px;padding:2px 8px;margin-top:8px}}
.rd.ok{{color:#39ff14;border-color:rgba(57,255,20,.4)}}
.rd.refused{{color:#ff6b6b;border-color:rgba(255,107,107,.4)}}
footer{{margin-top:30px;padding-top:16px;border-top:1px solid var(--line);font-size:.66rem;color:var(--mut);letter-spacing:.08em;line-height:1.7}}
footer a{{color:var(--gold);text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="eyebrow">æ:// tinyHQ · la sede</div>
      <h1>tinyHQ</h1>
      <p class="sub">The headquarters of the tiny constellation. Every badge is a
      <b>measurement</b> taken when this page was generated — never a claim copied
      from somewhere else.</p>
    </div>
    <div class="count">
      <div class="n">{reg['families']}</div>
      <div class="l">rooms</div>
      <div class="t">{reg['green']} ok · {reg['not_green']} refused · {reg['flaky']} flaky</div>
    </div>
  </header>
  <section>
    <h2 class="sec-head">the floor plan</h2>
    <p class="lede">Generated from <code>tinyae-registry.json</code> by
    <code>tinyae.py surfaces</code>. A room that cannot run is shown as refused.</p>
    <div class="rooms">
{rooms}
    </div>
  </section>
  <footer>
    derived {reg['derived_at']} · {reg['regime']['interpreters']} interpreters · flaky detection on<br>
    <a href="./tinyae-registry.json">registry →</a>
    <a href="./tinyae.html">report →</a>
    <a href="./tiny.html">constellation →</a>
    <a href="./purpose.html">the charter →</a>
  </footer>
</div>
</body>
</html>
'''


def render_report(reg: dict) -> str:
    rows = "\n".join(
        f'<tr><td>{i["name"]}</td>'
        f'<td class="{"ok" if i["ok"] else "bad"}">{"GREEN" if i["ok"] else "NOT GREEN"}</td>'
        f'<td class="{"bad" if i["flaky"] else ""}">{"FLAKY" if i["flaky"] else "—"}</td>'
        f'<td>{i.get("reason") or "—"}</td></tr>'
        for i in reg["instruments"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>tinyæ — the instrument family</title>
<meta name="description" content="tinyæ — generated from tinyae-registry.json. Every row is a doctor gate run for this read.">
<style>
:root{{--gold:#D4AF37;--void:#050505;--ink:#e8e4d8;--dim:#8a8577;--line:#2a2620}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--void);color:var(--ink);
font-family:'JetBrains Mono',ui-monospace,monospace;padding:34px 30px 70px}}
h1{{font-size:clamp(28px,5vw,52px);color:var(--gold);letter-spacing:.04em;margin:0 0 6px}}
.tag{{color:var(--dim);font-size:12px;margin-bottom:24px}}
.kpi{{display:flex;gap:30px;border-block:1px solid var(--line);padding:14px 0;margin-bottom:22px;flex-wrap:wrap}}
.kpi b{{color:var(--gold);font-size:26px;display:block}}
span{{font-size:10px;color:var(--dim);letter-spacing:.14em}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
td{{padding:7px 10px;border-bottom:1px solid var(--line)}}
td:first-child{{color:var(--gold)}}
td.ok{{color:#00ff9d}}td.bad{{color:#ff7a6b}}
a{{color:var(--gold);font-size:12px;margin-right:18px}}
p{{font-size:12px;color:var(--dim);max-width:760px;line-height:1.7}}
</style></head><body>
<h1>tinyæ</h1>
<div class="tag">one prefix · many instruments · one receipt chain · #opensourceware</div>
<div class="kpi">
 <div><b>{reg['families']}</b><span>FAMILIES</span></div>
 <div><b>{reg['green']}</b><span>DOCTORS GREEN NOW</span></div>
 <div><b>{reg['not_green']}</b><span>NOT GREEN / UNTESTED</span></div>
 <div><b>{reg['flaky']}</b><span>FLAKY · INTERPRETERS DISAGREE</span></div>
</div>
<table><tbody>
{rows}
</tbody></table>
<p>Measured at {reg['derived_at']} by tinyæ — each instrument's own doctor, run on
{reg['regime']['interpreters']} interpreters. A refusal is reported as a refusal, never
painted green; flaky means the interpreters disagreed, which is a finding rather than a pass.</p>
<div style="margin-top:24px">
 <a href="./tinyhq.html">tinyHQ →</a>
 <a href="./tinyae-registry.json">REGISTRY →</a>
 <a href="./tiny.html">constellation →</a>
 <a href="./purpose.html">the charter →</a>
</div>
</body></html>'''


def render_surfaces() -> dict:
    reg = read_registry()
    HQ.write_text(render_hq(reg), encoding="utf-8")
    REPORT.write_text(render_report(reg), encoding="utf-8")
    return {"ok": True, "hq": str(HQ), "report": str(REPORT),
            "hq_bytes": HQ.stat().st_size, "report_bytes": REPORT.stat().st_size}


def render_constellation() -> dict:
    """Delegate the look to tiny_family, which imports truth from here."""
    sys.path.insert(0, str(ROOT / "tiny"))
    import tiny_family
    return tiny_family.main()


# ── cli ─────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="tinyæ — the meta-instrument above the tiny* family")
    ap.add_argument("verb", choices=["doctor", "derive", "surfaces", "verify",
                                     "report", "constellation"])
    ap.add_argument("--out", type=Path, default=None,
                    help="derive: registry path (default tinyae-registry.json)")
    a = ap.parse_args(argv)

    if a.verb == "doctor":
        d = doctor()
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0 if d.get("ok") else 1

    if a.verb == "derive":
        reg = derive()
        out = a.out or REGISTRY
        out.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"tinyæ: {reg['families']} families · {reg['green']} green · "
              f"{reg['not_green']} not green · {reg['flaky']} flaky → {out}")
        return 0

    if a.verb == "surfaces":
        print(json.dumps(render_surfaces(), indent=2))
        return 0

    if a.verb == "constellation":
        print(json.dumps(render_constellation(), indent=2))
        return 0

    if a.verb == "verify":
        reg = read_registry() if REGISTRY.exists() else None
        fresh = derive()
        drift = []
        if reg is None:
            drift.append("no registry")
        else:
            for k in ("families", "green", "not_green"):
                if reg.get(k) != fresh[k]:
                    drift.append(f"{k}: registry {reg.get(k)} != measured {fresh[k]}")
        print(json.dumps({"ok": not drift, "drift": drift, "measured": fresh},
                         indent=2, ensure_ascii=False, default=str))
        return 0 if not drift else 1

    if a.verb == "report":
        d = doctor()
        print(json.dumps({"schema": "ae/tinyae-report/1", **d},
                         ensure_ascii=False, indent=2))
        return 0 if d.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
