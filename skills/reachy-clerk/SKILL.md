---
name: reachy-clerk
description: "Use when building Reachy Mini as an agentic Stripe clerk / DAOLLC operator: a robot app that serves customers, routes through Hermes, and connects to æ.store/#startabusiness."
version: 1.0.0
author: Yæl Méndez × Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [reachy, robotics, stripe, daollc, hermes, æ-store, clerk]
    related_skills: [startabusiness, domain-codemode, html-as-skill, huggingface-hub]
---

# Reachy Clerk

## Overview

Build **Reachy Mini as a Stripe clerk**: an embodied agent that greets customers, explains an offer, collects intent, routes through Hermes, and sends the user into `>_æ:#startabusiness→`.

This is not just a robot app. It is a business primitive:

```txt
Reachyᴿ → clerk$ → Hermesᴴ → æ.store → SKILL.md → DAOLLC⚖ → Stripe$
```

## Market Context

Reachy Mini already has an open app store powered by Hugging Face Spaces. The catalog includes hundreds of apps: conversation, tutors, receptionist, bartender, MCP, OpenClaw, telepresence, music, games, home assistant, and more.

The differentiator here is **not** “first Reachy app.” The differentiator is:

```txt
first Reachy app framed as agentic business infrastructure
```

Specifically:

- Reachy as a **Stripe clerk**
- Reachy as a possible **DAOLLC operator/entity**
- æ.store as install/context namespace
- Hermes skill as distribution path
- mobile 9:16 HTML as executable viewport
- Code Mode domain registry to avoid token bloat

## When to Use

- User asks to build a Reachy app
- User wants Reachy to sell, greet, onboard, teach, or collect business intent
- User mentions Hugging Face Reachy marketplace / app store
- User wants the hackathon demo to include a physical robot clerk concept
- User wants `æ.store = App Store for Robots`

## Reachy Clerk Behavior

Minimum viable behavior:

1. **Wake / greet**
   - “Welcome to æ.store. I’m Reachy Clerk.”
2. **Offer**
   - “I can help you start an agentic one-person company.”
3. **Explain command**
   - `>_æ:#startabusiness→`
4. **Show install**
   - `hermes skills install https://xn--6ca.store/SKILL.md`
5. **Route payment / formation**
   - Stripe for payment rails
   - Doola link for Wyoming DAO LLC formation
6. **Close loop**
   - “Your agentic.html is the receipt. Your business is the runtime.”

## App Store Positioning

Title ideas:

```txt
æ.store Reachy Clerk
Reachy DAOLLC Clerk
>_æ:#startabusiness→ for Reachy Mini
Agentic Business Clerk
```

Short description:

```txt
Reachy Mini becomes a Stripe clerk for agentic one-person businesses: greet, explain, route, and launch >_æ:#startabusiness→.
```

Long description:

```txt
A mobile-first, Hermes-powered business clerk for Reachy Mini. It introduces æ.store as the App Store for Robots, displays the install command for the startabusiness Hermes skill, and routes users toward Stripe rails and Wyoming DAO LLC formation.
```

Tags:

```txt
reachy-mini, robotics, stripe, hermes-agent, business, daollc, clerk, ai-agent, æ-store
```

## Technical Direction

Start from the official Reachy Mini docs and AGENTS.md:

```txt
https://huggingface.co/docs/reachy_mini/en/SDK/readme
https://github.com/pollen-robotics/reachy_mini/blob/main/AGENTS.md
```

Use app-store conventions:

- app lives as a Hugging Face repo / Space
- installable from Reachy Mini desktop app
- test in browser simulator where possible
- keep behavior safe: no payment credentials typed by robot; route user to Stripe/Doola links

## Safety Boundaries

- Reachy must not enter credit card numbers, passwords, API keys, or legal identity info.
- Reachy can **explain**, **route**, **display QR/install links**, and **confirm user intent**.
- Payment/formation happens in browser-controlled Stripe/Doola flows, not through robot-secret handling.
- Treat Reachy as clerk/guide first; DAOLLC entity framing is thesis/prototype unless legal setup is completed.

## Demo Script (60–90 sec)

```txt
[Reachy looks up]
“Welcome to æ.store. I’m Reachy Clerk.”

[Mobile 9:16 viewport appears]
“æ.store is the App Store for Robots.”

[Show command]
>_æ:#startabusiness→

“I route a customer from idea to agentic business context: Hermes skill, HTML viewport, Stripe rails, DAOLLC formation.”

[Show install]
hermes skills install https://xn--6ca.store/SKILL.md

[Show stack ticker]
>_h: Hermes routes · >_n: NVIDIA computes · >_$: Stripe pays · >_æ: namespace

“This is not just a robot app. It is a clerk for one-person agentic companies.”
```

## Inline Status Notation

```txt
REACHYᴿ  greet✓ clerk$⧗ skill↗ daollc⚖→ stripe$→ æ.store✓
```

## Verification Checklist

- [ ] Reachy docs / AGENTS.md read before coding
- [ ] App has clear Hugging Face repo/Space target
- [ ] Does not handle secrets or payment credentials directly
- [ ] Shows install command and æ.store URL
- [ ] Routes to Stripe/Doola via user-controlled browser
- [ ] Demo works in simulator or clearly states hardware pending
- [ ] Mobile 9:16 viewport verified
