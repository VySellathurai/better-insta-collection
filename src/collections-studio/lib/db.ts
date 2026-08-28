import "server-only";
import postgres from "postgres";

import { DATABASE_URL } from "./paths";

// Same driver as ../backoffice/db/client.ts, but no Drizzle here — this app
// only ever needs one read query, so a hand-written SQL string against the
// schema backoffice/db/schema.ts owns (and migrates) is simpler than pulling
// in Drizzle + hand-copying its schema module (the two apps have no shared
// package to import it from — see collections-studio/README.md). Keep this
// query's column/table names in sync with that schema by hand.
const globalForDb = globalThis as unknown as { csPgClient?: postgres.Sql };

const client = globalForDb.csPgClient ?? postgres(DATABASE_URL);

if (process.env.NODE_ENV !== "production") {
  globalForDb.csPgClient = client;
}

export type DisplayPost = {
  titre: string;
  lien: string;
  auteur: string;
  themes: string[];
  contenu: string;
  images: string[];
};

type Row = {
  title: string;
  source_url: string;
  author: string;
  summary: string;
  themes: string[];
  images: string[];
};

export async function getCollectionResults(collectionName: string): Promise<DisplayPost[]> {
  // Themes and images are pre-aggregated in their own subqueries (each is a
  // 1:many join off `posts` on its own) before joining back to posts — doing
  // both joins directly against `posts` in one GROUP BY would fan out into a
  // cross product (3 themes × 3 images = 9 rows per post) and corrupt both
  // array_aggs.
  const rows = await client<Row[]>`
    SELECT p.title,
           p.source_url,
           p.author,
           p.summary,
           coalesce(t.themes, '{}') AS themes,
           coalesce(i.images, '{}') AS images
    FROM posts p
    LEFT JOIN (
      SELECT pt.post_id, array_agg(th.name) AS themes
      FROM post_themes pt
      JOIN themes th ON th.id = pt.theme_id
      GROUP BY pt.post_id
    ) t ON t.post_id = p.id
    LEFT JOIN (
      SELECT pi.post_id, array_agg(pi.file_name ORDER BY pi.position) AS images
      FROM post_images pi
      GROUP BY pi.post_id
    ) i ON i.post_id = p.id
    WHERE p.collection = ${collectionName}
    ORDER BY p.processed_at DESC
  `;

  return rows.map((r) => ({
    titre: r.title,
    lien: r.source_url,
    auteur: r.author,
    themes: r.themes,
    contenu: r.summary,
    images: r.images,
  }));
}
