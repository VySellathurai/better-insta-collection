import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Collections Studio",
  description: "Choisis une collection Instagram et digère-en jusqu'à 3 posts à la fois.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
