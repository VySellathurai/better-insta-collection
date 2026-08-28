// Purely presentational — no state/handlers of its own. Shown/hidden by CSS
// alone (see .tile-overlay / [data-peek] rules in app/globals.css); the
// hover/long-press mechanics live on the wrapping <a> in photo-album.tsx.
export function TileOverlay({
  title,
  tags,
  text,
}: {
  title: string;
  tags: string[];
  text: string;
}) {
  return (
    <div className="tile-overlay">
      <p className="tile-overlay-title">{title}</p>
      {tags.length > 0 && (
        <p className="tile-overlay-tags">{tags.map((t) => `#${t}`).join(" ")}</p>
      )}
      {text && <p className="tile-overlay-text">{text}</p>}
    </div>
  );
}
