// ─────────────────────────────────────────────────────────────────────────────
// app/(admin)/admin/analytics/page.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useEffect, useState } from "react"
import { api, type AnalyticsSummary } from "@/lib/api"

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <p className="text-xs font-medium text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-semibold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function AnalyticsPage() {
  const [data,    setData]    = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    api.admin.analytics()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6 text-sm text-gray-500">Chargement…</div>
  if (error)   return <div className="p-6 text-sm text-red-600">{error}</div>
  if (!data)   return null

  const fb          = data.feedback
  const feedbackRate = fb.total > 0
    ? Math.round((fb.correct / fb.total) * 100)
    : null

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <h1 className="text-lg font-semibold text-gray-900">Analytiques</h1>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Sessions totales"   value={data.total_sessions} />
        <StatCard label="Utilisateurs 7j"    value={data.active_users_7d} sub="actifs cette semaine"/>
        <StatCard
          label="Latence P95"
          value={`${(data.p95_latency_ms / 1000).toFixed(1)}s`}
          sub={data.p95_latency_ms <= 8000 ? "✓ objectif < 8s" : "⚠ objectif dépassé"}
        />
        <StatCard
          label="Taux de citation"
          value={`${Math.round(data.citation_rate * 100)}%`}
          sub={data.citation_rate >= 0.95 ? "✓ objectif ≥ 95%" : "⚠ objectif non atteint"}
        />
        <StatCard
          label="Taux d'urgences"
          value={`${Math.round(data.emergency_rate * 100)}%`}
          sub="des consultations"
        />
        <StatCard
          label="Latence P50"
          value={`${(data.p50_latency_ms / 1000).toFixed(1)}s`}
          sub="médiane"
        />
        {data.guideline_adherence != null && (
          <StatCard
            label="Adhérence PNLP (eval)"
            value={`${Math.round(data.guideline_adherence * 100)}%`}
            sub="objectif ≥ 90%"
          />
        )}
      </div>

      {/* Feedback accuracy */}
      {feedbackRate !== null && (
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-gray-500 mb-2">
            Exactitude (retour cliniciens) — {data.feedback_total} évaluations
          </p>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 rounded-full bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-green-500"
                style={{ width: `${feedbackRate}%` }}
              />
            </div>
            <span className="text-sm font-semibold text-gray-900 w-12 text-right">
              {feedbackRate}%
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">objectif ≥ 82% (top-1)</p>
        </div>
      )}

      {/* Top diseases */}
      <div className="rounded-xl border bg-white p-4 shadow-sm">
        <p className="text-xs font-medium text-gray-500 mb-3">Maladies les plus consultées</p>
        <div className="space-y-2">
          {data.top_diseases.slice(0, 10).map((d, i) => {
            const max = data.top_diseases[0]?.count ?? 1
            return (
              <div key={d.disease} className="flex items-center gap-3">
                <span className="w-5 text-xs text-gray-400 text-right">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 truncate">{d.disease}</p>
                </div>
                <div className="w-32 h-2 rounded-full bg-gray-100 overflow-hidden shrink-0">
                  <div
                    className="h-full rounded-full bg-blue-400"
                    style={{ width: `${(d.count / max) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 w-8 text-right tabular-nums">{d.count}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}