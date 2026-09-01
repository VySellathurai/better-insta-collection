import Link from "next/link";

import { PhotoAlbum } from "@/components/photo-album";
import { TagHeader } from "@/components/tag-header";
import { getPostsPage, getThemeCounts, PAGE_SIZE } from "@/lib/queries";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; theme?: string }>;
}) {
  const { page: rawPage, theme } = await searchParams;
  const page = Math.max(1, Number.parseInt(rawPage ?? "1", 10) || 1);

  const [{ items, total }, tags] = await Promise.all([
    getPostsPage(page, theme),
    getThemeCounts(),
  ]);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Mirrors real Instagram: a post never shows as a tile until it has media,
  // so posts without a collected cover image yet are simply left out of the
  // album rather than rendered as a differently-shaped placeholder tile.
  const photos = items
    .filter((post) => post.cover !== null)
    .map((post) => ({
      id: post.id,
      src: `/images/${post.cover}`,
      title: post.title,
      href: post.sourceUrl,
      description: post.description,
      summary: post.summary,
      tags: post.tags,
    }));

  // Preserves the active tag filter across page navigation.
  const pageHref = (n: number) => (theme ? `/?page=${n}&theme=${encodeURIComponent(theme)}` : `/?page=${n}`);

  return (
    <div className="wrap">
      <header>
        <h1>Musée des Mêmes</h1>
        <p className="subtitle">
          {total} post{total === 1 ? "" : "s"} collecté{total === 1 ? "" : "s"} — page {page}/
          {totalPages}
        </p>
      </header>

      <TagHeader tags={tags} active={theme ?? null} />

      {total === 0 ? (
        <p className="empty">
          {theme ? (
            <>
              Aucun post avec ce tag. <Link href="/">Voir tous les posts</Link>.
            </>
          ) : (
            <>
              Aucun post pour l&apos;instant — lance <code>make mm-pipeline</code> pour en
              collecter.
            </>
          )}
        </p>
      ) : photos.length === 0 ? (
        <p className="empty">Ces posts n&apos;ont pas encore d&apos;image collectée.</p>
      ) : (
        <PhotoAlbum photos={photos} allThemes={tags} />
      )}

      <div className="pager">
        {page > 1 ? (
          <a href={pageHref(page - 1)}>&larr; précédent</a>
        ) : (
          <span className="disabled">&larr; précédent</span>
        )}
        {page < totalPages ? (
          <a href={pageHref(page + 1)}>suivant &rarr;</a>
        ) : (
          <span className="disabled">suivant &rarr;</span>
        )}
      </div>
    </div>
  );
}
