// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/chat/page.tsx — main consultation page
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState } from "react"
import { api } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { IntakeForm }  from "@/components/intake/IntakeForm"
import { ChatStream }  from "@/components/chat/ChatStream"

type Phase = "intake" | "chat"

export default function ChatPage() {
  const { language, setSession } = useAppStore()
  const [phase,     setPhase]    = useState<Phase>("intake")
  const [sessionId, setSessionId]= useState<string | null>(null)
  const [error,     setError]    = useState<string | null>(null)

  async function handleIntakeComplete(context: Record<string, unknown>) {
    try {
      const { session_id } = await api.sessions.create(context, language)
      setSessionId(session_id)
      setSession({ sessionId: session_id, language, createdAt: new Date().toISOString() })
      setPhase("chat")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur lors de la création de la session")
    }
  }

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
            className="text-xs text-gray-500 hover:text-blue-600 border rounded-md px-2 py-1"
          >
            + Nouvelle session
          </button>
        )}
      </header>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-4">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        {phase === "intake" && (
          <IntakeForm onComplete={handleIntakeComplete} language={language} />
        )}

        {phase === "chat" && sessionId && (
          <ChatStream sessionId={sessionId} />
        )}
      </div>
    </div>
  )
}