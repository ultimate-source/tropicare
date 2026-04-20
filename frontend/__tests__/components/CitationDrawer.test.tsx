/**
 * Unit tests for CitationDrawer component
 * Validates: Requirements 1.2, 1.3, 1.4, 1.5
 *
 * Tests focus trap cycling, Escape closes, backdrop click closes, initial focus.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { CitationDrawer } from "@/components/chat/CitationDrawer"
import type { Citation } from "@/lib/types"

// ── Mock useTranslation ───────────────────────────────────────────────────────
const translations: Record<string, string> = {
  "citation.title": "Sources",
  "citation.search": "Rechercher dans les sources…",
  "citation.count": "{{matched}} / {{total}} sources",
  "citation.close": "Fermer le panneau des sources",
}

jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      let val = translations[key] ?? key
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          val = val.replace(`{{${k}}}`, String(v))
        })
      }
      return val
    },
    locale: "fr" as const,
  }),
}))

// ── Test fixtures ─────────────────────────────────────────────────────────────
const sampleCitations: Citation[] = [
  {
    ref_id: 1,
    source_title: "WHO Guidelines",
    section: "Malaria Treatment",
    page: 42,
    version: "2023",
    date: "2023-06-01",
    chunk_snippet: "Artemisinin-based combination therapy is recommended",
  },
  {
    ref_id: 2,
    source_title: "CAME Formulary",
    section: "Antimalarials",
    page: 15,
    version: "v3",
    date: "2024-01-15",
    chunk_snippet: "Artesunate injection available in all regional hospitals",
  },
]

function renderDrawer(props: Partial<Parameters<typeof CitationDrawer>[0]> = {}) {
  const onClose = props.onClose ?? jest.fn()
  return {
    onClose,
    ...render(
      <CitationDrawer
        open={true}
        onClose={onClose}
        citations={sampleCitations}
        {...props}
      />,
    ),
  }
}

describe("CitationDrawer — Accessibility", () => {
  describe("Requirement 1.5: Initial focus on first focusable element", () => {
    it("sets focus on the close button (first focusable element) when opened", () => {
      renderDrawer()

      const closeButton = screen.getByRole("button", { name: /fermer le panneau/i })
      expect(closeButton).toHaveFocus()
    })

    it("does not render when open is false", () => {
      render(
        <CitationDrawer open={false} onClose={jest.fn()} citations={sampleCitations} />,
      )

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    })
  })

  describe("Requirement 1.3: Escape key closes the drawer", () => {
    it("calls onClose when Escape is pressed inside the drawer", () => {
      const { onClose } = renderDrawer()

      const dialog = screen.getByRole("dialog")
      fireEvent.keyDown(dialog, { key: "Escape" })

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  describe("Requirement 1.4: Clicking backdrop closes the drawer", () => {
    it("calls onClose when the backdrop overlay is clicked", () => {
      const { onClose } = renderDrawer()

      // The backdrop is the aria-hidden div
      const backdrop = document.querySelector('[aria-hidden="true"]')
      expect(backdrop).toBeInTheDocument()
      fireEvent.click(backdrop!)

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  describe("Requirement 1.2: Focus trap constrains Tab/Shift+Tab cycling", () => {
    it("wraps focus from last focusable element back to first on Tab", () => {
      renderDrawer()

      const dialog = screen.getByRole("dialog")
      const focusables = dialog.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )

      expect(focusables.length).toBeGreaterThan(1)

      const first = focusables[0]
      const last = focusables[focusables.length - 1]

      // Focus the last element
      last.focus()
      expect(last).toHaveFocus()

      // Press Tab on the last element — should wrap to first
      fireEvent.keyDown(dialog, { key: "Tab", shiftKey: false })
      expect(first).toHaveFocus()
    })

    it("wraps focus from first focusable element back to last on Shift+Tab", () => {
      renderDrawer()

      const dialog = screen.getByRole("dialog")
      const focusables = dialog.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )

      const first = focusables[0]
      const last = focusables[focusables.length - 1]

      // Focus the first element
      first.focus()
      expect(first).toHaveFocus()

      // Press Shift+Tab on the first element — should wrap to last
      fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true })
      expect(last).toHaveFocus()
    })
  })

  describe("Dialog ARIA attributes", () => {
    it("has role=dialog and aria-modal=true", () => {
      renderDrawer()

      const dialog = screen.getByRole("dialog")
      expect(dialog).toHaveAttribute("aria-modal", "true")
      expect(dialog).toHaveAttribute("aria-label", "Sources")
    })
  })
})
