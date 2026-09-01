// Tag ("theme") name/slug helpers, shared by the client editor and the server
// action. NOT `server-only` on purpose — components/tag-editor.tsx imports
// slugifyTagName to dedupe chips before they ever reach the server.
//
// The slug rule mirrors src/reels_pipeline/publish.py EXACTLY
// (`tag.strip().lower().replace(" ", "-")`, and Python's str.replace swaps
// every occurrence). Slug parity with the pipeline matters: the pipeline
// upserts themes by slug, so a divergent rule here would create duplicate
// theme rows for what is really the same tag. Deliberately does NOT collapse
// internal whitespace or strip punctuation — publish.py doesn't either.

export function slugifyTagName(name: string): string {
  return name.trim().toLowerCase().replaceAll(" ", "-");
}

export type NormalizedTag = { slug: string; name: string };

/**
 * Normalize a raw list of tag names into `{ slug, name }` pairs:
 * trims each name, drops entries whose slug is empty, and dedupes by slug —
 * keeping the first occurrence's (trimmed) name. That last rule is the
 * two-names-one-slug collision resolution (e.g. "Dank Memes" and "dank memes"
 * both slug to `dank-memes`; the first one typed wins).
 */
export function normalizeTagNames(names: string[]): NormalizedTag[] {
  const seen = new Set<string>();
  const out: NormalizedTag[] = [];
  for (const raw of names) {
    const name = raw.trim();
    const slug = slugifyTagName(name);
    if (!slug || seen.has(slug)) continue;
    seen.add(slug);
    out.push({ slug, name });
  }
  return out;
}
