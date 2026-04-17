// ─────────────────────────────────────────────────────────────────────────────
// components/chat/TreatmentPlan.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState } from "react"
import type { TreatmentPlanData, DrugRegimen, Citation } from "@/lib/types"
import { cn } from "@/lib/utils"

const SEVERITY_BADGE: Record<string, string> = {
  contraindicated: "bg-red-100 text-red-700 border-red-200",
  major:           "bg-orange-100 text-orange-700 border-orange-200",
  moderate:        "bg-amber-100 text-amber-700 border-amber-200",
  minor:           "bg-gray-100 text-gray-600 border-gray-200",
}

const TABS = [
  { key: "first_line",   label: "1ère ligne" },
  { key: "second_line",  label: "2ème ligne" },
  { key: "alternatives", label: "Alternatives" },
] as const

function RegimenCard({ r, citations }: { r: DrugRegimen; citations: Citation[] }) {
  return (
    <div className={cn(
      "rounded-lg border p-3 space-y-2",
      !r.came_available ? "opacity-60 border-dashed" : "border-border",
    )}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-sm">{r.drug_name}</p>
          <p className="text-xs text-muted-foreground">{r.generic_name}</p>
        </div>
        <div className="flex gap-1 flex-wrap justify-end shrink-0">
          {r.came_available
            ? <span className="rounded border border-green-200 bg-green-50 px-1.5 py-0.5 text-xs text-green-700">CAME ✓</span>
            : <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-xs text-red-600">CAME ✗</span>
          }
          {r.pregnancy_class && (
            <span className="rounded border border-purple-200 bg-purple-50 px-1.5 py-0.5 text-xs text-purple-700">
              Grossesse {r.pregnancy_class}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <span className="text-muted-foreground">Dose</span>
        <span>{r.dose}</span>
        <span className="text-muted-foreground">Voie</span>
        <span>{r.route}</span>
        <span className="text-muted-foreground">Fréquence</span>
        <span>{r.frequency}</span>
        {r.duration_days != null && <>
          <span className="text-muted-foreground">Durée</span>
          <span>{r.duration_days} jour{r.duration_days > 1 ? "s" : ""}</span>
        </>}
      </div>

      {r.ddi_warnings.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2">
          <p className="text-xs font-semibold text-amber-700 mb-1">Interactions</p>
          {r.ddi_warnings.map((w, i) => <p key={i} className="text-xs text-amber-700">⚠ {w}</p>)}
        </div>
      )}

      {r.amr_note && (
        <p className="text-xs text-muted-foreground italic">{r.amr_note}</p>
      )}

      {r.monitoring.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground">Surveillance</p>
          {r.monitoring.map((m, i) => <p key={i} className="text-xs">• {m}</p>)}
        </div>
      )}

      {r.citations.length > 0 && (
        <div className="flex flex-wrap gap-1 border-t pt-1">
          {r.citations.map(ref => {
            const cit = citations.find(c => c.ref_id === ref)
            return (
              <span key={ref}
                title={cit ? `${cit.source_title} p.${cit.page}` : ""}
                className="text-xs text-blue-600 bg-blue-50 rounded px-1 border border-blue-200 cursor-help">
                [{ref}]
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function TreatmentPlan({ plan, citations }: { plan: TreatmentPlanData; citations: Citation[] }) {
  const [tab, setTab] = useState<"first_line" | "second_line" | "alternatives">("first_line")

  const regimens = plan[tab] ?? []

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex-1 py-2 text-xs font-medium transition-colors",
              tab === t.key
                ? "border-b-2 border-blue-600 text-blue-700 bg-blue-50"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
            {(plan[t.key]?.length ?? 0) > 0 && (
              <span className="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-xs">
                {plan[t.key].length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="p-3 space-y-3">
        {/* Clinical rationale */}
        {plan.clinical_rationale && tab === "first_line" && (
          <p className="text-xs text-muted-foreground border-l-2 border-blue-300 pl-2 italic">
            {plan.clinical_rationale}
          </p>
        )}

        {regimens.length === 0
          ? <p className="text-sm text-muted-foreground text-center py-4">Aucun traitement dans cette ligne</p>
          : regimens.map((r, i) => <RegimenCard key={i} r={r} citations={citations} />)
        }

        {/* Contraindicated */}
        {tab === "alternatives" && plan.contraindicated.length > 0 && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-xs font-semibold text-red-700 mb-1">Contre-indiqués</p>
            {plan.contraindicated.map((c, i) => (
              <p key={i} className="text-xs text-red-700">🚫 <strong>{c.drug}</strong> — {c.reason}</p>
            ))}
          </div>
        )}
      </div>

      {/* Disclaimer */}
      {plan.disclaimer && (
        <div className="border-t bg-amber-50 px-3 py-2">
          <p className="text-xs text-amber-700">{plan.disclaimer}</p>
        </div>
      )}
    </div>
  )
}

