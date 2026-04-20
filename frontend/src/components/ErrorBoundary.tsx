// ─────────────────────────────────────────────────────────────────────────────
// components/ErrorBoundary.tsx — catches rendering errors with localized fallback
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import React from "react"
import { fr, en, interpolate } from "@/lib/i18n"
import type { Locale } from "@/lib/i18n"

interface ErrorBoundaryProps {
  language: "fr" | "en"
  children: React.ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

const dictionaries: Record<Locale, Record<string, string>> = { fr, en }

/**
 * Create a translation function for a given locale.
 * Mirrors the logic in lib/i18n/index.ts but usable in a class component.
 */
function createT(locale: Locale) {
  return function t(key: string, params?: Record<string, string | number>): string {
    const value = dictionaries[locale]?.[key] ?? dictionaries.fr[key] ?? key
    return interpolate(value, params)
  }
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[ErrorBoundary] Rendering error caught:", error)
    console.error("[ErrorBoundary] Component stack:", errorInfo.componentStack)
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      const t = createT(this.props.language)

      return (
        <div
          role="alert"
          className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8 text-center"
        >
          <span className="text-4xl" aria-hidden="true">⚠️</span>
          <h2 className="text-xl font-semibold text-gray-900">{t("error.unexpected")}</h2>
          <p className="max-w-md text-sm text-gray-600">{t("error.renderDescription")}</p>
          <button
            onClick={this.handleRetry}
            className="mt-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            aria-label={t("error.retry")}
          >
            {t("error.retry")}
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
