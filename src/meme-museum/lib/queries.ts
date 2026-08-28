import "server-only";
import { asc, desc, eq, inArray, sql } from "drizzle-orm";

import { db } from "@/db/client";
import { postThemes, posts, themes } from "@/db/schema";

export type GridPost = {
  id: string;
  sourceUrl: string;
  title: string;
  cover: string | null;
  description: string | null;
  summary: string;
  tags: string[];
};

export type ThemeCount = {
  slug: string;
  name: string;
  count: number;
};

// 4 columns (see app/globals.css's .grid) x 10 rows per page.
export const PAGE_SIZE = 40;

export async function getPostsPage(
  page = 1,
  themeSlug?: string,
): Promise<{ items: GridPost[]; total: number }> {
  const offset = Math.max(page - 1, 0) * PAGE_SIZE;

  // Deliberately a correlated subquery, not a join: post_images is keyed
  // (post_id, position), so "position = 1" is a primary-key point lookup per
  // post — cheap, and it can never fan out into duplicate post rows the way
  // joining posts -> post_images directly would (see the fan-out bug fixed
  // in collections-studio/lib/db.ts — this sidesteps the whole class of bug).
  //
  // NOTE: `posts.id` is written as raw "posts.id" text here, NOT interpolated
  // as ${posts.id} — drizzle's sql`` template doesn't table-qualify an
  // embedded Column reference, so it renders as a bare "id". That's harmless
  // here (post_images has no column named id to collide with), but the same
  // pattern in `tags` below DOES collide with themes.id — see there.
  const cover = sql<string | null>`(
    select pi.file_name from post_images pi
    where pi.post_id = posts.id and pi.position = 1
  )`;

  // Same "correlated subquery, not a join" rule as `cover` above — an
  // array_agg via a direct join onto post_themes would fan out one row per
  // tag and corrupt pagination/count() exactly like a naive post_images join
  // would.
  //
  // `posts.id` MUST be qualified explicitly (not ${posts.id}, see note on
  // `cover` above): this subquery joins in `themes`, which has its own `id`
  // column, so an unqualified "id" resolves to the nearer themes.id (an
  // integer) instead of correlating out to posts.id (text) — Postgres then
  // fails with "operator does not exist: text = integer" comparing it
  // against post_themes.post_id. Caught live via the dev server's error log.
  const tags = sql<string[]>`(
    select coalesce(array_agg(th.name order by th.name), '{}')
    from post_themes pt join themes th on th.id = pt.theme_id
    where pt.post_id = posts.id
  )`;

  // Same rule applied to the theme filter: a subquery producing matching
  // post ids, not a join from posts onto post_themes/themes directly (which
  // would fan out one row per tag and corrupt both pagination and count()).
  const whereClause = themeSlug
    ? inArray(
        posts.id,
        db
          .select({ postId: postThemes.postId })
          .from(postThemes)
          .innerJoin(themes, eq(themes.id, postThemes.themeId))
          .where(eq(themes.slug, themeSlug)),
      )
    : undefined;

  const [items, totalRows] = await Promise.all([
    db
      .select({
        id: posts.id,
        sourceUrl: posts.sourceUrl,
        title: posts.title,
        cover,
        description: posts.description,
        summary: posts.summary,
        tags,
      })
      .from(posts)
      .where(whereClause)
      .orderBy(desc(posts.processedAt))
      .limit(PAGE_SIZE)
      .offset(offset),
    db.select({ count: sql<number>`count(*)::int` }).from(posts).where(whereClause),
  ]);

  return { items, total: totalRows[0]?.count ?? 0 };
}

export async function getThemeCounts(): Promise<ThemeCount[]> {
  return db
    .select({
      slug: themes.slug,
      name: themes.name,
      count: sql<number>`count(${postThemes.postId})::int`,
    })
    .from(themes)
    .innerJoin(postThemes, eq(postThemes.themeId, themes.id))
    .groupBy(themes.id)
    .orderBy(desc(sql`count(${postThemes.postId})`), asc(themes.name));
}
