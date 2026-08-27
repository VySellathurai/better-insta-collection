import "server-only";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

/**
 * Ported (not cross-imported — separate, isolated app) from
 * src/backoffice/scripts/parse-vault.ts's parseIndex(), itself a port of
 * src/reels_vault/publish.py's parse_index(). Kept verbatim.
 */

export type IndexEntry = {
  titre: string;
  lien: string;
  auteur: string;
  themes: string[];
  contenu: string;
};

export type RawMeta = {
  sourceUrl: string;
  collection: string | null;
  genre: string | null;
  status: string;
};

/** Port of publish.py's parse_index(): splits on "### " blocks, prefix-matches
 * `- lien / auteur / th*me* / contenu` lines, filters the literal
 * "(aucun thème identifiable)" placeholder out of the theme list. */
export function parseIndex(text: string): IndexEntry[] {
  const blocks = text.split(/^### /m);
  const entries: IndexEntry[] = [];

  // blocks[0] is the "# Index..." header before the first entry.
  for (const block of blocks.slice(1)) {
    const lines = block.split("\n");
    const titre = (lines[0] ?? "").trim();

    let lien = "";
    let auteur = "";
    let themesRaw = "";
    let contenu = "";

    for (const rawLine of lines.slice(1)) {
      const line = rawLine.trim();
      const colonIdx = line.indexOf(":");
      if (colonIdx === -1) continue;
      const value = line.slice(colonIdx + 1).trim();
      const prefix = line.slice(0, colonIdx);

      if (line.startsWith("- lien")) {
        lien = value;
      } else if (line.startsWith("- auteur")) {
        auteur = value;
      } else if (line.startsWith("- th") && prefix.includes("me")) {
        themesRaw = value;
      } else if (line.startsWith("- contenu")) {
        contenu = value;
      }
    }

    const themes = themesRaw
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0)
      .filter((t) => !t.toLowerCase().includes("aucun th"));

    entries.push({ titre, lien, auteur, themes, contenu });
  }

  return entries;
}

function extractSection(text: string, heading: string): string | null {
  // No "m" flag: unlike Python's re.MULTILINE (where `\Z` still means true
  // end-of-string), JS's `$` under "m" matches end-of-*line*, which would
  // make the lazy `[\s\S]*?` stop after the section's first line. Matching
  // "^" via a "(?:^|\n)" alternation instead lets us drop "m" and keep `$`
  // meaning true end-of-string.
  const re = new RegExp(`(?:^|\\n)## ${heading}\\n([\\s\\S]*?)(?:\\n## |$)`);
  const m = re.exec(text);
  return m?.[1]?.trim() ?? null;
}

/** Ported from src/backoffice/scripts/parse-vault.ts's parseRawImages(): maps
 * source URL -> ordered list of bare image filenames (the `images/` prefix
 * is stripped here — URL-building is a presentation concern). */
export function parseRawImages(rawDir: string): Map<string, string[]> {
  const imagesByUrl = new Map<string, string[]>();
  let files: string[];
  try {
    files = readdirSync(rawDir).filter((f) => f.endsWith(".md"));
  } catch {
    return imagesByUrl;
  }

  for (const file of files) {
    const text = readFileSync(join(rawDir, file), "utf-8");
    const sourceMatch = /^source:\s*(\S+)/m.exec(text);
    if (!sourceMatch || !sourceMatch[1]) continue;

    const imagesBlock = extractSection(text, "Images");
    const images: string[] = [];
    if (imagesBlock) {
      for (const rawLine of imagesBlock.split("\n")) {
        const line = rawLine.trim();
        if (line.startsWith("- ")) {
          const path = line.slice(2).trim();
          images.push(path.replace(/^images\//, ""));
        }
      }
    }
    imagesByUrl.set(sourceMatch[1].trim(), images);
  }
  return imagesByUrl;
}

/** Reads raw/*.md frontmatter, keyed by source URL — just the fields this
 * app needs (collection, for the results filter; genre/status for display). */
export function parseRawMetaByUrl(rawDir: string): Map<string, RawMeta> {
  const metaByUrl = new Map<string, RawMeta>();
  let files: string[];
  try {
    files = readdirSync(rawDir).filter((f) => f.endsWith(".md"));
  } catch {
    return metaByUrl;
  }

  for (const file of files) {
    const text = readFileSync(join(rawDir, file), "utf-8");
    const frontmatterMatch = /^---\n([\s\S]*?)\n---/m.exec(text);
    const frontmatter: Record<string, string> = {};
    if (frontmatterMatch?.[1]) {
      for (const line of frontmatterMatch[1].split("\n")) {
        const idx = line.indexOf(":");
        if (idx === -1) continue;
        const key = line.slice(0, idx).trim();
        const value = line.slice(idx + 1).trim(); // .trim() — see the trailing-
        // whitespace note in lib/collections.ts's findName()
        if (key) frontmatter[key] = value;
      }
    }

    const sourceUrl = frontmatter.source;
    if (!sourceUrl) continue;

    metaByUrl.set(sourceUrl.trim(), {
      sourceUrl: sourceUrl.trim(),
      collection: frontmatter.collection || null,
      genre: frontmatter.genre ?? null,
      status: frontmatter.statut ?? "brut",
    });
  }
  return metaByUrl;
}
