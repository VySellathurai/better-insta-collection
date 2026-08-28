# Collections Studio

Pick one Instagram saved collection (from `../../your_instagram_activity/saved/saved_collections.json`),
trigger the pipeline scoped to just that collection — you choose how many new links per click via
a form field, defaulting to 3, **hard-capped at 50 server-side** (the pipeline's yt-dlp/gallery-dl
calls hit real Instagram endpoints, so this ceiling is always re-enforced in `lib/job-runner.ts`
regardless of what the form sends) — and see the resulting posts once published.

Reads/writes `../../Vault/images/` directly (extracted frames only — no more `index.md`/`raw/*.md`,
see `../reels_pipeline/`). Everything else — collection results, resumability/dedup — comes
from the same Postgres database `../backoffice/` reads, populated by the Python pipeline.

## Run it

```bash
cd src/collections-studio
cp .env.example .env       # DATABASE_URL must match ../backoffice/.env's
npm install
ln -s ../../../Vault/images public/images   # or: make cs-images-link from the repo root
npm run dev                 # http://localhost:3100
```

(`make cs-setup` from the repo root does all of the above, including the symlink.)

Requires the Python side already set up (`make install` at the repo root, Firefox logged into
Instagram) and `../backoffice/`'s Postgres running and migrated (`make bo-db-up bo-db-migrate`)
— this app shells out to `uv run reels-pipeline` and reads its output straight from that database.

## What's in here

- `lib/collections.ts` — parses `saved_collections.json` (handles Meta's Latin-1/UTF-8 mojibake
  export bug), lists collections, extracts a given collection's ordered URL list.
- `lib/job-runner.ts` — in-memory background job: spawns a single `reels-pipeline` subprocess
  (limited to the requested count, clamped server-side to 50, scoped to the selected collection via
  `--collection`, pointed at `DATABASE_URL`), tracks status/logs. Only one job runs at a time.
- `lib/db.ts` — one hand-written SQL query (via the `postgres` driver, no Drizzle) returning a
  collection's published posts with their themes and images, joined/aggregated from the same
  `posts`/`themes`/`post_themes`/`post_images` tables `../backoffice/db/schema.ts` owns and migrates.
  There's no shared package between the two apps, so this query's column names are kept in sync
  with that schema by hand.
- `public/images` — symlink to `../../../Vault/images`, same convention as `../backoffice/`, so
  `next/image` can serve the extracted frames directly.
- `app/page.tsx` — collection picker + trigger + live job status + results, all Server-Component-first.
- `app/api/job/status/route.ts` — polled by the client to show live progress.
