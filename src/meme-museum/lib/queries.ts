import "server-only";
import { desc, sql } from "drizzle-orm";

import { db } from "@/db/client";
import { posts } from "@/db/schema";

export type GridPost = {
  id: string;
  sourceUrl: string;
  title: string;
  cover: string | null;
};

// 4 columns (see app/globals.css's .grid) x 10 rows per page.
export const PAGE_SIZE = 40;

export async function getPostsPage(page = 1): Promise<{ items: GridPost[]; total: number }> {
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

  const [items, totalRows] = await Promise.all([
    db
      .select({
        id: posts.id,
        sourceUrl: posts.sourceUrl,
        title: posts.title,
        cover,
      })
      .from(posts)
      .orderBy(desc(posts.processedAt))
      .limit(PAGE_SIZE)
      .offset(offset),
    db.select({ count: sql<number>`count(*)::int` }).from(posts),
  ]);

  return { items, total: totalRows[0]?.count ?? 0 };
}
