import "server-only";
import { and, asc, desc, eq, ilike, inArray, or, sql } from "drizzle-orm";

import { db } from "@/db/client";
import { postImages, postThemes, posts, themes } from "@/db/schema";

export type PostListItem = {
  id: string;
  sourceUrl: string;
  title: string;
  author: string;
  summary: string;
  themes: string[];
  images: string[];
};

export type PostDetail = PostListItem & {
  platform: string;
  genre: string | null;
  authorHandle: string | null;
  durationS: number | null;
  processedAt: string;
  status: string;
  description: string | null;
  transcript: string | null;
};

export type ThemeCount = {
  slug: string;
  name: string;
  count: number;
};

async function attachThemesAndImages(
  postRows: (typeof posts.$inferSelect)[],
): Promise<Map<string, { themes: string[]; images: string[] }>> {
  const details = new Map<string, { themes: string[]; images: string[] }>();
  for (const p of postRows) details.set(p.id, { themes: [], images: [] });

  if (postRows.length === 0) return details;

  const ids = postRows.map((p) => p.id);

  const [themeRows, imageRows] = await Promise.all([
    db
      .select({ postId: postThemes.postId, name: themes.name })
      .from(postThemes)
      .innerJoin(themes, eq(themes.id, postThemes.themeId))
      .where(inArray(postThemes.postId, ids)),
    db
      .select({ postId: postImages.postId, fileName: postImages.fileName, position: postImages.position })
      .from(postImages)
      .where(inArray(postImages.postId, ids))
      .orderBy(asc(postImages.position)),
  ]);
  for (const row of themeRows) {
    details.get(row.postId)?.themes.push(row.name);
  }
  for (const row of imageRows) {
    details.get(row.postId)?.images.push(row.fileName);
  }

  return details;
}

function toListItem(
  p: typeof posts.$inferSelect,
  detail: { themes: string[]; images: string[] } | undefined,
): PostListItem {
  return {
    id: p.id,
    sourceUrl: p.sourceUrl,
    title: p.title,
    author: p.author,
    summary: p.summary,
    themes: detail?.themes ?? [],
    images: detail?.images ?? [],
  };
}

export type GetAllPostsParams = {
  theme?: string;
  q?: string;
  page?: number;
  pageSize?: number;
};

export async function getAllPostsWithDetails(
  params: GetAllPostsParams = {},
): Promise<{ items: PostListItem[]; total: number }> {
  // pageSize is only applied when the caller explicitly asks for a page —
  // callers that want the full list (e.g. the gallery page, which filters
  // client-side over everything) get every row, so the displayed count
  // never silently disagrees with the "total" also returned here.
  const { page, pageSize } = params;

  let idsForTheme: string[] | null = null;
  if (params.theme) {
    const rows = await db
      .select({ postId: postThemes.postId })
      .from(postThemes)
      .innerJoin(themes, eq(themes.id, postThemes.themeId))
      .where(eq(themes.slug, params.theme));
    idsForTheme = rows.map((r) => r.postId);
    if (idsForTheme.length === 0) {
      return { items: [], total: 0 };
    }
  }

  const conditions = [];
  if (idsForTheme) {
    conditions.push(inArray(posts.id, idsForTheme));
  }
  if (params.q) {
    const like = `%${params.q}%`;
    conditions.push(or(ilike(posts.title, like), ilike(posts.author, like), ilike(posts.summary, like)));
  }

  const whereClause = conditions.length > 0 ? and(...conditions) : undefined;

  const baseQuery = db.select().from(posts).where(whereClause).orderBy(asc(posts.sortOrder));
  const rowsQuery =
    pageSize !== undefined ? baseQuery.limit(pageSize).offset(((page ?? 1) - 1) * pageSize) : baseQuery;

  const [rows, totalRows] = await Promise.all([
    rowsQuery,
    db.select({ count: sql<number>`count(*)::int` }).from(posts).where(whereClause),
  ]);

  const details = await attachThemesAndImages(rows);

  return {
    items: rows.map((p) => toListItem(p, details.get(p.id))),
    total: totalRows[0]?.count ?? 0,
  };
}

export async function getPostBySlug(slug: string): Promise<PostDetail | null> {
  const rows = await db.select().from(posts).where(eq(posts.id, slug)).limit(1);
  const post = rows[0];
  if (!post) return null;

  const details = await attachThemesAndImages([post]);
  const detail = details.get(post.id);

  return {
    ...toListItem(post, detail),
    platform: post.platform,
    genre: post.genre,
    authorHandle: post.authorHandle,
    durationS: post.durationS,
    processedAt: post.processedAt.toISOString().slice(0, 10),
    status: post.status,
    description: post.description,
    transcript: post.transcript,
  };
}

export async function getThemeCounts(): Promise<ThemeCount[]> {
  const rows = await db
    .select({
      slug: themes.slug,
      name: themes.name,
      count: sql<number>`count(${postThemes.postId})::int`,
    })
    .from(themes)
    .innerJoin(postThemes, eq(postThemes.themeId, themes.id))
    .groupBy(themes.id)
    .orderBy(desc(sql`count(${postThemes.postId})`), asc(themes.name));

  return rows;
}
