// ─────────────────────────────────────────────────────────────────────────────
// Property tests for DifferentialCard component
// Feature: ui-ux-improvements
// Property 2: DifferentialCard aria-expanded reflects expanded state
// Property 3: DifferentialCard confidence meter attributes
// **Validates: Requirements 3.1, 3.3, 3.4**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { DifferentialCard } from "@/components/chat/DifferentialCard"
import type { DiagnosisItem } from "@/lib/types"

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (key === "differential.confidence" && params?.pct !== undefined) {
        return `Confiance : ${params.pct}%`
      }
      return key
    },
    locale: "fr" as const,
  }),
}))

// ── Generators ────────────────────────────────────────────────────────────────

const arbNonEmptyString = fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0)

const arbDiagnosisItem: fc.Arbitrary<DiagnosisItem> = fc.record({
  rank: fc.integer({ min: 1, max: 10 }),
  disease_name: arbNonEmptyString,
  icd11_code: arbNonEmptyString,
  confidence: fc.float({ min: 0, max: 1, noNaN: true }),
  supporting_evidence: fc.array(arbNonEmptyString, { minLength: 0, maxLength: 3 }),
  against_evidence: fc.array(arbNonEmptyString, { minLength: 0, maxLength: 3 }),
  confirmatory_tests: fc.constant([]),
  red_flags: fc.array(arbNonEmptyString, { minLength: 0, maxLength: 3 }),
  citations: fc.constant([]),
})

// ── Property 2: aria-expanded reflects expanded state ─────────────────────────

describe("Property 2: DifferentialCard aria-expanded reflects expanded state", () => {
  it("aria-expanded matches the expanded state for any DiagnosisItem", () => {
    fc.assert(
      fc.property(
        arbDiagnosisItem,
        fc.boolean(),
        (item, shouldBeExpanded) => {
          // rank=1 starts expanded, others start collapsed
          const testItem = { ...item, rank: shouldBeExpanded ? 1 : 2 }

          const { container } = render(
            <DifferentialCard item={testItem} citations={[]} />
          )

          const button = container.querySelector("button")!
          expect(button).toBeTruthy()
          expect(button.getAttribute("aria-expanded")).toBe(String(shouldBeExpanded))
        },
      ),
      { numRuns: 100 },
    )
  })

  it("aria-expanded toggles when the button is clicked", () => {
    fc.assert(
      fc.property(
        arbDiagnosisItem,
        (item) => {
          // Start collapsed (rank != 1)
          const testItem = { ...item, rank: 2 }

          const { container } = render(
            <DifferentialCard item={testItem} citations={[]} />
          )

          const button = container.querySelector("button")!
          expect(button.getAttribute("aria-expanded")).toBe("false")

          // Click to expand
          fireEvent.click(button)
          expect(button.getAttribute("aria-expanded")).toBe("true")

          // Click to collapse
          fireEvent.click(button)
          expect(button.getAttribute("aria-expanded")).toBe("false")
        },
      ),
      { numRuns: 100 },
    )
  })
})

// ── Property 3: Confidence meter attributes ───────────────────────────────────

describe("Property 3: DifferentialCard confidence meter attributes", () => {
  it("meter has correct role, aria-valuemin, aria-valuemax, aria-valuenow, and aria-label for any confidence", () => {
    fc.assert(
      fc.property(
        arbDiagnosisItem,
        (item) => {
          const { container } = render(
            <DifferentialCard item={item} citations={[]} />
          )

          const meter = container.querySelector('[role="meter"]')!
          expect(meter).toBeTruthy()

          const expectedPct = Math.round(item.confidence * 100)

          expect(meter.getAttribute("aria-valuemin")).toBe("0")
          expect(meter.getAttribute("aria-valuemax")).toBe("100")
          expect(meter.getAttribute("aria-valuenow")).toBe(String(expectedPct))
          expect(meter.getAttribute("aria-label")).toContain(`${expectedPct}%`)
        },
      ),
      { numRuns: 100 },
    )
  })
})
