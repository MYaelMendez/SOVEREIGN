#!/usr/bin/env python3
"""Apply Hostinger domain forwarding from C:\æ\store\redirect-manifest.json.

Requirements:
  set HOSTINGER_API_TOKEN in the environment.

Default mode is dry-run. Use --apply to mutate forwarding.
"""
import argparse, json, os, sys, time
from pathlib import Path
from urllib import request, error

API = "https://developers.hostinger.com"
ROOT = Path(r"C:\æ")
MANIFEST = ROOT / "store" / "redirect-manifest.json"


def api(method, path, token, body=None):
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "ignore")
            return r.status, json.loads(raw) if raw.strip() else None
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = raw
        return e.code, payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually create/update forwarding")
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--only", nargs="*", help="Limit to specific domains (unicode or punycode)")
    args = ap.parse_args()

    token = os.environ.get("HOSTINGER_API_TOKEN")
    if not token:
        raise SystemExit("HOSTINGER_API_TOKEN is not set. Refusing to read token from argv/history.")

    data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    only = {x.lower() for x in args.only or []}
    routes = data["routes"]
    if only:
        routes = [r for r in routes if r["domain"].lower() in only or r.get("unicode", "").lower() in only]

    print(f"mode={'APPLY' if args.apply else 'DRY-RUN'} routes={len(routes)} redirect_type={data.get('redirect_type','302')}")

    for r in routes:
        domain = r["domain"]
        body = {"domain": domain, "redirect_type": data.get("redirect_type", "302"), "redirect_url": r["target"]}
        print(f"\n{r.get('unicode', domain)} ({domain}) -> {r['target']}")
        status, existing = api("GET", f"/api/domains/v1/forwarding/{domain}", token)
        print(f"  current: HTTP {status}")
        if not args.apply:
            continue
        if status == 200:
            # Hostinger API exposes delete + create rather than update.
            ds, dp = api("DELETE", f"/api/domains/v1/forwarding/{domain}", token)
            print(f"  delete: HTTP {ds}")
            time.sleep(0.5)
        cs, cp = api("POST", "/api/domains/v1/forwarding", token, body)
        print(f"  create: HTTP {cs}")
        if cs not in (200, 201):
            print(f"  response: {cp}")


if __name__ == "__main__":
    main()
