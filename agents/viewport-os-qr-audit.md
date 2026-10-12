# Viewport OS — kanban QR audit

**Surface:** `https://yael-mendez.teologia-7508.chatgpt.site/#home` → `#board`
**Producer:** `kanban.js` → `qrSvg(card)` using `vendor/qrcode.js`
**Verdict:** the codec is **sound**; the render path is **ungated**.

---

## What it does

Each kanban card renders a QR carrying a **URL with the card encoded in the
fragment**:

```js
cardUrl(card) = 'https://yael-mendez.teologia-7508.chatgpt.site/#board/qr/' + encode(card)
qrSvg(card)   = qrcode(0,'M').addData(cardUrl(card)).make().createSvgTag({cellSize:4, margin:16, scalable:true})
```

`encode()` is base64url over `JSON.stringify(validate(card))`. Reading it back is
`loadQr()` → `decode(location.hash.slice(10))` → `showCard(...)`.

This is a good design: the QR is a **URL**, so a phone camera opens the card with
no app. No secret is involved — the payload is title/notes/link, and the page
says so plainly ("Escanear no ejecuta herramientas ni concede permisos").

## The codec is sound — verified, not assumed

I extracted `validate`/`encode`/`decode` verbatim and probed them in Node.

| Property | Measured |
|---|---|
| round trip | `decode(cardUrl(c)) === c` ✓ |
| normal card URL | 196 chars |
| **largest card `validate()` permits** | notes=280, JSON=1276 bytes → **URL 1759 chars** |
| QR v40 / EC-M byte capacity | 2331 |
| headroom at max card | **572 bytes** |
| `decode()` input guard | 2400 chars |
| guard vs what `encode` can produce | **consistent** (1759 ≤ 2400) |

**No overflow bug.** A worst-case card still fits a v40 QR with 572 bytes to
spare, and `decode`'s 2400-char guard can never reject a URL that `encode`
produced. The layered limits (`validate` byte cap 1600 → QR cap 2331) are
coherent.

Also correct: `decode` validates the fragment against `/^[A-Za-z0-9_-]+$/` before
decoding, uses `TextDecoder(..., {fatal:true})`, and re-runs `validate()` on the
parsed object. Malformed input fails closed with `QR inválido.`

## The gap — it renders QR and never decodes it back

`qrSvg()` calls `qr.make()` then `createSvgTag()`. **There is no decode step.**
The artifact is handed to the user on the producer's word alone.

Per the æ:// rule now enforced in `qr_supervision.py`:

> A QR that has not been decoded back is not a QR — it is a picture of one.

The render is *probably* fine — the math says so. But "probably" is exactly what
the gate exists to replace with a receipt, and this surface is the family's
physical-to-digital bridge, so it is the one place the rule most applies.

## The gate, executed in a real browser

`kanban-qr-gate.js` renders the SVG, rasterizes it, decodes it back through every
decoder present, and compares to the exact URL. It **fails closed** when no
decoder is armed.

Verified over CDP against headless Chrome 154, using the page's **own**
`vendor/qrcode.js` and the page's **own** codec:

| Step | Result |
|---|---|
| real `qrcode.js` loaded | `typeof qrcode = function` ✓ |
| real codec loaded | `qrSvg = function` ✓ |
| SVG rendered | 56,555 chars |
| decoders armed | **0** → gate **refused**, correctly |
| decoders armed (with jsQR vendored) | 1 |
| **GATE** | `ok:true, verified:true, decoders:['jsQR'], urlChars:265` ✓ |
| **NEGATIVE CONTROL** | QR of a *different* card decodes to the wrong card, `matchesRightCard:false` ✓ |

The negative control is the one that matters: it proves the gate compares against
the *expected* URL rather than merely asserting "a QR decoded." Without it,
"it decoded" would be indistinguishable from "it decoded correctly."

## Finding — `BarcodeDetector` is absent in headless Chrome

The first run armed **zero** decoders and the gate refused. That is the gate
working, and it is worth stating as a finding rather than a glitch:

- **`BarcodeDetector` is not available in headless Chrome 154**, even though it
  exists in headed Chromium on Windows.
- Therefore a gate that relies on it alone **fails closed in CI/headless** — which
  is correct behavior but means the surface must vendor a second decoder
  (`jsQR`, ~257 KB) for the gate to be armed anywhere.

**Recommendation:** vendor `jsQR` alongside `vendor/qrcode.js`. With it, the gate
arms in headless, in CI, and in browsers lacking `BarcodeDetector`.

## Changes to apply

1. Add `kanban-qr-gate.js` after `kanban.js`.
2. Vendor `jsQR` (the gate works without it but fails closed; with it, it arms
   everywhere).
3. Replace `qrSvg(card)` with `await qrSvgVerified(card)` at the two call sites.
   The function returns the SVG on PASS and **throws** on FAIL — the caller must
   not fall back to an unverified render.
4. Surface the verdict in the UI (a small "verified · jsQR" marker), so a card
   that failed the gate is visibly distinct from one that passed.

## Why this belongs in the same family

This is the browser twin of `qr_kanban.py`: cards → QR → state, with a
camera-readable artifact as the bridge. The Python side learned the lesson the
expensive way (the rune magic that encoded fine and failed on scan). The browser
side can inherit the rule for free — the failure mode is identical, only the
language differs.
