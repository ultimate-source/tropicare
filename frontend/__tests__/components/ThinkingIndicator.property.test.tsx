// ─────────────────────────────────────────────────────────────────────────────
// Property tests for ThinkingIndicator component
// Feature: ui-ux-improvements
// Property 6: ThinkingIndicator renders all reasoning lines
// **Validates: Requirements 10.1**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render } from "@testing-library/react"
import "@testing-library/jest-dom"
import { ThinkingIndicator } from "@/components/chat/ThinkingIndicator"

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "fr" as const,
  }),
}))

// ── Mock useAutoScroll ────────────────────────────────────────────────────────
jest.mock("@/hooks/useAutoScroll", () => ({
  useAutoScroll: () => ({ isAtBottom: true, scrollToBottom: jest.fn() }),
}))

// ── Generators ────────────────────────────────────────────────────────────────

const arbLine = fc.string({ minLength: 1, maxLength: 80 }).filter((s) => s.trim().length > 0)

const arbLines = fc.array(arbLine, { minLength: 1, maxLength: 50 })

// ── Property 6: ThinkingIndicator renders all reasoning lines ─────────────────

describe("Property 6: ThinkingIndicator renders all reasoning lines", () => {
  it("renders all lines and count matches input length for any list of 1–50 strings", () => {
    fc.assert(
      fc.property(arbLines, (lines) => {
        const { container } = render(<ThinkingIndicator lines={lines} />)

        // All lines are rendered as <p> elements inside the scrollable container
        const scrollContainer = container.querySelector(".overflow-y-auto")!
        expect(scrollContainer).toBeTruthy()

        const renderedParagraphs = scrollContainer.querySelectorAll("p")
        expect(renderedParagraphs.length).toBe(lines.length)

        // Each line's text content matches the input
        lines.forEach((line, i) => {
          expect(renderedParagraphs[i].textContent).toBe(line)
        })
      }),
      { numRuns: 100 },
    )
  })

  it("none of the lines are truncated (no truncate class on line elements)", () => {
    fc.assert(
      fc.property(arbLines, (lines) => {
        const { container } = render(<ThinkingIndicator lines={lines} />)

        const scrollContainer = container.querySelector(".overflow-y-auto")!
        const renderedParagraphs = scrollContainer.querySelectorAll("p")

        renderedParagraphs.forEach((p) => {
          expect(p.classList.contains("truncate")).toBe(false)
        })
      }),
      { numRuns: 100 },
    )
  })
})
