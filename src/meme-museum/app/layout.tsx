import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Musée des Mêmes",
  description: "Grille des posts Instagram collectés dans la collection « Musée des Mêmes ».",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
