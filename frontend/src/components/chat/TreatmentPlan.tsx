// ─────────────────────────────────────────────────────────────────────────────
// components/chat/TreatmentPlan.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState } from "react"
import type { TreatmentPlanData, DrugRegimen, Citation } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useTranslation } from "@/lib/i18n"

const TAB_KEYS = ["first_line", "second_line", "alternatives"] as const
const TAB_I18N: Record<string, string> = {
  first_line:   "treatment.firstLine",
  second_line:  "treatment.secondLine",
  alternatives: "treatment.alternatives",
}

function RegimenCard({
  r,
  citations,
  t,
  index,
}: {
  r: DrugRegimen
  citations: Citation[]
  t: (key: string, params?: Record<string, string | number>) => string
  index: number
}) {
  const tooltipId = `came-tooltip-${index}`

  return (
    <div className={cn(
      "rounded-lg border p-3 space-y-2 relative",
      !r.came_available ? "opacity-60 border-dashed" : "border-border",
    )}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-sm">{r.drug_name}</p>
          <p className="text-xs text-muted-foreground">{r.generic_name}</p>
        </div>
        <div className="flex gap-1 flex-wrap justify-end shrink-0">
          {r.came_available
            ? <span className="rounded border border-green-200 bg-green-50 px-1.5 py-0.5 text-xs text-green-700">{t("treatment.cameAvailable")}</span>
            : (
              <span
                className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-xs text-red-600 cursor-help group/came relative"
                tabIndex={0}
                aria-describedby={tooltipId}
              >
                {t("treatment.cameUnavailable")}
                <span
                  id={tooltipId}
                  role="tooltip"
                  className="invisible group-focus/came:visible group-hover/came:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white z-10"
                >
                  {t("treatment.cameTooltip")}
                </span>
              </span>
            )
          }
          {r.pregnancy_class && (
            <span className="rounded border border-purple-200 bg-purple-50 px-1.5 py-0.5 text-xs text-purple-700">
              {t("treatment.pregnancy")} {r.pregnancy_class}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <span className="text-muted-foreground">{t("treatment.dose")}</span>
        <span>{r.dose}</span>
        <span className="text-muted-foreground">{t("treatment.route")}</span>
        <span>{r.route}</span>
        <span className="text-muted-foreground">{t("treatment.frequency")}</span>
        <span>{r.frequency}</span>
        {r.duration_days != null && <>
          <span className="text-muted-foreground">{t("treatment.duration")}</span>
          <span>
            {r.duration_days > 1
              ? t("treatment.durationDays", { days: r.duration_days })
              : t("treatment.durationDay", { days: r.duration_days })}
          </span>
        </>}
      </div>

      {r.ddi_warnings.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2">
          <p className="text-xs font-semibold text-amber-700 mb-1">{t("treatment.interactions")}</p>
          {r.ddi_warnings.map((w, i) => <p key={i} className="text-xs text-amber-700">⚠ {w}</p>)}
        </div>
      )}

      {r.amr_note && (
        <p className="text-xs text-muted-foreground italic">{r.amr_note}</p>
      )}

      {r.monitoring.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground">{t("treatment.monitoring")}</p>
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
  const { t } = useTranslation()

  const regimens = plan[tab] ?? []

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b">
        {TAB_KEYS.map(key => (
          <button
            key={key}
            onClick={() => setTab(key)}
            aria-label={`${t("treatment.showAriaLabel")} ${t(TAB_I18N[key])}`}
            className={cn(
              "flex-1 py-2 text-xs font-medium transition-colors",
              tab === key
                ? "border-b-2 border-blue-600 text-blue-700 bg-blue-50"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(TAB_I18N[key])}
            {(plan[key]?.length ?? 0) > 0 && (
              <span className={cn(
                "ml-1 rounded-full px-1.5 py-0.5 text-xs",
                tab === key
                  ? "bg-blue-600 text-white"
                  : "bg-muted",
              )}>
                {plan[key].length}
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
          ? <p className="text-sm text-muted-foreground text-center py-4">{t("treatment.noRegimens")}</p>
          : regimens.map((r, i) => <RegimenCard key={i} r={r} citations={citations} t={t} index={i} />)
        }

        {/* Contraindicated */}
        {tab === "alternatives" && plan.contraindicated.length > 0 && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-xs font-semibold text-red-700 mb-1">{t("treatment.contraindicated")}</p>
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
