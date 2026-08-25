import "server-only";
import { resolve } from "node:path";

// Resolved relative to process.cwd() (this app's own dir when run via
// `npm run dev`/`next start` there) — not __dirname, which isn't reliable
// through Next's bundler.
export const REPO_ROOT = resolve(process.env.REPO_ROOT ?? "../..");
export const VAULT_DIR = resolve(process.env.VAULT_DIR ?? "../../Vault");
export const SAVED_COLLECTIONS_PATH = resolve(
  process.env.SAVED_COLLECTIONS_PATH ?? "../../your_instagram_activity/saved/saved_collections.json",
);
export const COLLECT_COOKIES = process.env.COLLECT_COOKIES || "firefox";
