// ─────────────────────────────────────────────────────────────────────────────
// components/chat/DifferentialCard.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState } from "react"
import type { DiagnosisItem, Citation } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useTranslation } from "@/lib/i18n"

const PRIORITY_COLORS = {
  urgent:   "bg-red-100 text-red-700 border-red-200",
  standard: "bg-amber-100 text-amber-700 border-amber-200",
  optional: "bg-gray-100 text-gray-600 border-gray-200",
}
const AVAIL_COLORS = {
  disponible:   "text-green-700",
  limité:       "text-amber-600",
  indisponible: "text-red-600 line-through",
}

export function DifferentialCard({ item, citations }: { item: DiagnosisItem; citations: Citation[] }) {
  const [expanded, setExpanded] = useState(item.rank === 1)
  const { t } = useTranslation()
  const pct = Math.round(item.confidence * 100)
  const barColor = pct >= 70 ? "bg-blue-500" : pct >= 40 ? "bg-amber-400" : "bg-gray-300"

  return (
    <div className={cn(
      "rounded-xl border bg-card transition-shadow",
      item.rank === 1 ? "border-blue-200 shadow-sm" : "border-border",
    )}>
      {/* Header row */}
      <button
        onClick={() => setExpanded(x => !x)}
        aria-expanded={expanded}
        aria-label={`${expanded ? t("differential.collapse") : t("differential.expand")} : ${item.disease_name}`}
        className="flex w-full items-center gap-3 p-3 text-left"
      >
        {/* Rank badge */}
        <span className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
          item.rank === 1 ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground",
        )}>
          {item.rank}
        </span>

        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">{item.disease_name}</p>
          <p className="text-xs text-muted-foreground">{item.icd11_code}</p>
        </div>

        {/* Confidence bar + chevron — wraps below name on mobile */}
        <div className="flex items-center gap-2 shrink-0 max-sm:basis-full max-sm:pl-10">
          <div
            role="meter"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label={t("differential.confidence", { pct })}
            className="w-20 h-2 rounded-full bg-muted overflow-hidden"
          >
            <div className={cn("h-full rounded-full", barColor)} style={{ width: `${pct}%` }} />
          </div>
          <span className="text-xs font-medium text-muted-foreground w-8">{pct}%</span>
          {/* CSS chevron */}
          <span
            aria-hidden="true"
            className={cn(
              "inline-block h-2 w-2 border-r-2 border-b-2 border-current text-muted-foreground transition-transform duration-200",
              expanded ? "-rotate-135" : "rotate-45",
            )}
          />
        </div>
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t px-4 pb-4 pt-3 space-y-3">

          {/* Red flags */}
          {item.red_flags.length > 0 && (
            <div className="rounded-md bg-red-50 border border-red-200 p-2">
              <p className="text-xs font-semibold text-red-700 mb-1">{t("differential.redFlags")}</p>
              {item.red_flags.map((f, i) => (
                <p key={i} className="text-xs text-red-700">• {f}</p>
              ))}
            </div>
          )}

          {/* Evidence */}
          {item.supporting_evidence.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">{t("differential.supporting")}</p>
              {item.supporting_evidence.map((e, i) => (
                <p key={i} className="text-xs text-foreground">✓ {e}</p>
              ))}
            </div>
          )}
          {item.against_evidence.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">{t("differential.against")}</p>
              {item.against_evidence.map((e, i) => (
                <p key={i} className="text-xs text-muted-foreground">✗ {e}</p>
              ))}
            </div>
          )}

          {/* Tests */}
          {item.confirmatory_tests.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">{t("differential.tests")}</p>
              <div className="space-y-1">
                {item.confirmatory_tests.map((test, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className={cn("mt-0.5 rounded border px-1 py-0.5 font-medium shrink-0",
                      PRIORITY_COLORS[test.priority])}>
                      {test.priority}
                    </span>
                    <span className={cn("font-medium", AVAIL_COLORS[test.availability_togo])}>
                      {test.name}
                    </span>
                    <span className="text-muted-foreground">— {test.interpretation}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Citations */}
          {item.citations.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1 border-t">
              {item.citations.map(ref => {
                const cit = citations.find(c => c.ref_id === ref)
                return (
                  <span key={ref}
                    title={cit ? `${cit.source_title} — ${cit.section} p.${cit.page}` : ""}
                    className="text-xs text-blue-600 bg-blue-50 rounded px-1 cursor-help border border-blue-200">
                    [{ref}]
                  </span>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
