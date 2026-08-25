export type JobPhase = "idle" | "queued" | "collecting" | "digesting" | "done" | "error";

export type JobState = {
  phase: JobPhase;
  collection: string | null;
  startedAt: number | null;
  finishedAt: number | null;
  logs: string[];
  errorMessage: string | null;
};
