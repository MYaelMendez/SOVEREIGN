# Results

Every number measured on this machine by `tinyaudio doctor` / `loss` / `grade`.

## Machine

```
Host     teknium · Windows 11 · git-bash
ffmpeg   n7.1.5-12-g1fdbca85aa  (C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-7.1-nvenc\bin)
codecs   flac · aac · aac_mf · libmp3lame · libopus · opus · pcm_s16le · pcm_f32le
muxers   wav · mp3 · ogg · oga · adts · flac · ipod
filtros  284 de audio
python   numpy OK · scipy OK · wave OK · audioop OK · (soundfile/librosa NO)
estudio  agents/scratch_studio/v1-studio/track.wav · 18.497 s · 24000 Hz · mono · pcm_s16le
```

## doctor()

```
codecs         flac=ok, aac=ok, libmp3lame=ok, libopus=ok
numpy          ok
wave           ok
studio         18.497s · 24000Hz · 1ch · pcm_s16le · peak -0.087 dB
grade_flac     determinista en esta maquina (lossless)
grade_aac      determinista en esta maquina (lossy)
loss_mp3_128k  26.04 dB SNR
ok             true
```

## La suposición que el instrumento refutó

Escribí `grade` asumiendo que **un codec lossy no puede ser determinista**.
Medido:

```
aac 128k, dos encodes → mismo sha256
verdict: "determinista en esta maquina (lossy)"
```

El doctor **rechazó esa aserción** (`REFUSED: un codec lossy no puede ser
determinista`) y el código se corrigió: la reproducibilidad se **mide**, no se
supone. El mismo encoder, la misma versión y la misma máquina sí reproducen.

## La pérdida, medida

`loss(track.wav, track.mp3 @128k)`:

```
snr_dB             26.04
lossless           false
samples_compared   ...
```

Ese es el número que un MP3 esconde: **26 dB de SNR**, no «suena bien».

Para contraste, FLAC da SNR > 90 dB y `lossless: true`.

## ffmpeg elige el muxer por la EXTENSIÓN

Un archivo de salida sin extensión (`out`) hace que ffmpeg falle aunque el codec
sea válido. tinyAUDIO lo resolvió con una tabla `EXT` y lo **pinnea un test**:

```
encode(src, "out", "flac")  →  dst "out.flac" · ok
```

## Determinismo por codec

| codec | lossy | determinista aquí |
|---|---|---|
| flac | no | ✓ |
| aac 128k | sí | ✓ medido |
| libmp3lame | sí | medido |
| libopus | sí | medido |

`grade` nunca afirma sin medir; el verdict dice **en esta maquina**.

## Tests

12/12.

| refusal / chequeo | pinned por |
|---|---|
| archivo ausente | `test_missing_file` |
| no-audio | `test_non_audio_file` |
| sin extensión | `test_encode_requires_an_extension` |
| pérdida de un lossy | `test_lossy_has_a_real_loss` |
| fidelidad de un lossless | `test_lossless_is_near_infinite_snr` |
| lossy medido, no asumido | `test_lossy_is_MEASURED_not_assumed` |
| canales distintos | `test_loss_refuses_mismatched_channels` |
| ledger | `test_chain_verifies` |

## Ledger

```
chain_ok  true
records   1
head      3990cebdfb2c
```
