// ─────────────────────────────────────────────────────────────────────────────
// lib/errors.ts — error categorization utility
// ─────────────────────────────────────────────────────────────────────────────

export type ErrorCategory = "network" | "authentication" | "server"

/**
 * Categorize an HTTP status code into a user-understandable error type.
 *
 * - 0 or connection failures → "network"
 * - 401, 403 → "authentication"
 * - All other codes → "server"
 */
export function categorizeError(status: number): ErrorCategory {
  if (status === 0) return "network"
  if (status === 401 || status === 403) return "authentication"
  return "server"
}
