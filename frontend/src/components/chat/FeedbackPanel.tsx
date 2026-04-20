// ─────────────────────────────────────────────────────────────────────────────
// components/chat/FeedbackPanel.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useCallback, useState } from "react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import { ApiErrorBanner } from "@/components/ui/ApiErrorBanner"
import { useTranslation } from "@/lib/i18n"

type Verdict = "correct" | "incorrect" | "partial"

export function FeedbackPanel({ turnId }: { turnId: string }) {
  const { t } = useTranslation()
  const [verdict, setVerdict]    = useState<Verdict | null>(null)
  const [note, setNote]          = useState("")
  const [submitted, setSubmit]   = useState(false)
  const [error, setError]        = useState<string | null>(null)

  const submit = useCallback(async () => {
    if (!verdict) return
    setError(null)
    try {
      await api.feedback.submit({
        turn_id: turnId,
        verdict,
        clinician_note: note || undefined,
      })
      setSubmit(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("error.feedbackSubmit"))
    }
  }, [turnId, verdict, note, t])

  if (submitted) return (
    <p className="text-xs text-green-700 text-center py-2">{t("feedback.success")}</p>
  )

  return (
    <div className="rounded-lg border bg-card p-3 space-y-2">
      <p className="text-xs font-medium text-muted-foreground">{t("feedback.question")}</p>
      <div className="flex gap-2">
        {(["correct", "partial", "incorrect"] as Verdict[]).map(v => (
          <button key={v}
            onClick={() => setVerdict(v)}
            aria-label={t(`feedback.${v}AriaLabel`)}
            className={cn(
              "flex-1 rounded-md border py-1.5 text-xs font-medium transition-colors",
              verdict === v
                ? v === "correct"   ? "border-green-400 bg-green-100 text-green-800"
                : v === "partial"   ? "border-amber-400 bg-amber-100 text-amber-800"
                :                     "border-red-400 bg-red-100 text-red-800"
                : "border-border text-muted-foreground hover:bg-muted",
            )}>
            {t(`feedback.${v}`)}
          </button>
        ))}
      </div>
      {verdict && verdict !== "correct" && (
        <textarea
          value={note}
          onChange={e => setNote(e.target.value)}
          aria-label={t("feedback.placeholder")}
          placeholder={t("feedback.placeholder")}
          rows={2}
          className="w-full resize-none rounded border px-2 py-1.5 text-xs bg-background text-foreground"
        />
      )}
      {error && (
        <ApiErrorBanner error={error} onRetry={submit} />
      )}
      {verdict && (
        <button
          onClick={submit}
          aria-label={t("feedback.submitAriaLabel")}
          className="w-full rounded-md bg-blue-600 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
        >
          {t("feedback.submit")}
        </button>
      )}
    </div>
  )
}
