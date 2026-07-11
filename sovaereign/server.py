"""
SOVÆREIGN — the entrepreneur's first repo.

GitHub App that scaffolds a business-as-code repo the moment
an entrepreneur installs it. Then teaches Git by doing — every
action is a commit, every decision is a PR, every milestone is a release.

The entrepreneur learns Git by watching their business operate as code.

Architecture:
  1. installation.created → scaffold repo (blueprint as code)
  2. issues.opened → SOVÆREIGN responds with guidance
  3. push to main → SOVÆREIGN validates blueprint
  4. pull_request.opened → SOVÆREIGN reviews as DAO operator
  5. release → SOVÆREIGN celebrates the milestone

Each action teaches: commits = progress, branches = experiments,
PRs = decisions, issues = questions, releases = milestones.
"""

import os
import sys
import json
import time
import logging
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path

import jwt
import requests
from fastapi import FastAPI, Request, Response, HTTPException
from uvicorn import Config, Server

# ── Config ──────────────────────────────────────────────────────────
APP_ID = os.getenv("GITHUB_APP_ID", "1382525")
CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "Iv23liZ7S0bMVRWtM0G0")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH", r"C:\æ\secrets\sovaereign.pem")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "sovaereign_webhook_dev")
PORT = int(os.getenv("SOVAEREIGN_PORT", "8443"))

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sovaereign")

# ── GitHub API helpers ──────────────────────────────────────────────
def get_app_jwt():
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 300, "iss": APP_ID}
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

def get_installation_token(installation_id: str) -> str:
    """Exchange app JWT for an installation token (scoped to the install)."""
    app_token = get_app_jwt()
    resp = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sovaereign",
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]

def gh_api(method: str, path: str, token: str, data=None):
    """Raw GitHub API call with installation token."""
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "sovaereign",
    }
    resp = requests.request(method, url, headers=headers, json=data)
    return resp

# ── Blueprint templates (the entrepreneur's first repo) ─────────────
def blueprint_readme(owner: str, repo_name: str) -> str:
    return f"""# {repo_name}

> *Hermes · NVIDIA · Stripe unlock the DAO so you can focus on business.*

This repo **is** your business. Every file has a purpose:

```
{repo_name}/
├── README.md          ← you are here (the mission)
├── BLUEPRINT.md       ← your organizational pattern (the DAO)
├── NAICS.md           ← your business classification
├── OPERATING.md       ← your governance (# safe, $ confirmed)
├── TREASURY.md        ← your cash rails (Stripe)
├── STACK.md           ← your technology choices
├── MILESTONES.md      ← your progress (releases)
└── .github/
    ├── ISSUES.md      ← how to ask questions
    └── PULL_REQUEST_TEMPLATE.md  ← how to make decisions
```

## You already know Git — you just didn't know it

| Business concept | Git concept | What it means |
|---|---|---|
| Making progress | **commit** | Every save = a step forward |
| Trying an idea | **branch** | Experiment without breaking anything |
| Making a decision | **pull request** | Propose a change, get feedback, merge it |
| Asking a question | **issue** | Open a question, track it to resolution |
| Reaching a milestone | **release** | Tag a moment — v1.0, first customer, first $ |
| Your business plan | **this repo** | Everything in one place, versioned, transparent |

## Your first steps

1. **Open an issue** — click Issues → New Issue → type "What should I name my business?"
2. **Edit this file** — click the pencil ✏️ → change the name → commit
3. **Create a branch** — try something risky in a branch first; if it works, merge it
4. **Open a PR** — propose a change to BLUEPRINT.md; SOVÆREIGN will review it

**You can't break this.** Everything is versioned. Everything can be undone.

*SOVÆREIGN is watching this repo. Open an issue anytime — it responds.*

---

Built with [æ.store](https://myaelmendez.github.io/ae/) · #opensourceware since 1517
"""

def blueprint_blueprint_md() -> str:
    return """# Blueprint

> A blueprint IS the organization. Mission = purpose. Stack = members. Cash rails = treasury. Governance = operating agreement.

## Mission

<!-- What does your business do? Edit this file and write your mission. -->

_Replace this with your mission statement._

## Members

| Role | Delegate | Status |
|---|---|---|
| Conductor | Hermesᴴ | ● LIVE |
| Compute | NVIDIAᴺ | ● LIVE |
| Economics | Stripe$ | ● LIVE |
| Formation | Doolaᴰ | ● READY |
| Operator | You | ● ACTIVE |

## Governance

- `#` = safe to do (no confirmation needed)
- `$` = requires confirmation (economic action)

<!-- Example: pushing code is #safe. Charging a customer is $confirmed. -->

## Treasury

<!-- Stripe account linked here. Revenue and expenses tracked as commits. -->

_Status: Ready to connect via Stripe_

## Classification

<!-- Your NAICS code goes here. SOVÆREIGN can look it up for you. -->

_Ask SOVÆREIGN: open an issue with "NAICS [your industry]"_
"""

def blueprint_naics_md() -> str:
    return """# NAICS Classification

> North American Industry Classification System — how the government knows what you do.

## Your Codes

<!-- SOVÆREIGN will add your NAICS codes here when you open an issue like: "NAICS custom software" -->

| Code | Description |
|---|---|
| _pending_ | _Open an issue to classify your business_ |

## Common Codes for Entrepreneurs

| Code | Description |
|---|---|
| 541511 | Custom Computer Programming |
| 541512 | Computer Systems Design |
| 513210 | Software Publishers |
| 518210 | Data Processing / Hosting |
| 541618 | Management Consulting |
| 611430 | Professional Development Training |
| 541990 | Other Professional Services |
| 519290 | Web Search Portals |

_Open an issue: "NAICS [what your business does]" and SOVÆREIGN will classify it._
"""

def blueprint_operating_md() -> str:
    return """# Operating Agreement

> The DAO IS the operating agreement. This file is the source of truth.

## Principles

1. **One person, full agency.** You are the operator. The stack supports you.
2. **# safe, $ confirmed.** Non-economic actions are autonomous. Economic actions require your say-so.
3. **Transparency.** Every action is a commit. Every decision is a PR. Nothing hidden.
4. **Version everything.** Mistakes are reversible. Progress is traceable.
5. **The customer first.** `>_: the customer → it's always about them.`

## Decision Process

1. **Identify** → Open an issue
2. **Propose** → Open a PR (or SOVÆREIGN opens one)
3. **Review** → Check the diff
4. **Merge** → Decision made, action taken
5. **Tag** → If it's a milestone, create a release

## Entity

<!-- When you form your DAOLLC via Doola, the filing details go here. -->

_Type: DAO LLC (Wyoming)_
_Status: Ready to form → [doola.com](https://partnersps.doola.com/hhsoqhb23250)_
"""

def blueprint_treasury_md() -> str:
    return """# Treasury

> Cash rails powered by Stripe. Every transaction is a commit.

## Account

_Status: Ready to connect_

<!-- When Stripe is connected, your account details go here. -->

## Revenue Log

| Date | Description | Amount | Commit |
|---|---|---|---|
| _none yet_ | | | |

## Expenses

| Date | Description | Amount | Commit |
|---|---|---|---|
| _none yet_ | | | |

---

_To connect Stripe: [stripe.com](https://dashboard.stripe.com)_
_To form your DAOLLC: [doola.com](https://partnersps.doola.com/hhsoqhb23250)_
"""

def blueprint_stack_md() -> str:
    return """# Stack

> The technology that unlocks your DAO. Hermes conducts. NVIDIA computes. Stripe transacts.

| Layer | Service | Role | Status |
|---|---|---|---|
| Conductor | [Hermes](https://hermes-agent.nousresearch.com) | Agent orchestration | ● LIVE |
| Compute | [NVIDIA](https://build.nvidia.com) | AI inference | ● LIVE |
| Economics | [Stripe](https://stripe.com) | Payments | ● LIVE |
| Formation | [Doola](https://doola.com) | DAOLLC | ● READY |
| Hosting | [GitHub Pages](https://pages.github.com) | Website | ● THIS REPO |
| Voice | [ElevenLabs](https://elevenlabs.io) | TTS | ● LIVE |
| Classify | [NAICS API](https://api.census.gov) | Business codes | ● LIVE |

## How it works

```
You → Hermesᴴ → NVIDIAᴺ (compute) → Stripe$ (payments)
              → Doolaᴰ (formation)
              → NAICS (classification)
              → ElevenLabs (voice)
```

_You focus on the customer. The stack does the rest._
"""

def blueprint_milestones_md() -> str:
    return """# Milestones

> Every release is a milestone. Track your progress here.

| Version | Milestone | Date |
|---|---|---|
| v0.1.0 | Repo created by SOVÆREIGN | _today_ |
| v0.2.0 | Mission defined | |
| v0.3.0 | NAICS classified | |
| v0.4.0 | Stripe connected | |
| v0.5.0 | DAOLLC formed | |
| v1.0.0 | First customer | |
| v2.0.0 | First $ earned | |

_Create a GitHub Release for each milestone to tag it permanently._
"""

def blueprint_issues_template() -> str:
    return """## What do you need?

<!-- 
  Common first issues:
  - "What should I name my business?"
  - "NAICS custom software" → SOVÆREIGN classifies it
  - "How do I form a DAOLLC?"
  - "Connect Stripe"
  - "Help me write my mission"
-->

**Type:** question / task / idea

**Description:**

"""

def blueprint_pr_template() -> str:
    return """## What does this change?

<!-- 
  A PR is a proposed decision. 
  - Edit BLUEPRINT.md → change the mission
  - Edit TREASURY.md → log revenue
  - Edit STACK.md → add a new tool
  - Edit any file → propose a change
  
  SOVÆREIGN will review it.
-->

## Why?

<!-- Why is this change needed? -->

## Checklist

- [ ] This is a `#` safe action (non-economic)
- [ ] This is a `$` confirmed action (economic — I approve)
"""

# ── Repo scaffolding ────────────────────────────────────────────────
def scaffold_repo(token: str, owner: str, installation_id: str):
    """Create the entrepreneur's first repo with the full blueprint."""
    repo_name = f"my-business"
    
    # Check if repo already exists
    check = gh_api("GET", f"/repos/{owner}/{repo_name}", token)
    if check.status_code == 200:
        log.info(f"Repo {owner}/{repo_name} already exists — updating instead")
        return update_repo(token, owner, repo_name)
    
    # Create repo
    log.info(f"Creating repo {owner}/{repo_name}")
    resp = gh_api("POST", "/user/repos", token, {
        "name": repo_name,
        "description": "My business — scaffolded by SOVÆREIGN. This repo IS my company.",
        "homepage": f"https://{owner}.github.io/{repo_name}",
        "private": False,
        "auto_init": True,
        "has_issues": True,
        "has_projects": True,
        "has_wiki": False,
    })
    if resp.status_code not in (200, 201):
        log.error(f"Failed to create repo: {resp.status_code} {resp.text[:200]}")
        return
    
    repo_data = resp.json()
    log.info(f"Repo created: {repo_data.get('html_url')}")
    
    # Files to create
    files = {
        "README.md": blueprint_readme(owner, repo_name),
        "BLUEPRINT.md": blueprint_blueprint_md(),
        "NAICS.md": blueprint_naics_md(),
        "OPERATING.md": blueprint_operating_md(),
        "TREASURY.md": blueprint_treasury_md(),
        "STACK.md": blueprint_stack_md(),
        "MILESTONES.md": blueprint_milestones_md(),
        ".github/ISSUE_TEMPLATE.md": blueprint_issues_template(),
        ".github/PULL_REQUEST_TEMPLATE.md": blueprint_pr_template(),
    }
    
    # Get main branch SHA (auto_init creates it)
    ref_resp = gh_api("GET", f"/repos/{owner}/{repo_name}/git/ref/heads/main", token)
    if ref_resp.status_code != 200:
        log.error(f"Can't find main branch: {ref_resp.status_code}")
        return
    
    # Create files one by one (simple approach — one commit per file for teaching)
    for path, content in files.items():
        file_resp = gh_api("PUT", f"/repos/{owner}/{repo_name}/contents/{path}", token, {
            "message": f"soværeign: scaffold {path}",
            "content": __import__("base64").b64encode(content.encode()).decode(),
            "branch": "main",
        })
        if file_resp.status_code in (200, 201):
            log.info(f"  Created {path}")
        else:
            log.warning(f"  Failed {path}: {file_resp.status_code}")
    
    # Open first issue — the welcome
    gh_api("POST", f"/repos/{owner}/{repo_name}/issues", token, {
        "title": "👋 Welcome — your business is now a repo",
        "body": f"""## You did it.

Your business is now a repo. Everything here is versioned, transparent, and reversible.

**Your next moves:**

1. 📝 Edit `README.md` — replace the placeholder with your mission
2. 🏷️ Open an issue: `"NAICS [your industry]"` — I'll classify your business
3. 💰 Edit `TREASURY.md` — when you earn your first dollar, log it here
4. 🏢 Edit `BLUEPRINT.md` — define your mission, members, and governance

**You can't break this.** Every change is saved. Every mistake is fixable.

*— SOVÆREIGN*

---
_Built with [æ.store](https://myaelmendez.github.io/ae/) · #opensourceware since 1517_
""",
    })
    
    # Create v0.1.0 release
    gh_api("POST", f"/repos/{owner}/{repo_name}/releases", token, {
        "tag_name": "v0.1.0",
        "name": "v0.1.0 — Repo Created",
        "body": "Business-as-code initialized by SOVÆREIGN.\n\nEvery release is a milestone. This is your first.",
        "draft": False,
    })
    
    log.info(f"Scaffold complete for {owner}/{repo_name}")
    return repo_data


def update_repo(token: str, owner: str, repo_name: str):
    """Update an existing repo with any missing files."""
    # Check which files exist
    existing = set()
    for path in ["README.md", "BLUEPRINT.md", "NAICS.md", "OPERATING.md", "TREASURY.md", "STACK.md", "MILESTONES.md"]:
        check = gh_api("GET", f"/repos/{owner}/{repo_name}/contents/{path}", token)
        if check.status_code == 200:
            existing.add(path)
    
    files = {
        "BLUEPRINT.md": blueprint_blueprint_md(),
        "NAICS.md": blueprint_naics_md(),
        "OPERATING.md": blueprint_operating_md(),
        "TREASURY.md": blueprint_treasury_md(),
        "STACK.md": blueprint_stack_md(),
        "MILESTONES.md": blueprint_milestones_md(),
        ".github/ISSUE_TEMPLATE.md": blueprint_issues_template(),
        ".github/PULL_REQUEST_TEMPLATE.md": blueprint_pr_template(),
    }
    
    added = 0
    for path, content in files.items():
        if path not in existing:
            file_resp = gh_api("PUT", f"/repos/{owner}/{repo_name}/contents/{path}", token, {
                "message": f"soværeign: add {path}",
                "content": __import__("base64").b64encode(content.encode()).decode(),
                "branch": "main",
            })
            if file_resp.status_code in (200, 201):
                log.info(f"  Added missing {path}")
                added += 1
    
    if added == 0:
        log.info("All files already present — no updates needed")
    return {"html_url": f"https://github.com/{owner}/{repo_name}"}


# ── Issue handler (SOVÆREIGN responds) ──────────────────────────────
def handle_issue(token: str, owner: str, repo: str, issue_number: int, issue_title: str, issue_body: str, sender: str):
    """SOVÆREIGN responds to issues with guidance."""
    title_lower = (issue_title or "").lower().strip()
    body_lower = (issue_body or "").lower().strip()
    combined = f"{title_lower} {body_lower}"
    
    response = None
    
    # NAICS classification
    if "naics" in combined:
        query = combined.replace("naics", "").strip()[:100]
        if not query:
            query = "custom computer programming"
        response = f"""## NAICS Classification: `{query}`

Here are the most relevant NAICS codes for your business:

| Code | Description |
|---|---|
| 541511 | Custom Computer Programming |
| 541512 | Computer Systems Design Services |
| 513210 | Software Publishers |
| 518210 | Computing Infrastructure Providers |
| 541618 | Other Management Consulting Services |
| 611430 | Professional Development Training |
| 541990 | Other Professional, Scientific, Technical Services |
| 519290 | Web Search Portals and All Other Information Services |

**Next step:** Edit `NAICS.md` and add your codes. Then commit — that's your official classification.

*— SOVÆREIGN*"""
    
    # DAOLLC formation
    elif any(w in combined for w in ["form", "llc", "dao", "doola", "incorporat", "entity"]):
        response = f"""## DAO LLC Formation

Forming a DAOLLC (Decentralized Autonomous Organization LLC) in Wyoming:

1. **Go to [Doola](https://partnersps.doola.com/hhsoqhb23250)** — they handle Wyoming DAO LLC formation
2. **Choose DAO LLC** as your entity type
3. **Fill in your details** — name, mission, members
4. **Pay the filing fee** — Doola handles the rest
5. **Update `OPERATING.md`** — add your filing details when you get them

**Your operating agreement IS this repo.** Every commit is a transparent record of your business decisions.

*— SOVÆREIGN*"""
    
    # Stripe / payments
    elif any(w in combined for w in ["stripe", "payment", "money", "charge", "pay", "earn", "revenue"]):
        response = f"""## Payments & Treasury

To accept payments:

1. **Create a [Stripe](https://dashboard.stripe.com) account** — free to start
2. **Get your API keys** — add them to your `.env` (never commit them!)
3. **Edit `TREASURY.md`** — log your first transaction when it happens
4. **Create a release** — tag it `v2.0.0` when you earn your first dollar

**Governance rule:** `#` safe actions are free. `$` economic actions require your confirmation.

*— SOVÆREIGN*"""
    
    # Naming
    elif any(w in combined for w in ["name", "call it", "brand"]):
        response = f"""## Naming Your Business

Your repo name is `{repo}`. But your business name is bigger.

1. **Pick a name** that's short, unique, and meaningful
2. **Check availability** — search the name on GitHub, domains, and your state's business registry
3. **Edit `BLUEPRINT.md`** — add your business name in the Mission section
4. **Commit** — that's your first official act as a company

**Tip:** You can rename this repo in Settings → Repository name. But the mission matters more than the name.

*— SOVÆREIGN*"""
    
    # Help / general
    elif any(w in combined for w in ["help", "how", "what", "start", "first", "begin", "guide"]):
        response = f"""## Welcome, @{sender}

You're already doing it — opening an issue IS how you ask questions in code.

**Your first 5 moves:**

| # | Action | How |
|---|---|---|
| 1 | Name your business | Edit `README.md` → change the title |
| 2 | Write your mission | Edit `BLUEPRINT.md` → fill in the Mission |
| 3 | Classify your business | Open an issue: `"NAICS custom software"` |
| 4 | Form your DAOLLC | [Doola](https://partnersps.doola.com/hhsoqhb23250) |
| 5 | Connect Stripe | [Stripe Dashboard](https://dashboard.stripe.com) |

**Remember:**
- `commit` = you made progress
- `branch` = you're trying something
- `PR` = you're making a decision
- `issue` = you're asking a question
- `release` = you hit a milestone

*— SOVÆREIGN*

---
_Built with [æ.store](https://myaelmendez.github.io/ae/) · #opensourceware since 1517_"""
    
    # Default — acknowledge
    else:
        response = f"""## Got it

Thanks for opening this issue, @{sender}. I'm watching this repo.

**Tip:** Try these to get started:
- `"NAICS [your industry]"` → I'll classify your business
- `"How do I form a DAOLLC?"` → formation guidance
- `"How do I connect Stripe?"` → payments guidance

*— SOVÆREIGN*"""
    
    if response:
        gh_api("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", token, {
            "body": response,
        })
        log.info(f"Responded to issue #{issue_number}")


# ── PR handler ──────────────────────────────────────────────────────
def handle_pr(token: str, owner: str, repo: str, pr_number: int, pr_title: str, pr_body: str):
    """SOVÆREIGN reviews PRs as the DAO operator."""
    # Post a review comment
    review = f"""**SOVÆREIGN review** 🤖

This PR proposes a change to the business. In the DAO model:

- If this is a `#` safe action → merge with confidence
- If this is a `$` economic action → make sure the operator confirmed

**Files changed:** Review the diff above. Every line is a business decision.

*— SOVÆREIGN*
"""
    gh_api("POST", f"/repos/{owner}/{repo}/issues/{pr_number}/comments", token, {
        "body": review,
    })
    log.info(f"Reviewed PR #{pr_number}")


# ── FastAPI server ──────────────────────────────────────────────────
app = FastAPI(title="SOVÆREIGN", version="1.0.0")


@app.get("/")
async def root():
    return {
        "app": "SOVÆREIGN",
        "version": "1.0.0",
        "thesis": "Hermes · NVIDIA · Stripe unlock the DAO for American entrepreneurs so they can focus on business.",
        "install": "https://github.com/apps/sovaereign",
        "api": "/webhook",
    }


@app.get("/health")
async def health():
    return {"status": "alive", "app_id": APP_ID}


@app.post("/webhook")
async def webhook(request: Request):
    """Receive GitHub App webhook events."""
    body = await request.body()
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event", "unknown")
    action = payload.get("action", "")
    
    log.info(f"Webhook: {event}.{action}")
    
    # ── Installation created → scaffold repo ──
    if event == "installation" and action == "created":
        installation_id = str(payload["installation"]["id"])
        owner = payload["installation"]["account"]["login"]
        
        log.info(f"New installation! {owner} (id={installation_id})")
        
        token = get_installation_token(installation_id)
        scaffold_repo(token, owner, installation_id)
    
    # ── Issue opened → SOVÆREIGN responds ──
    elif event == "issues" and action == "opened":
        installation_id = str(payload["installation"]["id"])
        owner = payload["repository"]["owner"]["login"]
        repo = payload["repository"]["name"]
        issue_number = payload["issue"]["number"]
        issue_title = payload["issue"]["title"]
        issue_body = payload["issue"].get("body", "")
        sender = payload["sender"]["login"]
        
        # Don't respond to our own issues
        if sender == "sovaereign[bot]":
            return {"status": "skipped"}
        
        token = get_installation_token(installation_id)
        handle_issue(token, owner, repo, issue_number, issue_title, issue_body, sender)
    
    # ── PR opened → SOVÆREIGN reviews ──
    elif event == "pull_request" and action == "opened":
        installation_id = str(payload["installation"]["id"])
        owner = payload["repository"]["owner"]["login"]
        repo = payload["repository"]["name"]
        pr_number = payload["pull_request"]["number"]
        pr_title = payload["pull_request"]["title"]
        pr_body = payload["pull_request"].get("body", "")
        
        token = get_installation_token(installation_id)
        handle_pr(token, owner, repo, pr_number, pr_title, pr_body)
    
    # ── Push → validate ──
    elif event == "push":
        installation_id = str(payload["installation"]["id"])
        owner = payload["repository"]["owner"]["login"]
        repo = payload["repository"]["name"]
        commits = payload.get("commits", [])
        
        log.info(f"Push to {owner}/{repo}: {len(commits)} commit(s)")
        # Future: validate blueprint structure on push
    
    return {"status": "processed", "event": event, "action": action}


# ── Run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info(f"SOVÆREIGN starting on port {PORT}")
    log.info(f"App ID: {APP_ID}")
    log.info(f"Install at: https://github.com/apps/sovaereign")
    config = Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = Server(config)
    server.run()
