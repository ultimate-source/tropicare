// ─────────────────────────────────────────────────────────────────────────────
// components/chat/CitationDrawer.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useRef, useState, useMemo } from "react"
import type { Citation } from "@/lib/types"
import { useFocusTrap } from "@/hooks/useFocusTrap"
import { useTranslation } from "@/lib/i18n"

interface Props { open: boolean; onClose: () => void; citations: Citation[] }

/**
 * Filter citations by a case-insensitive search string against
 * source_title, section, and chunk_snippet.
 */
export function filterCitations(citations: Citation[], search: string): Citation[] {
  const trimmed = search.trim()
  if (!trimmed) return citations
  const lower = trimmed.toLowerCase()
  return citations.filter(
    (c) =>
      c.source_title.toLowerCase().includes(lower) ||
      c.section.toLowerCase().includes(lower) ||
      c.chunk_snippet.toLowerCase().includes(lower),
  )
}

export function CitationDrawer({ open, onClose, citations }: Props) {
  const drawerRef = useRef<HTMLDivElement>(null)
  const [search, setSearch] = useState("")
  const { t } = useTranslation()

  useFocusTrap(drawerRef, open, onClose)

  const filtered = useMemo(() => filterCitations(citations, search), [citations, search])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={t("citation.title")}
        className="fixed inset-y-0 right-0 z-50 flex w-80 flex-col bg-background border-l shadow-xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold text-sm">{t("citation.title")}</h2>
          <button
            onClick={onClose}
            aria-label={t("citation.close")}
            className="text-muted-foreground hover:text-foreground text-lg"
          >
            ✕
          </button>
        </div>

        {/* Search */}
        <div className="border-b px-4 py-2">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("citation.search")}
            className="w-full rounded border px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-blue-500"
            aria-label={t("citation.search")}
          />
          <p className="mt-1 text-xs text-muted-foreground" data-testid="citation-count">
            {t("citation.count", { matched: filtered.length, total: citations.length })}
          </p>
        </div>

        {/* Citation list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {filtered.map((c) => (
            <div key={c.ref_id} className="space-y-1" data-testid="citation-item">
              <p className="text-xs font-semibold text-blue-700">[{c.ref_id}] {c.source_title}</p>
              <p className="text-xs text-muted-foreground">{c.section} · p. {c.page} · {c.version} ({c.date})</p>
              <p className="text-xs italic text-foreground/70 border-l pl-2">"{c.chunk_snippet}"</p>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
