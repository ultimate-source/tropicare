// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/sessions/page.tsx — session history list
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { api, type SessionSummary } from "@/lib/api"
import { formatRelative } from "date-fns"
import { fr } from "date-fns/locale"
import { SkeletonCard } from "@/components/LoadingSkeleton"

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)

  useEffect(() => {
    api.sessions.list()
      .then(data => setSessions(data.sessions))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="h-full overflow-y-auto p-6">
      <header>
        <h1 className="text-lg font-semibold text-gray-900 mb-4">Historique des consultations</h1>
      </header>

      {loading && (
        <div className="space-y-2">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}
      {error   && <p className="text-sm text-red-600">{error}</p>}

      {!loading && sessions.length === 0 && (
        <div className="rounded-xl border bg-white p-8 text-center text-gray-400 text-sm">
          Aucune session pour le moment.{" "}
          <Link href="/chat" className="text-blue-600 underline" aria-label="Démarrer une nouvelle consultation">Démarrer une consultation</Link>
        </div>
      )}

      <div className="space-y-2">
        {sessions.map(s => (
          <Link
            key={s.id}
            href={`/sessions/${s.id}`}
            aria-label={`Voir la session : ${s.last_query || "sans requête"}`}
            className="block rounded-xl border bg-white px-4 py-3 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {s.last_query || "—"}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {s.turn_count} tour{s.turn_count !== 1 ? "s" : ""} ·{" "}
                  {s.language.toUpperCase()}
                </p>
              </div>
              <span className="shrink-0 text-xs text-gray-400">
                {formatRelative(new Date(s.created_at), new Date(), { locale: fr })}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
