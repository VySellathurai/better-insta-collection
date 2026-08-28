import Image from "next/image";

import type { GridPost } from "@/lib/queries";

// Requires public/images to be a symlink to ../vault/images — see `make
// mm-images-link` / README.md. Always shows the post's FIRST collected image
// (post.cover, position = 1 — see lib/queries.ts) — falls back to the title
// as plain text for the rare post with no image yet.
export function PostTile({ post }: { post: GridPost }) {
  return (
    <a
      href={post.sourceUrl}
      target="_blank"
      rel="noopener"
      className="tile"
      title={post.title}
    >
      {post.cover ? (
        <Image
          src={`/images/${post.cover}`}
          alt={post.title}
          fill
          sizes="(max-width: 700px) 25vw, 275px"
          loading="lazy"
        />
      ) : (
        <span className="fallback">{post.title}</span>
      )}
    </a>
  );
}
