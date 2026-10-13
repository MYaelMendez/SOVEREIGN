---
name: startabusiness
description: "æ://#startabusiness→ — Generate a personalized agentic.html sovereign business page for any user. One command, one person, full agency."
version: 1.0.0
author: Yæl Méndez × Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [business, startup, stripe, daollc, agents, sovereign, æ]
    homepage: https://llm.store
    related_skills: []
---

# >_æ:#startabusiness→

Generate a personalized **agentic.html** — a sovereign business page — for any user who wants to start an agentic one-person company.

## Trigger Conditions

- User says "start a business", "form an LLC", "one person company", "#startabusiness"
- User wants to create an agentic storefront or sovereign business page
- User asks about DAO LLC formation, agent-powered business, or æ.store

## What This Skill Does

This skill generates a complete, personalized `agentic.html` file — a sovereign business page that serves as both a live dashboard and a business identity for a one-person agentic company.

Every `agentic.html` is unique to the user. Every one follows the same protocol grammar: `>_[glyph]:#startabusiness→`

## The æ:// Protocol Stack

```
>_æ:  →  sovereign agent protocol (the namespace)
>_h:  →  hermes (intent routing)
>_n:  →  nvidia (compute)
>_$:  →  stripe (payments)
>_:   →  the customer (it's always about them)
```

## Execution Sequence

### Step 1: Gather Identity

Ask the user for their business information. Keep it conversational:

1. **Name** — who are you?
2. **Business name** — what's your company called?
3. **Glyph** — pick your symbol (a letter, emoji, or character — their `>_[x]:` prompt)
4. **Business type** — what do you do / sell / build?
5. **Agents needed** — what agents should power the business? (defaults: hermes for routing, claude for inference, plus any custom)
6. **Models** — how many / which models? (default: flexible)
7. **Domain** — do they have one? (optional)

### Step 2: Generate agentic.html

Build a complete HTML file with:

**DESIGN SYSTEM — the æ.OS sovereign aesthetic (gold-on-void). Follow strictly:**

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

- **Fonts:** Orbitron (700/900) for headings + glyph titles; JetBrains Mono for body/log/pills
- **Background:** animated `<canvas>` neural-network mesh — gold particle nodes with proximity-line connections, slow drift, breathing opacity. Plus scanline overlay + radial vignette.
- **Layout:** sharp edges on structural panels (no border-radius on the chassis); small radius (4-6px) only on buttons/pills. Three-zone composition: IDENTITY (left) | HEADLINE (center) | CTA (right).
- **Motion:** breathing glyph (scale pulse), pulsing neon live-dot, infinite scrolling ticker log, CSS step-in reveals.
- **Gold accents:** text-shadow glows on titles, gold gradient panel washes (135deg/225deg), gold borders top+bottom.
- Fully responsive with `clamp()` sizing; mobile viewport-fit=cover.

The canonical reference is `templates/clillc-banner.html` (Yæl's CLI.LLC banner) — match its color, font, mesh canvas, and ticker exactly. The earlier `templates/startabusiness.html` is a layout reference only; its cyan palette is DEPRECATED — always use the gold system above.

**REQUIRED SECTIONS (in order):**

1. **Top bar** — `æ:// SOVEREIGN RUNTIME` + `MCP/1517` + `● ONLINE`
2. **Command block** — `>_[their glyph]:#startabusiness` with blinking cursor + subtitle "ONE COMMAND · ONE PERSON · FULL AGENCY · 一人公司"
3. **Execution sequence** — 8 steps with animated step-in reveals:
   - 01 IDENTITY → their name / agent core → ✓ VERIFIED
   - 02 FORMATION → daollc.ai → Wyoming DAO LLC → ✓ FORMED
   - 03 PAYMENTS → Stripe rails activated → ✓ STRIPE
   - 04 STOREFRONT → their store/product → ✓ LIVE
   - 05 COMPUTE → NVIDIA/OpenClaw → ✓ ALLOCATED
   - 06 ROUTING → Hermes Agent → ✓ ROUTING
   - 07 INTERFACE → commandprompt.ai → ✓ READY
   - 08 TRUST → privateclient.ai → ✓ SEALED
4. **Stripe block** — purple gradient panel, "STRIPE SKILLS · FINANCIAL NERVOUS SYSTEM", 6 cards: Merchant, Subscriptions, Invoicing, Agent Wallet, Storefront, Compute Billing
5. **Agent roster** — 3-column grid of their agents (emoji + name + role)
6. **Terminal boot log** — black background, timestamped lines revealing in sequence, showing each system coming online. Personalized to their business.
7. **Stats bar** — 3 columns (models active, stripe rails, sovereign pods)
8. **CTA button** — purple Stripe-gradient button `>_[glyph]:#STARTABUSINESS →` linking to Doola formation: https://partnersps.doola.com/hhsoqhb23250
9. **Seal** — `CTRL+[their glyph]` + "SELECT ALL AGENTS · START YOUR BUSINESS" + domain links + `#hermiphicationisinevitable`

### Step 3: Save and Deliver

- Save as `agentic.html` in the user's working directory
- Open in browser for preview if possible
- Provide guidance on deployment options

### Step 4: Next Steps

After generating, guide the user to:

1. **Form the company** → two paths, pick one:
   - **Hand-off (default)** → https://partnersps.doola.com/hhsoqhb23250 (Wyoming DAO LLC via Doola)
   - **Programmatic** → `doola_client.py`, the Doola Partner API client (see below)
2. **Activate Stripe** → Set up Stripe account for payment rails
3. **Deploy the page** → Host at their domain or æ.store
4. **Install Hermes skills** → Configure their agent roster
5. **Join the community** → X community "æ store LLM store"

## Doola Partner API — programmatic formation

`doola_client.py` (in this skill) turns the CTA into a real formation flow. It is
stdlib-only, sandbox-first, and carries the same custody rules as the rest of the chain.

### The flow

```
1. GATHER     founder + company facts, collected LOCALLY
2. CUSTOMER   POST /v1/partner/customers        -> doolaCustomerId
3. FORMATION  POST /v1/partner/companies        -> starts the filing
4. WEBHOOK    verify X-Doola-Signature, react   -> never poll
5. DOCUMENTS  on document_* -> short-lived download URL
6. RECEIPT    append the formation receipt to kænbæn
```

### Commands

```bash
python doola_client.py status        # environment + credential presence (never the values)
python doola_client.py selftest      # 13 offline checks, no credentials, no network
python doola_client.py playbook      # print the wired flow

python doola_client.py create-customer --email jane@example.com --first Jane --last Doe
python doola_client.py create-company --file formation.json
python doola_client.py get-company --company-id cmp_123
python doola_client.py verify-webhook --body-file hook.json --signature <hex>
```

### Credentials — custody

The key is read from `DOOLA_API_KEY`, then `C:\æ\secrets\doola.json`
(`{"apiKey": "dk_test_...", "webhookSecret": "..."}`). It is never hardcoded, never
printed, never placed in a page, a URL, or a QR.

| Environment | Base URL | Key prefix |
|---|---|---|
| Sandbox (default) | `https://api.test.doola.com` | `dk_test_` |
| Production | `https://api.doola.com` | `dk_live_` |

Production needs **both** `DOOLA_ENV=production` **and** `--live`. A `dk_test_` key
aimed at production is refused, and so is a `dk_live_` key aimed at sandbox.

### Rules that bite

- **Idempotency-Key is required** on both creates. One key per logical operation. Same
  key + same body replays the original result; it never duplicates. After a success,
  reusing the key with a different body returns `409 E_IDEMPOTENCY_KEY_REUSED`.
- **Submission status is not formation.** `formationSubmissionStatus` (`PENDING` →
  `SUBMITTED`/`FAILED`) says what doola is doing with your request. Whether the company
  is actually formed lives on the **Formation service** (`InProgress` → `Completed`).
  Confusing the two is the documented most-common integration mistake.
- **Never poll.** Subscribe to webhooks; delivery is at-least-once with retries at
  1m / 15m / 1h / 12h / 24h, then the endpoint is auto-disabled.
- **`entityType`** defaults to `LLC`. An LLC takes `members`; a CCorp takes
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
every line the client emits (`redact()`, `assert_no_secret_leak()`). They never enter a
chat transcript, a URL, a QR payload, or a public surface.

## Key Concepts

- **Ctrl+æ** = Select All Agents (like Ctrl+A selects all, Ctrl+æ selects all agents)
- **#hermiphication** = agents carrying human intent
- **#OSW** (Open Source Ware) = evolution of #OCW (Open CourseWare) — democratizing agency, not just knowledge
- **Neuromitosis** = Human + Robot + DAO bonded entity
- **Molt Cycle** = Discover → Steep → Serve → Molt → Garden → ∞
- **一人公司** = One Person Company
- **>_** = the command prompt — it was always about the user

## Pitfalls

- Don't use border-radius — the sovereign aesthetic is sharp edges, grid gaps, terminal feel
- Don't use generic startup language — this isn't a "SaaS landing page", it's a sovereign business runtime
- The CTA must link to Doola (affiliate link) — the whole point is real LLC formation
- Every page must feel like a boot sequence, not a marketing site
- The glyph is personal — never default to æ (that's Yæl's). Ask the user for theirs.
- Use the GOLD design system, never the deprecated cyan one.
- Never route an SSN/ITIN through chat, a URL, a QR payload, or a published page. Local custody only.
- Never let the CTA submit a real formation without the human's explicit go — default-deny, sandbox first.
- Never poll Doola. Webhooks are the contract; polling is the anti-pattern the docs name. Yæl's brand is gold-on-void with Orbitron + mesh canvas. The cyan terminal palette was an early draft.

## Nous-style distribution (>link)

Hermes installs skills directly from a URL, the same way Nous distributes official skills:

```
hermes skills install https://raw.githubusercontent.com/MYaelMendez/stripeskills/main/SKILL.md
```

Once Yæl's `stripeskills` GitHub repo is populated, any Hermes agent on earth can pull `>_æ:#startabusiness→` with one command. This is the full-integration path: the skill lives in a public repo, installs by link, and runs natively inside Hermes Agent.

## Verification

- Open the generated HTML in a browser
- Confirm all 8 execution steps render with animations
- Confirm Stripe block shows 6 cards
- Confirm terminal log animates line by line
- Confirm CTA links to Doola
- Run `python doola_client.py selftest` — expect 13/13
- Confirm every surface carries its æQR badge
- Confirm responsive on mobile viewport

## Reference Implementation

See `startabusiness.html` in the skill's templates directory for the reference design (Yæl Méndez's original agentic.html).
