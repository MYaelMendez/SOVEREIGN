# Three.JSæRTX — Módulo de Render Determinístico

**Nivel:** Avanzado (requiere Fase 1-4 del currículo Three.js)
**Duración:** 2 semanas (16 horas)
**Prerrequisitos:** Fase 4 completa (shaders avanzados), Node.js, Chrome headless
**Filosofía:** Cada frame es un artefacto verificable. Same input → same video, byte for byte.

---

## El Problema que Resuelve æRTXrender

El render determinístico es la diferencia entre un demo y un sistema de producción.

**Render tradicional (no determinístico):**
```
requestAnimationFrame → render → capture → encode
     ↑ desync, black frames, dropped frames, non-reproducible
```

**æRTXrender (determinístico):**
```
__renderFrame(i, total) → GPU paint → capture → verify → encode
     ↑ frame i is ALWAYS the same visual, every run
```

El hook `__renderFrame(i, totalFrames)` reemplaza al `requestAnimationFrame`. El agente controla el tiempo, no el navegador.

---

## Semana 1: Pipeline Determinístico

### Día 1: El Hook `__renderFrame`

```javascript
// ❌ WRONG — pause() takes seconds, not 0-1
window.__renderFrame = function(i, total) {
  tl.pause(i / (total - 1));  // BUG
  render();
};

// ✅ CORRECT — progress() takes 0-1
window.__renderFrame = function(i, total) {
  tl.progress(i / Math.max(1, total - 1));
  render();
};
```

**Verificación:** Render 450 frames dos veces. Los hashes SHA-256 deben ser idénticos.

### Día 2: Integración con render.mjs

```bash
# Render determinístico con NVENC
node render.mjs \
  --url=http://127.0.0.1:8123/scene.html \
  --out=output.mp4 \
  --frames=450 \
  --fps=30 \
  --w=720 \
  --h=1280 \
  --encoder=nvenc \
  --supervise-preview
```

**Verificación:** El output MP4 tiene hash reproducible. `ffmpeg -i output.mp4` muestra 720x1280, 30fps, h264_nvenc.

### Día 3: Supervisión de Frames

```bash
# Verificar frames antes de encode
C:/gpu/Scripts/python.exe C:/æ/vidæo/vidæo.py verify output-frames/
```

**Gate thresholds:**
```
luminancia_media  > 20   (video-level minimum)
contraste_medio   > 8
movimiento_medio  > 0.5
frames_negros     < 5%   (0% ideal)
```

**Verificación:** Si `frames_negros > 10%`, el render se rechaza antes de encode.

### Día 4: NVENC vs libx264

```bash
# NVENC (GPU, rápido, requiere driver 592.27 + ffmpeg 7.1)
node render.mjs --url=... --out=nvenc.mp4 --encoder=nvenc

# libx264 (CPU, compatible, más lento)
node render.mjs --url=... --out=x264.mp4 --encoder=libx264

# Auto (prueba NVENC, fallback a libx264)
node render.mjs --url=... --out=auto.mp4 --encoder=auto
```

**Verificación:** NVENC produce el video en ~30s. libx264 en ~3min. Ambos son visualmente equivalentes.

### Día 5: PID Lock y Concurrencia

```bash
# Si un render anterior falló sin limpiar:
rm output.mp4.lock

# Verificar que no hay renders concurrentes
tasklist | findstr node
```

**Verificación:** Dos renders concurrentes no pueden escribir al mismo output.

### Día 6: Captura CDP (Chrome DevTools Protocol)

```javascript
// render.mjs usa CDP para:
// 1. Navegar a la URL
// 2. Set viewport exacto (720x1280)
// 3. Inyectar __renderFrame
// 4. Capturar cada frame como PNG
// 5. Verificar que no es negro
```

**Verificación:** `Page.captureScreenshot` devuelve PNGs de exactamente 720x1280.

### Día 7: Proyecto Mini

**Entregable:** `aertx-demo.html` — escena Three.js con:
- 1000 cubos instancados
- Animación GSAP con `tl.progress()`
- Hook `__renderFrame` funcional
- Render determinístico a MP4 verificado

---

## Semana 2: Integración con el Currículo

### Día 8: Three.js + æRTXrender + QR

```html
<!-- Escena Three.js con badge QR de verificación -->
<div id="scene-container"></div>
<div id="æ-qr-badge">
  <img src="https://api.qrserver.com/v1/create-qr-code/?size=48x48&data=https://myaelmendez.github.io/aertx-demo.html&color=D4AF37&bgcolor=050505">
</div>
```

**Verificación:** El QR apunta a la URL canónica de la superficie.

### Día 9: Telemetría GPU en Vivo

```javascript
// nvidia-smi snapshot durante el render
const { execSync } = require('child_process');
const gpuInfo = execSync('nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader').toString();
console.log(gpuInfo);
// NVIDIA GeForce RTX 3050 Laptop GPU, 6144 MiB, 6144 MiB, 85 %
```

**Verificación:** El render usa < 6GB VRAM. La utilización GPU es > 80%.

### Día 10: Receipt de Render

```json
{
  "render_id": "aertx-20261008-001",
  "url": "http://127.0.0.1:8123/scene.html",
  "output": "output.mp4",
  "frames": 450,
  "fps": 30,
  "resolution": "720x1280",
  "encoder": "nvenc",
  "sha256": "abc123...",
  "gpu": "RTX 3050",
  "vram_used": "6144 MiB",
  "duration_seconds": 45.2,
  "supervision": "PASS",
  "timestamp": "2026-10-08T12:00:00Z"
}
```

**Verificación:** El receipt tiene hash SHA-256 del MP4. El receipt es verificable.

### Día 11: VLC Pane — Gate Visual Humano

```bash
# Abrir el MP4 en VLC para verificación humana
vlc output.mp4
```

**Reglas VLC 3.0.x:**
- `in_play` carga (nunca `pl_add`, no-op silencioso)
- Paths Unicode → copiar a `%TEMP%/vlc-preview/` ASCII
- Estado real desde `http://127.0.0.1:8081/requests/status.json`

**Verificación:** El humano VE el video. El supervisor NO es todo el gate.

### Día 12: WebMCP + æRTXrender

```javascript
// Registrar herramienta WebMCP para render
server.registerTool('render_video', {
  description: 'Render Three.js scene to verified MP4',
  parameters: {
    url: { type: 'string', description: 'Scene URL' },
    frames: { type: 'number', default: 450 },
    fps: { type: 'number', default: 30 }
  },
  handler: async (params) => {
    const result = await renderDeterministic(params);
    return { receipt: result.receipt, video: result.output };
  }
});
```

**Verificación:** El agente puede invocar `render_video` y recibir un receipt verificable.

### Día 13: Fleet Waves — Render Distribuido

```bash
# Render la misma escena desde 4 rutas diferentes
node render.mjs --url=... --out=render-1.mp4 --port=9333
node render.mjs --url=... --out=render-2.mp4 --port=9334
node render.mjs --url=... --out=render-3.mp4 --port=9335
node render.mjs --url=... --out=render-4.mp4 --port=9336

# Verificar que todos producen el mismo hash
sha256sum render-*.mp4
```

**Verificación:** Los 4 renders producen hashes idénticos. El sistema es determinístico.

### Día 14: Publicación Automática

```bash
# Si el gate PASS, publicar automáticamente
if grep -q "PASS" supervision.txt; then
  git add output.mp4 receipt.json
  git commit -m "æ:// render verified — output.mp4"
  git push origin gh-pages
fi
```

**Verificación:** El MP4 está live en `https://myaelmendez.github.io/output.mp4`.

### Día 15: Catálogo Vivo

```javascript
// catalog.json — catálogo de renders verificados
{
  "renders": [
    {
      "id": "aertx-20261008-001",
      "title": "1000 Cubos Instanciados",
      "url": "https://myaelmendez.github.io/output.mp4",
      "sha256": "abc123...",
      "supervision": "PASS",
      "gpu": "RTX 3050"
    }
  ]
}
```

**Verificación:** El catálogo es un JSON válido. Cada render tiene hash y receipt.

### Día 16: Proyecto Final

**Entregable:** `aertx-final.html` + `receipt.json` + `output.mp4`

**Requisitos:**
- Escena Three.js con 10k+ objetos
- Animación determinística con `__renderFrame`
- Render a 720x1280, 30fps, 450 frames
- Supervisión PASS
- QR badge de verificación
- Receipt con hash SHA-256
- Publicado en GitHub Pages

---

## Verificación Final

```bash
# 1. Render determinístico
node render.mjs --url=http://127.0.0.1:8123/aertx-final.html \
  --out=aertx-final.mp4 --frames=450 --fps=30 --encoder=nvenc --supervise-preview

# 2. Verificar hash reproducible
sha256sum aertx-final.mp4
# Render de nuevo → mismo hash

# 3. Verificar supervisión
C:/gpu/Scripts/python.exe C:/æ/vidæo/vidæo.py verify aertx-final-frames/
# Debe decir PASS

# 4. Verificar en VLC
vlc aertx-final.mp4
# El humano VE el video

# 5. Publicar
git add aertx-final.mp4 receipt.json
git commit -m "æ:// aertx-final — verified render"
git push origin gh-pages

# 6. Verificar live
curl -s https://myaelmendez.github.io/aertx-final.mp4 | sha256sum
# Debe coincidir con el hash local
```

---

## Métricas de æRTXrender

| Métrica | Baseline | Objetivo |
|---|---|---|
| Frames por render | 0 | 450+ |
| Hash reproducible | No | Sí |
| Supervisión PASS | No | Sí |
| VRAM usage | 0 MB | < 6 GB |
| Tiempo de render | 0s | < 60s |
| Publicación automática | No | Sí |
| QR badge | No | Sí |

---

## La Regla de Oro

```
Same input → same video, byte for byte.
```

Si el hash no es reproducible, el render es inválido.
Si el hash es reproducible, el render es un artefacto verificable.
Si es verificable, es soberano.

---

*Three.JSæRTX — Ingeniería Electrónica Agéntica con render determinístico*
*Versión 1.0 — Octubre 2026*
