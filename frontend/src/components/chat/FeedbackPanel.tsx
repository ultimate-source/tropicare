// ─────────────────────────────────────────────────────────────────────────────
// components/chat/FeedbackPanel.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"

type Verdict = "correct" | "incorrect" | "partial"

export function FeedbackPanel({ turnId }: { turnId: string }) {
  const [verdict, setVerdict]  = useState<Verdict | null>(null)
  const [note, setNote]        = useState("")
  const [submitted, setSubmit] = useState(false)

  const submit = async () => {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ turn_id: turnId, verdict, clinician_note: note }),
    })
    setSubmit(true)
  }

  if (submitted) return (
    <p className="text-xs text-green-700 text-center py-2">✓ Retour enregistré — merci</p>
  )

  return (
    <div className="rounded-lg border bg-card p-3 space-y-2">
      <p className="text-xs font-medium text-muted-foreground">Cette réponse est-elle correcte ?</p>
      <div className="flex gap-2">
        {(["correct", "partial", "incorrect"] as Verdict[]).map(v => (
          <button key={v}
            onClick={() => setVerdict(v)}
            className={cn(
              "flex-1 rounded-md border py-1.5 text-xs font-medium transition-colors",
              verdict === v
                ? v === "correct"   ? "border-green-400 bg-green-100 text-green-800"
                : v === "partial"   ? "border-amber-400 bg-amber-100 text-amber-800"
                :                     "border-red-400 bg-red-100 text-red-800"
                : "border-border text-muted-foreground hover:bg-muted",
            )}>
            {v === "correct" ? "✓ Correcte" : v === "partial" ? "~ Partielle" : "✗ Incorrecte"}
          </button>
        ))}
      </div>
      {verdict && verdict !== "correct" && (
        <textarea
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Diagnostic réel / commentaire (optionnel)"
          rows={2}
          className="w-full resize-none rounded border px-2 py-1.5 text-xs bg-background text-foreground"
        />
      )}
      {verdict && (
        <button
          onClick={submit}
          className="w-full rounded-md bg-blue-600 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
        >
          Envoyer le retour
        </button>
      )}
    </div>
  )
}

