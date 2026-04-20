// ─────────────────────────────────────────────────────────────────────────────
// Property test for CitationDrawer filter logic
// Feature: ui-ux-improvements, Property 8: Citation filter correctness and count
// **Validates: Requirements 14.2, 14.3, 14.4**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { filterCitations } from "@/components/chat/CitationDrawer"
import type { Citation } from "@/lib/types"

/** Arbitrary that generates a valid Citation object. */
const arbCitation: fc.Arbitrary<Citation> = fc.record({
  ref_id: fc.integer({ min: 1, max: 999 }),
  source_title: fc.string({ minLength: 1, maxLength: 60 }),
  section: fc.string({ minLength: 1, maxLength: 40 }),
  page: fc.integer({ min: 1, max: 500 }),
  version: fc.string({ minLength: 1, maxLength: 10 }),
  date: fc.string({ minLength: 4, maxLength: 10 }),
  chunk_snippet: fc.string({ minLength: 1, maxLength: 120 }),
})

describe("Property 8: Citation filter correctness and count", () => {
  it("empty search returns all citations", () => {
    fc.assert(
      fc.property(
        fc.array(arbCitation, { minLength: 0, maxLength: 20 }),
        (citations) => {
          const result = filterCitations(citations, "")
          expect(result).toHaveLength(citations.length)
        },
      ),
      { numRuns: 100 },
    )
  })

  it("only matching citations are returned for any search string", () => {
    fc.assert(
      fc.property(
        fc.array(arbCitation, { minLength: 0, maxLength: 20 }),
        fc.string({ minLength: 0, maxLength: 30 }),
        (citations, search) => {
          const result = filterCitations(citations, search)
          const lower = search.toLowerCase().trim()

          if (!lower) {
            // Empty/whitespace search returns all
            expect(result).toHaveLength(citations.length)
            return
          }

          // Every returned citation must match the search
          for (const c of result) {
            const matches =
              c.source_title.toLowerCase().includes(lower) ||
              c.section.toLowerCase().includes(lower) ||
              c.chunk_snippet.toLowerCase().includes(lower)
            expect(matches).toBe(true)
          }

          // Every non-returned citation must NOT match
          const resultIds = new Set(result.map((c) => c.ref_id))
          for (const c of citations) {
            if (resultIds.has(c.ref_id)) continue
            const matches =
              c.source_title.toLowerCase().includes(lower) ||
              c.section.toLowerCase().includes(lower) ||
              c.chunk_snippet.toLowerCase().includes(lower)
            expect(matches).toBe(false)
          }
        },
      ),
      { numRuns: 200 },
    )
  })

  it("result count is always <= total citations", () => {
    fc.assert(
      fc.property(
        fc.array(arbCitation, { minLength: 0, maxLength: 20 }),
        fc.string({ minLength: 0, maxLength: 30 }),
        (citations, search) => {
          const result = filterCitations(citations, search)
          expect(result.length).toBeLessThanOrEqual(citations.length)
        },
      ),
      { numRuns: 100 },
    )
  })

  it("search is case-insensitive", () => {
    fc.assert(
      fc.property(
        fc.array(arbCitation, { minLength: 1, maxLength: 20 }),
        fc.integer({ min: 0, max: 19 }).chain((idx) =>
          fc.constant(idx),
        ),
        (citations, rawIdx) => {
          const idx = rawIdx % citations.length
          const citation = citations[idx]
          // Pick a substring from source_title and change its case
          const title = citation.source_title
          if (title.length === 0) return

          const sub = title.slice(0, Math.min(3, title.length))
          const lowerResult = filterCitations(citations, sub.toLowerCase())
          const upperResult = filterCitations(citations, sub.toUpperCase())

          // Both should return the same set of citations
          expect(lowerResult.length).toBe(upperResult.length)
        },
      ),
      { numRuns: 100 },
    )
  })
})
