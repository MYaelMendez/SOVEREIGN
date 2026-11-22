# Results

Every number measured on this machine by `tinyqr doctor` / `grade`. Nothing projected.

## Machine

```
Host    teknium · Windows 11 · git-bash
Python  3.14.9
Deps    cryptography · qrcode · pillow · pyzbar · opencv-python 5.0.0
```

## The chain, proved

```
doctor()
  modules             qr_key_manager + contract_qr cargables
  keypair             ed25519 · pub d39f9aaf278bbaa4…
  sign                ok · sig 6aacbd0ece3bba98…
  verify              ok
  encode              ok · (890, 890) · v16
  decode              ok · roundtrip
  artifact_verifies   ok
  ok                  true
```

`artifact_verifies` es el chequeo que importa: el QR **decodifica** y la firma
**verificada desde los bytes decodificados** sigue siendo válida. Un QR que no
verifica es la foto de una firma.

## Determinismo

```
grade({"a":1,"b":"tinyqr"})
  sha256_a  c5b66df9dc4ea9e9fec9cc1d7f1a06416e7d81c6ffaa800d61914dbc1c71a4fd
  sha256_b  c5b66df9dc4ea9e9fec9cc1d7f1a06416e7d81c6ffaa800d61914dbc1c71a4fd
  deterministic  true
```

Dos encodes, byte a byte.

## Refusals verificados

| refusal | pinned por |
|---|---|
| firma forjada | `test_verify_refuses_a_forged_signature` |
| archivo ausente | `test_decode_refuses_a_missing_file` |
| imagen sin QR | `test_decode_refuses_a_non_qr_image` |
| clave desconocida | `test_sign_refuses_an_unknown_key` |
| ledger manipulado | `test_tamper_breaks_the_chain` |
| path no-ASCII | `test_supervision_reads_a_unicode_path` |

10/10 tests pass.

## El defecto que costó tiempo (y su arreglo)

**`cv2.imread` no puede leer un path no-ASCII en Windows.** Con
`C:\æ\secrets\keys\qr\….png` devuelve `None`, y el gate de supervisión del QR
reportaba:

```
supervision refused — loadable: cannot read C:\æ\secrets\keys\qr\qr_20261122_111104.png
```

Consecuencia medida: **0 claves creadas** y 34 QR huérfanos en disco.

Arreglo: leer los bytes con `numpy.fromfile` y decodificar con `cv2.imdecode`
(`qr_supervision._imread`, aplicado en `supervise`, `supervise_raw`,
`video_supervision`, `qr_kanban`, `qr_kanban_local`, `degraded_capture`).

Verificado después del arreglo:

```
POST /api/key/create  →  fingerprint 772db97e51c7a3ba
                          qr 850×850 · version 15
supervise_raw         →  cross_decoder: 2/2 decoders: cv2, pyzbar
```

El bug ya estaba documentado en `series_engine.py` y se había esquivado con un
path ASCII de staging. Ahora está arreglado en la raíz.

## Sellar un artefacto — `seal`

```
python tinyqr.py seal <file> [--key sovereign-web]
```

```
artifact     tiny.html
sha256       c438e352133fa8bf…
fingerprint  1cc18a8917380464   (clave `sovereign-web`)
qr           tiny.html.receipt.png   · version 5
qr_payload   https://myaelmendez.github.io/verify.html?a=tiny.html&h=c438e352133f
receipt      tiny.html.receipt.json  (firma ed25519 completa)
```

El artefacto **no se toca**: el recibo es un archivo aparte, así el hash es el que
descarga el lector.

### El defecto que costó el primer intento
El QR llevaba la firma completa (`{v,a,m,p,s}` = 304 chars) → **QR v18**, y
OpenCV no detecta el quad en versiones ≥18:

```
supervision refused — cross_decoder: 1/2 decoders: pyzbar;
                       contrast: no quad detected; quiet_zone: no quad detected
```

El mismo gate pasaba **10/10** con 300 chars. El QR ahora lleva la URL corta
(~80 chars, v5), escaneable por cualquier teléfono; la firma vive en el JSON.

## Ledger

```
chain_ok  true
records   51
head      ec56a6d055e1
```
