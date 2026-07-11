---
name: domain-codemode
description: "Use when working with Yæl's domain portfolio as an agentic syntax stack. One compact Code Mode interface searches/executes per-domain skills without loading every domain into context."
version: 1.0.0
author: Yæl Méndez × Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [domains, codemode, skills, æ, low-token, agentic-stack]
    related_skills: [startabusiness]
---

# Domain Code Mode

## Overview

Each domain is a skill. Do **not** load every domain-skill into the prompt. Use a Cloudflare-style Code Mode pattern: keep one tiny interface in context, then search or execute against `C:\æ\store\domain-stack.json` as needed.

This is the æ version of Code Mode: the model writes/uses code against a compact registry instead of carrying every domain's full lore every turn.

## When to Use

- User references the domain portfolio as a syntax stack
- User asks which domain maps to a capability
- User wants to generate/deploy assets for a domain
- User wants low-token operation: "each domain is a skill" without context bloat
- User says `>_æ:` / `#startabusiness` / `æ.store` / "App Store for Robots"

## Interface

Use the script:

```bash
python C:/æ/skills/domain-codemode/scripts/domain_mode.py search <query>
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute <domain-or-skill> <operation>
```

Common operations:

```bash
python C:/æ/skills/domain-codemode/scripts/domain_mode.py search stripe payments
python C:/æ/skills/domain-codemode/scripts/domain_mode.py search reachy robot
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute æ.store install_skill
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute æ.store deploy_plan
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute daollc.ai formation_blueprint
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute privateclient.ai session_seal
```

## Domain Stack Grammar

```
>_æ:       æ.store             namespace / App Store for Robots
>_llm:     llm.store           model combinator / intelligence layer
>_cli:     cli.llc             command line incorporated / execution
>_dao:     daollc.ai           Wyoming DAO LLC blueprint
>_pc:      privateclient.ai    sovereign session / trust
>_:        commandprompt.ai    human intent enters here
>_æææ:     æææ.com             æ.OS root
>_sov:     soværeign.com       sovereign thesis / enchiridion
>_n:       zacapa.ai           compute / NVIDIA/OpenClaw mapping
>_theo:    teologia.ai         first principles / OCW→OSW
>_ænet:    æ.net               agent network / AT Protocol
>_yæl:     yæl.com             person as protocol
>_æl:      æl.net              personal network node
```

## Rule

Search first. Execute second. Summarize only the result needed for the current user task.

## Verification

A valid run returns JSON. Example:

```bash
python C:/æ/skills/domain-codemode/scripts/domain_mode.py execute æ.store install_skill
```

Must include both install forms:

- `hermes skills install https://æ.store/SKILL.md`
- `hermes skills install https://xn--6ca.store/SKILL.md`
