import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TropiCare RAG",
  description:
    "Système de diagnostic et recommandations thérapeutiques pour le Togo",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
