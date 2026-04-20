// ─────────────────────────────────────────────────────────────────────────────
// components/intake/SummaryPreview.tsx — Modal summary preview before submission
// Requirements: 9.1, 9.2, 9.3, 9.4
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useRef } from "react"
import { useTranslation } from "@/lib/i18n"
import { useFocusTrap } from "@/hooks/useFocusTrap"
import type { PatientContext } from "@/lib/types"

export interface SummaryPreviewProps {
  context: PatientContext
  onConfirm: () => void
  onEdit: () => void
}

/**
 * Modal overlay displaying all filled PatientContext fields for review.
 * Implements focus trap and closes on Escape.
 */
export function SummaryPreview({ context, onConfirm, onEdit }: SummaryPreviewProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)

  useFocusTrap(containerRef, true, onEdit)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-label={t("intake.summaryTitle")}
        className="mx-4 max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
      >
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          {t("intake.summaryTitle")}
        </h2>

        <dl className="space-y-2 text-sm">
          {/* Mandatory fields */}
          <SummaryField label={t("intake.age")} value={String(context.age_years)} />
          <SummaryField label={t("intake.sex")} value={context.sex} />
          <SummaryField label={t("intake.region")} value={context.region} />
          <SummaryField label={t("intake.complaint")} value={context.chief_complaint} />

          {/* Optional fields — only render if filled */}
          {context.weight_kg != null && (
            <SummaryField label={t("intake.weight")} value={String(context.weight_kg)} />
          )}

          {context.symptom_onset_days != null && (
            <SummaryField label={t("intake.onset")} value={String(context.symptom_onset_days)} />
          )}

          {context.pregnancy_status && (
            <SummaryField label={t("intake.pregnancy")} value={context.pregnancy_status} />
          )}

          {context.symptoms.length > 0 && (
            <SummaryField
              label={t("intake.symptoms")}
              value={context.symptoms.map((s) => s.text).join(", ")}
            />
          )}

          {/* Vital signs */}
          {context.vital_signs && hasFilledVitals(context.vital_signs) && (
            <SummarySection label={t("intake.sectionVitals")}>
              {Object.entries(context.vital_signs).map(([key, val]) =>
                val != null ? (
                  <span key={key} className="mr-3">
                    {key}: {val}
                  </span>
                ) : null
              )}
            </SummarySection>
          )}

          {/* Lab results */}
          {context.lab_results.length > 0 && (
            <SummarySection label={t("intake.sectionLabs")}>
              {context.lab_results.map((lab, i) => (
                <span key={i} className="mr-3">
                  {lab.name}: {lab.value} {lab.unit}
                </span>
              ))}
            </SummarySection>
          )}

          {/* Medications */}
          {context.current_medications.length > 0 && (
            <SummarySection label={t("intake.contextMeds")}>
              {context.current_medications.map((med, i) => (
                <span key={i} className="mr-3">
                  {med.name} {med.dose} {med.frequency}
                </span>
              ))}
            </SummarySection>
          )}

          {/* Allergies */}
          {context.allergies.length > 0 && (
            <SummaryField
              label={t("intake.contextAllergies")}
              value={context.allergies.join(", ")}
            />
          )}

          {/* Travel history */}
          {context.travel_history.length > 0 && (
            <SummaryField
              label={t("intake.contextTravel")}
              value={context.travel_history.join(", ")}
            />
          )}
        </dl>

        {/* Action buttons */}
        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 rounded-lg bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            {t("intake.summaryConfirm")}
          </button>
          <button
            type="button"
            onClick={onEdit}
            className="flex-1 rounded-lg border border-gray-300 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
          >
            {t("intake.summaryEdit")}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Helper components ─────────────────────────────────────────────────────────

function SummaryField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="font-medium text-gray-600">{label}:</dt>
      <dd className="text-gray-900">{value}</dd>
    </div>
  )
}

function SummarySection({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div>
      <dt className="font-medium text-gray-600">{label}:</dt>
      <dd className="mt-0.5 text-gray-900">{children}</dd>
    </div>
  )
}

function hasFilledVitals(vitals: Partial<Record<string, unknown>>): boolean {
  return Object.values(vitals).some((v) => v != null)
}
