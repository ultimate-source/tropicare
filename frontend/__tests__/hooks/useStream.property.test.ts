// ─────────────────────────────────────────────────────────────────────────────
// Property test for streaming error preservation
// Feature: ui-ux-improvements, Property 9: Streaming error preserves partial results
// **Validates: Requirements 16.3**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { applyEvent, emptyTurn, type Turn } from "@/hooks/useStream"
import type { DiagnosisItem, Citation, SSEEvent } from "@/lib/types"

// ── Arbitraries ──────────────────────────────────────────────────────────────

const arbDiagnosisItem: fc.Arbitrary<DiagnosisItem> = fc.record({
  rank:                fc.integer({ min: 1, max: 20 }),
  disease_name:        fc.string({ minLength: 1, maxLength: 50 }),
  icd11_code:          fc.string({ minLength: 1, maxLength: 10 }),
  confidence:          fc.double({ min: 0, max: 1, noNaN: true }),
  supporting_evidence: fc.array(fc.string({ minLength: 1, maxLength: 30 }), { minLength: 0, maxLength: 3 }),
  against_evidence:    fc.array(fc.string({ minLength: 1, maxLength: 30 }), { minLength: 0, maxLength: 3 }),
  confirmatory_tests:  fc.constant([]),
  red_flags:           fc.array(fc.string({ minLength: 1, maxLength: 30 }), { minLength: 0, maxLength: 3 }),
  citations:           fc.array(fc.integer({ min: 1, max: 100 }), { minLength: 0, maxLength: 5 }),
})

const arbCitation: fc.Arbitrary<Citation> = fc.record({
  ref_id:        fc.integer({ min: 1, max: 100 }),
  source_title:  fc.string({ minLength: 1, maxLength: 50 }),
  section:       fc.string({ minLength: 1, maxLength: 30 }),
  page:          fc.integer({ min: 1, max: 500 }),
  version:       fc.string({ minLength: 1, maxLength: 10 }),
  date:          fc.string({ minLength: 1, maxLength: 10 }),
  chunk_snippet: fc.string({ minLength: 1, maxLength: 100 }),
})

const arbErrorMessage: fc.Arbitrary<string> = fc.string({ minLength: 1, maxLength: 100 })

// Build a Turn with random differential items and citations
const arbTurnWithContent: fc.Arbitrary<Turn> = fc.record({
  query:        fc.string({ minLength: 1, maxLength: 50 }),
  thinking:     fc.array(fc.string({ minLength: 1, maxLength: 50 }), { minLength: 0, maxLength: 5 }),
  emergencies:  fc.constant([]),
  differential: fc.array(arbDiagnosisItem, { minLength: 1, maxLength: 5 }),
  treatment:    fc.constant({ first_line: [], second_line: [], alternatives: [] }),
  citations:    fc.array(arbCitation, { minLength: 0, maxLength: 3 }),
  annotations:  fc.constant([]),
  turnId:       fc.constant(null),
  error:        fc.constant(null),
})

// ── Property Tests ───────────────────────────────────────────────────────────

describe("Property 9: Streaming error preserves partial results", () => {
  it("for any Turn with differential items and citations, applying an error event retains all existing items while setting the error field", () => {
    fc.assert(
      fc.property(
        arbTurnWithContent,
        arbErrorMessage,
        (turn, errorMsg) => {
          const errorEvent: SSEEvent = { type: "error", message: errorMsg }
          const result = applyEvent(turn, errorEvent)

          // Error field is set
          expect(result.error).toBe(errorMsg)

          // All differential items are preserved
          expect(result.differential).toHaveLength(turn.differential.length)
          expect(result.differential).toEqual(turn.differential)

          // All citations are preserved
          expect(result.citations).toHaveLength(turn.citations.length)
          expect(result.citations).toEqual(turn.citations)

          // Thinking lines are preserved
          expect(result.thinking).toEqual(turn.thinking)

          // Query is preserved
          expect(result.query).toBe(turn.query)
        }
      ),
      { numRuns: 200 }
    )
  })

  it("error event does not modify any field other than error", () => {
    fc.assert(
      fc.property(
        arbTurnWithContent,
        arbErrorMessage,
        (turn, errorMsg) => {
          const errorEvent: SSEEvent = { type: "error", message: errorMsg }
          const result = applyEvent(turn, errorEvent)

          // Every field except error should be identical
          expect(result.query).toBe(turn.query)
          expect(result.thinking).toEqual(turn.thinking)
          expect(result.emergencies).toEqual(turn.emergencies)
          expect(result.differential).toEqual(turn.differential)
          expect(result.treatment).toEqual(turn.treatment)
          expect(result.citations).toEqual(turn.citations)
          expect(result.annotations).toEqual(turn.annotations)
          expect(result.turnId).toBe(turn.turnId)
        }
      ),
      { numRuns: 200 }
    )
  })
})
