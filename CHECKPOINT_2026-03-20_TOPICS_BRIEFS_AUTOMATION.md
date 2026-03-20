# Checkpoint 2026-03-20 — Topics / briefs / automation

## Included changes
- fixed dashboard/listen audio payload integration so `/dashboard` no longer crashes after the last Gemini patch
- unified topic seeding so every active topic is topped up to at least 10 RSS sources
- changed brief generation so every active topic gets a brief, even if no fresh articles are available yet
- added secured internal endpoints for:
  - `/internal/sync-rss`
  - `/internal/render-publish-briefs`
  - `/internal/pipeline-hourly`
- added GitHub Actions schedules for:
  - hourly RSS sync
  - render/publish briefs 3x daily

## Required setup after upload
1. Keep `SYNC_SECRET` in Render environment.
2. In GitHub repo settings → Secrets and variables → Actions, create secret:
   - `RESERSE_SYNC_SECRET` = same value as `SYNC_SECRET` on Render
3. In GitHub Actions, enable scheduled workflows if GitHub disabled them.

## Notes
- Render free web services can stay on free plan.
- Render Cron Jobs are paid-only, so scheduling is handled via GitHub Actions.
- Hourly RSS sync and 3x daily briefing are intentionally separated.
