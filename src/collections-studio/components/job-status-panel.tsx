"use client";

import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type { JobState } from "@/types/job";
import { startCollectionJob } from "@/app/actions";

import { TriggerButton } from "./trigger-button";

const POLL_INTERVAL_MS = 2000;

const idleState: JobState = {
  phase: "idle",
  collection: null,
  startedAt: null,
  finishedAt: null,
  logs: [],
  errorMessage: null,
};

export function JobStatusPanel({ collection }: { collection: string }) {
  const router = useRouter();
  const [job, setJob] = useState<JobState>(idleState);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const previousPhase = useRef<JobState["phase"]>("idle");

  const poll = useCallback(async () => {
    try {
      const res = await fetch("/api/job/status", { cache: "no-store" });
      const state = (await res.json()) as JobState;
      setJob(state);
      if (
        (state.phase === "done" || state.phase === "error") &&
        previousPhase.current !== state.phase &&
        state.collection === collection
      ) {
        router.refresh();
      }
      previousPhase.current = state.phase;
    } catch {
      // transient — next poll retries
    }
  }, [router, collection]);

  useEffect(() => {
    // Polling requires an immediate fetch on mount, not just the interval —
    // the resulting setState happens after the internal `await fetch(...)`,
    // not synchronously during this effect's own execution.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void poll();
    const id = setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [poll]);

  const running = job.phase === "queued" || job.phase === "collecting" || job.phase === "digesting";
  const runningOther = running && job.collection !== collection;

  const handleClick = () => {
    setTriggerError(null);
    startTransition(async () => {
      const result = await startCollectionJob(collection);
      if (!result.ok) {
        setTriggerError(result.reason);
      } else {
        void poll();
      }
    });
  };

  return (
    <div className="panel">
      <TriggerButton disabled={pending || running} pending={pending} onClick={handleClick} />
      {triggerError && <p className="trigger-error">{triggerError}</p>}
      {runningOther && (
        <p className="trigger-error">
          Un job tourne déjà pour « {job.collection} ». Attends qu’il se termine.
        </p>
      )}

      {job.phase !== "idle" && job.collection === collection && (
        <div style={{ marginTop: 12 }}>
          <div className={`job-status${job.phase === "error" ? " error" : ""}`}>
            {running && <span className="spinner" />}
            <span className="phase">{job.phase}</span>
            {job.errorMessage && <span>— {job.errorMessage}</span>}
          </div>
          {job.logs.length > 0 && (
            <div className="log-tail">{job.logs.slice(-40).join("\n")}</div>
          )}
        </div>
      )}
    </div>
  );
}
