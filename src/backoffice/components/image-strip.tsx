import Image from "next/image";

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
