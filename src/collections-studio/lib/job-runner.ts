import "server-only";
import { spawn } from "node:child_process";
import { mkdtempSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { DEFAULT_LIMIT, MAX_LIMIT, type JobState } from "@/types/job";

import { getCollectionUrls } from "./collections";
import { COLLECT_COOKIES, REPO_ROOT, VAULT_DIR } from "./paths";

const MAX_LOG_LINES = 500;
// DEFAULT_LIMIT / MAX_LIMIT live in types/job.ts so the client form can import
// them without pulling in this module's "server-only" guard. MAX_LIMIT is the
// real safety boundary against tripping Instagram's rate-limiting/detection —
// always re-enforced below, no matter what the form (or a direct Server Action
// call) sends.
const DIGEST_BATCH = 100; // generous: digest is 100% local/Ollama, carries none of
// collect's Instagram rate-limit risk — also sweeps up any older not-yet-digested
// fiches already sitting in this collection.

type Store = { state: JobState; running: boolean };

const idleState = (): JobState => ({
  phase: "idle",
  collection: null,
  limit: null,
  startedAt: null,
  finishedAt: null,
  logs: [],
  errorMessage: null,
});

const globalForJob = globalThis as unknown as { __collectionsStudioJob?: Store };

const store: Store = globalForJob.__collectionsStudioJob ?? { state: idleState(), running: false };
if (process.env.NODE_ENV !== "production") {
  globalForJob.__collectionsStudioJob = store;
}

function pushLog(line: string): void {
  store.state.logs.push(line);
  if (store.state.logs.length > MAX_LOG_LINES) {
    store.state.logs.splice(0, store.state.logs.length - MAX_LOG_LINES);
  }
}

export function getJobState(): JobState {
  return { ...store.state, logs: [...store.state.logs] };
}

export function startCollectionJob(
  collectionName: string,
  requestedLimit: number = DEFAULT_LIMIT,
): { ok: true } | { ok: false; reason: string } {
  if (store.running) {
    return {
      ok: false,
      reason: `A job is already running for "${store.state.collection}". Wait for it to finish.`,
    };
  }
  if (!Number.isInteger(requestedLimit) || requestedLimit < 1) {
    return { ok: false, reason: "Limit must be a whole number of at least 1." };
  }
  // Clamp rather than reject: the client already clamps for UX, but this is the
  // real enforcement point — it also covers a direct call bypassing the form.
  const limit = Math.min(requestedLimit, MAX_LIMIT);
  store.running = true;
  store.state = {
    phase: "queued",
    collection: collectionName,
    limit,
    startedAt: Date.now(),
    finishedAt: null,
    logs: [],
    errorMessage: null,
  };
  void runJob(collectionName, limit).finally(() => {
    store.running = false;
  });
  return { ok: true };
}

async function runJob(collectionName: string, limit: number): Promise<void> {
  let tmpFile: string | null = null;
  try {
    const urls = getCollectionUrls(collectionName);
    if (urls.length === 0) {
      throw new Error(`No URLs found for collection "${collectionName}".`);
    }

    const tmpDir = mkdtempSync(join(tmpdir(), "collections-studio-"));
    tmpFile = join(tmpDir, "urls.txt");
    writeFileSync(tmpFile, urls.join("\n"), "utf-8");

    store.state.phase = "collecting";
    pushLog(
      `Collecting up to ${limit} new video(s) from "${collectionName}" ` +
        `(${urls.length} URLs in this collection).`,
    );
    await runChild(
      "uv",
      [
        "run",
        "reels-collect",
        tmpFile,
        "--vault",
        VAULT_DIR,
        "--collection",
        collectionName,
        "--cookies",
        COLLECT_COOKIES,
        "--limite",
        String(limit),
      ],
      REPO_ROOT,
    );

    store.state.phase = "digesting";
    pushLog(`Collect done. Digesting "${collectionName}".`);
    await runChild(
      "uv",
      [
        "run",
        "reels-digest",
        "--vault",
        VAULT_DIR,
        "--collection",
        collectionName,
        "--batch",
        String(DIGEST_BATCH),
      ],
      REPO_ROOT,
    );

    store.state.phase = "done";
    store.state.finishedAt = Date.now();
    pushLog("Done.");
  } catch (err) {
    store.state.phase = "error";
    store.state.finishedAt = Date.now();
    store.state.errorMessage = err instanceof Error ? err.message : String(err);
    pushLog(`ERROR: ${store.state.errorMessage}`);
  } finally {
    if (tmpFile) {
      try {
        unlinkSync(tmpFile);
      } catch {
        // best-effort cleanup — a leaked file in the OS temp dir is harmless
      }
    }
  }
}

function runChild(cmd: string, args: string[], cwd: string): Promise<void> {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(cmd, args, { cwd }); // array form, no shell
    const onData = (chunk: Buffer): void => {
      for (const line of chunk.toString("utf-8").split("\n")) {
        if (line.trim()) pushLog(line);
      }
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("error", (err) => reject(err));
    child.on("close", (code) => {
      if (code === 0) resolvePromise();
      else reject(new Error(`${cmd} ${args[1]} exited with code ${code} (see logs above).`));
    });
  });
}
