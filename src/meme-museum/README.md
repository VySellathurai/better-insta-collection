# Meme Museum

A minimal Instagram-style grid of every post collected from one locked Instagram saved
collection — **"Musée des Mêmes"** — via the same `../reels_pipeline`'s `reels-pipeline` used
elsewhere in this repo.

Fully self-contained: its own Postgres database (own `docker-compose.yml`, own port), its own
pipeline vault (`vault/`, own downloaded/extracted media — not shared with the root `Vault/`),
and its own UI. No coupling to `../backoffice/` or `../collections-studio/` beyond running the
same Python pipeline binary with different arguments.

## Run it end-to-end

```bash
cd src/meme-museum
cp .env.example .env
npm install

npm run db:up          # docker compose up -d — postgres only, host port 5434
npm run db:generate    # first run, or after editing db/schema.ts
npm run db:migrate

# create the images symlink once (Next serves vault/images via public/images)
rm -rf public/images
ln -s ../vault/images public/images

npm run dev              # http://localhost:3200
```

(`make mm-setup` from the repo root does the Postgres + migration steps for you.)

Then collect posts with the pipeline, **locked to this collection** — the repo root
`Makefile`'s `mm-pipeline` target always passes `--collection "Musée des Mêmes"`,
`--vault src/meme-museum/vault`, and `--database-url` pointing at this project's own Postgres, so
there's no risk of it writing anywhere else:

```bash
cd ../..    # repo root
make mm-pipeline COOKIES=firefox LIMIT=20
```

## What's in here

- `db/schema.ts` — Drizzle schema: `posts`, `themes`, `post_themes`, `post_images`. Same shape as
  `../backoffice/db/schema.ts` on purpose — `reels-pipeline`'s `publish.py` runs fixed-column-name
  SQL against whichever database it's pointed at, so any target database must match this shape.
  Kept as an independent copy (not shared/imported) so this project's schema can evolve on its own.
  Adds one index over `../backoffice`'s version: `posts_processed_at_idx`, for the grid's
  `ORDER BY processed_at DESC LIMIT/OFFSET` pagination query.
- `lib/queries.ts` — `getPostsPage(page)`: the only query this app runs. Fetches each post's
  **first** collected image (`post_images` where `position = 1`) via a correlated subquery rather
  than a join — a join here would fan out one row per image and corrupt pagination, the same class
  of bug `../collections-studio/lib/db.ts` hit and fixed for its own (multi-image) query.
- `app/page.tsx` + `components/post-tile.tsx` — the whole UI: a 4-column CSS grid of square tiles,
  each showing the post's first image and linking out to the original Instagram post. Deliberately
  no search/filtering/theme UI — this is a single-collection grid, not a general browser.
- `public/images` — symlink to `./vault/images`.
- `vault/` — this project's own pipeline working directory (created by `reels-pipeline` on first
  run) — audio/video temp files and extracted frames, gitignored.

## Why its own database

The pipeline's `--database-url` is just a connection string — `publish.py` doesn't care which
Postgres it's talking to, only that the table shape matches. Giving this project its own instance
(rather than reusing `../backoffice/`'s) keeps "Musée des Mêmes" fully isolated: no risk of this
grid's queries slowing down or being affected by unrelated collections, and no risk of `mm-pipeline`
ever writing into the wrong database.

## Populating Postgres

There is nothing to seed — `make mm-pipeline` (or `reels-pipeline ... --collection "Musée des
Mêmes" --database-url <this-project's-DATABASE_URL>` directly) upserts straight into Postgres as
it processes each link. New posts show up here on the next page load (newest-processed first).
