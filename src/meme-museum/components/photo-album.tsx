"use client";

import Image from "next/image";
import { ColumnsPhotoAlbum } from "react-photo-album";
import "react-photo-album/columns.css";

export type AlbumPhoto = {
  id: string;
  src: string;
  title: string;
  href: string;
};

// Real Instagram crops every grid tile to an equal square regardless of the
// source image's real proportions — so every photo gets a FORCED 1:1 ratio
// here (width/height are layout-only, not the real pixel dimensions, which
// we never read from disk). ColumnsPhotoAlbum then balances 4 equal-width
// square columns exactly like Instagram's grid, instead of the masonry/
// justified look this library normally produces from real aspect ratios.
export function PhotoAlbum({ photos }: { photos: AlbumPhoto[] }) {
  return (
    <ColumnsPhotoAlbum
      columns={4}
      spacing={3}
      photos={photos.map((p) => ({
        key: p.id,
        src: p.src,
        width: 1,
        height: 1,
        title: p.title,
        href: p.href,
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
          <Image
            src={photo.src}
            alt={photo.title ?? ""}
            width={width}
            height={height}
            style={{ width: "100%", height: "auto", aspectRatio: `${width} / ${height}`, objectFit: "cover" }}
            sizes="(max-width: 700px) 25vw, 275px"
            loading="lazy"
          />
        ),
      }}
      componentsProps={{
        link: { target: "_blank", rel: "noopener" },
      }}
    />
  );
}
