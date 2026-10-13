#!/usr/bin/env python3
"""Daily podcast social feed gatherer.

Gathers social media posts (X/Twitter #schoolofhermes, Bluesky) as guidance
for a daily podcast episode. Feeds are stored as structured JSON for the
daily-cron spec engine.

Sources (in priority order):
  1. X/Twitter @yaelmendez and @schoolofhermes via web_search (no API key configured)
  2. Bluesky via atproto-private-client (BSKY_AGENT_<NAME> pattern)

Output: scripts/cron/social-feeds-<date>.json
"""

import json, os, sys, subprocess, hashlib, datetime, warnings
from pathlib import Path

ROOT = Path(r"C:\æ")
SITE = ROOT / "site" / "aipodcast_me"
SPECS = ROOT / "studio" / "specs"
OUTPUT = ROOT / "studio" / "output"
SCRIPTS = ROOT / "scripts" / "cron"
FEEDS_DIR = SCRIPTS / "feeds"
SECRETS = ROOT / "secrets"
AGENTS = ROOT / "agents"

# Ensure dirs
FEEDS_DIR.mkdir(parents=True, exist_ok=True)

# Load local secrets (never expose in transcript)
def load_secret(key):
    """Load a secret from C:/æ/secrets/secrets.json. Returns [REDACTED] marker."""
    secrets_file = SECRETS / "secrets.json"
    if not secrets_file.exists():
        return "[REDACTED]"
    try:
        data = json.loads(secrets_file.read_text(encoding="utf-8"))
        return data.get(key, "[REDACTED]")
    except Exception:
        return "[REDACTED]"

# X/Twitter handle from vault
BSKY_HANDLE = load_secret("BSKY_AGENT_aipodcast")
X_HANDLE = load_secret("X_API_KEY") or "@yaelmendez"

# Web search for X/Twitter #schoolofhermes
def fetch_x_tweets(hashtag="#schoolofhermes", max_results=20):
    """Fetch recent X/Twitter posts mentioning #schoolofhermes via web_search.

    Returns list of {date, author, text, url, confidence}
    """
    import urllib.parse
    queries = [
        f'{hashtag} site:x.com',
        f'~{hashtag} twitter X post',
        f"schoolofhermes X thread",
        f"#schoolofhermes philosophy",
        f"schoolofhermes daily podcast",
    ]
    results = []
    for q in queries[:4]:
        try:
            r = subprocess.run(
                ['python3', '-c', """
import sys, json
from hermes_tools import web_search
results = web_search(%s, limit=3)
for item in results.get("data", {}).get("web", []):
    print(json.dumps({
        "url": item.get("url", ""),
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "query": %s
    }))
""" % (q, q)], capture_output=True, text=True, timeout=15)
            for line in r.stdout.strip().splitlines():
                if line.strip():
                    try:
                        item = json.loads(line)
                        results.append({
                            "date": datetime.date.today().isoformat(),
                            "author": "web_search",
                            "text": f'{item.get("title", "")} {item.get("description", "")}',
                            "url": item.get("url", ""),
                            "confidence": "inferred"
                        })
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            warnings.warn(f"web_search failed: {e}")
            pass
    return results[:max_results]

# Bluesky feed via atproto (if configured)
def fetch_bluesky_feed(handle=BSKY_HANDLE, max_results=10):
    """Fetch recent Bluesky posts from configured agent handle.

    Uses the atproto-private-client packages directly via node.
    """
    if not BSKY_HANDLE or BSKY_HANDLE == "[REDACTED]":
        return []
    try:
        # Use the atproto client directly via node (JSON-RPC over https)
        script = f'''
const {{
    BskyAgent
}} = require('/c/æ/atproto-private-client/packages/bsky/src/index.js');
const handle = process.argv[1];
const agent = new BskyAgent({{ service: 'https://bsky.social' }});
(async () => {{
    try {{
        const profile = await agent.getProfile(handle);
        console.log(JSON.stringify({{ profile, handle }}));
    }} catch (e) {{
        console.log(JSON.stringify({{ error: e.message }}));
    }}
}})();
'''
        r = subprocess.run(
            ['node', '-e', script, BSKY_HANDLE],
            capture_output=True, text=True, timeout=15,
            cwd='/c/æ/atproto-private-client'
        )
        if r.returncode == 0 and r.stdout.strip():
            parsed = json.loads(r.stdout.strip())
            if 'error' not in parsed:
                return [{
                    "date": datetime.date.today().isoformat(),
                    "author": "Bluesky",
                    "text": f"Bluesky agent: {parsed.get('handle')}",
                    "url": f"https://bsky.social/profile/{handle}",
                    "confidence": "verified"
                }]
    except Exception as e:
        warnings.warn(f"Bluesky fetch failed: {e}")
        pass
    return []

def gather_feed(hashtag="#schoolofhermes", max_x=20, max_bsky=10):
    """Gather all available social posts. Returns structured feed."""
    x_tweets = fetch_x_tweets(hashtag, max_x)
    bsky_posts = fetch_bluesky_feed(max_results=max_bsky)
    feed = {
        "source": "daily-pod-social-gatherer",
        "date": datetime.date.today().isoformat(),
        "x_tweets": x_tweets,
        "bluesky_posts": bsky_posts,
        "total": len(x_tweets) + len(bsky_posts)
    }
    return feed

def compute_receipt(data):
    """Compute SHA-256 receipt for the gathered feed."""
    raw = json.dumps(data, sort_keys=True, separators=(',',':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gather social media posts for daily podcast")
    parser.add_argument("--source", default="auto", choices=["auto", "x", "bsky"])
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"Gathering social feed for {datetime.date.today().isoformat()}...")
    feed = gather_feed()
    feed["x_tweets_count"] = len(feed["x_tweets"])
    feed["bluesky_posts_count"] = len(feed["bluesky_posts"])
    feed["receipt"] = compute_receipt(feed)

    out_file = args.output or FEEDS_DIR / f"feeds-{feed['date']}.json"
    out_file.write_text(json.dumps(feed, indent=2), encoding="utf-8")

    print(f"  X tweets: {feed['x_tweets_count']}")
    print(f"  Bluesky posts: {feed['bluesky_posts_count']}")
    print(f"  Receipt: {feed['receipt'][:16]}...")
    print(f"  Saved: {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
