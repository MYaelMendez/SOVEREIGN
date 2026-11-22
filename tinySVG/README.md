# tinySVG

El instrumento soberano de las **superficies vectoriales**. Apache-2.0 · un archivo · stdlib.

**tinySVG no dibuja.** Goberna lo único que hizo ilegible una constelación de 20
nodos: **el viewBox no es la pantalla.** Mide el ancho de render, deriva la
escala y **se niega** cuando la tipografía cae bajo el suelo de legibilidad o
cuando los nodos se solapan.

La familia: `tinycuda` (píxeles) · `tinygpu` (robots) · `tinymujoco` (movimiento) ·
`tinycan` (el bus) · `tinycudavideo` (el seam) · `tinyffmpeg` (códecs) ·
`tinyqr` (identidad) · `tinySVG` (geometría) · `tinylab` (el auto-estudio).

## When to use

- Vas a publicar un gráfico y quieres saber si **se lee** en el chat, no en tu monitor.
- Un layout se ve bien en el SVG source y mal en la página.
- Nodos que se pisan, etiquetas cortadas por el borde.
- Quieres emitir una constelación que **se auto-dimensiona** al ancho real.

## Shape

```
tinySVG/
  tinySVG.py              doctor() + check/constellation/grade + ledger
  tests/test_tinySVG.py   pinnea los REFUSALS (viewBox ausente, tipo pequeña, solape)
  README.md · RESULTS.md · pyproject.toml · LICENSE
```

## Las cuatro invariantes

1. **`doctor()` mide el render, no el viewBox** — construye una constelación a
   707 px (el ancho real de una columna de chat) y la checa.
2. **Cada verbo tiene refusal** — archivo ausente, SVG que no parsea, viewBox
   ausente o degenerado, tipo bajo el suelo, nodos fuera, solapes.
3. **El contrato se lee del artefacto** — si el archivo es HTML, extrae el bloque
   `<svg>…</svg>`; nunca asume que es XML puro.
4. **Un receipt es claim hasta re-ejecutar** — `grade()` emite dos veces y
   compara bytes.

## Use

```bash
python tinySVG.py doctor                                # la cadena, a 707 px
python tinySVG.py check <surface.html> --render-w 707   # mide una superficie real
python tinySVG.py constellation a,b,c --render-w 707   # emite un SVG auto-dimensionado
python demo.py --out demo.svg                           # la regla, dibujada y auto-verificada
python tinySVG.py grade                                 # determinismo
python tinySVG.py ledger                                # integridad de la cadena
```

`demo.py` dibuja la lección (viewBox 1590 → pantalla 707 → 12.0 px) y **se
autoverifica con `check`**: si el SVG del demo no pasa, no se publica.

Tests: `python -m unittest tests.test_tinySVG -v`

## Medido en esta máquina

Ver `RESULTS.md`.

## Límites (una capacidad sin su límite es marketing)

- **El suelo es 12 px.** Es una decisión, no una ley: se puede bajar, pero el
  instrumento lo declara.
- **`check` mide nodos con `class="node"` y `transform="translate(x,y)"`.** Un SVG
  con otra estructura se parsea pero reporta `nodes: 0` — no es un pase.
- **`constellation()` es un emisor mínimo**, no un motor de gráficos: no_layout
  automático de etiquetas largas ni evitación de solape por fuerza.
- **El ancho de render es un parámetro, no una adivinanza.** Si lo omites, se usa
  el ancho del viewBox (es decir, asume pantalla completa).

## Ledger

`C:\æ\logs\tinySVG.jsonl` (override `TINYSVG_LEDGER`). Append-only, hash-chain,
registra DECISIONES, nunca intención.

---

*#opensourceware · medido, no declarado · el viewBox no es la pantalla*
