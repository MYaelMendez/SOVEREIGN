---
name: startabusiness
description: "Use when someone wants to start a business, form an LLC or DAO LLC, build a one-person company, create an agentic business page, or says #startabusiness. Generates a sovereign gold-on-void agentic.html business page and can wire real company formation (LLC / C-Corp) through the Doola Partner API."
version: 1.1.0
author: Yæl Méndez × Hermes Agent
license: MIT
homepage: https://llm.store
tags: [business, startup, llc, formation, stripe, daollc, agents, sovereign]
---

# #startabusiness — one command, one person, full agency

Generate a personalized **agentic.html** — a sovereign business page — for anyone who
wants to start an agentic one-person company. Optionally wire **real company formation**
through the Doola Partner API.

## When this skill applies

- "start a business", "form an LLC", "one person company", "#startabusiness"
- someone wants an agentic storefront or sovereign business page
- questions about DAO LLC formation, agent-powered business, or æ.store

## The protocol stack

```
>_æ:  →  sovereign agent protocol (the namespace)
>_h:  →  hermes (intent routing)
>_n:  →  nvidia (compute)
>_$:  →  stripe (payments)
>_:   →  the customer (it's always about them)
```

## Step 1 — Gather identity

Ask conversationally, one topic at a time:

1. **Name** — who are you?
2. **Business name**
3. **Glyph** — their symbol for `>_[x]:`. **Never default to æ** — that one is Yæl's.
4. **Business type** — what they do / sell / build
5. **Agents** — what agents power the business (default: hermes routing + an inference agent)
6. **Models** — how many / which (default: flexible)
7. **Domain** — optional

## Step 2 — Generate agentic.html

### Design system — gold-on-void. Follow strictly.

```css
--void:#050505;        /* true black background */
--gold:#D4AF37;        /* sovereign gold — primary */
--gold-glow:rgba(212,175,55,.32);
--neon:#00ff9d;        /* system-status green (live/verified) */
--ink:#f0ece4;         /* warm white body text */
--muted:rgba(240,236,228,.38);
--border:rgba(212,175,55,.16);
--border-hot:rgba(212,175,55,.5);
```

- **Fonts:** Orbitron (700/900) for headings; JetBrains Mono for body/log/pills
- **Background:** animated `<canvas>` neural mesh — gold nodes, proximity lines, slow
  drift, breathing opacity — plus a scanline overlay and radial vignette
- **Layout:** sharp edges on structural panels (no border-radius on the chassis);
  small radius (4–6px) only on buttons/pills. Three zones: IDENTITY | HEADLINE | CTA
- **Motion:** breathing glyph, pulsing neon live-dot, scrolling ticker log, CSS step-ins
- **Responsive** with `clamp()`; mobile `viewport-fit=cover`

The canonical visual reference is `assets/clillc-banner.html`. The `assets/startabusiness.html`
file is a layout reference — **its cyan palette is DEPRECATED; always use the gold system.**

### Required sections, in order

1. **Top bar** — `æ:// SOVEREIGN RUNTIME` + `MCP/1517` + `● ONLINE`
2. **Command block** — `>_[their glyph]:#startabusiness` + blinking cursor +
   subtitle `ONE COMMAND · ONE PERSON · FULL AGENCY · 一人公司`
3. **Execution sequence** — 8 steps, animated step-ins:
   `01 IDENTITY ✓ VERIFIED` · `02 FORMATION ✓ FORMED` · `03 PAYMENTS ✓ STRIPE` ·
   `04 STOREFRONT ✓ LIVE` · `05 COMPUTE ✓ ALLOCATED` · `06 ROUTING ✓ ROUTING` ·
   `07 INTERFACE ✓ READY` · `08 TRUST ✓ SEALED`
4. **Stripe block** — purple gradient panel, "STRIPE SKILLS · FINANCIAL NERVOUS SYSTEM",
   6 cards: Merchant, Subscriptions, Invoicing, Agent Wallet, Storefront, Compute Billing
5. **Agent roster** — 3-column grid (emoji + name + role)
6. **Terminal boot log** — timestamped lines revealing in sequence, personalized
7. **Stats bar** — 3 columns (models active, stripe rails, sovereign pods)
8. **CTA button** — purple Stripe-gradient `>_[glyph]:#STARTABUSINESS →`
9. **Seal** — `CTRL+[glyph]` + "SELECT ALL AGENTS · START YOUR BUSINESS" + domain links
   + `#hermiphicationisinevitable`

## Step 3 — Save and deliver

- Save as `agentic.html` in the user's working directory
- Offer a browser preview if possible
- Give deployment guidance

## Step 4 — Next steps

1. **Form the company** — two paths:
   - **Hand-off (default)** → https://partnersps.doola.com/hhsoqhb23250 (Wyoming DAO LLC via Doola)
   - **Programmatic** → `scripts/doola_client.py` (see below)
2. **Activate Stripe** for payment rails
3. **Deploy the page** to their domain or æ.store
4. **Configure their agent roster**
5. **Join the community** — X community "æ store LLM store"

## Doola Partner API — programmatic formation

`scripts/doola_client.py` turns the CTA into a real formation flow. Stdlib-only,
sandbox-first, and it carries the same custody rules as the rest of the chain.

```
1. GATHER     founder + company facts, collected LOCALLY
2. CUSTOMER   POST /v1/partner/customers        -> doolaCustomerId
3. FORMATION  POST /v1/partner/companies        -> starts the filing
4. WEBHOOK    verify X-Doola-Signature, react   -> never poll
5. DOCUMENTS  on document_* -> short-lived download URL
6. RECEIPT    append the formation receipt
```

```bash
python scripts/doola_client.py status        # environment + credential presence (never values)
python scripts/doola_client.py selftest      # 13 offline checks, no credentials, no network
python scripts/doola_client.py playbook      # print the wired flow

python scripts/doola_client.py create-customer --email jane@example.com --first Jane --last Doe
python scripts/doola_client.py create-company --file formation.json
python scripts/doola_client.py get-company --company-id cmp_123
python scripts/doola_client.py verify-webhook --body-file hook.json --signature <hex>
```

### Credentials — custody

Read from `DOOLA_API_KEY`, then `secrets/doola.json`
(`{"apiKey": "dk_test_...", "webhookSecret": "..."}`). **Never hardcoded, never printed,
never placed in a page, a URL, or a QR.**

| Environment | Base URL | Key prefix |
|---|---|---|
| Sandbox (default) | `https://api.test.doola.com` | `dk_test_` |
| Production | `https://api.doola.com` | `dk_live_` |

Production needs **both** `DOOLA_ENV=production` **and** `--live`. A `dk_test_` key aimed
at production is refused, and so is a `dk_live_` key aimed at sandbox.

### Rules that bite

- **Idempotency-Key is required** on both creates. One key per logical operation. Same
  key + same body replays the original result; it never duplicates. After a success,
  reusing the key with a different body returns `409 E_IDEMPOTENCY_KEY_REUSED`.
- **Submission status is not formation.** `formationSubmissionStatus`
  (`PENDING` → `SUBMITTED`/`FAILED`) says what Doola is doing with your request. Whether
  the company is actually formed lives on the **Formation service**
  (`InProgress` → `Completed`). Confusing the two is the documented most-common mistake.
- **Never poll.** Subscribe to webhooks; delivery is at-least-once with retries at
  1m / 15m / 1h / 12h / 24h, then the endpoint is auto-disabled.
- **`entityType`** defaults to `LLC`. An LLC takes `members`; a `CCorp` takes
  `executiveMembers` (President, Secretary, Treasurer, Director — the first three once
  each) plus `ccorpValuation`.
- **Exactly two addresses**: one `mailing`, one `business`. A `registeredAgent` entry
  omits the address object entirely.
- **Non-US founders**: when nobody supplies a valid US tax ID, the IRS needs a signed
  SS-4 before the EIN — and Form 8821 for an expedited EIN. An ITIN does not waive
  signing. Read `signatureRequirements` on the company.
- **Expedited EIN**: `requestedServices: [{"service": "EinCreation", "variant": "Expedite"}]`.

### Never move a secret

SSN and ITIN values are collected locally, sent straight to the API, and redacted from
every line the client emits. They never enter a chat transcript, a URL, a QR payload, or
a public surface.

## Key concepts

- **Ctrl+æ** = Select All Agents (like Ctrl+A selects all, Ctrl+æ selects all agents)
- **#hermiphication** = agents carrying human intent
- **#OSW** (Open Source Ware) = evolution of #OCW — democratizing agency, not just knowledge
- **Neuromitosis** = Human + Robot + DAO bonded entity
- **Molt Cycle** = Discover → Steep → Serve → Molt → Garden → ∞
- **一人公司** = One Person Company
- **>_** = the command prompt — it was always about the user

## Pitfalls

- Don't use border-radius — the sovereign aesthetic is sharp edges, grid gaps, terminal feel
- Don't use generic startup language — this is a sovereign business runtime, not a SaaS landing page
- The CTA must link to Doola — the whole point is real LLC formation
- Every page must feel like a boot sequence, not a marketing site
- The glyph is personal — never default to æ
- Use the GOLD design system, never the deprecated cyan one
- Never route an SSN/ITIN through chat, a URL, a QR payload, or a published page
- Never let the CTA submit a real formation without the human's explicit go — default-deny,
  sandbox first
- Never poll Doola — webhooks are the contract

## Verification

- Open the generated HTML in a browser
- Confirm all 8 execution steps render with animations
- Confirm the Stripe block shows 6 cards
- Confirm the terminal log animates line by line
- Confirm the CTA links to Doola
- Run `python scripts/doola_client.py selftest` — expect 13/13
- Confirm responsive on a mobile viewport

## Reference implementation

- `assets/startabusiness.html` — the reference agentic.html layout
- `assets/clillc-banner.html` — the canonical gold-on-void visual reference
- `references/doola-api.md` — the Doola Partner API reference
