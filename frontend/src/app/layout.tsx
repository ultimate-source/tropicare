// ─────────────────────────────────────────────────────────────────────────────
// app/layout.tsx — root layout
// ─────────────────────────────────────────────────────────────────────────────
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import LangUpdater from "@/components/LangUpdater"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title:       "TropiCare — Aide au diagnostic",
  description: "Système d'aide au diagnostic des maladies tropicales — Togo",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={inter.className}>
        <LangUpdater />
        {children}
      </body>
    </html>
  )
}
