# tinyAUDIO

El instrumento soberano del **canal de audio**. Apache-2.0 · stdlib + ffmpeg.

**tinyAUDIO no hace sonido.** Goberna el canal: prueba que los **codecs reales**
codifican, mide lo que entra, lo que sale y — la parte que nadie hace —
**cuánto se perdió**. AAC y MP3 son *lossy*: el instrumento **declara** la
pérdida en vez de fingir fidelidad.

La familia: `tinycuda` (píxeles) · `tinygpu` (robots) · `tinymujoco` (movimiento) ·
`tinycan` (el bus) · `tinycudavideo` (el seam) · `tinyffmpeg` (códecs) ·
`tinyqr` (identidad) · `tinySVG` (geometría) · `tinyXML` (el documento) ·
`tinyaudio` (el canal) · `tinylab` (el auto-estudio).

## When to use

- Vas a entregar audio y quieres el **recibo**: codec, bitrate, duración, pico, sha.
- Un MP3 «suena bien» pero quieres saber **cuánto perdió** (SNR medido).
- El audio y el vídeo de un film están desalineados.
- Quieres saber si un encode es **reproducible en esta máquina** — medido, no supuesto.

## Shape

```
tinyaudio/
  tinyaudio.py              doctor() + probe/encode/loss/sync/grade + ledger
  tests/test_tinyaudio.py   12 tests que pinnean los refusals y la suposicion refutada
  README.md · RESULTS.md · pyproject.toml · LICENSE
```

## Las cuatro invariantes

1. **`doctor()` mide los codecs de verdad** — codifica 0.2 s con flac/aac/mp3/opus.
2. **Cada verbo tiene refusal** — archivo ausente, no-audio, sin extensión.
3. **El contrato se lee del artefacto** — ffprobe sobre los bytes.
4. **Un receipt es claim hasta re-ejecutar** — `grade()` codifica dos veces.

## Use

```bash
python tinyaudio.py doctor                       # la cadena del canal
python tinyaudio.py probe <file>                 # duración, sr, ch, pico, RMS, clipping
python tinyaudio.py encode <in> <out> --codec libmp3lame --bitrate 128
python tinyaudio.py loss <original> <transcode>  # SNR medido — la pérdida real
python tinyaudio.py sync <audio> <video>         # delta de duración
python tinyaudio.py grade <in> --codec flac      # determinismo medido
python tinyaudio.py ledger                       # integridad de la cadena
```

## Medido en esta máquina

Ver `RESULTS.md`.

## Límites (una capacidad sin su límite es marketing)

- **La pérdida se computa en mono.** Si los canales difieren, `loss` se niega.
- **PCM de 24/32 bits no se comparan** (`wave` es 8/16 bits); el `loss` lo dice.
- **`sync` compara duraciones**, no hace correlación de señales. El offset fino de muestra queda fuera.
- **No compone ni sintetiza** — eso es `tinyvoca` (voz) y `heartmula` (música).
- **Sin `soundfile`/`librosa`**: el análisis espectral saldría de `numpy`+`scipy` o de `ffmpeg`.

## Ledger

`C:\æ\logs\tinyaudio.jsonl` (override `TINYAUDIO_LEDGER`). Append-only, hash-chain,
registra DECISIONES, nunca intención.

---

*#opensourceware · medido, no declarado · la pérdida se mide, no se asume*
