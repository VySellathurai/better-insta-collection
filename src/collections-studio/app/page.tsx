import { getCollectionUrls, listCollections } from "@/lib/collections";
import { getCollectionResults } from "@/lib/vault-results";
import { CollectionPicker } from "@/components/collection-picker";
import { JobStatusPanel } from "@/components/job-status-panel";
import { ResultCard } from "@/components/result-card";

// Always re-read saved_collections.json, Vault/, and the in-memory job state
// on every request — this page reflects live, frequently-changing local
// state, not something that should be cached/statically prerendered.
export const dynamic = "force-dynamic";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ collection?: string }>;
}) {
  const { collection: rawParam } = await searchParams;
  const collections = listCollections();
  const requested = rawParam?.trim();
  const known = new Set(collections.map((c) => c.name));
  const selected = requested && known.has(requested) ? requested : (collections[0]?.name ?? null);

  const results = selected ? getCollectionResults(selected) : [];
  const totalInCollection = selected ? getCollectionUrls(selected).length : 0;

  return (
    <div className="wrap">
      <h1>🗂️ Collections Studio</h1>
      <p className="subtitle">
        Choisis une collection Instagram sauvegardée, puis digère-en jusqu’à 3 nouveaux posts à la
        fois.
      </p>

      <CollectionPicker collections={collections} selected={selected} />

      {selected ? (
        <>
          <JobStatusPanel collection={selected} />
          <p className="subtitle">
            {results.length} digéré{results.length !== 1 ? "s" : ""} / {totalInCollection} dans «{" "}
            {selected} ».
          </p>
          {results.length === 0 ? (
            <p className="no-results">Aucun post digéré pour cette collection pour l’instant.</p>
          ) : (
            <div className="results">
              {results.map((post) => (
                <ResultCard key={post.lien} post={post} />
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="no-results">Aucune collection trouvée dans saved_collections.json.</p>
      )}
    </div>
  );
}
