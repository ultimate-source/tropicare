// ─────────────────────────────────────────────────────────────────────────────
// components/ErrorBoundary.tsx — catches rendering errors with localized fallback
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import React from "react"

interface ErrorBoundaryProps {
  language: "fr" | "en"
  children: React.ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

const MESSAGES = {
  fr: {
    title: "Une erreur inattendue s'est produite",
    description: "Quelque chose s'est mal passé lors du rendu de cette page.",
    retry: "Réessayer",
  },
  en: {
    title: "An unexpected error occurred",
    description: "Something went wrong while rendering this page.",
    retry: "Retry",
  },
} as const

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
      const msgs = MESSAGES[this.props.language] ?? MESSAGES.fr

      return (
        <div
          role="alert"
          className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8 text-center"
        >
          <span className="text-4xl" aria-hidden="true">⚠️</span>
          <h2 className="text-xl font-semibold text-gray-900">{msgs.title}</h2>
          <p className="max-w-md text-sm text-gray-600">{msgs.description}</p>
          <button
            onClick={this.handleRetry}
            className="mt-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            aria-label={msgs.retry}
          >
            {msgs.retry}
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
