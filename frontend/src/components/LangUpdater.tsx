// ─────────────────────────────────────────────────────────────────────────────
// components/LangUpdater.tsx — syncs Zustand language to <html lang="">
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useEffect } from "react"
import { useAppStore } from "@/lib/store"

export default function LangUpdater(): null {
  const language = useAppStore((s) => s.language)

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  return null
}
