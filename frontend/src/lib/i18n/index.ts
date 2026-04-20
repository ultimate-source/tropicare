// ─────────────────────────────────────────────────────────────────────────────
// lib/i18n/index.ts — lightweight i18n system
// ─────────────────────────────────────────────────────────────────────────────

import { fr } from "./fr"
import { en } from "./en"
import { useAppStore } from "@/lib/store"

type Locale = "fr" | "en"

const dictionaries: Record<Locale, Record<string, string>> = { fr, en }

/**
 * Interpolate `{{key}}` placeholders in a template string.
 */
export function interpolate(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_, key: string) => {
    const val = params[key]
    return val !== undefined ? String(val) : ""
  })
}

/**
 * Create a translation function for a given locale.
 * Fallback chain: active locale → French → raw key string.
 */
function createT(locale: Locale) {
  return function t(key: string, params?: Record<string, string | number>): string {
    const value = dictionaries[locale]?.[key] ?? dictionaries.fr[key] ?? key
    return interpolate(value, params)
  }
}

/**
 * React hook for client components.
 * Reads locale from Zustand store, returns `{ t, locale }`.
 */
export function useTranslation() {
  const locale = useAppStore((s) => s.language)
  return { t: createT(locale), locale }
}

/**
 * Server-side helper for Server Components.
 * Parses cookie value, defaults to "fr".
 */
export function getServerTranslation(cookieValue?: string) {
  const locale: Locale = cookieValue === "en" ? "en" : "fr"
  return { t: createT(locale), locale }
}

// Re-export dictionaries for testing
export { fr, en }
export type { Locale }
