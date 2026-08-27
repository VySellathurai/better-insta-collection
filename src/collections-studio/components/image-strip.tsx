import Image from "next/image";

// Ported verbatim from src/backoffice/components/image-strip.tsx. Requires
// public/images to be a symlink to ../../../Vault/images — see `make
// cs-images-link` / README.md.
export function ImageStrip({ images, alt }: { images: string[]; alt: string }) {
  if (images.length === 0) return null;

  return (
    <div className="images">
      {images.map((fileName) => (
        <a
          key={fileName}
          href={`/images/${fileName}`}
          target="_blank"
          rel="noopener"
          className="image-box"
        >
          <Image
            src={`/images/${fileName}`}
            alt={alt}
            fill
            sizes="(max-width: 480px) 140px, 220px"
            loading="lazy"
          />
        </a>
      ))}
    </div>
  );
}
