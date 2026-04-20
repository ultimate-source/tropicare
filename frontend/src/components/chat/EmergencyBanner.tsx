// ─────────────────────────────────────────────────────────────────────────────
// components/chat/EmergencyBanner.tsx
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import type { EmergencyFlag } from "@/lib/types"
import { useTranslation } from "@/lib/i18n"

export function EmergencyBanner({ flag, onDismiss }: { flag: EmergencyFlag; onDismiss: () => void }) {
  const { t } = useTranslation()

  const levelLabel = flag.level === "critical"
    ? t("emergency.critical")
    : t("emergency.urgent")

  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border-2 border-red-400 bg-red-50 p-4">
      <span className="text-2xl">🚨</span>
      <div className="flex-1">
        <p className="font-semibold text-red-800">
          {levelLabel} — {flag.disease}
        </p>
        <p className="text-sm text-red-700 mt-0.5">{flag.action}</p>
      </div>
      <button
        onClick={onDismiss}
        aria-label={t("emergency.closeAriaLabel")}
        className="shrink-0 rounded-lg border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
      >
        {t("emergency.dismiss")}
      </button>
    </div>
  )
}
