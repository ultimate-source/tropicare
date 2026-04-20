// ─────────────────────────────────────────────────────────────────────────────
// Property tests for ChatStream component
// Feature: ui-ux-improvements
// Property 7: ChatStream preserves all previous turns
// **Validates: Requirements 11.1**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render } from "@testing-library/react"
import "@testing-library/jest-dom"
import { ChatStream } from "@/components/chat/ChatStream"
import type { DiagnosisItem } from "@/lib/types"
import type { Turn, StreamState } from "@/hooks/useStream"

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (key === "chat.turnCount" && params?.count !== undefined) {
        return `${params.count} tour`
      }
      if (key === "citation.show" && params?.count !== undefined) {
        return `Afficher ${params.count} source`
      }
      if (key === "citation.showPlural" && params?.count !== undefined) {
        return `Afficher ${params.count} sources`
      }
      return key
    },
    locale: "fr" as const,
  }),
}))

// ── Mock useAutoScroll ────────────────────────────────────────────────────────
jest.mock("@/hooks/useAutoScroll", () => ({
  useAutoScroll: () => ({ isAtBottom: true, scrollToBottom: jest.fn() }),
}))

// ── Mock useAppStore ──────────────────────────────────────────────────────────
jest.mock("@/lib/store", () => ({
  useAppStore: (selector: (s: any) => any) => {
    const state = { dismissedAlerts: [], dismissAlert: jest.fn(), clearDismissedAlerts: jest.fn() }
    return selector(state)
  },
}))

// ── Mock child components to simplify rendering ──────────────────────────────
jest.mock("@/components/chat/EmergencyBanner", () => ({
  EmergencyBanner: () => null,
}))
jest.mock("@/components/chat/CitationDrawer", () => ({
  CitationDrawer: () => null,
}))
jest.mock("@/components/chat/FeedbackPanel", () => ({
  FeedbackPanel: () => null,
}))
jest.mock("@/components/chat/ThinkingIndicator", () => ({
  ThinkingIndicator: () => null,
}))
jest.mock("@/components/chat/TreatmentPlan", () => ({
  TreatmentPlan: () => null,
}))

// ── Mock DifferentialCard to render disease name visibly ──────────────────────
jest.mock("@/components/chat/DifferentialCard", () => ({
  DifferentialCard: ({ item }: { item: DiagnosisItem }) => (
    <div data-testid="differential-card">{item.disease_name}</div>
  ),
}))

// ── Mock useStream ────────────────────────────────────────────────────────────
const mockStreamState: { current: StreamState } = {
  current: {
    turns: [],
    currentTurn: {
      query: "",
      thinking: [],
      emergencies: [],
      differential: [],
      treatment: { first_line: [], second_line: [], alternatives: [] },
      citations: [],
      annotations: [],
      turnId: null,
      error: null,
    },
    isStreaming: false,
    lastQuery: null,
  },
}

jest.mock("@/hooks/useStream", () => ({
  useStream: () => ({
    state: mockStreamState.current,
    send: jest.fn(),
    abort: jest.fn(),
    retry: jest.fn(),
  }),
}))

// ── Generators ────────────────────────────────────────────────────────────────

const arbNonEmptyString = fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0)

const arbDiagnosisItem: fc.Arbitrary<DiagnosisItem> = fc.record({
  rank: fc.integer({ min: 1, max: 10 }),
  disease_name: arbNonEmptyString,
  icd11_code: arbNonEmptyString,
  confidence: fc.float({ min: 0, max: 1, noNaN: true }),
  supporting_evidence: fc.constant([]),
  against_evidence: fc.constant([]),
  confirmatory_tests: fc.constant([]),
  red_flags: fc.constant([]),
  citations: fc.constant([]),
})

const arbTurn: fc.Arbitrary<Turn> = fc.record({
  query: arbNonEmptyString,
  thinking: fc.constant([]),
  emergencies: fc.constant([]),
  differential: fc.array(arbDiagnosisItem, { minLength: 1, maxLength: 3 }).map(items =>
    items.map((item, i) => ({ ...item, rank: i + 1 }))
  ),
  treatment: fc.constant({ first_line: [], second_line: [], alternatives: [] }),
  citations: fc.constant([]),
  annotations: fc.constant([]),
  turnId: fc.constant("turn-id"),
  error: fc.constant(null),
})

const arbTurns = fc.array(arbTurn, { minLength: 1, maxLength: 5 })

// ── Property 7: ChatStream preserves all previous turns ───────────────────────

describe("Property 7: ChatStream preserves all previous turns", () => {
  it("renders all disease names from all turns and turn section count matches", () => {
    fc.assert(
      fc.property(arbTurns, (turns) => {
        // Set up mock state with the generated turns
        mockStreamState.current = {
          turns,
          currentTurn: {
            query: "",
            thinking: [],
            emergencies: [],
            differential: [],
            treatment: { first_line: [], second_line: [], alternatives: [] },
            citations: [],
            annotations: [],
            turnId: null,
            error: null,
          },
          isStreaming: false,
          lastQuery: null,
        }

        const { container } = render(<ChatStream sessionId="test-session" />)

        // Verify turn section count matches
        const turnSections = container.querySelectorAll("[data-turn]")
        expect(turnSections.length).toBe(turns.length)

        // Verify all disease names are rendered
        const allDiseaseNames = turns.flatMap(t => t.differential.map(d => d.disease_name))
        const renderedCards = container.querySelectorAll('[data-testid="differential-card"]')

        expect(renderedCards.length).toBe(allDiseaseNames.length)

        allDiseaseNames.forEach(name => {
          const found = Array.from(renderedCards).some(card => card.textContent === name)
          expect(found).toBe(true)
        })
      }),
      { numRuns: 100 },
    )
  })
})
