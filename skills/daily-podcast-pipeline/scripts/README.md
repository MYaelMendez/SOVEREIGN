# Skills — Daily Podcast Pipeline

Class-level skill for generating daily podcast episodes from social media posts.
See parent SKILL.md for the procedure and pitfalls.

## Static re-runnable scripts

| Script | Purpose |
|--------|---------|
| `scripts/cron/social_feed.py` | Gather X/Twitter + Bluesky posts → `feeds/<date>.json` |
| `scripts/cron/daily_pod_cron.py` | Full pipeline: gather → spec → render → gate → mux → export → deploy → receipt |
| `scripts/cron/daily_pod-cron.bat` | schtasks wrapper (hourly every 6h) |

## Feed store

```
scripts/cron/feeds/
  feeds-20261013.json
  feeds-<date>.json   # one per daily run
```

## Spec store

```
studio/specs/
  spec-daily-<timestamp>.json
  receipt-daily-<date>.json
```

## Deployed output

```
github-pages/aipodcast_me/
  <timestamp>.mp4
  <timestamp>.mp3
  spec-daily-<ts>.json
```
