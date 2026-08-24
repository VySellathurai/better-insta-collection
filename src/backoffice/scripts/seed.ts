/**
 * Loads all of Vault/ (index.md + raw/*.md) into Postgres.
 *
 * Truncate-and-reload inside one transaction — not upsert. posts.id is the
 * natural slug (not a serial int) so a full reload doesn't break link
 * stability, the dataset is small enough for a reload to be instant, and a
 * partial upsert would still need to delete-diff post_themes/post_images
 * for removed themes/images anyway.
 *
 * Usage:
 *   tsx scripts/seed.ts [--vault ../../Vault]
 */
import "dotenv/config";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import { MAX_IMAGES_PER_POST, postImages, postThemes, posts, themes } from "../db/schema";
import { identifiant, normalizeThemeSlug, parseIndex, parseRawImages, parseRawMeta } from "./parse-vault";

function resolveVaultDir(): string {
  const argIdx = process.argv.indexOf("--vault");
  if (argIdx !== -1 && process.argv[argIdx + 1]) {
    return resolve(process.argv[argIdx + 1] as string);
  }
  if (process.env.VAULT_DIR) {
    return resolve(process.env.VAULT_DIR);
  }
  return resolve(__dirname, "../../../Vault");
}

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set — copy .env.example to .env and fill it in.");
  }

  const vaultDir = resolveVaultDir();
  const indexPath = join(vaultDir, "index.md");
  const rawDir = join(vaultDir, "raw");

  if (!existsSync(indexPath)) {
    throw new Error(`index.md not found at ${indexPath}`);
  }

  const indexText = readFileSync(indexPath, "utf-8");
  const imagesByUrl = parseRawImages(rawDir);
  const rawByUrl = parseRawMeta(rawDir);
  const entries = parseIndex(indexText);

  type JoinedPost = {
    id: string;
    sourceUrl: string;
    platform: string;
    genre: string | null;
    author: string;
    authorHandle: string | null;
    durationS: number | null;
    processedAt: Date;
    status: string;
    title: string;
    summary: string;
    description: string | null;
    transcript: string | null;
    sortOrder: number;
    themeNames: string[];
    images: string[];
  };

  const joined: JoinedPost[] = [];
  const seenSlugs = new Set<string>();
  const seenSourceUrls = new Set<string>();
  let skipped = 0;

  entries.forEach((entry, i) => {
    if (!entry.lien) {
      console.warn(`skip: entry "${entry.titre}" has no lien`);
      skipped += 1;
      return;
    }

    if (seenSourceUrls.has(entry.lien)) {
      console.warn(`skip: duplicate lien in index.md, already seen: ${entry.lien}`);
      skipped += 1;
      return;
    }

    const raw = rawByUrl.get(entry.lien);
    if (!raw) {
      console.warn(`skip: no matching raw fiche for ${entry.lien}`);
      skipped += 1;
      return;
    }

    const slug = identifiant(entry.lien);
    if (!slug) {
      console.warn(`skip: could not derive a slug for ${entry.lien}`);
      skipped += 1;
      return;
    }

    if (seenSlugs.has(slug)) {
      console.warn(`skip: slug "${slug}" collides with an already-seeded entry (${entry.lien})`);
      skipped += 1;
      return;
    }

    const images = imagesByUrl.get(entry.lien) ?? [];
    if (images.length > MAX_IMAGES_PER_POST) {
      console.warn(
        `truncating ${images.length} images to ${MAX_IMAGES_PER_POST} for ${entry.lien}`,
      );
    }

    const processedAt = raw.processedAt
      ? new Date(`${raw.processedAt}T00:00:00Z`)
      : new Date();

    seenSourceUrls.add(entry.lien);
    seenSlugs.add(slug);

    joined.push({
      id: slug,
      sourceUrl: entry.lien,
      platform: raw.platform,
      genre: raw.genre,
      author: entry.auteur,
      authorHandle: raw.authorHandle,
      durationS: raw.durationS,
      processedAt,
      status: raw.status,
      title: entry.titre,
      summary: entry.contenu,
      description: raw.description,
      transcript: raw.transcript,
      sortOrder: i + 1,
      themeNames: entry.themes,
      images: images.slice(0, MAX_IMAGES_PER_POST),
    });
  });

  const themeSlugToName = new Map<string, string>();
  for (const post of joined) {
    for (const name of post.themeNames) {
      const slug = normalizeThemeSlug(name);
      if (!themeSlugToName.has(slug)) {
        themeSlugToName.set(slug, name);
      }
    }
  }

  const client = postgres(connectionString);
  const db = drizzle(client);

  try {
    await db.transaction(async (tx) => {
      await tx.execute(sql`DELETE FROM post_images`);
      await tx.execute(sql`DELETE FROM post_themes`);
      await tx.execute(sql`DELETE FROM posts`);
      await tx.execute(sql`DELETE FROM themes`);

      const themeSlugToId = new Map<string, number>();
      if (themeSlugToName.size > 0) {
        const themeRows = await tx
          .insert(themes)
          .values(
            Array.from(themeSlugToName.entries()).map(([slug, name]) => ({ slug, name })),
          )
          .returning({ id: themes.id, slug: themes.slug });
        for (const row of themeRows) {
          themeSlugToId.set(row.slug, row.id);
        }
      }

      if (joined.length > 0) {
        await tx.insert(posts).values(
          joined.map((p) => ({
            id: p.id,
            sourceUrl: p.sourceUrl,
            platform: p.platform,
            genre: p.genre,
            author: p.author,
            authorHandle: p.authorHandle,
            durationS: p.durationS,
            processedAt: p.processedAt,
            status: p.status,
            title: p.title,
            summary: p.summary,
            description: p.description,
            transcript: p.transcript,
            sortOrder: p.sortOrder,
          })),
        );
      }

      const postThemeRows = joined.flatMap((p) =>
        p.themeNames.map((name) => {
          const slug = normalizeThemeSlug(name);
          const themeId = themeSlugToId.get(slug);
          if (themeId === undefined) {
            throw new Error(`internal error: theme "${name}" was not inserted`);
          }
          return { postId: p.id, themeId };
        }),
      );
      if (postThemeRows.length > 0) {
        await tx.insert(postThemes).values(postThemeRows);
      }

      const postImageRows = joined.flatMap((p) =>
        p.images.map((fileName, idx) => ({
          postId: p.id,
          position: idx + 1,
          fileName,
        })),
      );
      if (postImageRows.length > 0) {
        await tx.insert(postImages).values(postImageRows);
      }
    });
  } finally {
    await client.end();
  }

  const totalImages = joined.reduce((sum, p) => sum + p.images.length, 0);
  console.log(
    `Seeded ${joined.length} posts, ${themeSlugToName.size} themes, ${totalImages} images from ${vaultDir}` +
      (skipped > 0 ? ` (${skipped} entries skipped, see warnings above)` : ""),
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
