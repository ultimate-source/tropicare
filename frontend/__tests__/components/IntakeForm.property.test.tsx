// ─────────────────────────────────────────────────────────────────────────────
// Property tests for IntakeForm Section component
// Feature: ui-ux-improvements
// Property 1: Section aria-expanded reflects open state
// **Validates: Requirements 2.1**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render } from "@testing-library/react"
import "@testing-library/jest-dom"
import { Section } from "@/components/intake/IntakeForm"

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "fr" as const,
  }),
}))

// ── Property 1: Section aria-expanded reflects open state ─────────────────────

describe("Property 1: Section aria-expanded reflects open state", () => {
  it("for any boolean open state, the toggle button's aria-expanded equals the string representation", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0),
        (openState, title) => {
          const { container } = render(
            <Section
              title={title}
              open={openState}
              onToggle={() => {}}
              id="test-section"
            >
              <div>Content</div>
            </Section>
          )

          const button = container.querySelector("button")!
          expect(button).toBeTruthy()
          expect(button.getAttribute("aria-expanded")).toBe(String(openState))
        },
      ),
      { numRuns: 100 },
    )
  })

  it("aria-controls references the content panel id", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        fc.constantFrom("vitals", "labs", "context"),
        (openState, sectionId) => {
          const { container } = render(
            <Section
              title="Test Section"
              open={openState}
              onToggle={() => {}}
              id={sectionId}
            >
              <div>Content</div>
            </Section>
          )

          const button = container.querySelector("button")!
          expect(button.getAttribute("aria-controls")).toBe(`${sectionId}-content`)

          // If open, the content panel with that id should exist
          if (openState) {
            const panel = container.querySelector(`#${sectionId}-content`)
            expect(panel).toBeTruthy()
          }
        },
      ),
      { numRuns: 100 },
    )
  })

  it("uses CSS chevron with aria-hidden instead of text characters", () => {
    fc.assert(
      fc.property(
        fc.boolean(),
        (openState) => {
          const { container } = render(
            <Section
              title="Test"
              open={openState}
              onToggle={() => {}}
              id="test"
            >
              <div>Content</div>
            </Section>
          )

          const button = container.querySelector("button")!
          // Should not contain text chevron characters
          expect(button.textContent).not.toContain("▲")
          expect(button.textContent).not.toContain("▼")

          // Should have an element with aria-hidden="true" for the chevron
          const chevron = button.querySelector('[aria-hidden="true"]')
          expect(chevron).toBeTruthy()
        },
      ),
      { numRuns: 100 },
    )
  })
})
