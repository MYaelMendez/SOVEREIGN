# Results

Every number measured on this machine by `tinyEMOJI doctor` / `resolve`.

## Machine

```
Host      teknium · Windows 11 · git-bash
Python    3.14.9
Decoders  pyzbar · OpenCV QRCodeDetector 5.0.0
Registry  aipodcast_me/emoji-registry.html · CORE de 25 símbolos
QRs       aipodcast_me/assets/qr/ · 26 PNG · 328×328 · oro (212,175,55) sobre blanco
```

## doctor()

```
symbols        25
qr_ok          25
missing        0
bad_payload    0
punycode       🍊 → xn--ki8h
multichar      4 símbolos son multicode (['♾️','🏎️','❤️','⌨️'])
ok             true
```

Los 4 multicode son honestidad de grafema: `♾️` son **dos** puntos de código
(U+267E + U+FE0F), no uno.

## El falso negativo que costó 18 falsas alarmas

La primera versión usaba **solo pyzbar**. Reportó:

```
18 QR "no decodifican a su anchor"
U+1F34A.png  decodifica a '\ue05e濠'   y debe ser '🍊'
```

Decodificaban a **texto chino**. El diagnóstico apuntaba a una codificación
rota; la realidad era otra:

```
cv2     : '...emoji-registry.html#🍊'     ✓
pyzbar  : '...emoji-registry.html#\ue05e濠'  ✗
```

**pyzbar mal-decodifica UTF-8 de 4 bytes.** Los QR eran correctos; el lector no.

Y regeneré los 18 con el mismo resultado — lo cual fue la prueba: si el QR nuevo
también «falla», el QR no es el problema.

Arreglado con `decode_qr_all()`: se prueban **los dos decoders** y basta con que
**uno** lea el anchor. `cross_decoder` es la norma aquí, igual que en el gate del
QR.

**Revierto**: los 18 originales quedaron intactos — estaban bien.

## resolve 🍊

```
codepoints     ['U+1F34A']
names          ['TANGERINE']
punycode       xn--ki8h
qr             assets/qr/U+1F34A.png
anchor_matches true
```

## Verificación en bucle cerrado

`make_qr` genera el QR en el esquema del registry y **se autoverifica**: devuelve
`decodes_to`, que tiene que ser `BASE#<símbolo>`.

```
python tinyemoji.py qr ♾️  →  version 4 · 328×328 · 1756 bytes
                              decodes_to https://.../emoji-registry.html#♾️
```

## Tests

11/11.

| refusal / chequeo | pinned por |
|---|---|
| superficie ausente | `test_missing_surface` |
| sin CORE | `test_surface_without_core` |
| QR ausente (nombrado) | `test_missing_qr_is_a_named_refusal` |
| el falso negativo de pyzbar | `test_pyzbar_alone_would_fail` |
| anchor coincide por un decoder | `test_resolve_reports_the_anchor` |
| lectura reproducible | `test_registry_read_is_stable` |
| punycode reproducible | `test_punycode_reproducible` |
| ledger | `test_chain_verifies` |

## Ledger

```
chain_ok  true
records   1
head      3990cebdfb2c
```
