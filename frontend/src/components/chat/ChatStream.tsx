// ─────────────────────────────────────────────────────────────────────────────
// components/chat/ChatStream.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { useStream, type Turn } from "@/hooks/useStream"
import { useAutoScroll } from "@/hooks/useAutoScroll"
import { useAppStore } from "@/lib/store"
import { useTranslation } from "@/lib/i18n"
import type { TreatmentPlanData } from "@/lib/types"
import { DifferentialCard } from "./DifferentialCard"
import { TreatmentPlan }    from "./TreatmentPlan"
import { EmergencyBanner }  from "./EmergencyBanner"
import { CitationDrawer }   from "./CitationDrawer"
import { FeedbackPanel }    from "./FeedbackPanel"
import { ThinkingIndicator }from "./ThinkingIndicator"
import { cn } from "@/lib/utils"

interface Props { sessionId: string }

export function ChatStream({ sessionId }: Props) {
  const { state, send, abort, retry } = useStream(sessionId)
  const [input,      setInput]      = useState("")
  const [citOpen,    setCitOpen]    = useState(false)
  const [dismissAnnouncement, setDismissAnnouncement] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const { t } = useTranslation()
  const dismissedAlerts = useAppStore((s) => s.dismissedAlerts)
  const dismissAlert = useAppStore((s) => s.dismissAlert)

  const { isAtBottom, scrollToBottom } = useAutoScroll(
    scrollContainerRef,
    [state.currentTurn, state.turns],
  )

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || state.isStreaming) return
    send(q)
    setInput("")
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter (or Cmd+Enter on Mac) submits
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
    // Plain Enter → default behavior (newline)
  }

  const handleDismiss = (disease: string) => {
    dismissAlert(disease)
    setDismissAnnouncement(t("emergency.dismissAnnouncement", { disease }))
  }

  const current = state.currentTurn
  const activeEmergencies = current.emergencies.filter(f => !dismissedAlerts.includes(f.disease))

  // Collect all citations across all turns + current for the drawer
  const allCitations = [
    ...state.turns.flatMap(turn => turn.citations),
    ...current.citations,
  ]

  // Loading state: streaming started but no content yet
  const isLoadingBeforeFirstEvent =
    state.isStreaming &&
    current.thinking.length === 0 &&
    current.differential.length === 0 &&
    current.emergencies.length === 0 &&
    current.treatment.first_line.length === 0 &&
    current.treatment.second_line.length === 0 &&
    current.treatment.alternatives.length === 0 &&
    current.annotations.length === 0 &&
    !current.error &&
    !current.turnId

  return (
    <div className="flex h-full flex-col gap-4">

      {/* ── Emergency banners (current turn) ── */}
      {activeEmergencies.map(flag => (
        <EmergencyBanner
          key={flag.disease}
          flag={flag}
          onDismiss={() => handleDismiss(flag.disease)}
        />
      ))}

      {/* ── Dismissal announcement for screen readers ── */}
      <div aria-live="polite" className="sr-only" data-testid="dismiss-live-region">
        {dismissAnnouncement}
      </div>

      {/* ── Main scrollable content ── */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto space-y-4 px-1"
      >

        {/* ── Previous turns ── */}
        {state.turns.map((turn, idx) => (
          <TurnSection key={idx} turn={turn} turnIndex={idx} citations={turn.citations} />
        ))}

        {/* ── Current turn ── */}

        {/* Loading state before first stream event */}
        {isLoadingBeforeFirstEvent && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="loading-sending">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span>{t("chat.sending")}</span>
          </div>
        )}

        {/* Thinking stream */}
        {state.isStreaming && current.thinking.length > 0 && (
          <ThinkingIndicator lines={current.thinking} />
        )}

        {/* Validation annotations */}
        {current.annotations.length > 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 space-y-1">
            <p className="font-medium">{t("chat.validationWarnings")}</p>
            {current.annotations.map((a, i) => <p key={i}>• {a}</p>)}
          </div>
        )}

        {/* Differential */}
        {current.differential.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-medium text-muted-foreground">
              {t("chat.differential")}
            </h2>
            <div className="space-y-2">
              {current.differential.map(item => (
                <DifferentialCard
                  key={item.rank}
                  item={item}
                  citations={current.citations}
                />
              ))}
            </div>
          </section>
        )}

        {/* Treatment plan */}
        {(current.treatment.first_line.length > 0 ||
          current.treatment.second_line.length > 0 ||
          current.treatment.alternatives.length > 0) && (
          <section>
            <h2 className="mb-2 text-sm font-medium text-muted-foreground">
              {t("chat.treatmentPlan")}
            </h2>
            <TreatmentPlan
              plan={current.treatment as TreatmentPlanData}
              citations={current.citations}
            />
          </section>
        )}

        {/* Error with retry */}
        {current.error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <strong>{t("chat.errorPrefix")}</strong>{current.error}
            {state.lastQuery && (
              <button
                type="button"
                onClick={retry}
                className="ml-3 rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-800 hover:bg-red-200"
              >
                {t("error.retry")}
              </button>
            )}
          </div>
        )}

        {/* Feedback (shown after response complete) */}
        {current.turnId && !state.isStreaming && (
          <FeedbackPanel turnId={current.turnId} />
        )}
      </div>

      {/* ── Scroll to bottom button ── */}
      {!isAtBottom && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="absolute bottom-24 right-4 rounded-full bg-white shadow-md border px-3 py-1 text-xs text-muted-foreground hover:bg-gray-50"
          aria-label={t("chat.scrollToBottom")}
        >
          ↓ {t("chat.scrollToBottom")}
        </button>
      )}

      {/* ── Input bar ── */}
      <div className="border-t pt-3 flex flex-col sm:flex-row gap-2 items-stretch sm:items-end">
        {allCitations.length > 0 && (
          <button
            onClick={() => setCitOpen(true)}
            aria-label={
              allCitations.length > 1
                ? t("citation.showPlural", { count: allCitations.length })
                : t("citation.show", { count: allCitations.length })
            }
            className="shrink-0 text-xs text-blue-600 underline hover:text-blue-800 mb-2"
          >
            {allCitations.length > 1
              ? t("citation.showPlural", { count: allCitations.length })
              : t("citation.show", { count: allCitations.length })}
          </button>
        )}
        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row flex-1 gap-2 w-full">
          <div className="flex-1">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              aria-label={t("chat.inputAriaLabel")}
              placeholder={t("chat.placeholder")}
              rows={2}
              className={cn(
                "w-full resize-none rounded-lg border px-3 py-2 text-sm",
                "focus:outline-none focus:ring-2 focus:ring-blue-500",
                "bg-background text-foreground placeholder:text-muted-foreground",
              )}
            />
            <p className="mt-1 text-xs text-muted-foreground">{t("chat.submitHint")}</p>
          </div>
          {state.isStreaming ? (
            <button
              type="button"
              onClick={abort}
              aria-label={t("chat.stopAriaLabel")}
              className="shrink-0 rounded-lg bg-red-100 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-200"
            >
              {t("chat.stop")}
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              aria-label={t("chat.sendAriaLabel")}
              className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
            >
              {t("chat.send")}
            </button>
          )}
        </form>
      </div>

      {/* ── Citation drawer ── */}
      <CitationDrawer
        open={citOpen}
        onClose={() => setCitOpen(false)}
        citations={allCitations}
      />
    </div>
  )
}


// ── TurnSection — renders a completed turn with a divider ────────────────────

function TurnSection({ turn, turnIndex, citations }: { turn: Turn; turnIndex: number; citations: typeof turn.citations }) {
  const { t } = useTranslation()

  return (
    <div className="space-y-3" data-turn={turnIndex}>
      {/* Turn divider */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <hr className="flex-1 border-muted" />
        <span>{t("chat.turnCount", { count: turnIndex + 1 })}{turn.query ? ` — ${turn.query}` : ""}</span>
        <hr className="flex-1 border-muted" />
      </div>

      {/* Differential */}
      {turn.differential.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">
            {t("chat.differential")}
          </h2>
          <div className="space-y-2">
            {turn.differential.map(item => (
              <DifferentialCard key={item.rank} item={item} citations={citations} />
            ))}
          </div>
        </section>
      )}

      {/* Treatment plan */}
      {(turn.treatment.first_line.length > 0 ||
        turn.treatment.second_line.length > 0 ||
        turn.treatment.alternatives.length > 0) && (
        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">
            {t("chat.treatmentPlan")}
          </h2>
          <TreatmentPlan plan={turn.treatment as TreatmentPlanData} citations={citations} />
        </section>
      )}

      {/* Error */}
      {turn.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <strong>{t("chat.errorPrefix")}</strong>{turn.error}
        </div>
      )}

      {/* Feedback */}
      {turn.turnId && (
        <FeedbackPanel turnId={turn.turnId} />
      )}
    </div>
  )
}
