# teologia.ai · æ://

Plataforma soberana de devoción — 5 superficies æqr verificadas, cero CDN, cero servidores.

## Artefactos

| # | Artefacto | HTML | PDF | Badge æqr | Decode |
|---|---|---|---|---|---|
| 01 | Una manera sencilla de orar | 64 KB | 175 KB | ✅ | PASS |
| 02 | Catecismo Menor | 100 KB | 420 KB | ✅ | PASS |
| 03 | Enchiridion | 76 KB | 241 KB | ✅ | PASS |
| 04 | Catecismo Mayor | 85 KB | 299 KB | ✅ | PASS |
| 05 | Fórmula de Concordia | 85 KB | 280 KB | ✅ | PASS |
| — | Plataforma (index) | 88 KB | 125 KB | ✅ | PASS |

## Núcleo de cómputo (en el navegador)

La plataforma no es una página: es una superficie de cómputo. Todo local, nada simulado.

| Capacidad | Implementación | Verificación |
|---|---|---|
| **WebGPU** | Compute shader WGSL nativo, 65.536 partículas | Self-test con readback: `d[i]=d[i]*2+1` → `d[0]=1 d[63]=127` |
| **WebLLM** | `@mlc-ai/web-llm` vendorizado (141 modelos) | Import ESM real: `CreateMLCEngine` presente |
| **Rust WASM** | Núcleo compilado a `wasm32-unknown-unknown` | SHA-256 de bytes reales == hash del manifiesto |
| **Three.js** | r186 local vía importmap | Escena activa, 0 refs CDN |

**El núcleo WASM verifica, no solo carga.** Reproduce el vector NIST
(`sha256("abc") = ba7816bf…`) y hashea los bytes reales de `catecismo-mayor.html`
obteniendo `30a9a8ddda3d6597` — el mismo valor que `platform-manifest.json` registra.
Ese es el bucle cerrado: el binario que corre en el navegador confirma la integridad
de los artefactos que sirve.

## Estructura

```
teologia/
├── index.html                    ← Plataforma 9:16 (Three.js, gold-on-void)
├── una-manera-sencilla-de-orar.html / .pdf
├── catecismo-menor.html / .pdf
├── catecismo-mayor.html / .pdf
├── enchiridion.html / .pdf
├── formula-de-concordia.html / .pdf
├── aeqr-badge-*.svg              ← Chips verificados (5)
├── *.aqr.json                    ← Receipts con payload/hash/issuer
├── platform-manifest.json        ← Agregado sobre los 5 artefactos
├── scripts/
│   ├── make_aqr*.py              ← Generadores de badge (matriz real + decode cv2)
│   ├── verify_*.py               ← Verificación de PDF (el chip sobrevive al papel)
│   ├── compose_index.py          ← Plantilla + badge → index.html
│   ├── extract_badge.py          ← Extrae el badge inline verificado
│   └── cdp_*.mjs                 ← Verificación en navegador real (CDP)
├── wasm/
│   ├── Cargo.toml                ← sha2, serde, wasm-bindgen
│   ├── src/lib.rs                ← SHA-256 real, 5 artefactos, payloads æqr
│   ├── build.sh                  ← Build reproducible (corrige el PATH de Rust)
│   └── dist/                     ← Paquete compilado (rastreado, se sirve)
└── vendor/
    ├── three.module.js           ← Three.js r186 (local, sin CDN)
    ├── three.core.js
    ├── OrbitControls.js
    └── webllm/web-llm.js         ← WebLLM vendorizado (~6 MB ESM)
```

## Pipeline æqr

Cada artefacto tiene su badge æqr generado desde una matriz real (librería `qrcode`) y verificado decodificándolo de vuelta (OpenCV). El hash se calcula sobre el texto canónico del artefacto — quitar el badge no cambia el hash, porque el badge es contenedor, no mensaje.

El badge de plataforma es un agregado: el hash cubre un manifiesto JSON con los
SHA-256 reales de los 5 HTML en disco.

## Reproducibilidad

```bash
# Núcleo Rust WASM (compila + tests + paquete)
bash wasm/build.sh

# Generar todos los badges æqr
python scripts/make_aqr.py
python scripts/make_aqr_catecismo.py
python scripts/make_aqr_enchiridion.py
python scripts/make_aqr_mayor.py
python scripts/make_aqr_formula.py
python scripts/make_aqr_platform.py

# Recomponer la plataforma con el badge verificado
python scripts/compose_index.py

# Verificar todos los PDFs (badge æqr sobrevive al papel)
python scripts/verify_pamphlet.py
python scripts/verify_catecismo.py
python scripts/verify_enchiridion.py
python scripts/verify_mayor.py
python scripts/verify_platform.py

# Verificar el núcleo en un navegador real
python -m http.server 8124 --bind 127.0.0.1 &
node scripts/cdp_wasm_verify.mjs 9223
```

### Nota sobre el toolchain de Rust (Windows)

Esta máquina tiene **dos instalaciones de Rust**: una standalone en
`C:\Program Files\Rust stable MSVC 1.96` (sin las libs de wasm32) y el toolchain
de rustup en `~/.rustup/toolchains/stable-…` (que sí las tiene). La standalone gana
en `PATH`, así que un `cargo build --target wasm32-unknown-unknown` directo falla
con `can't find crate for core`. Peor: mezclar ambas a mitad de build produce
`E0514` (crate compilado por una versión incompatible de rustc). `build.sh` corrige
el `PATH` para toda la invocación — es la única cura fiable.

## Canon

- solo scriptura · solo fide · solo gratia
- un archivo · se copia · se pasa · no se pide permiso
- Truth over marketing: "when you tell the truth you don't have to remember anything."
- Donde hay gate se pasa por él; donde no, se dice que falta el chequeo.

## Issuer

☺://cc · æ:// namespace · sovereign operator of the æ:// namespace
