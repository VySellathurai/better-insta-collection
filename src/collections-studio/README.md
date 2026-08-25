# Collections Studio

Pick one Instagram saved collection (from `../../your_instagram_activity/saved/saved_collections.json`),
trigger collect+digest scoped to just that collection — hard-capped at **3 new videos per click**
(a fixed safety constant, not configurable — collect.py's yt-dlp/gallery-dl calls hit real Instagram
endpoints) — and see the resulting digested posts.

Self-contained, file-based: reads/writes `../../Vault/` directly, same as the Python pipeline. No
Postgres/Docker (unlike `../backoffice/`).

## Run it

```bash
cd src/collections-studio
cp .env.example .env       # adjust paths if your layout differs
npm install
npm run dev                 # http://localhost:3100
```

Requires the Python side already set up (`make install` at the repo root, Firefox logged into
Instagram) since this app shells out to `uv run reels-collect` / `uv run reels-digest`.

## What's in here

- `lib/collections.ts` — parses `saved_collections.json` (handles Meta's Latin-1/UTF-8 mojibake
  export bug), lists collections, extracts a given collection's ordered URL list.
- `lib/job-runner.ts` — in-memory background job: spawns `reels-collect` (limited to 3, scoped to
  the selected collection via `--collection`) then `reels-digest` (same scope), tracks status/logs.
  Only one job runs at a time.
- `lib/vault-parse.ts` / `lib/vault-results.ts` — reads `Vault/index.md` + `Vault/raw/*.md`,
  filtered to fiches whose `collection:` frontmatter matches the selected collection.
- `app/page.tsx` — collection picker + trigger + live job status + results, all Server-Component-first.
- `app/api/job/status/route.ts` — polled by the client to show live progress.

## First-time gotcha on this checkout

`Vault/journal.json` may already mark some URLs as collected from earlier testing even though no
matching fiche exists in `Vault/raw/` — `collect.py`'s existing resumability logic will then skip
them as already-done. If a collection's trigger reports "0 collected" unexpectedly, check whether
its URLs are stuck in `journal.json` with `"statut": "ok"` and no matching file, and clear those
entries if so.
