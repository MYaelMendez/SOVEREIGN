# Results

Every number measured on this machine by `tinyXML doctor` / `check` / `sign`.

## Machine

```
Host    teknium · Windows 11 · git-bash
Python  3.14.9
Deps    stdlib (xml.etree, xml.parsers.expat, xml.sax) + defusedxml
lxml    NO — no instalado; la canonicalizacion es propia (C14N-like)
```

## doctor()

```
probe              XML bien formado
parser             defusedxml.ElementTree
namespaces         2
canonical          149 chars · sha 52dbb4a0d080…
deterministic      true
xxe_refused        true
error_position     linea 1, columna 9
ok                 true
```

## El XML real del fleet

`github-pages/ffmpeg-asimov/asimov_1_25dof.xml` (30,002 B, el MJCF del robot):

```
well_formed        true
depth              10
namespaces         []
canonical_sha256   408dfbf660c0a97129c61d279f033ae02ea0275c6b5befc9834638f5fa2a816d
deterministic      true
ok                 true
```

## La diagnosis que ElementTree no da

`tinySVG.html` **no es XML** (es HTML). ElementTree solo dice «mal formado»:

```
tinyXML check → no es XML bien formado: not well-formed (invalid token)
                (linea 13, columna 68)
```

Ese es el valor del instrumento: la **posición**, no el veredicto.

## XXE

```
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>
<foo>&xxe;</foo>
```

Con `defusedxml` → `EntitiesForbidden`. El doctor lo pinnea; un XML con DOCTYPE
recibe advertencia en `check`.

## Canonicalización

```python
canon('<r b="2" a="1"/>') == canon('<r a="1" b="2"/>')   # atributos ordenados
```

Dos canonicalizaciones del mismo árbol → **byte a byte iguales**.

### El límite, declarado

**El whitespace ES contenido en XML.** A diferencia de HTML, los espacios entre
elementos son texto, y la canonicalización los conserva. Un test lo pinnea:
`<c> x </c>` y `<c>x</c>` producen formas distintas. Un canonicalizador que
normalizara el whitespace haría que dos documentos distintos hashearan igual.

## Firmar

```
python tinyXML.py sign <doc.xml>
```

Firma la **forma canónica** con `tinyqr` (clave `sovereign-web`). Dos archivos con
distinta indentación pero el mismo documento producen la **misma firma**: eso es
precisamente lo que se quiere.

## Tests

13/13.

| refusal | pinned por |
|---|---|
| archivo ausente | `test_missing_file` |
| XML mal formado + posición | `test_broken_xml_reports_line_and_column` |
| HTML no es XML | `test_html_is_not_xml` |
| XXE | `test_xxe_is_refused` |
| atributos reordenados | `test_attributes_are_sorted` |
| texto conservado | `test_text_is_preserved_exactly` |
| firma de lo canónico | `test_signs_the_canonical_form` |
| firma sobre XML roto | `test_sign_refuses_a_broken_document` |
| ledger | `test_chain_verifies` |

## Ledger

```
chain_ok  true
records   1
head      3990cebdfb2c
```
