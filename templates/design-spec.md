# æ:// Design Specification

Basada en Nous Research Hermes Agent conventions — Desktop Plugin SDK, Adding Tools, Codebase Ownership, Creating Skills, Contributing.

---

## 1. Naming Conventions

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Plugin ID | kebab-case, folder = ID | `sovereign-mesh`, `ae-letterspace` |
| Tool name | snake_case | `mesh_status`, `py_nl_exec` |
| Skill name | kebab-case | `sovereign-browser-surface` |
| Scheme | `æ://` prefix | `æ://glocal-agent` |
| Route | `pc://mesh/victus/local` | codemode address |
| NSID | `ae.core#fleetNode` | signed records |
| Domain | `æ.store`, `llm.store` | letterspace |

---

## 2. Plugin Contract

### Disk Door
```
$HERMES_HOME/desktop-plugins/<id>/plugin.js
```

### ESM Export
```javascript
export default {
  id: 'sovereign-mesh',        // must match folder name
  name: 'Sovereign Mesh',      // human name
  defaultEnabled: true,        // false = opt-in
  register(ctx) {
    // ctx.register({ id, area, title, data, render })
    // ctx.rest('/path') → /api/plugins/<id>/path
    // ctx.socket('/events') → live WebSocket
    // ctx.os.notify() → native OS notification
    // ctx.storage.get/set → plugin-scoped persistence
    // ctx.i18n.register({ en: {...} }) → locale bundles
  }
}
```

### UI Areas

| Area | Uso | Ejemplo |
|------|-----|---------|
| `panes` | Layout zones | Sovereign Mesh dashboard |
| `statusBar.right` | Chips | `◈ mesh`, `æ://`, `◈ glocal` |
| `statusBar.left` | Chips | Left-side indicators |
| `PALETTE_AREA` | ⌘K commands | Quick actions |
| `KEYBINDS_AREA` | Rebindable actions | Shortcuts |
| `THEMES_AREA` | Full DesktopTheme | Skin selector |
| `SIDEBAR_NAV_AREA` | Nav rows | Page links |
| `ROUTES_AREA` | Full pages | `/sovereign-mesh` |
| `TRANSCRIPT_DIRECTIVE_AREA` | Inline chat widgets | `::task{id="..."}` |

### Delivery Modes

| Mode | Where | Build |
|------|-------|-------|
| **Disk** | `$HERMES_HOME/desktop-plugins/<id>/plugin.js` | None |
| **Unified** | `$HERMES_HOME/plugins/<id>/desktop/plugin.js` | None |
| **Bundled** | `apps/desktop/src/plugins/<id>/plugin.tsx` | Vite |

---

## 3. Tool Contract

```python
# Handler MUST return JSON string, never raw dict
# Errors MUST be {"error": "message"}, never raised
# check_fn gates availability (returns False = silently excluded)

registry.register(
    name="mesh_status",
    toolset="sovereign-mesh",
    schema=MESH_STATUS_SCHEMA,
    handler=lambda args, **kw: json.dumps(handle_mesh_status(args)),
    check_fn=check_mesh_requirements,
)
```

### Key Rules
- Handlers return JSON string via `json.dumps()`
- Errors returned as `{"error": "message"}`, never raised
- `check_fn` called at tool definition build — `False` = silently excluded
- Handler receives `(args: dict, **kwargs)`

---

## 4. Skill Format

```yaml
---
name: sovereign-browser-surface
description: "Build sovereign gold-on-void HTML surfaces."
version: 1.0.0
author: Yael Mendez
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [html, browser, sovereign, gold-on-void]
    related_skills: [glocal-mesh, hermes-agent]
---
```

### Skill Structure
```
skills/
└── category/
    └── skill-name/
        ├── SKILL.md              # Required
        ├── references/           # Optional
        ├── templates/            # Optional
        └── scripts/              # Optional
```

---

## 5. Design Tokens

```css
:root {
  --void: #050505;        /* base surface */
  --gold: #D4AF37;        /* primary accent */
  --gold2: #f0d487;       /* gradient highlight */
  --neon: #00ff9d;        /* success / live */
  --cyan: #00eaff;        /* info / tools */
  --violet: #8c72ff;      /* volatility / VIX */
  --red: #ff4d5f;         /* error / panic */
  --ink: #e8e6df;         /* body text */
  --muted: #6f6a5c;       /* secondary */
  --line: rgba(212,175,55,.22); /* borders */
  --mono: "JetBrains Mono", ui-monospace, monospace;
  --display: "Orbitron", sans-serif;
}
```

### Typography

| Rol | Fuente | Weight |
|-----|--------|--------|
| Display | Orbitron | 700, 900 |
| Body | JetBrains Mono | 400, 700 |

### Textures

| Elemento | Efecto |
|----------|--------|
| Scanlines | `repeating-linear-gradient` 4px, opacity 0.18 |
| Vignette | Radial gradient transparent → void |
| Neural mesh | Canvas partículas gold con conexiones |
| Gold glow | `box-shadow: 0 0 40px rgba(212,175,55,.32)` |

---

## 6. Data Patterns

| Principio | Implementación |
|-----------|---------------|
| Honest reporting | Errores visibles, nunca silentes |
| Fallback | Valores razonables cuando fetch falla |
| Stale flag | Dato viejo marcado, no oculto |
| Live polling | 5s GPU, 10s mesh, 60s markets |
| CORS proxy | `api.allorigins.win/raw?url=` |
| Environment probe | Feature-detect antes de runtime |
| Strict protocol | JSON-only + nudge en bucle |
| Real metrics | TTFT, tok/s, steps, tool calls |

---

## 7. Contribution Priorities

1. Bug fixes — crashes, incorrect behavior
2. Cross-platform compatibility
3. Security hardening
4. Performance and robustness
5. New skills
6. New tools (rarely needed)
7. Documentation

---

## 8. Codebase Ownership

| Subsystem | Source | Docs |
|-----------|--------|------|
| Agent core | `agent/`, `run_agent.py` | Agent Loop |
| Tools | `tools/` | Adding Tools |
| Plugins | `plugins/` | Build a Plugin |
| Skills | `skills/` | Creating Skills |
| Desktop | `apps/desktop/` | Desktop Plugin SDK |
| CLI | `hermes_cli/` | Extending the CLI |
| Gateway | `gateway/` | Gateway Internals |

---

## 9. Plugin Registry

### Active Plugins

| Plugin | ID | Chip | Backend Routes |
|--------|-----|------|----------------|
| Sovereign Mesh | `sovereign-mesh` | `◈ mesh` | `/gpu`, `/vps`, `/mesh` |
| æ Letterspace | `ae-letterspace` | `æ://` | `/domains`, `/stack`, `/fleet`, `/redirects` |
| Glocal Dashboard | `glocal-dashboard` | `◈ glocal` | `/gpu`, `/vps`, `/mesh`, `/sessions`, `/detect`, `/frame` |
| Python NL | `py-nl` | `py›nl` | `/exec`, `/history` |
| Funding Loops | `funding-loops` | `◈ loops` | `/loops`, `/gates`, `/economics`, `/links` |
| LLM.STORE | `llm-store` | `◈ store` | `/orb`, `/mesh`, `/funding`, `/store` |
| Local Scale | `local-scale` | `◈ scale` | `/resources`, `/ollama`, `/gpu`, `/scale` |

---

## 10. Surfaces

| Surface | Location | Data Source |
|---------|----------|-------------|
| videolab.html | `C:\æ\site\` | Live mesh + CV |
| markets.html | `C:\æ\site\aipodcast_me\` | Yahoo Finance (CORS proxy) |
| indices.html | `C:\æ\site\aipodcast_me\` | Yahoo Finance + VIX narrative |
| llamacpp.html | `C:\æ\github-pages\aipodcast_me\` | wllama WASM + OPFS tools |

---

## 11. Skin

```yaml
name: sovereign
description: "Gold on void — the canonical æ sovereign design language"
colors:
  background: "#050505"
  ui_accent: "#D4AF37"
  banner_title: "#D4AF37"
  banner_text: "#f0ece4"
  ui_ok: "#00ff9d"
  ui_warn: "#ffcf5f"
  ui_error: "#ff6b7d"
branding:
  agent_name: "æ"
  prompt_symbol: ">"
  help_header: "æ:// commands"
```

---

*æ:// language is compute. #hermiphicationisinevitable*
