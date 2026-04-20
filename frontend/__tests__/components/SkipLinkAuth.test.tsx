/**
 * Unit tests for SkipLink and Auth pages
 * Validates: Requirements 32.1, 32.2, 32.3, 5.1, 5.2
 *
 * - Skip link visibility on focus, focus moves to main
 * - Auth pages have no html/body tags, use Tailwind CSS classes
 */
import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "skipLink.label": "Aller au contenu principal",
      }
      return translations[key] ?? key
    },
    locale: "fr" as const,
  }),
  getServerTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        "auth.subtitle": "Système d'aide à la décision clinique",
        "auth.email": "Email",
        "auth.emailPlaceholder": "votre@email.com",
        "auth.password": "Mot de passe",
        "auth.passwordPlaceholder": "••••••••",
        "auth.login": "Se connecter",
        "auth.loginError": "Identifiants incorrects",
        "auth.noAccount": "Pas de compte ?",
        "auth.createAccount": "Créer un compte",
        "auth.disclaimer": "Usage professionnel uniquement",
        "auth.registerTitle": "Créer un compte",
        "auth.register": "S'inscrire",
        "auth.registerError": "Erreur lors de l'inscription",
        "auth.hasAccount": "Déjà un compte ?",
        "auth.signIn": "Se connecter",
      }
      return translations[key] ?? key
    },
    locale: "fr" as const,
  }),
}))

// ── Mock next/headers (cookies) ───────────────────────────────────────────────
jest.mock("next/headers", () => ({
  cookies: jest.fn().mockResolvedValue({
    get: () => ({ value: "fr" }),
  }),
}))

// ── Mock Zustand store ────────────────────────────────────────────────────────
jest.mock("@/lib/store", () => ({
  useAppStore: (selector?: (s: Record<string, unknown>) => unknown) => {
    const state = { language: "fr" }
    return selector ? selector(state) : state
  },
}))

import { SkipLink } from "@/components/ui/SkipLink"

// ── SkipLink Tests ────────────────────────────────────────────────────────────
describe("SkipLink — Visibility and focus behavior (Requirements 32.1, 32.2, 32.3)", () => {
  it("renders a link with text 'Aller au contenu principal' (Req 32.1)", () => {
    render(<SkipLink />)

    const link = screen.getByText("Aller au contenu principal")
    expect(link).toBeInTheDocument()
    expect(link.tagName).toBe("A")
  })

  it("links to #main-content (Req 32.3)", () => {
    render(<SkipLink />)

    const link = screen.getByText("Aller au contenu principal")
    expect(link).toHaveAttribute("href", "#main-content")
  })

  it("is visually hidden by default using sr-only class (Req 32.1)", () => {
    render(<SkipLink />)

    const link = screen.getByText("Aller au contenu principal")
    expect(link).toHaveClass("sr-only")
  })

  it("becomes visible on focus via focus:not-sr-only class (Req 32.2)", () => {
    render(<SkipLink />)

    const link = screen.getByText("Aller au contenu principal")
    // The component uses focus:not-sr-only which removes sr-only on focus
    expect(link.className).toContain("focus:not-sr-only")
  })

  it("has focus styles that make it visible (Req 32.2)", () => {
    render(<SkipLink />)

    const link = screen.getByText("Aller au contenu principal")
    // Verify it has focus styles for visibility
    expect(link.className).toContain("focus:fixed")
    expect(link.className).toContain("focus:z-50")
  })

  it("is the first focusable element when placed as first child", () => {
    render(
      <div>
        <SkipLink />
        <button>Other button</button>
      </div>
    )

    const link = screen.getByText("Aller au contenu principal")
    const button = screen.getByText("Other button")

    // SkipLink should come before other elements in DOM order
    const parent = link.parentElement!
    const children = Array.from(parent.children)
    expect(children.indexOf(link)).toBeLessThan(children.indexOf(button))
  })
})

// ── Auth Pages Tests ──────────────────────────────────────────────────────────
describe("Login page — Layout compliance (Requirements 5.1, 5.2)", () => {
  let LoginPage: (props: { searchParams: Promise<{ error?: string }> }) => Promise<React.JSX.Element>

  beforeAll(async () => {
    const mod = await import("@/app/(auth)/login/page")
    LoginPage = mod.default as unknown as (props: { searchParams: Promise<{ error?: string }> }) => Promise<React.JSX.Element>
  })

  const defaultProps = { searchParams: Promise.resolve({}) }

  it("does NOT render html element (Req 5.1)", async () => {
    const element = await LoginPage(defaultProps)
    const { container } = render(element)

    const htmlElements = container.querySelectorAll("html")
    expect(htmlElements.length).toBe(0)
  })

  it("does NOT render body element (Req 5.1)", async () => {
    const element = await LoginPage(defaultProps)
    const { container } = render(element)

    const bodyElements = container.querySelectorAll("body")
    expect(bodyElements.length).toBe(0)
  })

  it("uses Tailwind CSS classes instead of inline styles (Req 5.2)", async () => {
    const element = await LoginPage(defaultProps)
    const { container } = render(element)

    // Check that no elements have inline style attributes
    const allElements = container.querySelectorAll("*")
    allElements.forEach((el) => {
      const styleAttr = el.getAttribute("style")
      expect(styleAttr).toBeNull()
    })
  })

  it("uses Tailwind classes for layout", async () => {
    const element = await LoginPage(defaultProps)
    const { container } = render(element)

    // The root div should have Tailwind classes
    const rootDiv = container.firstElementChild as HTMLElement
    expect(rootDiv).not.toBeNull()
    expect(rootDiv.className).toContain("min-h-screen")
    expect(rootDiv.className).toContain("flex")
  })

  it("renders a form with action /api/auth/login", async () => {
    const element = await LoginPage(defaultProps)
    const { container } = render(element)

    const formEl = container.querySelector('form[action="/api/auth/login"]')
    expect(formEl).not.toBeNull()
  })
})

describe("Register page — Layout compliance (Requirements 5.1, 5.2)", () => {
  let RegisterPage: (props: { searchParams: Promise<{ error?: string; msg?: string }> }) => Promise<React.JSX.Element>

  beforeAll(async () => {
    const mod = await import("@/app/(auth)/register/page")
    RegisterPage = mod.default as unknown as (props: { searchParams: Promise<{ error?: string; msg?: string }> }) => Promise<React.JSX.Element>
  })

  const defaultProps = { searchParams: Promise.resolve({}) }

  it("does NOT render html element (Req 5.1)", async () => {
    const element = await RegisterPage(defaultProps)
    const { container } = render(element)

    const htmlElements = container.querySelectorAll("html")
    expect(htmlElements.length).toBe(0)
  })

  it("does NOT render body element (Req 5.1)", async () => {
    const element = await RegisterPage(defaultProps)
    const { container } = render(element)

    const bodyElements = container.querySelectorAll("body")
    expect(bodyElements.length).toBe(0)
  })

  it("uses Tailwind CSS classes instead of inline styles (Req 5.2)", async () => {
    const element = await RegisterPage(defaultProps)
    const { container } = render(element)

    // Check that no elements have inline style attributes
    const allElements = container.querySelectorAll("*")
    allElements.forEach((el) => {
      const styleAttr = el.getAttribute("style")
      expect(styleAttr).toBeNull()
    })
  })

  it("uses Tailwind classes for layout", async () => {
    const element = await RegisterPage(defaultProps)
    const { container } = render(element)

    const rootDiv = container.firstElementChild as HTMLElement
    expect(rootDiv).not.toBeNull()
    expect(rootDiv.className).toContain("min-h-screen")
    expect(rootDiv.className).toContain("flex")
  })

  it("renders a form with action /api/auth/register", async () => {
    const element = await RegisterPage(defaultProps)
    const { container } = render(element)

    const formEl = container.querySelector('form[action="/api/auth/register"]')
    expect(formEl).not.toBeNull()
  })
})
