import { sql } from "drizzle-orm";
import {
  check,
  date,
  doublePrecision,
  index,
  integer,
  pgTable,
  primaryKey,
  serial,
  text,
  uniqueIndex,
} from "drizzle-orm/pg-core";

/**
 * Same shape as src/backoffice/db/schema.ts, on purpose: this database is a
 * separate, dedicated Postgres instance (own docker-compose, own port), but
 * it's still populated by the exact same `reels-pipeline` binary (see the
 * repo root Makefile's `mm-pipeline` target) — publish.py's SQL targets these
 * fixed table/column names, so any database it writes to must match this
 * shape. Kept independent (copy, not import) so this project's schema can
 * evolve on its own without coupling to backoffice's migrations.
 */

/** Kept in sync with reels_pipeline/extract_images.py's 3-frame video
 * extraction — but note carousel posts (gallery-dl) aren't capped at 3, so
 * reels_pipeline/publish.py's publish_item() truncates each post's images
 * to this many before insert. */
export const MAX_IMAGES_PER_POST = 3;

export const posts = pgTable(
  "posts",
  {
    id: text("id").primaryKey(), // slug, e.g. insta_DMe9e8GoNYy
    sourceUrl: text("source_url").notNull(),
    platform: text("platform").notNull(),
    genre: text("genre"),
    author: text("author").notNull(),
    authorHandle: text("author_handle"),
    durationS: doublePrecision("duration_s"),
    processedAt: date("processed_at", { mode: "date" }).notNull(),
    status: text("status").notNull(),
    title: text("title").notNull(),
    summary: text("summary").notNull(),
    description: text("description"),
    transcript: text("transcript"),
    // Toujours "Musée des Mêmes" ici (voir mm-pipeline dans le Makefile), mais
    // la colonne reste requise : publish.py l'écrit inconditionnellement.
    collection: text("collection"),
  },
  (t) => ({
    sourceUrlUnique: uniqueIndex("posts_source_url_unique").on(t.sourceUrl),
    // Sert la seule requête de la grille (ORDER BY processed_at DESC LIMIT/OFFSET)
    // — pas là dans backoffice (il trie pareil mais n'a jamais eu besoin de
    // l'index vu son volume), ajouté ici en prévision du volume de la collection.
    processedAtIdx: index("posts_processed_at_idx").on(t.processedAt),
  }),
);

export const themes = pgTable(
  "themes",
  {
    id: serial("id").primaryKey(),
    slug: text("slug").notNull(),
    name: text("name").notNull(),
  },
  (t) => ({
    slugUnique: uniqueIndex("themes_slug_unique").on(t.slug),
  }),
);

export const postThemes = pgTable(
  "post_themes",
  {
    postId: text("post_id")
      .notNull()
      .references(() => posts.id, { onDelete: "cascade" }),
    themeId: integer("theme_id")
      .notNull()
      .references(() => themes.id, { onDelete: "cascade" }),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.postId, t.themeId] }),
    themeIdIdx: index("post_themes_theme_id_idx").on(t.themeId),
  }),
);

export const postImages = pgTable(
  "post_images",
  {
    postId: text("post_id")
      .notNull()
      .references(() => posts.id, { onDelete: "cascade" }),
    position: integer("position").notNull(), // 1..MAX_IMAGES_PER_POST
    fileName: text("file_name").notNull(),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.postId, t.position] }),
    positionCheck: check(
      "post_images_position_check",
      sql`${t.position} BETWEEN 1 AND ${sql.raw(String(MAX_IMAGES_PER_POST))}`,
    ),
  }),
);
