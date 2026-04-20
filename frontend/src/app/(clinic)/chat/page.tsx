// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/chat/page.tsx — main consultation page
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useCallback, useRef, useState } from "react"
import { api } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { IntakeForm }  from "@/components/intake/IntakeForm"
import { ChatStream }  from "@/components/chat/ChatStream"
import { Spinner }     from "@/components/LoadingSkeleton"
import { ApiErrorBanner } from "@/components/ui/ApiErrorBanner"
import type { PatientContext } from "@/lib/types"

type Phase = "intake" | "loading" | "chat"

export default function ChatPage() {
  const { language, setSession, clearDismissedAlerts } = useAppStore()
  const [phase,     setPhase]    = useState<Phase>("intake")
  const [sessionId, setSessionId]= useState<string | null>(null)
  const [error,     setError]    = useState<string | null>(null)
  const lastContextRef           = useRef<PatientContext | null>(null)

  const handleIntakeComplete = useCallback(async (context: PatientContext) => {
    lastContextRef.current = context
    setError(null)
    setPhase("loading")
    try {
      const { session_id } = await api.sessions.create(context, language)
      setSessionId(session_id)
      setSession({ sessionId: session_id, language, createdAt: new Date().toISOString() })
      clearDismissedAlerts()
      setPhase("chat")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur lors de la création de la session")
      setPhase("intake")
    }
  }, [language, setSession, clearDismissedAlerts])

  const retrySessionCreation = useCallback(() => {
    if (lastContextRef.current) {
      handleIntakeComplete(lastContextRef.current)
    }
  }, [handleIntakeComplete])

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <div>
          <h1 className="text-sm font-semibold text-gray-900">Nouvelle consultation</h1>
          {sessionId && (
            <p className="text-xs text-gray-400 font-mono">{sessionId.slice(0, 8)}</p>
          )}
        </div>
        {phase === "chat" && (
          <button
            onClick={() => { setPhase("intake"); setSessionId(null) }}
            aria-label="Créer une nouvelle session de consultation"
            className="text-xs text-gray-500 hover:text-blue-600 border rounded-md px-2 py-1"
          >
            + Nouvelle session
          </button>
        )}
      </header>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-4">
        {error && (
          <div className="mb-4">
            <ApiErrorBanner error={error} onRetry={retrySessionCreation} />
          </div>
        )}

        {phase === "intake" && (
          <IntakeForm onComplete={handleIntakeComplete} language={language} />
        )}

        {phase === "loading" && (
          <div className="flex flex-col items-center justify-center gap-3 py-12">
            <Spinner className="h-8 w-8" />
            <p className="text-sm text-gray-500">Création de la session…</p>
          </div>
        )}

        {phase === "chat" && sessionId && (
          <ChatStream sessionId={sessionId} />
        )}
      </div>
    </div>
  )
}