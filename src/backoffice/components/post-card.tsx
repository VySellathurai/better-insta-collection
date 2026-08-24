import type { PostListItem } from "@/lib/queries";

import { ImageStrip } from "./image-strip";

function highlight(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "ig"));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase() ? <mark key={i}>{part}</mark> : part,
  );
}

export function PostCard({ post, searchQuery }: { post: PostListItem; searchQuery: string }) {
  const q = searchQuery.trim();

  return (
    <article className="entry">
      <h2>
        {post.sourceUrl ? (
          <a href={post.sourceUrl} target="_blank" rel="noopener">
            {highlight(post.title, q)}
          </a>
        ) : (
          highlight(post.title, q)
        )}
      </h2>
      <div className="meta">
        {post.themes.map((t) => (
          <span key={t} className="tag">
            {t}
          </span>
        ))}
      </div>
      <ImageStrip images={post.images} alt={post.title} />
      <div className="auteur">👤 {highlight(post.author, q)}</div>
      <p className="contenu">{highlight(post.summary, q)}</p>
      {post.sourceUrl ? (
        <a className="lien" href={post.sourceUrl} target="_blank" rel="noopener">
          {post.sourceUrl}
        </a>
      ) : null}
    </article>
  );
}
