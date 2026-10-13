# #startabusiness — an Agent Skills package

One command, one person, full agency. Generates a sovereign gold-on-void
`agentic.html` business page, and can wire **real company formation** (LLC / C-Corp)
through the Doola Partner API.

## What this is

An **Agent Skills** package — the open standard published at
<https://agentskills.io>. OpenAI's own docs: *"OpenAI Skills follow the Agent Skills
open standard, so you can download them from one product and install them in another."*
The same folder runs in ChatGPT, Codex, Claude, Cursor, Gemini CLI, and Hermes.

```
startabusiness/
├── SKILL.md              instructions (name + description frontmatter)
├── scripts/
│   └── doola_client.py   Doola Partner API client — stdlib-only, sandbox-first
├── references/
│   └── doola-api.md      the API reference
├── assets/
│   ├── startabusiness.html   reference agentic.html layout
│   └── clillc-banner.html    canonical gold-on-void visual reference
└── agents/
    └── openai.yaml       optional appearance + dependency hints
```

## Install — ChatGPT

1. Sidebar → **Plugins** → **Skills** tab (or <https://chatgpt.com/skills>)
2. **Create** → **Upload from your computer**
3. Select the zip (or the `startabusiness/` folder)
4. Install. Then `@startabusiness` to invoke it explicitly, or just ask to start a business.

## Install — Codex / IDE

Codex reads skills from `.agents/skills/`. Copy the `startabusiness/` folder there,
then `$startabusiness` to mention it, or `/skills` to list.

## Install — Hermes Agent

```
hermes skills install <url-to-this-package>
```

## Install — any other Agent Skills host

Drop the `startabusiness/` folder into that host's skills directory. It is plain text —
nothing to compile, nothing to migrate.

## The two rules that carry the weight

1. **A QR is an address, not permission.** Discovery never grants execution.
2. **Never move a secret.** The Doola key and webhook secret live in local custody.
   SSN/ITIN values are collected locally, sent straight to the API, and redacted from
   every emitted line.

## Verify before you trust

```bash
python scripts/doola_client.py selftest   # expect 13/13, offline, no credentials
python scripts/doola_client.py status     # environment + credential presence (never values)
```

## Custody

`DOOLA_API_KEY` env, or a local secrets file `secrets/doola.json`
(`{"apiKey": "dk_test_...", "webhookSecret": "..."}`). Never in source, a chat
transcript, a URL, a QR payload, or a published page.

## License

MIT. #opensourceware — in the tradition of Project Wittenberg: the same gesture
(vernacular, cited, mirrored, no single custody) pointed at a different corpus.
