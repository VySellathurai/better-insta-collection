import type { DisplayPost } from "@/lib/db";

import { ImageStrip } from "./image-strip";

export function ResultCard({ post }: { post: DisplayPost }) {
  return (
    <article className="entry">
      <h2>
        {post.lien ? (
          <a href={post.lien} target="_blank" rel="noopener">
            {post.titre}
          </a>
        ) : (
          post.titre
        )}
      </h2>
      <div className="meta">
        {post.themes.map((t) => (
          <span key={t} className="tag">
            {t}
          </span>
        ))}
      </div>
      <div className="auteur">👤 {post.auteur}</div>
      <ImageStrip images={post.images} alt={post.titre} />
      <p className="contenu">{post.contenu}</p>
    </article>
  );
}
