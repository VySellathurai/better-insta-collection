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
    // Nom de la collection Instagram source (src/collections-studio), NULL
    // pour les posts venus du pipeline "vault entier" sans collection.
    collection: text("collection"),
  },
  (t) => ({
    sourceUrlUnique: uniqueIndex("posts_source_url_unique").on(t.sourceUrl),
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
