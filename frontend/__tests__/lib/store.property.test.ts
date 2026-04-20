// ─────────────────────────────────────────────────────────────────────────────
// Property tests for Zustand store persistence
// Feature: ui-ux-improvements
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"

// ── Storage mocks ─────────────────────────────────────────────────────────────

function createMockStorage(): Storage {
  const store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { Object.keys(store).forEach((k) => delete store[k]) },
    get length() { return Object.keys(store).length },
    key: (index: number) => Object.keys(store)[index] ?? null,
  }
}

let mockSessionStorage: Storage
let mockLocalStorage: Storage

beforeEach(() => {
  mockSessionStorage = createMockStorage()
  mockLocalStorage = createMockStorage()

  Object.defineProperty(globalThis, "sessionStorage", { value: mockSessionStorage, writable: true, configurable: true })
  Object.defineProperty(globalThis, "localStorage", { value: mockLocalStorage, writable: true, configurable: true })

  // Mock document.cookie for setLanguage
  let cookieStore = ""
  Object.defineProperty(document, "cookie", {
    get: () => cookieStore,
    set: (v: string) => { cookieStore = v },
    configurable: true,
  })

  // Reset module cache so each test gets a fresh store
  jest.resetModules()
})

// ── Arbitraries ───────────────────────────────────────────────────────────────

const languageArb = fc.constantFrom("fr" as const, "en" as const)

const sessionMetaArb = fc.record({
  sessionId: fc.string({ minLength: 1, maxLength: 36 }),
  language: languageArb,
  createdAt: fc.date({ min: new Date("2020-01-01"), max: new Date("2030-01-01") }).filter((d) => !isNaN(d.getTime())).map((d) => d.toISOString()),
})

const dismissedAlertsArb = fc.array(
  fc.string({ minLength: 1, maxLength: 50 }),
  { minLength: 0, maxLength: 10 }
)

const userArb = fc.record({
  id: fc.string({ minLength: 1, maxLength: 36 }),
  email: fc.emailAddress(),
  roles: fc.array(fc.stringMatching(/^[a-z]{2,10}$/), { minLength: 1, maxLength: 3 }),
})

const tokenArb = fc.string({ minLength: 10, maxLength: 200 })

// ─────────────────────────────────────────────────────────────────────────────
// Property 11: Preferences persist round-trip via localStorage
// Feature: ui-ux-improvements, Property 11: Preferences persist round-trip via localStorage
// **Validates: Requirements 24.1, 25.1**
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 11: Preferences persist round-trip via localStorage", () => {
  it("for any language, SessionMeta, and dismissed alerts, set → persist → rehydrate produces identical values", () => {
    fc.assert(
      fc.property(
        languageArb,
        sessionMetaArb,
        dismissedAlertsArb,
        (language, session, dismissedAlerts) => {
          // Clear storage and module cache for a clean slate
          mockLocalStorage.clear()
          mockSessionStorage.clear()
          jest.resetModules()

          // 1. Set values in the store
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const { useAppStore: store1 } = require("@/lib/store")
          store1.getState().setLanguage(language)
          store1.getState().setSession(session)
          dismissedAlerts.forEach((d: string) => store1.getState().dismissAlert(d))

          // 2. Verify localStorage was written
          const raw = mockLocalStorage.getItem("tropicare-prefs")
          expect(raw).not.toBeNull()

          // 3. Rehydrate: create a new store instance from the same storage
          jest.resetModules()
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const { useAppStore: store2 } = require("@/lib/store")

          // Trigger rehydration by accessing persisted state
          const rehydrated = store2.getState()

          expect(rehydrated.language).toBe(language)
          expect(rehydrated.session).toEqual(session)
          // dismissAlert deduplicates, so compare with unique set
          const uniqueAlerts = [...new Set(dismissedAlerts)]
          expect(rehydrated.dismissedAlerts).toEqual(uniqueAlerts)
        }
      ),
      { numRuns: 100 }
    )
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Property 12: Auth persist round-trip via sessionStorage
// Feature: ui-ux-improvements, Property 12: Auth persist round-trip via sessionStorage
// **Validates: Requirements 24.2**
// ─────────────────────────────────────────────────────────────────────────────

describe("Property 12: Auth persist round-trip via sessionStorage", () => {
  it("for any User object and token string, set → persist → rehydrate produces identical values", () => {
    fc.assert(
      fc.property(
        userArb,
        tokenArb,
        (user, token) => {
          // Clear storage and module cache for a clean slate
          mockLocalStorage.clear()
          mockSessionStorage.clear()
          jest.resetModules()

          // 1. Set auth values
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const { useAppStore: store1 } = require("@/lib/store")
          store1.getState().setUser(user, token)

          // 2. Verify sessionStorage was written
          const raw = mockSessionStorage.getItem("tropicare-auth")
          expect(raw).not.toBeNull()

          // 3. Rehydrate from a fresh store
          jest.resetModules()
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const { useAppStore: store2 } = require("@/lib/store")

          const rehydrated = store2.getState()

          expect(rehydrated.user).toEqual(user)
          expect(rehydrated.token).toBe(token)
        }
      ),
      { numRuns: 100 }
    )
  })
})
