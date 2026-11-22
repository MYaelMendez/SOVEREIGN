# tinyqr

El instrumento soberano del **chip QR**. Apache-2.0 · un archivo · stdlib + cryptography.

**tinyqr no reemplaza** la infraestructura QR (`qr_key_manager`, `contract_qr`,
`qr_server`). La **gobierna**: prueba la cadena completo de extremo a extremo —

```
keypair → sign → encode → decode → verify
```

— y se niega donde un eslabón no se puede medir.

La familia: `tinycuda` (píxeles) · `tinygpu` (robots) · `tinymujoco` (movimiento) ·
`tinycan` (el bus) · `tinycudavideo` (el seam) · `tinyffmpeg` (códecs) ·
`tinyqr` (identidad) · `tinylab` (el auto-estudio).

## When to use

- Vas a firmar o emitir un QR y quieres la prueba, no la promesa.
- Un contrato QR no verifica y necesitas saber **qué eslabón** falló.
- Quieres graduar la reproducibilidad del chip (mismo payload → mismo PNG).
- El gate de supervisión del QR se niega sin motivo visible.

## Shape

```
tinyqr/
  tinyqr.py               doctor() + sign/issue/decode/verify/grade + ledger
  tests/test_tinyqr.py    pinnea los REFUSALS en fixtures reales
  README.md · RESULTS.md · pyproject.toml · LICENSE
```

## Las cuatro invariantes

1. **`doctor()` firma de verdad** — keypair efímero → firma → QR → decodifica →
   verifica. Si la cadena no firma, se niega.
2. **Cada verbo tiene refusal** — llave desconocida, firma falsa, PNG ilegible,
   archivo ausente. Los tests los pinnean.
3. **El contrato se lee del artefacto** — los bytes del PNG y la firma, nunca del nombre.
4. **Un receipt es claim hasta re-ejecutar** — `grade()` codifica dos veces y
   compara bytes.

## Use

```bash
python tinyqr.py doctor                       # la cadena completa, probada
python tinyqr.py sign <name> "<mensaje>"      # firma con una clave local
python tinyqr.py verify <pub> "<msg>" <sig>   # verifica
python tinyqr.py decode <qr.png>              # decodifica el chip
python tinyqr.py issue '{"k":"v"}'            # emite + roundtrip + sha256
python tinyqr.py grade '{"k":"v"}'            # determinismo, dos encodes
python tinyqr.py ledger                       # integridad de la cadena
```

Tests: `python -m unittest tests.test_tinyqr -v`

## Medido en esta máquina

Ver `RESULTS.md`.

## Límites (una capacidad sin su límite es marketing)

- **`doctor()` usa un keypair efímero.** No crea ni guarda claves: gobierna el
  mecanismo, no el almacenamiento.
- **`issue()` escribe en un temporal.** Para un artefacto persistente, usa
  `qr_key_manager.create_key` / `encode_key_as_qr` con un path propio.
- **El gate de supervisión exige 2 decoders** (cv2 + pyzbar) y reporta
  `quiet_zone` como advertencia, no como bloqueo.
- **QR de alta densidad** (payload > ~80 chars) puede requerir versión alta; el
  gate lo mide, no lo asume.

## Ledger

`C:\æ\logs\tinyqr.jsonl` (override `TINYQR_LEDGER`). Append-only, hash-chain,
registra DECISIONES, nunca intención.

---

*#opensourceware · medido, no declarado · QR = el chip*
