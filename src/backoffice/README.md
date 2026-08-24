# Backoffice

A Postgres-backed back office that displays the digested Instagram posts from `../../Vault`
(the same data `reels-publish` renders into `Vault/gallery.html`), plus a small read-only
JSON API on top of the database.

Self-contained Node/TypeScript project — isolated from the Python pipeline in
`../reels_vault/`, sharing only the `Vault/` flat-file data contract on disk.

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
npm run db:seed         # parses ../../Vault and reloads all rows into Postgres
npm run dev              # http://localhost:3000
```

## What's in here

- `db/schema.ts` — Drizzle schema: `posts`, `themes`, `post_themes`, `post_images`.
- `scripts/parse-vault.ts` / `scripts/seed.ts` — parses `Vault/index.md` + `Vault/raw/*.md`
  (ported from `src/reels_vault/publish.py` and `_naming.py`) and truncate-reloads Postgres.
- `lib/queries.ts` — shared typed queries used by both the API routes and the page.
- `app/api/posts`, `app/api/posts/[slug]`, `app/api/themes` — read-only JSON API.
- `app/page.tsx` + `components/gallery.tsx` — the display page, fetching directly via
  `lib/queries.ts` (not by calling its own API), reproducing `gallery.html`'s search +
  theme-pill filtering UX.

## Re-seeding

Re-run `npm run db:seed` any time `Vault/` changes (e.g. after `make digest` / `make publish`
in the repo root). It's a full truncate-and-reload each time, so it's safe to re-run.
