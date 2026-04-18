// ─────────────────────────────────────────────────────────────────────────────
// components/chat/ChatStream.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useRef, useState, type FormEvent } from "react"
import { useStream } from "@/hooks/useStream"
import { DifferentialCard } from "./DifferentialCard"
import { TreatmentPlan }    from "./TreatmentPlan"
import { EmergencyBanner }  from "./EmergencyBanner"
import { CitationDrawer }   from "./CitationDrawer"
import { FeedbackPanel }    from "./FeedbackPanel"
import { ThinkingIndicator }from "./ThinkingIndicator"
import { cn } from "@/lib/utils"

interface Props { sessionId: string }

export function ChatStream({ sessionId }: Props) {
  const { state, send, abort } = useStream(sessionId)
  const [input,      setInput]      = useState("")
  const [citOpen,    setCitOpen]    = useState(false)
  const [dismissed,  setDismissed]  = useState<string[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || state.isStreaming) return
    send(q)
    setInput("")
  }

  const activeEmergencies = state.emergencies.filter(f => !dismissed.includes(f.disease))

  return (
    <div className="flex h-full flex-col gap-4">

      {/* ── Emergency banners ── */}
      {activeEmergencies.map(flag => (
        <EmergencyBanner
          key={flag.disease}
          flag={flag}
          onDismiss={() => setDismissed(d => [...d, flag.disease])}
        />
      ))}

      {/* ── Main scrollable content ── */}
      <div className="flex-1 overflow-y-auto space-y-4 px-1">

        {/* Thinking stream */}
        {state.isStreaming && state.thinking.length > 0 && (
          <ThinkingIndicator lines={state.thinking} />
        )}
        {state.isStreaming && state.thinking.length === 0 && (
          <ThinkingIndicator lines={["Analyse en cours…"]} />
        )}

        {/* Validation annotations */}
        {state.annotations.length > 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 space-y-1">
            <p className="font-medium">⚠ Avertissements de validation</p>
            {state.annotations.map((a, i) => <p key={i}>• {a}</p>)}
          </div>
        )}

        {/* Differential */}
        {state.differential.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-medium text-muted-foreground">
              Diagnostic différentiel
            </h2>
            <div className="space-y-2">
              {state.differential.map(item => (
                <DifferentialCard
                  key={item.rank}
                  item={item}
                  citations={state.citations}
                />
              ))}
            </div>
          </section>
        )}

        {/* Treatment plan */}
        {(state.treatment.first_line.length > 0 ||
          state.treatment.second_line.length > 0 ||
          state.treatment.alternatives.length > 0) && (
          <section>
            <h2 className="mb-2 text-sm font-medium text-muted-foreground">
              Plan thérapeutique
            </h2>
            <TreatmentPlan
              plan={state.treatment as any}
              citations={state.citations}
            />
          </section>
        )}

        {/* Error */}
        {state.error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <strong>Erreur : </strong>{state.error}
          </div>
        )}

        {/* Feedback (shown after response complete) */}
        {state.turnId && !state.isStreaming && (
          <FeedbackPanel turnId={state.turnId} />
        )}
      </div>

      {/* ── Input bar ── */}
      <div className="border-t pt-3 flex gap-2 items-end">
        {state.citations.length > 0 && (
          <button
            onClick={() => setCitOpen(true)}
            aria-label={`Afficher ${state.citations.length} source${state.citations.length > 1 ? "s" : ""}`}
            className="shrink-0 text-xs text-blue-600 underline hover:text-blue-800 mb-2"
          >
            {state.citations.length} source{state.citations.length > 1 ? "s" : ""}
          </button>
        )}
        <form onSubmit={handleSubmit} className="flex flex-1 gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e as any) }
            }}
            aria-label="Saisir le tableau clinique ou une question"
            placeholder="Décrivez le tableau clinique ou posez une question…"
            rows={2}
            className={cn(
              "flex-1 resize-none rounded-lg border px-3 py-2 text-sm",
              "focus:outline-none focus:ring-2 focus:ring-blue-500",
              "bg-background text-foreground placeholder:text-muted-foreground",
            )}
          />
          {state.isStreaming ? (
            <button
              type="button"
              onClick={abort}
              aria-label="Arrêter la génération"
              className="shrink-0 rounded-lg bg-red-100 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-200"
            >
              Arrêter
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              aria-label="Envoyer la question"
              className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
            >
              Envoyer
            </button>
          )}
        </form>
      </div>

      {/* ── Citation drawer ── */}
      <CitationDrawer
        open={citOpen}
        onClose={() => setCitOpen(false)}
        citations={state.citations}
      />
    </div>
  )
}

