import { Gallery } from "@/components/gallery";
import { getAllPostsWithDetails, getThemeCounts } from "@/lib/queries";

// Always read live from Postgres — the DB changes independently of deploys
// (re-seeded whenever Vault/ changes), so a build-time static snapshot would
// go stale until the next `npm run build`.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [{ items: posts, total }, themeCounts] = await Promise.all([
    getAllPostsWithDetails(),
    getThemeCounts(),
  ]);

  return (
    <div className="wrap">
      <header>
        <h1>🎬 Vault — Vidéos Instagram sauvegardées</h1>
        <p className="subtitle">{total} vidéos indexées — servi depuis Postgres</p>
      </header>
      <Gallery posts={posts} themeCounts={themeCounts} />
      <footer>Back office reels-vault — lit directement la base Postgres.</footer>
    </div>
  );
}
