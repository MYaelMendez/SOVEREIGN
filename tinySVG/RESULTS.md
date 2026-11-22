# Results

Every number measured on this machine by `tinySVG doctor` / `check`. Nothing projected.

## Machine

```
Host    teknium · Windows 11 · git-bash
Python  3.14.9
Deps    stdlib (xml.etree, hashlib) — zero third-party
```

## doctor() — the render is the unit

```
render_w          707            (a real chat-column width, not a desktop one)
viewBox           1590 x 1034
scale             0.4447
nodes             20
small_labels      0
overflow          0
overlaps          0
font_effective_px 12.0
ok                true
```

`font_effective_px` is the whole point: `27 * 707 / 1590 = 12.0`. The instrument
refuses below `MIN_FONT_PX = 12.0`.

## The defect it caught on the deployed surface

`tiny.html` shipped with `viewBox="0 0 1600 1040"` and `font-size="27"`:

```
27 * 707 / 1600 = 11.93 px   →  under the floor
tinySVG check → ok: false, small_labels: [20 of 20]
```

After wiring the generator to `tinySVG.viewBox_for(707, 27)`:

```
viewBox  1590 x 1034
scale    0.4447
small_labels  0   ·   overflow  0   ·   overlaps  0
ok       true
```

## The rule it encodes

```python
viewBox_for(render_w, font) = floor(render_w * font / MIN_FONT_PX)
```

A narrower render yields a narrower viewBox, so the type never shrinks. Pinning
the layout to a hand-picked `1600` is what broke it — the number was chosen for a
desktop and never re-measured for the chat column.

## Determinism

```
grade()
  sha256_a  47c8e277e52bf8f2682e68a845e1f1d3aefc57e732aa10d441053e8d018e99ba
  sha256_b  47c8e277e52bf8f2682e68a845e1f1d3aefc57e732aa10d441053e8d018e99ba
  deterministic  true
```

## Refusals verified

| refusal | pinned por |
|---|---|
| archivo ausente | `test_missing_file` |
| HTML envolviendo un SVG | `test_html_wrapper_is_unwrapped` (must PASS, not refuse) |
| viewBox ausente | `test_surfaces_without_viewBox_are_refused` |
| SVG no parsea | `test_unparseable_svg_is_refused` |
| tipografía bajo el suelo | `test_small_type_is_a_refusal` |
| solape de nodos | `test_no_two_nodes_overlap` |
| nodo bajo el hub | `test_inner_node_clears_the_hub` |

11/11 tests pass.

## Ledger

```
chain_ok  true
records   2
head      3990cebdfb2c
```
