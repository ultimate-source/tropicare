// ─────────────────────────────────────────────────────────────────────────────
// app/(clinic)/sessions/[id]/page.tsx — read-only session detail view
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useEffect, useReducer } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { api, type SessionDetail, type TurnRecord } from "@/lib/api"
import { SkeletonCard } from "@/components/LoadingSkeleton"
import { ApiErrorBanner } from "@/components/ui/ApiErrorBanner"
import { useTranslation } from "@/lib/i18n"

type State = {
  session: SessionDetail | null
  loading: boolean
  notFound: boolean
  error: string | null
  fetchKey: number
}

type Action =
  | { type: "FETCH_OK"; session: SessionDetail }
  | { type: "FETCH_NOT_FOUND" }
  | { type: "FETCH_ERR"; error: string }
  | { type: "REFETCH" }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FETCH_OK":
      return { ...state, loading: false, session: action.session, notFound: false, error: null }
    case "FETCH_NOT_FOUND":
      return { ...state, loading: false, notFound: true, error: null }
    case "FETCH_ERR":
      return { ...state, loading: false, error: action.error }
    case "REFETCH":
      return { ...state, fetchKey: state.fetchKey + 1, loading: true, error: null, notFound: false }
  }
}

const initialState: State = { session: null, loading: true, notFound: false, error: null, fetchKey: 0 }

export default function SessionDetailPage() {
  const { t } = useTranslation()
  const params = useParams<{ id: string }>()
  const [state, dispatch] = useReducer(reducer, initialState)

  useEffect(() => {
    if (!params.id) return
    let cancelled = false
    api.sessions.get(params.id)
      .then(data => { if (!cancelled) dispatch({ type: "FETCH_OK", session: data }) })
      .catch(e => {
        if (cancelled) return
        const msg = e.message ?? ""
        if (msg.startsWith("404")) {
          dispatch({ type: "FETCH_NOT_FOUND" })
        } else {
          dispatch({ type: "FETCH_ERR", error: msg })
        }
      })
    return () => { cancelled = true }
  }, [params.id, state.fetchKey])

  if (state.loading) {
    return (
      <div className="h-full overflow-y-auto p-6 space-y-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  if (state.notFound) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <Link href="/sessions" className="text-sm text-blue-600 hover:underline">
          {t("sessionDetail.backToHistory")}
        </Link>
        <div className="mt-6 rounded-xl border bg-white p-8 text-center">
          <p className="text-lg font-medium text-gray-900">{t("sessionDetail.notFound")}</p>
          <p className="mt-1 text-sm text-gray-400">{t("sessionDetail.notFoundDescription")}</p>
        </div>
      </div>
    )
  }

  if (state.error) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <Link href="/sessions" className="text-sm text-blue-600 hover:underline">
          {t("sessionDetail.backToHistory")}
        </Link>
        <div className="mt-4">
          <ApiErrorBanner error={state.error} onRetry={() => dispatch({ type: "REFETCH" })} />
        </div>
      </div>
    )
  }

  if (!state.session) return null

  const ctx = state.session.patient_context ?? {}
  const age = ctx.age_years as number | undefined
  const sex = ctx.sex as string | undefined
  const complaint = ctx.chief_complaint as string | undefined
  const region = ctx.region as string | undefined

  const sexLabel = sex === "M" ? t("sessionDetail.sexM")
    : sex === "F" ? t("sessionDetail.sexF")
    : t("sessionDetail.unknown")

  return (
    <div className="h-full overflow-y-auto p-6">
      <Link href="/sessions" className="text-sm text-blue-600 hover:underline">
        {t("sessionDetail.backToHistory")}
      </Link>

      <h1 className="mt-4 text-lg font-semibold text-gray-900">
        {t("sessionDetail.title")}
      </h1>

      {/* Patient context header */}
      <section className="mt-4 rounded-xl border bg-white px-4 py-3" aria-label={t("sessionDetail.patientContext")}>
        <h2 className="text-sm font-medium text-gray-700 mb-2">{t("sessionDetail.patientContext")}</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
          <div>
            <span className="text-gray-400">{t("sessionDetail.age")}: </span>
            <span className="text-gray-900">
              {age != null ? t("sessionDetail.years", { age }) : "—"}
            </span>
          </div>
          <div>
            <span className="text-gray-400">{t("sessionDetail.sex")}: </span>
            <span className="text-gray-900">{sex ? sexLabel : "—"}</span>
          </div>
          <div>
            <span className="text-gray-400">{t("sessionDetail.chiefComplaint")}: </span>
            <span className="text-gray-900">{complaint ?? "—"}</span>
          </div>
          <div>
            <span className="text-gray-400">{t("sessionDetail.region")}: </span>
            <span className="text-gray-900">{region ?? "—"}</span>
          </div>
        </div>
      </section>

      {/* Conversation turns */}
      <div className="mt-4 space-y-4">
        {state.session.conversation_history.map((turn) => (
          <TurnCard key={turn.turn_id} turn={turn} t={t} />
        ))}
      </div>
    </div>
  )
}


// ── Turn card sub-component ──────────────────────────────────────────────────

function TurnCard({ turn, t }: { turn: TurnRecord; t: (key: string, params?: Record<string, string | number>) => string }) {
  const resp = turn.response ?? {}
  const differential = (resp.diag as Record<string, unknown> | undefined)?.differential as Array<Record<string, unknown>> | undefined
  const anti = resp.anti as Record<string, unknown> | undefined
  const firstLine = anti?.first_line as Array<Record<string, unknown>> | undefined
  const secondLine = anti?.second_line as Array<Record<string, unknown>> | undefined
  const alternatives = anti?.alternatives as Array<Record<string, unknown>> | undefined
  const references = resp.references as Array<Record<string, unknown>> | undefined
  const warnings = resp.warnings

  return (
    <article className="rounded-xl border bg-white px-4 py-3">
      <h3 className="text-sm font-medium text-gray-700">
        {t("sessionDetail.turnTitle", { index: turn.turn_index + 1 })}
      </h3>

      {/* Clinician query */}
      <div className="mt-2">
        <p className="text-xs text-gray-400">{t("sessionDetail.query")}</p>
        <p className="text-sm text-gray-900 mt-0.5">{turn.query}</p>
      </div>

      {/* Warnings */}
      {warnings && warnings.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-amber-600">{t("sessionDetail.warnings")}</p>
          <ul className="mt-1 list-disc list-inside text-sm text-amber-700">
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* Differential diagnosis */}
      {differential && differential.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-gray-500">{t("sessionDetail.differential")}</p>
          <ul className="mt-1 space-y-1">
            {differential.map((dx, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span className="text-gray-900">{dx.disease_name as string ?? "—"}</span>
                {dx.confidence != null && (
                  <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700">
                    {t("sessionDetail.confidence", { pct: Math.round((dx.confidence as number) * 100) })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Treatment lines */}
      {anti && (firstLine?.length || secondLine?.length || alternatives?.length) ? (
        <div className="mt-3">
          <p className="text-xs font-medium text-gray-500">{t("sessionDetail.treatment")}</p>
          <TreatmentSection label={t("sessionDetail.firstLine")} drugs={firstLine} />
          <TreatmentSection label={t("sessionDetail.secondLine")} drugs={secondLine} />
          <TreatmentSection label={t("sessionDetail.alternatives")} drugs={alternatives} />
        </div>
      ) : null}

      {/* References */}
      {references && references.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-gray-500">{t("sessionDetail.references")}</p>
          <ul className="mt-1 list-disc list-inside text-sm text-gray-600">
            {references.map((ref, i) => (
              <li key={i}>{ref.source_title as string ?? `Ref #${ref.ref_id ?? i + 1}`}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}

// ── Treatment section sub-component ──────────────────────────────────────────

function TreatmentSection({ label, drugs }: { label: string; drugs?: Array<Record<string, unknown>> }) {
  if (!drugs || drugs.length === 0) return null
  return (
    <div className="mt-1">
      <p className="text-xs text-gray-400">{label}</p>
      <ul className="mt-0.5 space-y-0.5">
        {drugs.map((drug, i) => {
          const name = String(drug.drug_name ?? "—")
          const dose = drug.dose ? String(drug.dose) : null
          const route = drug.route ? String(drug.route) : null
          const freq = drug.frequency ? String(drug.frequency) : null
          const dur = drug.duration_days != null ? Number(drug.duration_days) : null
          return (
            <li key={i} className="text-sm text-gray-800">
              <span className="font-medium">{name}</span>
              {dose && <span className="text-gray-500"> · {dose}</span>}
              {route && <span className="text-gray-500"> · {route}</span>}
              {freq && <span className="text-gray-500"> · {freq}</span>}
              {dur != null && <span className="text-gray-500"> · {dur}d</span>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
