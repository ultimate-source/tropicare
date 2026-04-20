// ─────────────────────────────────────────────────────────────────────────────
// Property test for error categorization
// Feature: ui-ux-improvements, Property 10: HTTP status code error categorization
// **Validates: Requirements 17.3**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { categorizeError, type ErrorCategory } from "@/lib/errors"

const VALID_CATEGORIES: ErrorCategory[] = ["network", "authentication", "server"]

describe("Property 10: HTTP status code error categorization", () => {
  it("for any HTTP status code 100–599, returns exactly one of 'network', 'authentication', or 'server'", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 599 }),
        (status) => {
          const result = categorizeError(status)
          expect(VALID_CATEGORIES).toContain(result)
        }
      ),
      { numRuns: 500 }
    )
  })

  it("returns 'network' for status code 0 (connection failure)", () => {
    expect(categorizeError(0)).toBe("network")
  })

  it("returns 'authentication' for 401 and 403", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(401, 403),
        (status) => {
          expect(categorizeError(status)).toBe("authentication")
        }
      ),
      { numRuns: 100 }
    )
  })

  it("returns 'server' for any non-auth, non-network status code", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 599 }).filter((s) => s !== 401 && s !== 403),
        (status) => {
          expect(categorizeError(status)).toBe("server")
        }
      ),
      { numRuns: 100 }
    )
  })
})
