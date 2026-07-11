#!/usr/bin/env python3
"""
æ domain Code Mode: one compact search/execute interface over the domain skill stack.

Usage:
  python domain_mode.py search <query>
  python domain_mode.py execute <domain-or-skill> <operation> [--json]
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
STACK = ROOT / "store" / "domain-stack.json"


def load():
    return json.loads(STACK.read_text(encoding="utf-8"))


def score(item, terms):
    hay = " ".join([
        item.get("domain", ""), item.get("punycode", ""), item.get("skill", ""),
        item.get("prompt", ""), item.get("role", ""), " ".join(item.get("operations", [])),
    ]).lower()
    return sum(1 for t in terms if t in hay)


def search(q):
    data = load()
    terms = [t.lower() for t in q.replace("/", " ").replace("#", " ").split() if t.strip()]
    rows = []
    for d in data["domains"]:
        s = score(d, terms) if terms else 1
        if s:
            rows.append((s, d))
    rows.sort(key=lambda x: (-x[0], x[1]["domain"]))
    return [{k: v for k, v in d.items() if k in ("domain", "punycode", "skill", "prompt", "role", "operations")} for _, d in rows]


def find(name):
    n = name.lower()
    for d in load()["domains"]:
        if n in {d.get("domain", "").lower(), d.get("punycode", "").lower(), d.get("skill", "").lower()}:
            return d
    hits = search(name)
    if hits:
        return hits[0]
    raise SystemExit(f"No domain skill found for: {name}")


def execute(target, op):
    d = find(target)
    op = op.lower().replace("-", "_")
    base = {
        "domain": d["domain"],
        "skill": d["skill"],
        "prompt": d["prompt"],
        "role": d["role"],
        "operation": op,
    }

    if op in {"install_skill", "publish_skill"}:
        base["result"] = {
            "unicode": "hermes skills install https://æ.store/SKILL.md",
            "punycode": "hermes skills install https://xn--6ca.store/SKILL.md",
            "host_files": ["/SKILL.md", "/agentic.html", "/domain-stack.json"],
        }
    elif op in {"naics_search", "startabusiness", "classify"}:
        import urllib.request, json as _json, os
        naics_key = os.environ.get("NAICS_API_KEY", "")
        query = "custom computer programming"
        if naics_key:
            try:
                url = f"https://api.naics.com/api/search?q={urllib.parse.quote(query)}&limit=5"
                req = urllib.request.Request(url, headers={"X-API-Key": naics_key, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    api_data = _json.loads(r.read())
                results = []
                for item in api_data.get("data", [])[:5]:
                    results.append({"code": item.get("code"), "title": item.get("title"), "description": (item.get("description") or "")[:120]})
                base["result"] = {"source": "live NAICS API", "query": query, "results": results}
            except Exception as e:
                base["result"] = {"source": "static fallback", "error": str(e)[:100], "codes": {"541511": "Custom Computer Programming Services", "541512": "Computer Systems Design Services", "541519": "Other Computer Related Services"}}
        else:
            base["result"] = {"source": "static (no NAICS_API_KEY)", "codes": {"541511": "Custom Computer Programming Services", "541512": "Computer Systems Design Services", "541519": "Other Computer Related Services", "513210": "Software Publishers", "518210": "Data Processing, Hosting, and Related Services", "541618": "Other Management Consulting Services", "611430": "Professional and Management Development Training", "541715": "R&D in Nanotechnology/Biotech/Physical/Engineering/Life Sciences"}}
    elif op in {"generate_agentic_html", "robot_app_store", "reachy_clerk"}:
        base["result"] = {
            "title": f"{d['prompt']}#startabusiness→",
            "hero": "One command. One person. Full agency.",
            "cta": "https://partnersps.doola.com/hhsoqhb23250",
            "sections": ["identity", "formation", "payments", "storefront", "compute", "routing", "interface", "trust"],
            "design": "gold-on-void, Orbitron + JetBrains Mono, neural mesh, scanlines",
        }
    elif op in {"dns_plan", "deploy_plan"}:
        puny = d.get("punycode", d["domain"])
        base["result"] = {
            "domain": d["domain"],
            "canonical_host": puny,
            "files": ["agentic.html", "SKILL.md", "domain-stack.json"],
            "verify": [f"https://{puny}/agentic.html", f"https://{puny}/SKILL.md"],
        }
    else:
        base["result"] = {
            "available_operations": d.get("operations", []),
            "note": f"Operation '{op}' is not specialized yet; use this role as prompt context: {d['role']}",
        }
    return base


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("query", nargs="*", default=[])
    e = sub.add_parser("execute"); e.add_argument("target"); e.add_argument("operation"); e.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.cmd == "search":
        print(json.dumps(search(" ".join(args.query)), ensure_ascii=False, indent=2))
    else:
        out = execute(args.target, args.operation)
        print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
