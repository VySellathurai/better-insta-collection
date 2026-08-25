export function TriggerButton({
  disabled,
  pending,
  onClick,
}: {
  disabled: boolean;
  pending: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className="trigger" disabled={disabled} onClick={onClick}>
      {pending ? "Démarrage…" : "Digérer jusqu'à 3 posts"}
    </button>
  );
}
