import "server-only";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { VAULT_DIR } from "./paths";
import { parseIndex, parseRawMetaByUrl } from "./vault-parse";

export type DisplayPost = {
  titre: string;
  lien: string;
  auteur: string;
  themes: string[];
  contenu: string;
};

export function getCollectionResults(collectionName: string): DisplayPost[] {
  let indexText: string;
  try {
    indexText = readFileSync(join(VAULT_DIR, "index.md"), "utf-8");
  } catch {
    return [];
  }
  const rawByUrl = parseRawMetaByUrl(join(VAULT_DIR, "raw"));
  return parseIndex(indexText).filter((e) => rawByUrl.get(e.lien)?.collection === collectionName);
}
