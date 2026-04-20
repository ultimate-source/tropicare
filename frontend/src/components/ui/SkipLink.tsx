// ─────────────────────────────────────────────────────────────────────────────
// components/ui/SkipLink.tsx — Skip-to-content link for keyboard navigation
// Requirements: 32.1, 32.2, 32.3, 32.4
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useTranslation } from "@/lib/i18n"

/**
 * Visually hidden anchor that becomes visible on keyboard focus.
 * Links to #main-content so keyboard users can bypass navigation.
 */
export function SkipLink() {
  const { t } = useTranslation()

  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:outline-none focus:ring-2 focus:ring-blue-400"
    >
      {t("skipLink.label")}
    </a>
  )
}
