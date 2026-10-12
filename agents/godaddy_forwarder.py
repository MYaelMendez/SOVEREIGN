"""
æ://godaddy_forwarder.py
Redirect all GoDaddy domains to aipodcast.me via 301 forwarding.

Usage:
  python godaddy_forwarder.py --domains cli.llc commandprompt.ai ... --target aipodcast.me

Reads credentials from C:/æ/secrets/godaddy.json (never bakes secrets into code).
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

SECRETS_PATH = "C:/æ/secrets/godaddy.json"
GODADDY_API = "https://api.godaddy.com/v1/domains"


def load_credentials():
    if not os.path.exists(SECRETS_PATH):
        print(f"ERROR: secrets file not found at {SECRETS_PATH}")
        print("Create it with: {\"api_key\": \"...\", \"api_secret\": \"...\"}")
        sys.exit(1)
    with open(SECRETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def godaddy_request(method, url, headers, data=None):
    if data is not None:
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, {"error": body}


def set_forwarding(domain, target, creds):
    """Set 301 permanent forwarding for a domain."""
    url = f"{GODADDY_API}/{urllib.parse.quote(domain, safe='')}"
    headers = {
        "Authorization": f"sso-key {creds['api_key']}:{creds['api_secret']}",
        "Accept": "application/json",
    }

    # First, get current domain info to check if it exists
    status, body = godaddy_request("GET", url, headers)
    if status == 404:
        print(f"  SKIP: {domain} not found in GoDaddy account")
        return False
    if status != 200:
        print(f"  ERROR: {domain} → HTTP {status}: {body.get('message', body)}")
        return False

    # Set forwarding via PATCH
    # GoDaddy API: PUT /v1/domains/{domain} with forwarding config
    forward_data = {
        "forwarding": {
            "type": "permanent",
            "target": f"https://{target}",
            "masking": False,
        }
    }
    status, body = godaddy_request("PATCH", url, headers, forward_data)
    if status in (200, 204):
        print(f"  OK: {domain} → https://{target} (301)")
        return True
    else:
        print(f"  FAIL: {domain} → HTTP {status}: {body.get('message', body)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="æ:// GoDaddy domain forwarder")
    parser.add_argument("--domains", nargs="+", required=True, help="List of domains to forward")
    parser.add_argument("--target", default="aipodcast.me", help="Target domain")
    args = parser.parse_args()

    creds = load_credentials()
    print(f"Forwarding {len(args.domains)} domains → {args.target}\n")

    success = 0
    for domain in args.domains:
        if set_forwarding(domain, args.target, creds):
            success += 1

    print(f"\n{'='*50}")
    print(f"Result: {success}/{len(args.domains)} domains forwarded")
    if success < len(args.domains):
        sys.exit(1)


if __name__ == "__main__":
    main()