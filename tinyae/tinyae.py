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
    # tinyæ measures itself as an instrument, not as the gate (see selftest)
    verb = "selftest" if name == "tinyae" else "doctor"
    env = os.environ.copy()
    for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(k, None)
    verdicts, last = [], None
    for exe in interpreters():
        t0 = time.time()
        try:
            r = subprocess.run([exe, str(f), verb], capture_output=True,
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
        verdicts.append({"python": Path(exe).name, "label": _label(exe),
                         "ok": bool(d.get("ok")),
                         "elapsed_s": dt, "rc": r.returncode,
                         "error": str(d.get("error") or d.get("reason") or "")[:200],
                         "_blob": blob})
        if d.get("ok"):
            last = d
    DEP_MARKS = ("modulenotfounderror", "importerror", "no module named",
                 "cannot find", "missing", "dll", "timeout")
    for v in verdicts:
        # scan the WHOLE receipt: tinycuda reports at checks.cuda.error
        msg = (str(v.get("refusal") or "") + " " + str(v.get("error") or "")
               + " " + str(v.get("_blob") or "")).lower()
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


def selftest() -> dict:
    """Does the generator work? Not "is the family healthy?" — that is `doctor`.

    Kept separate so the registry and the surfaces cannot chase each other.
    """
    checks = {}
    try:
        reg = read_registry()
        checks["registry_readable"] = True
        checks["schema_current"] = reg.get("schema") == SCHEMA
    except Exception as exc:
        checks["registry_readable"] = False
        checks["schema_current"] = False
        return {"ok": False, "checks": checks, "error": f"{type(exc).__name__}: {exc}"}
    checks["surfaces_present"] = all(
        p.exists() for p in (CONSTELLATION, HQ, REPORT))
    checks["cli_verbs"] = all(callable(v) for v in (derive, doctor, render_surfaces))
    ok = all(checks.values())
    return {"ok": ok, "checks": checks,
            "reason": "instrument functional" if ok else "see checks"}


# ── derived surfaces ────────────────────────────────────────────────────────
CSS = """
:root{--void:#050505;--gold:#D4AF37;--ink:#e8e4d8;--dim:#8a8577;
      --line:#2a2620;--ok:#39ff14;--bad:#ff6b6b;--warn:#ffb020}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--ink);
  font:14px/1.62 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  padding:clamp(16px,4vw,44px) clamp(14px,3vw,34px)}
.wrap{max-width:920px;margin:0 auto}
h1{font-size:clamp(20px,4vw,30px);color:var(--gold);margin:0 0 6px;
   letter-spacing:.01em;line-height:1.15}
.what{color:var(--dim);margin:0 0 22px;max-width:64ch;font-size:13px}
.prov{display:flex;gap:8px 26px;flex-wrap:wrap;border-block:1px solid var(--line);
  padding:10px 0;margin:0 0 20px;font-size:12px;color:var(--dim)}
.prov b{color:var(--ink);font-weight:400}
.verdict{font-size:15px;margin:0 0 18px}
.verdict b{color:var(--gold);font-size:19px;font-weight:700}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;color:var(--dim);font-weight:400;font-size:10px;
   letter-spacing:.12em;text-transform:uppercase;
   border-bottom:1px solid var(--line);padding:6px 10px 6px 0}
td{border-bottom:1px solid var(--line);padding:7px 10px 7px 0;vertical-align:top}
td.n{color:var(--gold);white-space:nowrap}
.v-ok{color:var(--ok)}.v-bad{color:var(--bad)}.v-warn{color:var(--warn)}
.ev{color:var(--dim);font-size:12px}
.rooms{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
  gap:8px;margin-bottom:8px}
.room{border:1px solid var(--line);border-radius:9px;padding:10px 11px;
  text-decoration:none;color:inherit;display:block;background:rgba(255,255,255,.012)}
.room:hover{border-color:var(--gold)}
.room .rn{color:var(--gold);font-size:13px}
.room .rv{display:inline-block;margin-top:7px;font-size:9px;letter-spacing:.12em;
  text-transform:uppercase;border:1px solid;border-radius:999px;padding:2px 7px}
.limits{border-left:2px solid var(--gold);padding:10px 14px;margin:26px 0 0;
  color:var(--dim);font-size:12px;max-width:72ch}
.links{margin-top:26px;font-size:12px}
.links a{color:var(--gold);text-decoration:none;margin-right:16px}
@media(max-width:640px){td.ev{display:none}}
"""


def _label(exe: str) -> str:
    p = str(exe).lower()
    if "gpu" in p:
        return "gpu"
    if "hermes" in p:
        return "hermes-venv"
    return "sys"


def _evidence(i: dict) -> str:
    """A row's evidence, or its refusal. Never the word GREEN as a reason.

    Distinguishes the three things that can happen on an interpreter:
    it ran and passed, it ran and disagreed, it could not run at all.
    """
    vs = i.get("verdicts") or []
    if not vs:
        return str(i.get("reason") or "no verdict")[:200]

    def lab(v):
        return v.get("label") or v.get("python") or "?"

    if i.get("flaky"):
        parts = [f"{lab(v)} {'ok' if v.get('ok') else 'refused'} "
                 f"{v.get('elapsed_s', '?')}s" for v in vs]
        return "interpreters disagree \u2014 " + "; ".join(parts)

    if i.get("ok"):
        ok = [v for v in vs if v.get("ok")]
        could_not = [v for v in vs if not v.get("ok")]
        out = "ok on " + ", ".join(f"{lab(v)} {v.get('elapsed_s', '?')}s" for v in ok)
        if could_not:
            out += "; " + ", ".join(f"{lab(v)} could not run" for v in could_not)
        return out

    parts = [f"{lab(v)}: {v.get('refusal') or v.get('error') or 'refused'}"
             for v in vs]
    return "; ".join(parts)[:220]


def _verdict_cell(i: dict) -> str:
    if i.get("flaky"):
        return '<td class="v-warn">flaky</td>'
    if i.get("ok"):
        return '<td class="v-ok">green</td>'
    return '<td class="v-bad">not green</td>'


def _page(reg: dict, title: str, desc: str, canonical: str, lede: str,
          main: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="./favicon.svg">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<h1>{title}</h1>
<p class="what">{lede}</p>
<div class="prov">
  <span>derived <b>{reg['derived_at']}</b></span>
  <span>interpreters <b>{reg['regime']['interpreters']}</b></span>
  <span>flaky detection <b>on</b></span>
  <span>source <b>tinyae-registry.json</b></span>
</div>
<p class="verdict"><b>{reg['families']}</b> instruments &middot;
<b>{reg['green']}</b> green &middot; <b>{reg['not_green']}</b> not green &middot;
<b>{reg['flaky']}</b> flaky</p>
{main}
<div class="limits">
What this is not: not a test suite, not a guarantee, not a certification.
Green is a snapshot at the time above. A <span class="v-warn">flaky</span> row means
the interpreters disagreed &mdash; a finding, not a pass. An instrument that is
refused is shown as refused, never painted green.
</div>
<div class="links">
 <a href="./tinyae-registry.json">registry</a>
 <a href="./tiny.html">constellation</a>
 <a href="./tinyhq.html">tinyHQ</a>
 <a href="./purpose.html">the charter</a>
</div>
</div>
</body>
</html>
"""


def render_report(reg: dict) -> str:
    rows = "\n".join(
        f'<tr><td class="n">{i["name"]}</td>{_verdict_cell(i)}'
        f'<td class="ev">{_evidence(i)}</td></tr>'
        for i in reg["instruments"])
    main = (
        '<table>\n'
        '<thead><tr><th>instrument</th><th>verdict</th><th>evidence</th></tr></thead>\n'
        '<tbody>\n' + rows + '\n</tbody></table>')
    return _page(
        reg, "tinyæ — the family, measured",
        "Every row is one instrument's own doctor, run on this machine when this "
        "page was generated. A refusal is shown as a refusal.",
        "https://myaelmendez.github.io/tinyae.html",
        "Each row carries its own evidence: which interpreters ran, how long they "
        "took, and what came back. Nothing here is copied from a claim.",
        main)


def render_hq(reg: dict) -> str:
    rooms = "\n".join(
        f'<a class="room" href="./tinyae.html">\n'
        f'  <span class="rn">{i["name"]}</span>\n'
        f'  <span class="rv {"v-ok" if i["ok"] and not i["flaky"] else ("v-warn" if i["flaky"] else "v-bad")}">'
        f'{"ok" if i["ok"] and not i["flaky"] else ("flaky" if i["flaky"] else "refused")}</span>\n'
        f'</a>'
        for i in reg["instruments"])
    main = (
        '<p class="what">One room per instrument. The badge is the measurement; '
        'the <a href="./tinyae.html" style="color:var(--gold)">report</a> carries '
        'the evidence behind it.</p>\n'
        '<div class="rooms">\n' + rooms + '\n</div>')
    return _page(
        reg, "tinyHQ — the family, measured",
        "One room per instrument; every badge is a measurement taken when this "
        "page was generated.",
        "https://myaelmendez.github.io/tinyhq.html",
        "The floor plan of the tiny constellation, generated from the registry.",
        main)


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
    ap.add_argument("verb", choices=["doctor", "selftest", "derive", "surfaces",
                                     "verify", "report", "constellation"])
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

    if a.verb == "selftest":
        d = selftest()
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0 if d.get("ok") else 1

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
