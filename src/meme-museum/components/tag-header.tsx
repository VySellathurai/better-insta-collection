import type { ThemeCount } from "@/lib/queries";

// Plain links, no client JS: clicking a tag navigates to ?theme=<slug>
// (server-filtered in app/page.tsx), clicking the already-active tag clears
// the filter back to "/". Consistent with the rest of this app's pager,
// which is also plain <a href> links rather than client-side state.
export function TagHeader({ tags, active }: { tags: ThemeCount[]; active: string | null }) {
  if (tags.length === 0) return null;

  return (
    <div className="tags">
      {tags.map((tag) => {
        const isActive = tag.slug === active;
        return (
          <a
            key={tag.slug}
            href={isActive ? "/" : `/?theme=${encodeURIComponent(tag.slug)}`}
            className={isActive ? "tag-chip active" : "tag-chip"}
          >
            #{tag.name} <span className="count">{tag.count}</span>
          </a>
        );
      })}
    </div>
  );
}
