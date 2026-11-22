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

## Ledger

```
chain_ok  true
records   3
head      8654d9059889
```
