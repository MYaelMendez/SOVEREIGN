---
name: html-as-skill
description: "Use when treating HTML/CSS/JS as the executable agentic viewport: a compressed, portable, inspectable skill artifact deployable via Wrangler, Workers, WASM, or static hosting."
version: 1.0.0
author: Yæl Méndez × Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [html, viewport, codemode, wasm, wrangler, compression, agentic-ui]
    related_skills: [domain-codemode, startabusiness]
---

# HTML as Skill

## Overview

HTML is not merely a render target. In the æ stack, **HTML is the skill**: a portable executable viewport that carries interface, state hints, brand grammar, calls to action, install commands, and agent-readable structure in one inspectable artifact.

This goes beyond video generation and supervision. Video shows a result. HTML **is the operating surface**: clickable, copyable, deployable, auditable, forkable, and agent-routable.

## Lineage

- **Compression:** think like FFmpeg culture — maximum signal, minimum payload. Compress the viewport without flattening meaning.
- **Code Mode:** expose compact code interfaces instead of bloated tool inventories.
- **Wrangler / Workers:** deploy the viewport as an edge-native skill surface.
- **Rust / WASM:** move hot loops, parsers, codecs, and transforms into compact deterministic modules.
- **HTML/CSS:** keep the human-facing protocol visible. The URL is the command.

## When to Use

- User says "HTML is the skill" or wants an agentic viewport
- Building deployable `agentic.html`, banners, install pages, dashboards, or robot app store surfaces
- Need low-token UX generation: one HTML artifact instead of many tool calls
- Need to evolve Cloudflare Code Mode on top of Wrangler / Workers / WASM
- Need UI that is both human-readable and robot-executable

## Pattern

```
search()   → find the right domain-skill / endpoint / template
execute()  → generate or transform the HTML skill artifact
host()     → deploy via Hostinger / Wrangler / static edge
verify()   → fetch URL, inspect DOM, screenshot viewport
```

## Artifact Contract

A valid HTML skill artifact should be:

- **Mobile-first 9:16:** design the primary viewport for the phone, not desktop. Treat vertical video / TikTok / Shorts / Reels geometry as the default intent surface.
- **Device-intent native:** exploit what the device gives you — thumb reach, tap targets, copy-to-clipboard, share sheets, install links, deep links, camera/robot/voice affordances when appropriate.
- **Single-file first:** inline CSS/JS when portability matters.
- **Compressible:** no framework bulk unless it earns its bytes.
- **Inspectable:** semantic headings, links, install commands, JSON-LD or embedded registry where useful.
- **Agent-addressable:** exposes copyable commands and predictable IDs/classes.
- **Human-readable:** the visual grammar communicates the thesis without explanation.
- **Deployable:** works on static hosting, Hostinger, Workers, or local file preview.
- **Verifiable:** can be checked by DOM assertions + screenshot.

## æ House Style

- Gold on void: `#050505`, `#D4AF37`, `#00ff9d`, `#f0ece4`
- Orbitron headings, JetBrains Mono body
- Neural mesh canvas, scanlines, sharp chassis, terminal grammar
- `>_æ:` prompt syntax
- Copyable install lines
- Real CTA links: Doola, Stripe, Hermes install, domain routes

## Code Mode Extension

Do not load every possible UI/template/domain into prompt context. Use a compact registry and script interface:

```bash
python C:/æ/skills/domain-codemode/scripts/domain_mode.py search <query>
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute <domain> <operation>
```

Then generate the HTML artifact from only the returned slice.

## Wrangler / Worker Direction

The next evolution is an edge worker that serves:

```txt
/agentic.html        human viewport
/SKILL.md            Hermes install target
/domain-stack.json   domain skill registry
/api/search          Code Mode search endpoint
/api/execute         Code Mode execute endpoint
```

Wrangler becomes the deployment transport. HTML remains the skill surface.

## Pitfalls

1. **Do not reduce HTML to screenshots/video.** Video is marketing; HTML is runtime.
2. **Do not over-framework.** If static HTML/CSS/JS works, use it.
3. **Do not hide the command.** The install line and protocol prompt must be visible.
4. **Do not flood context.** Search first, execute second.
5. **Do not fake deployment.** Verify by fetching the hosted URL and inspecting DOM/screenshot.

## Verification Checklist

- [ ] HTML opens locally
- [ ] DOM contains install commands / CTA / protocol prompt
- [ ] No unresolved `{{placeholders}}`
- [ ] Links are real and intentional
- [ ] Screenshot matches æ house style
- [ ] If hosted: URL fetch returns 200 and expected content
- [ ] If Worker-backed: `/api/search` and `/api/execute` return bounded JSON
