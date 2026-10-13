# Daily Podcast Pipeline

Generate daily podcast episodes from gathered social media posts, using the
aipodcast engine (spec → render → gate → audio mux → deploy → receipt).
Runs as a daily cron (schtasks every 6h) and as a one-shot CLI.

## Scope

This skill covers the full daily podcast production loop:
gather social feed → synthesize spec → render with render.mjs →
gate video → mux audio + export MP3 → deploy to github-io →
write SHA-256 receipt. It does not cover the social source bridge
(X API credentials, Bluesky atproto keys) or the VLC visual gate.

## Always-On Rules

1. **Spec duration field is the hard cap.** `duration × fps = frames`.
   5-minute default episode = 1500 frames @ 30fps = 50s max. Do not
   change render.mjs defaults; pass `--frames` from spec.

2. **Render dimensions are NOT the defaults.** `render.mjs` ships with
   `W=720, H=1280` (portrait 9:16). Specs define `width`/`height`
   (typically 1920×1080 landscape). Always pass `--w`/`--h` from spec.

3. **Source of truth = myaelmendez.github.io.** Deployed MP4/MP3 at
   `aipodcast_me/` is the published surface. GitHub-pages branch is the
   deployment target, never the source.

4. **Never move secrets.** FFmpeg keys, Bluesky app-passwords, X API
   tokens live in `C:\æ\secrets\secrets.json` (never in transcripts,
   logs, or code). Read via `load_secret("key")` pattern.

5. **Receipt on every action.** SHA-256 of gathered feed is written to
   `receipt-daily-<date>.json` alongside the episode.

## Procedure

### Step 1 — Gather social feed
```bash
python3 scripts/cron/social_feed.py --source auto
```
Outputs: `scripts/cron/feeds/feeds-<date>.json`
- Reads BSKY_AGENT_* keys from vault; falls back to web_search for X.
- Returns 0 even when no posts found.

### Step 2 — Synthesize daily spec
Reads feed JSON, builds spec from `synthesize_daily_spec(feed)`:
```python
spec = synthesize_daily_spec(feed)
spec_path = generate_spec(spec, feed_path)
```
Default values: duration=15s, fps=30, width=1920, height=1080,
scene_html="demo-series-montage.html".

### Step 3 — Render episode
```bash
node threejs-curriculo/render.mjs \
  --url=http://localhost:8128/demo-series-montage.html \
  --out=studio/output/<timestamp>.mp4 \
  --w=1920 --h=1080 \
  --frames=<duration×fps> --fps=<fps> \
  --encoder=libx264
```
Default encoder `nvenc` fails on `æ` Windows paths — always use
`--encoder=libx264`. Output: 44KB+ H264 video, 15s at 1920×1080.

### Step 4 — Gate video
```python
gate_pass, metrics = gate_video(mp4_path)
```
Run `python3 vidæo/vidæo.py verify <mp4>`. Thresholds:
`lum > 20`, `con > 10`, `mov > 0.5`, `negros = 0`. **STOP if gate FAIL.**

### Step 5 — Mux audio + export MP3
```python
mp3_mux, _ = mux_audio(mp4_path)     # -map 0:v:0 -map 1:a:0
mp3_export = export_mp3(mp4_path)    # re-encode audio only
```
Use `libx264` re-encode on the fallback path (not `-c:v copy`).
`æ.mp3` is the audio source (NOT ae.mp3 — ligature issue).

### Step 6 — Deploy
Copy `*.mp4` and `*.mp3` to `github-pages/aipodcast_me/`,
commit, push to `origin gh-pages`.

### Step 7 — Write receipt
```python
receipt = {
    "day": "2026-10-13",
    "spec": "spec-daily-<ts>.json",
    "mp4": "021316.mp4",
    "mp3": "021316.mp3",
    "gate": "PASS",
    "receipt": "<sha256 of feed>",
    "source_feed": "feeds-20261013.json",
}
```

## Pitfalls

- **render.mjs default is portrait (720×1280).** Always pass `--w`
  `--h` from the spec. Missing this produces a 720×1280 video instead
  of the 1920×1080 landscape spec.
- **`-c:v copy` mux fails on 0-packet streams.** Re-encode with
  `libx264` + `aac` on the fallback path.
- **MP3 export uses is a separate step.** Muxing and exporting are
  distinct ffmpeg commands; do not conflate them.
- **No X API key yet?** web_search returns 0 tweets. Use Bluesky
  atproto bridge for actual social content.
- **`æ.mp3` ≠ `ae.mp3`.** The audio source is the ligature variant.

## Support Files

- `scripts/cron/social_feed.py` — social feed gatherer
- `scripts/cron/daily_pod_cron.py` — full pipeline CLI
- `scripts/cron/daily_pod-cron.bat` — schtasks wrapper
- `scripts/cron/feeds/` — gathered feed store
