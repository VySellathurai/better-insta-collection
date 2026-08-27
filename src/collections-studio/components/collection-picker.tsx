import Link from "next/link";

import type { CollectionSummary } from "@/lib/collections";

export function CollectionPicker({
  collections,
  selected,
}: {
  collections: CollectionSummary[];
  selected: string | null;
}) {
  return (
    <div className="collections">
      {collections.map((c) => (
        <Link
          key={c.name}
          href={`?collection=${encodeURIComponent(c.name)}`}
          className={`collection-chip${c.name === selected ? " active" : ""}`}
        >
          {c.name} <span className="count">{c.count}</span>
        </Link>
      ))}
    </div>
  );
}
