# Backoffice

A Postgres-backed back office that displays the digested Instagram posts written directly by the
Python pipeline (`../reels_pipeline`'s `reels-pipeline`), plus a small read-only JSON API on top of
the database.

Self-contained Node/TypeScript project — reads the same Postgres database the pipeline writes to,
and `Vault/images/` on disk (via a symlink) for the extracted frames. No other coupling to the
Python side.

## Run it end-to-end

```bash
cd src/backoffice
cp .env.example .env          # adjust POSTGRES_*/DATABASE_URL if the defaults don't suit you
npm install

# create the images symlink once (Next serves Vault/images via public/images)
rm -rf public/images
ln -s ../../../Vault/images public/images

npm run db:up          # docker compose up -d — postgres only, host port 5433
npm run db:generate    # first run, or after editing db/schema.ts
npm run db:migrate
npm run dev              # http://localhost:3000
```

Then run `reels-pipeline` (see the repo root `README.md` or the root `Makefile`'s `pipeline`
target) against the **same** `DATABASE_URL` — it upserts directly into Postgres as it processes
each link. There is nothing to seed here: this app only ever reads.

## What's in here

- `db/schema.ts` — Drizzle schema: `posts`, `themes`, `post_themes`, `post_images`. This is the
  schema authority — `reels-pipeline` only ever runs DML against it, never DDL/migrations.
- `lib/queries.ts` — shared typed queries used by both the API routes and the page.
- `app/api/posts`, `app/api/posts/[slug]`, `app/api/themes` — read-only JSON API.
- `app/page.tsx` + `components/gallery.tsx` — the display page, fetching directly via
  `lib/queries.ts` (not by calling its own API), with search + theme-pill filtering.

## Populating Postgres

Postgres is populated directly by `reels-pipeline` — there is nothing to seed. Just make sure
the pipeline's `--database-url` (or `DATABASE_URL` env var) points at the same database as this
app's `.env`. New/updated posts show up here on the next page load (newest-processed first).
