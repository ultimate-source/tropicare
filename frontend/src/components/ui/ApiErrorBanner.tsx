// ─────────────────────────────────────────────────────────────────────────────
// components/ui/ApiErrorBanner.tsx — reusable error banner for API failures
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { categorizeError, type ErrorCategory } from "@/lib/errors"
import { useTranslation } from "@/lib/i18n"

interface ApiErrorBannerProps {
  /** Raw error message (used as fallback if status is not provided) */
  error: string
  /** HTTP status code — used to categorize the error */
  status?: number
  /** Callback invoked when the user clicks "Réessayer" */
  onRetry?: () => void
}

/**
 * Extract an HTTP status code from an error message string.
 * The API client throws errors like "401 Unauthorized" or "500 Internal Server Error".
 */
function extractStatus(message: string): number {
  const match = message.match(/^(\d{3})\s/)
  return match ? parseInt(match[1], 10) : 0
}

export function ApiErrorBanner({ error, status, onRetry }: ApiErrorBannerProps) {
  const { t } = useTranslation()

  const resolvedStatus = status ?? extractStatus(error)
  const category: ErrorCategory = categorizeError(resolvedStatus)

  const title = t(`error.${category}`)
  const description = t(`error.${category}Description`)

  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm"
    >
      <p className="font-medium text-red-800">{title}</p>
      <p className="mt-1 text-red-700">{description}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 transition-colors"
        >
          {t("error.retry")}
        </button>
      )}
    </div>
  )
}
