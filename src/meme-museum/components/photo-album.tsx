"use client";

import Image from "next/image";
import { ColumnsPhotoAlbum } from "react-photo-album";
import "react-photo-album/columns.css";

import { TagEditor } from "./tag-editor";
import { TileOverlay } from "./tile-overlay";

export type EditableTheme = { slug: string; name: string; count: number };

export type AlbumPhoto = {
  id: string;
  src: string;
  title: string;
  href: string;
  description: string | null;
  summary: string;
  tags: string[];
};

const LONG_PRESS_MS = 500;

// Long-press-to-peek, implemented imperatively (no React state) directly on
// the wrapper <a> react-photo-album renders (via componentsProps.link) —
// render.image only controls the inner image slot, not the anchor itself.
// touchstart arms a timer that flips a data-peek attribute (purely CSS-driven
// reveal, see .tile-overlay[data-peek] in globals.css); touchmove/touchcancel
// (e.g. a scroll) abort it; touchend clears the timer and, if the hold
// actually reached the threshold, calls preventDefault() so the tap-to-
// navigate click that would otherwise follow doesn't fire — the user peeked
// and let go, they didn't ask to leave the page. A normal short tap never
// reaches the timeout, so it navigates exactly as before.
function armLongPress(e: React.TouchEvent<HTMLAnchorElement>): void {
  const el = e.currentTarget;
  const timer = window.setTimeout(() => {
    el.dataset.peek = "true";
  }, LONG_PRESS_MS);
  el.dataset.pressTimer = String(timer);
}

function cancelLongPress(e: React.TouchEvent<HTMLAnchorElement>): void {
  const el = e.currentTarget;
  if (el.dataset.pressTimer) {
    window.clearTimeout(Number(el.dataset.pressTimer));
    delete el.dataset.pressTimer;
  }
  delete el.dataset.peek;
}

function releaseLongPress(e: React.TouchEvent<HTMLAnchorElement>): void {
  const el = e.currentTarget;
  if (el.dataset.pressTimer) {
    window.clearTimeout(Number(el.dataset.pressTimer));
    delete el.dataset.pressTimer;
  }
  if (el.dataset.peek) {
    e.preventDefault();
    delete el.dataset.peek;
  }
}

// Real Instagram crops every grid tile to an equal square regardless of the
// source image's real proportions — so every photo gets a FORCED 1:1 ratio
// here (width/height are layout-only, not the real pixel dimensions, which
// we never read from disk). ColumnsPhotoAlbum then balances 4 equal-width
// square columns exactly like Instagram's grid, instead of the masonry/
// justified look this library normally produces from real aspect ratios.
export function PhotoAlbum({
  photos,
  allThemes,
}: {
  photos: AlbumPhoto[];
  allThemes: EditableTheme[];
}) {
  return (
    <ColumnsPhotoAlbum
      columns={4}
      spacing={3}
      photos={photos.map((p) => ({
        key: p.id,
        id: p.id,
        src: p.src,
        width: 1,
        height: 1,
        title: p.title,
        href: p.href,
        description: p.description,
        summary: p.summary,
        tags: p.tags,
      }))}
      render={{
        // The library's own .react-photo-album--photo wrapper has NO explicit
        // CSS height in the columns layout — it's derived from the image's
        // own `height: auto` + `aspect-ratio`. A plain `height: "100%"` here
        // asks an ancestor that has no height of its own (percentage height
        // against an auto-height parent is ignored per spec), so the whole
        // wrapper collapses to zero height and nothing is visible — even
        // though the <img> itself loads fine. Giving the image its own
        // intrinsic aspect-ratio (always 1/1, since every photo is forced
        // square above) breaks that circular dependency.
        image: (_props, { photo, width, height }) => (
          <>
            <Image
              src={photo.src}
              alt={photo.title ?? ""}
              width={width}
              height={height}
              style={{
                width: "100%",
                height: "auto",
                aspectRatio: `${width} / ${height}`,
                objectFit: "cover",
              }}
              sizes="(max-width: 700px) 25vw, 275px"
              loading="lazy"
            />
            <TileOverlay
              title={photo.title ?? ""}
              tags={photo.tags}
              text={photo.description || photo.summary}
            />
          </>
        ),
        // Separate slot from `image` so the pencil trigger + its portaled
        // popover aren't tangled with the image markup. Still rendered inside
        // the tile's <a> — TagEditor stops event propagation accordingly.
        extras: (_props, { photo }) => (
          <TagEditor postId={photo.id} tagNames={photo.tags} allThemes={allThemes} />
        ),
      }}
      componentsProps={{
        link: {
          target: "_blank",
          rel: "noopener",
          onTouchStart: armLongPress,
          onTouchEnd: releaseLongPress,
          onTouchMove: cancelLongPress,
          onTouchCancel: cancelLongPress,
        },
      }}
    />
  );
}
