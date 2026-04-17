// ─────────────────────────────────────────────────────────────────────────────
// components/chat/CitationDrawer.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import type { Citation } from "@/lib/types"

interface Props { open: boolean; onClose: () => void; citations: Citation[] }

export function CitationDrawer({ open, onClose, citations }: Props) {
  if (!open) return null
  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-80 flex-col bg-background border-l shadow-xl">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="font-semibold text-sm">Sources ({citations.length})</h2>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg">✕</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {citations.map(c => (
          <div key={c.ref_id} className="space-y-1">
            <p className="text-xs font-semibold text-blue-700">[{c.ref_id}] {c.source_title}</p>
            <p className="text-xs text-muted-foreground">{c.section} · p. {c.page} · {c.version} ({c.date})</p>
            <p className="text-xs italic text-foreground/70 border-l pl-2">"{c.chunk_snippet}"</p>
          </div>
        ))}
      </div>
    </div>
  )
}
