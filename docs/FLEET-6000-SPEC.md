# Total Build Specification — 6000-Agent Fleet

**Scheme:** `æ://fleet/6000` · **Status:** SPEC (not executed) · **License:** MIT · #opensourceware

> **6000 agents totales, no 6000 simultáneos por decisión de diseño.**
> Verificado: `_get_max_concurrent_children()` devuelve **10** — pero es un
> *default del código*, no un techo duro (`max_concurrent_children` no está en
> config.yaml; `DELEGATION_MAX_CONCURRENT_CHILDREN` unset; no hay ceiling en el
> resolver). Hay tres cap paths reales: reject por llamada, truncador por turno,
> y un log de coste que **no** limita. Si no aparecen `Too many tasks` /
> `Truncated…` en los logs, un batch reducido fue auto-limitado por el modelo,
> no por Hermes. Escalamos por waves para que el parent re-mida cada receipt —
> no porque el runtime lo prohíba.

---

## 0. Los cinco contratos duros

1. **Un artifact por agente.** Dos agentes sobre un artifact = dos inventarios con el mismo nombre y ningún receipt.
2. **Claim antes de actuar.** `fleet_wave.py claim --wave W --task T --agent A` produce un lease con SHA. Sin lease, el trabajo no existe.
3. **Children construyen, parent publica.** Los children corren gates y *stagean*; ningún `git`, ningún `kanban_push.py`, ninguna edición de `AE-CONTINUITY.md`.
4. **Fail-closed.** Falta evidencia → REFUSE, nunca "skipped = PASS". Aprendido y sabotado en `ae_lessons.py`.
5. **Receipt único por artifact.** `sha256(spec ⊕ gates ⊕ bytes)`. Si el receipt es idéntico tras un re-render, el artifact es viejo → REFUSE.

---

## 1. Topología

```
                    HUMAN://ROOT  (autoridad, intención)
                          │
                    conductor (parent)
              ┌───────────┼───────────┐
         wave-001    wave-002  ...  wave-600
          ≤N live     ≤N live        ≤N live   (N = max_concurrent_children)
              │           │             │
        fleet_wave.py claim/complete/release  ← ledger de 6000 tareas
              │
        gates por artifact (4, ver §4)
              │
        staging privado por task_id
              │
        kanban_push.py (ÚNICO publish serializado)
```

**6000 tareas / N concurrentes = 6000/N waves** (N=10 default verificado). Cada wave es una transacción:
claim → work → gates → complete → release. El ledger sobrevive a crashes.

---

## 2. Sharding —Cómo dividir 6000 tareas

Cada tarea lleva un **closed contract** en `batch-manifest.json`:

```json
{
  "batch_id": "b_20261122_6000",
  "schema": "ae/fleet-batch/1",
  "wave_size": 10,
  "tasks": [
    {
      "task_id": "t_00001",
      "agent": "child-0001",
      "claim": ["fleet_wave.py", "claim", "--wave", "w001"],
      "inputs": ["C:/æ/.../input.json"],
      "outputs": ["C:/æ/.../stage/t_00001/artifact.json"],
      "gates": ["schema", "sha", "lesson_check", "receipt"],
      "publish": false
    }
  ]
}
```

**Reglas de shard:**
- Las entradas son **inmutables** durante el batch (hash en el manifest).
- Los outputs van a `stage/<task_id>/` — nunca a un directorio compartido.
- Un task no lee el output de otro task del mismo wave (elimina dependencias).
- Dependencias cross-wave se resuelven por **artifact sellado**, no por memoria.

---

## 3. Pre-dispatch —inyectar lo ya aprendido

Antes de cada wave, el conductor corre:

```bash
python ae_lessons.py brief --task BRIEF.md    # 11 invariantes en el brief
python ae_lessons.py check --context ctx.json  # fail-closed
python check_story.py --spec ... --data ...    # gate semático (si aplica)
```

Un agente que recibe un brief sin bloque `KNOWN DEFECTS` **no despacha**. Ese es el
mecanismo por el que 6000 agentes no pagan 6000 veces el mismo error.

---

## 4. Gates por artifact (todos ejecutables, ninguno opcional)

| Gate | Mide | REFUSA si |
|---|---|---|
| `schema` | `ae/*-status/1` | schema ausente o distinto |
| `sha` | bytes del artifact | sha declarado ≠ sha medido |
| `lesson_check` | `ae_lessons.py check` | cualquier invariante violado |
| `receipt` | `sha256(spec⊕gates⊕bytes)` | receipt idéntico a corrida anterior |
| `pixel` (video) | `vidæo verify` | lum≤20, contraste≤8, mov≤0.5, frames negros>5% |
| `audio` (video) | PCM decodificado | peak≤1000 o span<50% de la voz |
| `semantic` | `check_story.py` | etiqueta con día sobre datos semanales, número no derivado |

**Ningún gate se baja para hacer pasar un artifact.** Se repara la escena, la voz o el dato.

---

## 5. Verificación del parent (no confiar en el child)

El reporte de un child es una **pista**, no una medición. El conductor, por cada artifact:

1. `sha256sum` del archivo — compara con el manifest.
2. Re-corre los gates **él mismo** con su propio proceso.
3. `fleet_wave.py complete --wave W --task T --agent A --sha <sha>`.
4. Lee el receipt y lo compara con la corrida anterior (detector de stale artifact).

Un child que reporta solo éxito **no está done**. Reporta: comandos, métricas, sha, paths y **qué no pasó**.

---

## 6. Batch capabilities (lo que hace "extensive")

- **Resume:** `fleet_wave.py status --wave W` reanuda desde el último `complete`; los `claim` huérfanos se liberan con `release`.
- **Idempotencia:** repetir un task con el mismo `task_id` y mismo input produce el mismo sha → se detecta y se omite.
- **Aislamiento:** un REFUSE no bloquea el wave; se registra en `batch-failures.jsonl` y el wave continúa.
- **Cuarentena:** artifact que falla gate va a `quarantine/<task_id>/` con el reason — nunca al staging limpio.
- **Replay:** cada task guarda `command`, `input_sha`, `output_sha`; cualquier artifact se reproduce con `replay --task T`.
- **Ratelimit:** `wave_size` configurable; default 10 (resolver verificado, **no techo duro**), sobre `FLEET_CONCURRENCY` declarado.
- **Dry-run:** `--dry-run` imprime los 6000 claims sin ejecutar — auditable antes de gastar.

---

## 7. Publish (un solo punto)

```bash
python kanban_push.py push \
  --task "batch b_20261122_6000: N artifacts" \
  --branch gh-pages
```

**Nunca `git push` directo.** `FLEET_REPO` explícito. Stage explícito por path:
nunca `git add -A` (el árbol es compartido; ya vimos commits ajenos con `index.lock`).

**Ladder de verificación:**
1. API `contents?ref=<branch>` — autoritativo, hash por archivo.
2. Pages build → `built`.
3. URL live → 200 + re-hash de bytes CDN.
4. 404 con build `built` = lag de CDN → esperar, **no re-push**.

---

## 8. Límites honestos (lo que NO promete)

- **6000 simultáneos: no por diseño, no por prohibición.** El resolver da 10
  por default pero es configurable sin techo. 6000 es un *batch total* con
  waves porque el parent debe re-medir cada receipt; no porque el runtime lo
  impida. Si un batch sale con menos de N, revisar logs: fue el modelo
  auto-limitándose, no Hermes.
- **6000 tareas independientes: sí**, si y solo si cada una tiene closed contract y no depende del output de otra del mismo wave.
- **Un child no puede firmar un receipt de gate que él mismo corrió** — el parent re-mide. "Evidence ≠ Authority."
- **Un catalog sin `--check` es un catálogo que miente** — todos los derivados llevan gate.
- **Advisory no cuenta como PASS.** `explicit_stage_only` es manual por diseño; se reporta, no se suma.

---

## 9. Secuencia de ejecución (cuando se autorice)

```
1. gen_batch_manifest.py --count 6000 --wave-size 10 → batch-manifest.json
2. ae_lessons.py brief --task BRIEF.md ; ae_lessons.py check --context ctx.json
3. por wave (1..600):
     claim → dispatch ≤10 → gates → parent verify → complete → release
4. batch-report.json: PASS / REFUSED / QUARANTINE por task
5. kanban_push.py push (único)
6. API → build → CDN ladder
7. ae_lessons.py: append la lección nueva del batch, sabotage-test, commit
```

---

## 10. Definición de "done"

Un batch de 6000 está **done** cuando:
- 6000 receipts únicos con sha medido por el parent.
- 0 artifacts con receipt idéntico a otra corrida.
- 0 gates bajados (diff de umbrales = 0).
- `ae_lessons.py verify` en verde con la lección nueva del batch.
- API contents re-hashed == staging, build `built`, CDN 200.

**Si falta uno de esos, el batch no está done** — y el reporte lo dice, ranked: PROVEN / BUILT / LIABILITY.
