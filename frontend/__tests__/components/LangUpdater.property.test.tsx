// ─────────────────────────────────────────────────────────────────────────────
// Property test for LangUpdater component
// Feature: ui-ux-improvements, Property 17: HTML lang attribute matches store language
// **Validates: Requirements 31.1**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render } from "@testing-library/react"
import { act } from "react"
import "@testing-library/jest-dom"
import LangUpdater from "@/components/LangUpdater"
import { useAppStore } from "@/lib/store"

// ─────────────────────────────────────────────────────────────────────────────
// Property 17: HTML lang attribute matches store language
// For any language value ("fr" or "en"), after LangUpdater re-renders,
// document.documentElement.lang equals that value.
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 17: HTML lang attribute matches store language", () => {
  beforeEach(() => {
    // Reset to default before each test
    document.documentElement.lang = "fr"
    act(() => {
      useAppStore.setState({ language: "fr" })
    })
  })

  it("for any language value, document.documentElement.lang equals the store language after render", () => {
    fc.assert(
      fc.property(
        fc.constantFrom("fr" as const, "en" as const),
        (language) => {
          // Set the language in the store
          act(() => {
            useAppStore.setState({ language })
          })

          // Render LangUpdater — useEffect will sync lang attribute
          const { unmount } = render(<LangUpdater />)

          expect(document.documentElement.lang).toBe(language)

          unmount()
        }
      ),
      { numRuns: 100 }
    )
  })

  it("updates the lang attribute when the store language changes after initial render", () => {
    fc.assert(
      fc.property(
        fc.constantFrom("fr" as const, "en" as const),
        fc.constantFrom("fr" as const, "en" as const),
        (initial, updated) => {
          // Set initial language
          act(() => {
            useAppStore.setState({ language: initial })
          })

          const { unmount } = render(<LangUpdater />)
          expect(document.documentElement.lang).toBe(initial)

          // Change language
          act(() => {
            useAppStore.setState({ language: updated })
          })

          expect(document.documentElement.lang).toBe(updated)

          unmount()
        }
      ),
      { numRuns: 100 }
    )
  })
})
