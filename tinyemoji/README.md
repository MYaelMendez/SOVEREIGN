# tinyEMOJI

El instrumento soberano del **registro emoji**. Apache-2.0 · stdlib + qrcode/PIL/pyzbar/cv2.

**tinyEMOJI no decora símbolos.** Goberna el registro: lee la lista `CORE` de la
propia superficie, comprueba que **cada símbolo tiene su QR en disco**, que el QR
**decodifica a su anchor**, y que el punycode está **computado** y no recordado.
Un QR ausente es una negativa nombrada, no una página rota que nadie nota.

## When to use

- Un registro emoji declara N símbolos y quieres saber si **todos tienen QR**.
- Escaneaste un QR del registry y salió **texto chino**.
- Quieres saber si un punycode está computado o copiado.
- Vas a añadir un símbolo y quieres que el instrumento te diga qué falta.

## Shape

```
tinyemoji/
  tinyemoji.py              doctor() + check/resolve/qr/grade + ledger
  tests/test_tinyemoji.py   11 tests que pinnean los refusals y el falso negativo
  README.md · RESULTS.md · pyproject.toml · LICENSE
```

## Las cuatro invariantes

1. **`doctor()` mide**: 25 símbolos → 25 QR → 25 que decodifican a su anchor.
2. **Cada verbo tiene refusal**: superficie ausente, sin `CORE`, QR ausente,
   QR que no decodifica.
3. **El contrato se lee del artefacto**: la lista sale del HTML, nunca de una
   copia en el instrumento.
4. **Un receipt es claim hasta re-ejecutar**: `grade()` relee dos veces.

## Use

```bash
python tinyemoji.py doctor                 # el registro completo, extremo a extremo
python tinyemoji.py check <surface.html>   # verifica una superficie cualquiera
python tinyemoji.py resolve 🍊             # codepoint, nombre, punycode, QR, anchor
python tinyemoji.py qr ♾️                   # genera el QR que falte, en el mismo esquema
python tinyemoji.py grade                  # determinismo de la lectura
python tinyemoji.py ledger                 # integridad de la cadena
```

## Medido en esta máquina

Ver `RESULTS.md`.

## Límites (una capacidad sin su límite es marketing)

- **Lee `CORE=[{s,cp,cap}]`** tal como lo emite la superficie; otro formato se
  niega con «CORE vacío o con formato desconocido».
- **`make_qr` solo produce 328×328** (el esquema del registry). Otro tamaño no.
- **El punycode es IDNA por etiqueta**, no una validación de dominio: el registry
  mismo advierte «NOT VERIFIED DOMAINS».
- **Un solo decoder no basta** — y el instrumento lo demuestra (ver RESULTS).

## Ledger

`C:\æ\logs\tinyemoji.jsonl` (override `TINYEMOJI_LEDGER`). Append-only,
hash-chain, registra DECISIONES, nunca intención.

---

*#opensourceware · medido, no declarado · un decoder no basta*
