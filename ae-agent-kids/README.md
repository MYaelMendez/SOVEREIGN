# æ-agent-kids — the sovereign absorption

Everything related to the **Replit Agent → æ** rename and knowledge absorption lives here.

## What this is

The æ surface bundle (`site/assets/index-BrxjQ5Dc.js`, mirrored to `github-pages/`) carried a
Spanish-language kids tutorial page titled *"¡Aprende Replit Agent!"* at route
`/replit-agent-kids`. This folder holds the extraction, the rename log, and the standalone
æ reimplementation.

**The page is now:** `¡Aprende æ!` at route `/ae-agent-kids`.

---

## Files

| File | What it is |
|---|---|
| `README.md` | This file — knowledge extraction + rename log |
| `source/xw.ae-agent-kids.raw.js` | Minified component extracted verbatim from the bundle |
| `source/xw.ae-agent-kids.js` | De-minified, readable source (prettier) |
| `ae-agent-kids.html` | Standalone runnable surface — æ gold-on-void reimplementation |

---

## What Replit Agent taught us

### The product concept

Replit Agent is an AI coding assistant inside the Replit browser IDE. Describe what you want in
plain language, and it builds the app — code, structure, styling, deployment. The tutorial frames
it as *"Tu amigo robot que hace apps geniales"* (your robot friend that makes cool apps).

### The 4-step interaction loop

| Step | Title | What happens |
|---|---|---|
| 🏁 1 | **Empieza tu Aventura** | Click "Create a new App" → "æ" |
| 💬 2 | **Dile qué Quieres** | Describe your idea in your own words |
| 📋 3 | **Revisa el Plan** | æ te dice qué va a hacer |
| ✨ 4 | **¡Mira la Magia!** | The app builds itself |

**Key insight:** Describe → Review → Generate. The human steers, the agent executes.

### Feature pillars

| Emoji | Claim | Child-friendly framing |
|---|---|---|
| 🎮 | **Hace Juegos** | "Like the ones you play!" |
| 🎨 | **Crea Apps** | "With pretty colors!" |
| 🔧 | **Arregla Todo** | "If something breaks!" |
| ✨ | **Es Mágico** | "Like having superpowers!" |

### Project templates (6)

| Project | Emoji | Prompt pattern |
|---|---|---|
| Juego de Memoria | 🧠 | "Crea un juego de memoria con cartas de animales" |
| Quiz de Dinos | 🦕 | "Haz un quiz sobre dinosaurios con puntos" |
| Piano Virtual | 🎹 | "Crea un piano que suene con el teclado" |
| Calculadora Bonita | 🔢 | "Haz una calculadora con colores bonitos" |
| Dibujo Mágico | 🎨 | "Crea una app para dibujar con colores" |
| Juego de Naves | 🚀 | "Haz un juego donde una nave esquiva asteroides" |

**Pattern:** every prompt is one sentence — action verb + subject + one sensory detail.

### Prompt engineering for kids (4 tricks)

| Icon | Rule | Example |
|---|---|---|
| 🎯 | **Be specific** | "Quiero un gato naranja" not just "un gato" |
| 🌈 | **Ask for colors** | "Hazlo con colores del arcoíris" |
| 🔊 | **Add sounds** | "Que haga sonido cuando gane" |
| 🎮 | **Make it fun** | "Que sea fácil de jugar" |

**Core principle:** specificity + sensory detail = better output. Same pattern as mech-lang's
territorial specificity.

### Safety rules

- 🔒 Never share real name or personal info
- 🤝 Ask parents/teachers for help
- 🎉 Have fun — there are no wrong answers

### First mission (starter prompt)

> "Hola æ, soy nuevo y tengo 10 años. Hazme un juego simple donde un emoji feliz 😊 atrapa
> estrellas ⭐ que caen del cielo. Usa colores del arcoíris 🌈 y que sea fácil de jugar con las
> flechas del teclado ⬅️➡️"

**Anatomy:** greeting + self-description + game concept + visual style + input method.

---

## What we adopted for æ

| Replit concept | æ equivalent |
|---|---|
| Replit Agent | æ (the sovereign agent) |
| "Create a new App" | `æ://` route invocation |
| Plain-language prompt | `æ://` dialect description |
| Plan review | `æ://mesh` liveness check |
| App generation | `æ://` dispatch → execution |
| 4-step loop | `æ://` → describe → review → execute → verify |

### Design principles inherited

1. **Specificity wins** — "un gato naranja" > "un gato" → `æ://gpu/matmul` > `æ://gpu`
2. **Sensory detail matters** — colors, sounds, themes → `æ://` routes carry full context
3. **Review before execute** — the plan step → `æ://mesh` shows topology before dispatch
4. **Safety first** — no personal info → no secrets in `æ://` routes, ever
5. **Fun is a feature** — "que sea fácil de jugar" → `æ://` should feel like magic, not work

### The æ advantage over Replit

| Dimension | Replit Agent | æ |
|---|---|---|
| **Sovereignty** | Cloud-hosted, platform-owned | Local RTX, operator-owned |
| **Custody** | Replit holds the code | Victus holds the keys |
| **Execution** | Sandboxed browser IDE | `æ://` dispatch to any node |
| **Identity** | Anonymous account | X-verified human owner |
| **Extensibility** | Closed platform | Open protocol, any dialect |
| **Cost** | Subscription | Local compute, no rent |

---

## Rename log

### Bundle edits (`site/assets/index-BrxjQ5Dc.js` + `github-pages/assets/index-BrxjQ5Dc.js`)

| Location | Before | After |
|---|---|---|
| Route path | `/replit-agent-kids` | `/ae-agent-kids` |
| Page title | `¡Aprende Replit Agent!` | `¡Aprende æ!` |
| Section header | `¿Qué es Replit Agent?` | `¿Qué es æ?` |
| Step 1 description | `...y luego "Replit Agent"` | `...y luego "æ"` |
| Step 3 description | `El Agent te dice qué va a hacer` | `æ te dice qué va a hacer` |
| Prompt label | `Cómo pedirlo al Agent:` | `Cómo pedirlo a æ:` |
| Closing text | `¡Ahora ya sabes usar Replit Agent! 🎉` | `¡Ahora ya sabes usar æ! 🎉` |
| Starter prompt | `Hola Agent, soy nuevo...` | `Hola æ, soy nuevo...` |
| Clipboard text | `Hola Agent, soy nuevo...` | `Hola æ, soy nuevo...` |

**Total:** 9 user-facing strings + 1 route path. Remaining `replit` occurrences: **0** in both mirrors.
Both bundles byte-identical (md5 `c43d500302a46ec4edd0e1fa8bdc2f09`).

> ⚠️ The SPA bundle is a build artifact — these edits live in the deployed JS. If the app is ever
> rebuilt from source, the rename must be re-applied at the source level. There is no SPA source
> tree in `C:\æ` today.

---

## Key takeaway

Replit Agent's core insight — **describe in plain language, review the plan, watch it build** — is
exactly the `æ://` philosophy. The difference is custody: Replit rents you an agent; æ *is* your
agent. The kids' tutorial format (emoji + color + simplicity) is a good model for `æ://`
documentation — make it feel like magic, not like work.

*æ:// language is compute. #hermiphicationisinevitable*
