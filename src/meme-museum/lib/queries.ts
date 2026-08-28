import "server-only";
import { asc, desc, eq, inArray, sql } from "drizzle-orm";

import { db } from "@/db/client";
import { postThemes, posts, themes } from "@/db/schema";

export type GridPost = {
  id: string;
  sourceUrl: string;
  title: string;
  cover: string | null;
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
  const cover = sql<string | null>`(
    select pi.file_name from post_images pi
    where pi.post_id = ${posts.id} and pi.position = 1
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
