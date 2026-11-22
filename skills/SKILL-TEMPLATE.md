# SKILL-TEMPLATE — formato canónico del fleet æ://

Copia este archivo como `SKILL.md` dentro de `~/.hermes/skills/<categoria>/<nombre>/`
(o en el árbol `skills/` del repo). Todo lo que está entre `{{ }}` se reemplaza.

El estándar es el de `hermes-agent-skill-authoring` v2.0.0. Los 48 skills
firmados por Yæl Méndez / HUMAN://ROOT ya pasan esta plantilla.

---

```yaml
---
name: mi-skill                       # lowercase, hyphens, <=64 chars
description: "Capacidad en una frase, <=57 chars."   # se paga CADA turno
version: 0.1.0                       # semver; nuevo = 0.1.0
author: Yael Mendez (yaelmendez), Hermes Agent       # humano primero
license: MIT
platforms: [linux, macos, windows]   # auditado, nunca copiado
metadata:
  hermes:
    tags: [cortos, descriptivos]
    related_skills: [skill-que-exista]   # debe resolver en el mismo arbol
---
```

## Reglas duras (hardline)

| Campo | Regla |
|---|---|
| `description` | **<=57 chars** — el índice del system prompt trunca a 57 + "...". Una frase, termina en punto. Sin nombres de marketing. Si contiene `:` , va entre comillas. |
| `author` | Humano primero, `Hermes Agent` después. Nunca solo la herramienta. |
| `platforms` | Auditado contra el contenido real: `systemctl`/`/proc` → `[linux]`; bloques `bash`/pipelines → `[linux, macos]`; stdlib + CLIs → `[linux, macos, windows]`. |
| `related_skills` | Cada entrada debe existir en el mismo árbol. Verificado, no planeado. |

## Cuerpo — orden de secciones

```
# <Nombre> Skill
2-3 frases: que hace, que NO hace, que depende.

## When to Use
- trigger concreto (+ "Don't use for:" como contra-trigger)

## Prerequisites
- env vars exactas, installs, de donde sale la credencial

## How to Run
- invocacion canonica por la herramienta `terminal`

## Quick Reference
- lista plana de comandos, sin narracion

## Procedure
- pasos numerados, cada uno con criterio de completion verificable

## Pitfalls
- limites conocidos, cosas que parecen rotas y no lo son

## Verification
- como probar que el skill funciono (comando + salida esperada)
```

Mínimo exigido: **When to Use + cuerpo accionable + Pitfalls + Verification**.

## Donde va cada cosa

| Contenido | Va en |
|---|---|
| Procedimiento corto, triggers | `SKILL.md` |
| Tablas largas, ejemplos, context | `references/*.md` |
| Lógica no trivial (parsers, gates) | `scripts/*.py` |
| Salidas reutilizables | `templates/` |

Los 4 skills más ricos del fleet siguen exactamente este patrón:
`sovereign-browser-surface` (10 archivos), `vaeult-render-pipeline` (7),
`hermes-desktop-plugins` (5), `qr-vision` (6).

## Prohibido

- **Paths de máquina local** (`C:\Users\...`, `/home/...`) — rompen en cualquier otro equipo.
- **Skills router/índice/hub** whose core sea "carga el skill X" — duplica los triggers.
- **Descripción >57** — el trigger queda cortado y el skill no dispara.
- **Gate que no se muestra como PASS si no se ejecutó.**

## Verificación antes de commitear

```bash
python - <<'PY'
import re, pathlib, yaml
p = pathlib.Path("SKILL.md")
c = p.read_text(encoding="utf-8")
assert c.startswith("---"), "frontmatter debe empezar en byte 0"
m = re.search(r"\n---\s*\n", c[3:])
fm = yaml.safe_load(c[3:m.start()+3])
assert fm["name"] and fm["description"].endswith(".")
assert len(fm["description"]) <= 57, f"desc {len(fm['description'])} > 57"
assert fm["platforms"], "platforms ausente"
assert len(c) <= 100_000
print("OK", fm["name"], len(fm["description"]), fm["platforms"])
PY
```

---

*#opensourceware · el formato es la interfaz · medido, no declarado*
