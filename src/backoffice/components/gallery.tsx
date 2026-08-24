"use client";

import { useMemo, useState } from "react";

import type { PostListItem, ThemeCount } from "@/lib/queries";

import { PostCard } from "./post-card";

function matchesSearch(post: PostListItem, q: string): boolean {
  if (!q) return true;
  const hay = `${post.title} ${post.author} ${post.summary}`.toLowerCase();
  return hay.includes(q);
}

export function Gallery({
  posts,
  themeCounts,
}: {
  posts: PostListItem[];
  themeCounts: ThemeCount[];
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTheme, setActiveTheme] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return posts.filter((post) => {
      const themeOk = activeTheme === null || post.themes.includes(activeTheme);
      return themeOk && matchesSearch(post, q);
    });
  }, [posts, searchQuery, activeTheme]);

  return (
    <>
      <div className="search-box">
        <input
          id="search"
          type="text"
          placeholder="Rechercher un titre, un auteur, un mot-clé..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="themes-bar">
        <button
          type="button"
          className={`theme-chip${activeTheme === null ? " active" : ""}`}
          onClick={() => setActiveTheme(null)}
        >
          Tous <span className="count">{posts.length}</span>
        </button>
        {themeCounts.map((t) => (
          <button
            key={t.slug}
            type="button"
            className={`theme-chip${activeTheme === t.name ? " active" : ""}`}
            onClick={() => setActiveTheme((current) => (current === t.name ? null : t.name))}
          >
            {t.name} <span className="count">{t.count}</span>
          </button>
        ))}
      </div>

      <div className="status-line">
        {filtered.length} résultat{filtered.length !== 1 ? "s" : ""}
        {activeTheme ? ` — thème : ${activeTheme}` : ""}
      </div>

      {filtered.length === 0 ? (
        <div className="no-results">Aucune entrée ne correspond à cette recherche.</div>
      ) : (
        <div className="entries">
          {filtered.map((post) => (
            <PostCard key={post.id} post={post} searchQuery={searchQuery} />
          ))}
        </div>
      )}
    </>
  );
}
