// Shared with both server code (lib/job-runner.ts) and client components (the
// limit form) — kept in this plain, server-only-free module so the client
// bundle can import the constants without pulling in "server-only".
export const DEFAULT_LIMIT = 3;
export const MAX_LIMIT = 50; // hard safety ceiling, always re-enforced server-side

export type JobPhase = "idle" | "queued" | "collecting" | "digesting" | "done" | "error";

export type JobState = {
  phase: JobPhase;
  collection: string | null;
  limit: number | null;
  startedAt: number | null;
  finishedAt: number | null;
  logs: string[];
  errorMessage: string | null;
};
