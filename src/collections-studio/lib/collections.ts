import "server-only";
import { readFileSync } from "node:fs";

import { SAVED_COLLECTIONS_PATH } from "./paths";

type Node = {
  label?: string;
  value?: string;
  title?: string;
  href?: string;
  timestamp_value?: number;
  dict?: Node[];
};

type RawCollection = {
  timestamp: number;
  media: unknown[];
  label_values: Node[];
};

export type CollectionSummary = { name: string; count: number };

export type CollectionPost = {
  url: string;
  caption: string | null;
  ownerName: string | null;
  ownerHandle: string | null;
  hashtags: string[];
};

/**
 * Meta's export tool double-encodes UTF-8 as Latin-1 ("Ã©" instead of "é").
 * Re-decoding every string value/label/title recovers the original text —
 * verified against real data: "Par dÃ©faut" -> "Par défaut". Applied
 * uniformly (even to pure-ASCII strings, which round-trip as a no-op)
 * rather than conditionally, since a wrong heuristic here would corrupt
 * every French collection name/caption.
 */
function fixMojibake(s: string): string {
  try {
    return Buffer.from(s, "latin1").toString("utf8");
  } catch {
    return s;
  }
}

function decode(node: Node): Node {
  return {
    ...node,
    label: node.label !== undefined ? fixMojibake(node.label) : undefined,
    value: node.value !== undefined ? fixMojibake(node.value) : undefined,
    title: node.title !== undefined ? fixMojibake(node.title) : undefined,
    dict: node.dict?.map(decode),
  };
}

let cache: RawCollection[] | null = null;

function loadCollections(): RawCollection[] {
  // No mtime-based invalidation: saved_collections.json is a static export
  // dropped once at repo root, not something this app writes — a dev-server
  // restart is an acceptable way to pick up a re-export.
  if (cache) return cache;
  const text = readFileSync(SAVED_COLLECTIONS_PATH, "utf-8");
  const raw = JSON.parse(text) as RawCollection[];
  cache = raw.map((c) => ({ ...c, label_values: c.label_values.map(decode) }));
  return cache;
}

function findName(labelValues: Node[]): string {
  // .trim() is load-bearing: "Comprendre " / "Cuisiner " have trailing
  // whitespace in the source export. digest.py's frontmatter reader and
  // this app's own vault-parse.ts both trim values when reading the
  // `collection:` field back out of a fiche — using the untrimmed name as
  // the --collection value would make the write and later reads silently
  // disagree, and every downstream filter would match zero fiches.
  // Trimming once here keeps the identifier byte-identical everywhere it's
  // used. No collision: trimmed "Cuisine" and "Cuisiner" stay distinct.
  const entry = labelValues.find((lv) => lv.label === "Nom");
  return (entry?.value ?? "").trim();
}

function findPostsBlock(labelValues: Node[]): Node[] {
  // The posts list is the one label_values entry that has `dict` but no
  // `label` key — matched structurally rather than by a hardcoded index,
  // in case export order varies between accounts/export runs.
  const block = labelValues.find((lv) => lv.dict !== undefined && lv.label === undefined);
  return block?.dict ?? [];
}

export function listCollections(): CollectionSummary[] {
  return loadCollections().map((c) => ({
    name: findName(c.label_values),
    count: findPostsBlock(c.label_values).length,
  }));
}

function findCollection(name: string): RawCollection | undefined {
  return loadCollections().find((c) => findName(c.label_values) === name);
}

export function getCollectionUrls(name: string): string[] {
  const collection = findCollection(name);
  if (!collection) return [];
  const urls: string[] = [];
  for (const post of findPostsBlock(collection.label_values)) {
    const urlField = post.dict?.find((f) => f.label === "URL");
    if (urlField?.value) urls.push(urlField.value);
  }
  return urls; // preserves the export's original order
}

export function getCollectionPosts(name: string): CollectionPost[] {
  const collection = findCollection(name);
  if (!collection) return [];
  return findPostsBlock(collection.label_values).flatMap((post): CollectionPost[] => {
    const fields = post.dict ?? [];
    const url = fields.find((f) => f.label === "URL")?.value;
    if (!url) return [];
    const hashtagsBlock = fields.find((f) => f.title === "Hashtags");
    const hashtags =
      hashtagsBlock?.dict?.flatMap((h) => h.dict?.find((n) => n.label === "Nom")?.value ?? []) ?? [];
    const ownerBlock = fields.find((f) => f.title === "Propriétaire")?.dict?.[0]?.dict;
    return [
      {
        url,
        caption: fields.find((f) => f.label === "Légende")?.value?.trim() || null,
        ownerName: ownerBlock?.find((f) => f.label === "Nom")?.value ?? null,
        ownerHandle: ownerBlock?.find((f) => f.label === "Nom de profil")?.value ?? null,
        hashtags,
      },
    ];
  });
}
