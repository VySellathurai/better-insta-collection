import { PostTile } from "@/components/post-tile";
import { getPostsPage, PAGE_SIZE } from "@/lib/queries";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { page: rawPage } = await searchParams;
  const page = Math.max(1, Number.parseInt(rawPage ?? "1", 10) || 1);

  const { items, total } = await getPostsPage(page);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="wrap">
      <header>
        <h1>Musée des Mêmes</h1>
        <p className="subtitle">
          {total} post{total === 1 ? "" : "s"} collecté{total === 1 ? "" : "s"} — page {page}/
          {totalPages}
        </p>
      </header>

      {items.length === 0 ? (
        <p className="empty">
          Aucun post pour l&apos;instant — lance <code>make mm-pipeline</code> pour en collecter.
        </p>
      ) : (
        <div className="grid">
          {items.map((post) => (
            <PostTile key={post.id} post={post} />
          ))}
        </div>
      )}

      <div className="pager">
        {page > 1 ? (
          <a href={`/?page=${page - 1}`}>&larr; précédent</a>
        ) : (
          <span className="disabled">&larr; précédent</span>
        )}
        {page < totalPages ? (
          <a href={`/?page=${page + 1}`}>suivant &rarr;</a>
        ) : (
          <span className="disabled">suivant &rarr;</span>
        )}
      </div>
    </div>
  );
}
