# Daily Podcast Pipeline — Reference

## Render command template

```bash
node threejs-curriculo/render.mjs \
  --url=http://localhost:8128/demo-series-montage.html \
  --out=studio/output/<timestamp>.mp4 \
  --w=<width> --h=<height> \
  --frames=<duration×fps> --fps=<fps> \
  --encoder=<libx264|auto>
```

| Flag | Default in render.mjs | Spec override |
|------|----------------------|---------------|
| `--w` | 720 | 1920 (from spec) |
| `--h` | 1280 | 1080 (from spec) |
| `--frames` | 450 | duration × fps |
| `--fps` | 30 | spec fps |
| `--encoder` | nvenc | libx264 (never nvenc) |

## Audio mux and export

| Step | Command |
|------|---------|
| Mux audio into video | `ffmpeg -i video.mp4 -i C:/æ/threejs-curriculo/æ.mp3 -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -ar 44100 -shortest -y output.mp4` |
| Export MP3 | `ffmpeg -i video.mp4 -c:a aac -b:a 192k -ar 44100 -y output.mp3` |
| Audio source | `C:/æ/threejs-curriculo/æ.mp3` (NOT ae.mp3 — ligature issue) |

## Gate thresholds (vidæo.py verify)

| Metric | Minimum | Metric | Maximum |
|--------|---------|--------|---------|
| luminance | 20 | black frames | 0 |
| contrast | 10 | | |
| motion (movimiento_medio) | 0.5 | | |

## Social feed format (`feeds/<date>.json`)

```json
{
  "source": "daily-pod-social-gatherer",
  "date": "2026-10-13",
  "x_tweets": [ { "date", "author", "text", "url", "confidence" } ],
  "bluesky_posts": [ { "date", "author", "text", "url", "confidence" } ],
  "total": 0,
  "receipt": "sha256-first-16-chars"
}
```

## Spec format (spec-daily-<ts>.json)

```json
{
  "title": "æ:// Daily Pod — topic",
  "subtitle": "Semana 23 · <date> · <count> X posts · <count> Bluesky posts",
  "scene_guide": "theme1 · theme2 · …",
  "themes": ["t1", "t2", "t3"],
  "source_feed": "receipt",
  "source_files": ["feeds-<date>.json"],
  "duration": 15,
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "scene_html": "demo-series-montage.html",
  "spec_number": 2026101302
}
```

## Social source priority

| Priority | Source | Requirements |
|----------|--------|--------------|
| 1 | Bluesky atproto bridge | BSKY_AGENT_* in vault, atproto-private-client |
| 2 | X/Twitter web_search | web_search tool (no API key configured yet) |

## Deployment layout

```
github-pages/
  aipodcast_me/
    spec-daily-<ts>.json
    <timestamp>.mp4
    <timestamp>.mp3
```

Commit with: `git add <files>`, `git commit -m "video: daily pod <date>"`,
`git pull --rebase origin gh-pages`, `git push origin gh-pages`.
