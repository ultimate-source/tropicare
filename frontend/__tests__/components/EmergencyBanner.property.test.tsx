// ─────────────────────────────────────────────────────────────────────────────
// Property tests for EmergencyBanner dismissal announcement
// Feature: ui-ux-improvements
// Property 4: Emergency dismissal announcement contains disease name
// **Validates: Requirements 4.1, 4.2**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { ChatStream } from "@/components/chat/ChatStream"
import type { StreamState, Turn } from "@/hooks/useStream"
import type { EmergencyFlag } from "@/lib/types"

// ── Mock useStream hook ──────────────────────────────────────────────────────

let mockState: StreamState

jest.mock("@/hooks/useStream", () => ({
  useStream: () => ({
    state: mockState,
    send: jest.fn(),
    abort: jest.fn(),
    retry: jest.fn(),
  }),
}))

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (key === "emergency.dismissAnnouncement" && params?.disease) {
        return `Alerte ${params.disease} prise en compte`
      }
      const map: Record<string, string> = {
        "emergency.critical": "URGENCE VITALE",
        "emergency.urgent": "URGENCE",
        "emergency.closeAriaLabel": "Fermer l'alerte",
        "emergency.dismiss": "Pris en compte",
      }
      return map[key] ?? key
    },
    locale: "fr" as const,
  }),
}))

// ── Mock useAppStore ──────────────────────────────────────────────────────────
const mockDismissAlert = jest.fn()
let mockDismissedAlerts: string[] = []

jest.mock("@/lib/store", () => ({
  useAppStore: (selector?: (s: any) => any) => {
    const state = {
      dismissedAlerts: mockDismissedAlerts,
      dismissAlert: mockDismissAlert,
    }
    return selector ? selector(state) : state
  },
}))

// ── Generators ────────────────────────────────────────────────────────────────

const arbNonEmptyString = fc
  .string({ minLength: 1, maxLength: 40 })
  .filter((s) => s.trim().length > 0)

const arbEmergencyLevel = fc.constantFrom<"critical" | "urgent">("critical", "urgent")

const arbEmergencyFlag: fc.Arbitrary<EmergencyFlag> = fc.record({
  disease: arbNonEmptyString,
  level: arbEmergencyLevel,
  action: arbNonEmptyString,
})

function makeEmptyTurn(): Turn {
  return {
    query: "",
    thinking: [],
    emergencies: [],
    differential: [],
    treatment: { first_line: [], second_line: [], alternatives: [] },
    citations: [],
    annotations: [],
    turnId: null,
    error: null,
  }
}

// ── Property 4: Emergency dismissal announcement contains disease name ────────

describe("Property 4: Emergency dismissal announcement contains disease name", () => {
  beforeEach(() => {
    mockDismissAlert.mockClear()
    mockDismissedAlerts = []
  })

  it("dismissing any EmergencyFlag causes the aria-live region to contain the disease name", () => {
    fc.assert(
      fc.property(arbEmergencyFlag, (flag) => {
        mockDismissedAlerts = []

        mockState = {
          turns: [],
          currentTurn: {
            ...makeEmptyTurn(),
            emergencies: [flag],
          },
          isStreaming: false,
          lastQuery: null,
        }

        const { unmount } = render(<ChatStream sessionId="test-session" />)

        // Find and click the dismiss button
        const dismissBtn = screen.getByRole("button", { name: /fermer l'alerte/i })
        fireEvent.click(dismissBtn)

        // Verify the aria-live region contains the disease name
        const liveRegion = screen.getByTestId("dismiss-live-region")
        expect(liveRegion).toHaveAttribute("aria-live", "polite")
        expect(liveRegion.textContent).toContain(flag.disease)

        // Verify dismissAlert was called with the disease name
        expect(mockDismissAlert).toHaveBeenCalledWith(flag.disease)

        unmount()
      }),
      { numRuns: 100 },
    )
  })
})
