import { MAX_LIMIT } from "@/types/job";

export function TriggerButton({
  disabled,
  pending,
  limit,
  onLimitChange,
  onSubmit,
}: {
  disabled: boolean;
  pending: boolean;
  limit: number;
  onLimitChange: (limit: number) => void;
  onSubmit: () => void;
}) {
  return (
    <form
      className="trigger-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <label className="trigger-limit">
        Limite
        <input
          type="number"
          min={1}
          max={MAX_LIMIT}
          step={1}
          value={limit}
          disabled={disabled}
          onChange={(e) => {
            const parsed = Math.trunc(Number(e.target.value));
            if (Number.isFinite(parsed)) {
              // Client-side clamp is UX only — lib/job-runner.ts re-clamps to
              // MAX_LIMIT server-side regardless of what this sends.
              onLimitChange(Math.min(MAX_LIMIT, Math.max(1, parsed)));
            }
          }}
        />
      </label>
      <button type="submit" className="trigger" disabled={disabled}>
        {pending ? "Démarrage…" : `Digérer jusqu'à ${limit} post${limit > 1 ? "s" : ""}`}
      </button>
      <span className="trigger-hint">max {MAX_LIMIT} par sécurité</span>
    </form>
  );
}
