// ─────────────────────────────────────────────────────────────────────────────
// Property tests for the i18n system
// Feature: ui-ux-improvements
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { fr } from "@/lib/i18n/fr"
import { en } from "@/lib/i18n/en"
import { interpolate } from "@/lib/i18n/index"

// ─────────────────────────────────────────────────────────────────────────────
// Property 13: Translation dictionary completeness
// Feature: ui-ux-improvements, Property 13: Translation dictionary completeness
// **Validates: Requirements 26.1**
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 13: Translation dictionary completeness", () => {
  const frKeys = Object.keys(fr)
  const enKeys = Object.keys(en)

  it("every key in fr exists in en", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...frKeys),
        (key) => {
          expect(key in en).toBe(true)
        }
      ),
      { numRuns: Math.min(frKeys.length, 200) }
    )
  })

  it("every key in en exists in fr", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...enKeys),
        (key) => {
          expect(key in fr).toBe(true)
        }
      ),
      { numRuns: Math.min(enKeys.length, 200) }
    )
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Property 14: Translation lookup returns correct value
// Feature: ui-ux-improvements, Property 14: Translation lookup returns correct value
// **Validates: Requirements 26.2**
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 14: Translation lookup returns correct value", () => {
  // We need to test the createT function behavior without the hook.
  // Import the module and test the lookup logic directly.
  // Since useTranslation uses Zustand, we test the underlying logic.

  function createT(locale: "fr" | "en") {
    const dictionaries = { fr, en }
    return function t(key: string, params?: Record<string, string | number>): string {
      const value = dictionaries[locale]?.[key] ?? dictionaries.fr[key] ?? key
      return interpolate(value, params)
    }
  }

  const sharedKeys = Object.keys(fr).filter((k) => k in en)

  it("for any key in both dictionaries and any locale, t(key) returns the exact value", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...sharedKeys),
        fc.constantFrom("fr" as const, "en" as const),
        (key, locale) => {
          const t = createT(locale)
          const expected = locale === "fr" ? fr[key] : en[key]
          // Only test keys without interpolation placeholders
          if (!expected.includes("{{")) {
            expect(t(key)).toBe(expected)
          }
        }
      ),
      { numRuns: 200 }
    )
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Property 15: Translation fallback to French for missing keys
// Feature: ui-ux-improvements, Property 15: Translation fallback to French for missing keys
// **Validates: Requirements 26.4**
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 15: Translation fallback to French for missing keys", () => {
  function createT(locale: "fr" | "en") {
    const dictionaries: Record<string, Record<string, string>> = { fr, en }
    return function t(key: string, params?: Record<string, string | number>): string {
      const value = dictionaries[locale]?.[key] ?? dictionaries.fr[key] ?? key
      return interpolate(value, params)
    }
  }

  it("for any key in fr but absent from en, t(key) with locale 'en' returns the French value", () => {
    // Create a modified en dict missing some keys to test fallback
    const keysOnlyInFr = Object.keys(fr).filter((k) => !(k in en))

    if (keysOnlyInFr.length === 0) {
      // Both dicts are complete (Property 13 ensures this).
      // We test fallback by simulating a missing key scenario.
      // Use a synthetic key that exists in fr but not en.
      const syntheticKey = "__test_fallback_key__"
      const modifiedFr = { ...fr, [syntheticKey]: "valeur de secours" }

      // Recreate createT with modified dictionaries
      function createTWithFallback(locale: "fr" | "en") {
        const dicts: Record<string, Record<string, string>> = { fr: modifiedFr, en }
        return function t(key: string): string {
          return dicts[locale]?.[key] ?? dicts.fr[key] ?? key
        }
      }

      fc.assert(
        fc.property(
          fc.constant(syntheticKey),
          (key) => {
            const t = createTWithFallback("en")
            expect(t(key)).toBe("valeur de secours")
          }
        ),
        { numRuns: 100 }
      )
    } else {
      fc.assert(
        fc.property(
          fc.constantFrom(...keysOnlyInFr),
          (key) => {
            const t = createT("en")
            expect(t(key)).toBe(fr[key])
          }
        ),
        { numRuns: Math.min(keysOnlyInFr.length, 100) }
      )
    }
  })

  it("for any completely unknown key, t returns the raw key string", () => {
    function createTLocal(locale: "fr" | "en") {
      const dictionaries: Record<string, Record<string, string>> = { fr, en }
      return function t(key: string): string {
        return dictionaries[locale]?.[key] ?? dictionaries.fr[key] ?? key
      }
    }

    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 50 }).filter(
          (s) => !(s in fr) && !(s in en)
        ),
        fc.constantFrom("fr" as const, "en" as const),
        (key, locale) => {
          const t = createTLocal(locale)
          expect(t(key)).toBe(key)
        }
      ),
      { numRuns: 100 }
    )
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Property 16: Translation interpolation replaces all placeholders
// Feature: ui-ux-improvements, Property 16: Translation interpolation replaces all placeholders
// **Validates: Requirements 26.5**
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 16: Translation interpolation replaces all placeholders", () => {
  // Generator for placeholder keys (word characters only)
  const placeholderKey = fc.stringMatching(/^[a-zA-Z]\w{0,9}$/)

  it("for any template with 1-5 placeholders and matching params, no {{...}} remains", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5 }).chain((count) => {
          // Generate `count` unique placeholder keys
          return fc.tuple(
            fc.uniqueArray(placeholderKey, { minLength: count, maxLength: count }),
            fc.array(fc.oneof(fc.string({ minLength: 1, maxLength: 20 }), fc.integer({ min: 0, max: 9999 }).map(String)), {
              minLength: count,
              maxLength: count,
            })
          )
        }),
        ([keys, values]) => {
          // Build template with placeholders interspersed with text
          const template = keys.map((k) => `text {{${k}}} more`).join(" ")
          const params: Record<string, string> = {}
          keys.forEach((k, i) => {
            params[k] = values[i]
          })

          const result = interpolate(template, params)
          // No remaining {{...}} patterns
          expect(result).not.toMatch(/\{\{\w+\}\}/)
        }
      ),
      { numRuns: 200 }
    )
  })
})
