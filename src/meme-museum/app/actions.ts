"use server";

import { revalidatePath } from "next/cache";
import { eq, sql } from "drizzle-orm";

import { db } from "@/db/client";
import { postThemes, posts, themes } from "@/db/schema";
import { normalizeTagNames } from "@/lib/tags";

export type SetPostTagsResult =
  | { ok: true; tags: string[] }
  | { ok: false; error: string };

const MAX_TAGS = 50;
const MAX_TAG_LEN = 100;
const MAX_POST_ID_LEN = 256;

/**
 * Replace the full set of tags on a single post, mirroring the pipeline's
 * model in src/reels_pipeline/publish.py (delete this post's post_themes,
 * upsert each theme by slug, re-insert the join rows) — all in one
 * transaction. Declarative "set the whole list", not add/remove ops: the
 * editor already holds the complete chip list, and this stays idempotent.
 *
 * Per-post scope only: no other post's rows are touched. After the rewrite,
 * themes left with zero posts are pruned so they leave the filter bar
 * (<TagHeader> only shows themes with count > 0 anyway, but the row would
 * otherwise linger in the table forever).
 *
 * No auth check on purpose: this app has no auth anywhere, runs on localhost
 * against a local Docker Postgres, single user. If it is ever deployed or
 * made multi-user, add an authorization guard here — Server Functions are
 * reachable by direct POST, not only through this UI.
 */
export async function setPostTags(
  postId: string,
  tagNames: string[],
): Promise<SetPostTagsResult> {
  if (typeof postId !== "string" || postId.length === 0 || postId.length > MAX_POST_ID_LEN) {
    return { ok: false, error: "Identifiant de post invalide." };
  }
  if (!Array.isArray(tagNames) || tagNames.length > MAX_TAGS) {
    return { ok: false, error: `Trop de tags (max ${MAX_TAGS}).` };
  }
  if (tagNames.some((t) => typeof t !== "string" || t.length > MAX_TAG_LEN)) {
    return { ok: false, error: `Tag invalide (max ${MAX_TAG_LEN} caractères).` };
  }

  const desired = normalizeTagNames(tagNames);

  try {
    await db.transaction(async (tx) => {
      const found = await tx
        .select({ id: posts.id })
        .from(posts)
        .where(eq(posts.id, postId))
        .limit(1);
      if (found.length === 0) {
        throw new Error("post introuvable");
      }

      await tx.delete(postThemes).where(eq(postThemes.postId, postId));

      for (const { slug, name } of desired) {
        const [row] = await tx
          .insert(themes)
          .values({ slug, name })
          .onConflictDoUpdate({ target: themes.slug, set: { name } })
          .returning({ id: themes.id });
        if (!row) continue;
        await tx
          .insert(postThemes)
          .values({ postId, themeId: row.id })
          .onConflictDoNothing();
      }

      // Orphan prune, same transaction. `${themes.id}` is table-qualified by
      // drizzle here (delete target is `themes`) — the bare-`sql` footgun in
      // lib/queries.ts is about fragments that join in another `id` column;
      // not the case in this correlated subquery. post_themes.theme_id is
      // ON DELETE CASCADE, so there is never a dangling join row.
      await tx
        .delete(themes)
        .where(
          sql`not exists (select 1 from post_themes pt where pt.theme_id = ${themes.id})`,
        );
    });
  } catch (err) {
    if (err instanceof Error && err.message === "post introuvable") {
      return { ok: false, error: "Ce post n'existe plus." };
    }
    console.error("setPostTags a échoué", err);
    return { ok: false, error: "Échec de l'enregistrement. Réessaie." };
  }

  revalidatePath("/");

  // Sorted by name to match getPostsPage's `array_agg(... order by th.name)`.
  return {
    ok: true,
    tags: desired.map((d) => d.name).sort((a, b) => a.localeCompare(b)),
  };
}
