# tinyXML

El instrumento soberano de **XML**. Apache-2.0 · stdlib + defusedxml.

**tinyXML no es un parser más.** Goberna XML como artefacto: mide si es bien
formado **y dónde rompe**, canonicaliza de forma determinista (la propiedad en la
que se apoya XMLDSig), **rechaza DTDs con entidades** (XXE) y firma la forma
canónica con `tinyqr`.

tinySVG ya parseaba XML; tinyXML es la generalización: lo que tinySVG hace para
un `viewBox`, tinyXML lo hace para cualquier documento.

La familia: `tinycuda` (píxeles) · `tinygpu` (robots) · `tinymujoco` (movimiento) ·
`tinycan` (el bus) · `tinycudavideo` (el seam) · `tinyffmpeg` (códecs) ·
`tinyqr` (identidad) · `tinySVG` (geometría) · `tinyXML` (el documento) ·
`tinylab` (el auto-estudio).

## When to use

- Vas a firmar o comparar XML y necesitas que **dos partes hasheen lo mismo**.
- Un XML se rompió y quieres la **línea y la columna**, no «mal formado».
- Sospechas de **XXE** (DTDs con entidades externas).
- Quieres medir un XML real: profundidad, namespaces, canonicidad.

## Shape

```
tinyXML/
  tinyXML.py               doctor() + check/canon/sign/grade + ledger
  tests/fixtures/          XML real para los refusals
  tests/test_tinyXML.py    13 tests que pinnean los refusals
  README.md · RESULTS.md · pyproject.toml · LICENSE
```

## Las cuatro invariantes

1. **`doctor()` mide** — parsea, canonicaliza dos veces, rechaza XXE, reporta
   posición de error.
2. **Cada verbo tiene refusal** — archivo ausente, no-XML, mal formado, XXE,
   canonicidad no determinista.
3. **El contrato se lee de los bytes** — nunca del nombre de archivo.
4. **Un receipt es claim hasta re-ejecutar** — `grade()` canonicaliza dos veces
   y compara bytes.

## Use

```bash
python tinyXML.py doctor                 # la cadena completa
python tinyXML.py check <doc.xml>        # mide: linea/columna, profundidad, namespaces
python tinyXML.py canon <doc.xml>        # forma canónica determinista
python tinyXML.py sign <doc.xml>         # canonicaliza + firma con tinyqr
python tinyXML.py grade <doc.xml>        # determinismo, byte a byte
python tinyXML.py ledger                 # integridad de la cadena
```

## Medido en esta máquina

Ver `RESULTS.md`.

## Límites (una capacidad sin su límite es marketing)

- **La canonicalización es C14N-like, no C14N 1.0 completo.** Ordena atributos,
  resuelve entidades y conserva el texto, pero **no re-declara namespaces** ni
  normaliza atributos de namespace como exigiría la especificación. Para firmar
  entre partes, ambas deben usar tinyXML.
- **No hay XSD.** `lxml` no está instalado en esta máquina; la validación de
  esquema queda fuera.
- **El whitespace ES contenido.** A diferencia de HTML, en XML los espacios entre
  elementos son texto. La canonicalización los conserva — y un test lo pinnea.
- **`sign` cubre la forma canónica, no los bytes del archivo.** Dos archivos con
  distinta indentación pero el mismo documento producen la misma firma.

## Ledger

`C:\æ\logs\tinyXML.jsonl` (override `TINYXML_LEDGER`). Append-only, hash-chain,
registra DECISIONES, nunca intención.

---

*#opensourceware · medido, no declarado · el documento es el contrato*
