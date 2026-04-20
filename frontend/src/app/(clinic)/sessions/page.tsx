// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/sessions/page.tsx — session history list
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useEffect, useMemo, useReducer } from "react"
import Link from "next/link"
import { api, type SessionSummary } from "@/lib/api"
import { formatRelative } from "date-fns"
import { fr as frLocale, enUS as enLocale } from "date-fns/locale"
import { SkeletonCard } from "@/components/LoadingSkeleton"
import { ApiErrorBanner } from "@/components/ui/ApiErrorBanner"
import { useTranslation } from "@/lib/i18n"

const dateFnsLocales = { fr: frLocale, en: enLocale } as const

type State = {
  sessions: SessionSummary[]
  loading: boolean
  error: string | null
  fetchKey: number
}

type Action =
  | { type: "FETCH_START" }
  | { type: "FETCH_OK"; sessions: SessionSummary[] }
  | { type: "FETCH_ERR"; error: string }
  | { type: "REFETCH" }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FETCH_START":
      return { ...state, loading: true, error: null }
    case "FETCH_OK":
      return { ...state, loading: false, sessions: action.sessions }
    case "FETCH_ERR":
      return { ...state, loading: false, error: action.error }
    case "REFETCH":
      return { ...state, fetchKey: state.fetchKey + 1, loading: true, error: null }
  }
}

const initialState: State = { sessions: [], loading: true, error: null, fetchKey: 0 }

export default function SessionsPage() {
  const { t, locale } = useTranslation()
  const [state, dispatch] = useReducer(reducer, initialState)

  const dateLocale = useMemo(() => dateFnsLocales[locale], [locale])

  useEffect(() => {
    let cancelled = false
    api.sessions.list()
      .then(data => { if (!cancelled) dispatch({ type: "FETCH_OK", sessions: data.sessions }) })
      .catch(e => { if (!cancelled) dispatch({ type: "FETCH_ERR", error: e.message }) })
    return () => { cancelled = true }
  }, [state.fetchKey])

  return (
    <div className="h-full overflow-y-auto p-6">
      <header>
        <h1 className="text-lg font-semibold text-gray-900 mb-4">{t("sessions.title")}</h1>
      </header>

      {state.loading && (
        <div className="space-y-2">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}
      {state.error && <ApiErrorBanner error={state.error} onRetry={() => dispatch({ type: "REFETCH" })} />}

      {!state.loading && state.sessions.length === 0 && (
        <div className="rounded-xl border bg-white p-8 text-center text-gray-400 text-sm">
          {t("sessions.empty")}{" "}
          <Link href="/chat" className="text-blue-600 underline" aria-label={t("sessions.start")}>{t("sessions.start")}</Link>
        </div>
      )}

      <div className="space-y-2">
        {state.sessions.map(s => {
          const turnLabel = s.turn_count !== 1
            ? t("sessions.turnCountPlural", { count: s.turn_count })
            : t("sessions.turnCount", { count: s.turn_count })

          return (
            <Link
              key={s.id}
              href={`/sessions/${s.id}`}
              aria-label={`${t("sessions.view")} : ${s.last_query || t("sessions.noQuery")}`}
              className="block rounded-xl border bg-white px-4 py-3 hover:border-blue-300 hover:shadow-sm transition-all"
            >
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {s.last_query || "—"}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {turnLabel} · {s.language.toUpperCase()}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-gray-400">
                  {s.created_at
                    ? formatRelative(new Date(s.created_at), new Date(), { locale: dateLocale })
                    : "—"}
                </span>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
