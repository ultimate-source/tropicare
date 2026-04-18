/**
 * Component tests for ChatStream
 * Validates: Requirements 17.2
 *
 * Tests that streaming events render differential cards,
 * treatment plans, and emergency banners.
 */
import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { ChatStream } from "@/components/chat/ChatStream"
import type { StreamState } from "@/hooks/useStream"
import type { DiagnosisItem, EmergencyFlag, DrugRegimen, Citation } from "@/lib/types"

// ── Mock useStream hook ──────────────────────────────────────────────────────

let mockState: StreamState

const mockSend = jest.fn()
const mockAbort = jest.fn()

jest.mock("@/hooks/useStream", () => ({
  useStream: () => ({
    state: mockState,
    send: mockSend,
    abort: mockAbort,
  }),
}))

// ── Test data factories ──────────────────────────────────────────────────────

function makeEmptyState(): StreamState {
  return {
    thinking: [],
    emergencies: [],
    differential: [],
    treatment: { first_line: [], second_line: [], alternatives: [] },
    citations: [],
    annotations: [],
    turnId: null,
    isStreaming: false,
    error: null,
  }
}

function makeDiagnosisItem(overrides: Partial<DiagnosisItem> = {}): DiagnosisItem {
  return {
    rank: 1,
    disease_name: "Paludisme à P. falciparum",
    icd11_code: "1F40",
    confidence: 0.85,
    supporting_evidence: ["Fièvre élevée", "Zone endémique"],
    against_evidence: [],
    confirmatory_tests: [],
    red_flags: [],
    citations: [],
    ...overrides,
  }
}

function makeEmergencyFlag(overrides: Partial<EmergencyFlag> = {}): EmergencyFlag {
  return {
    disease: "Paludisme grave",
    level: "critical",
    action: "Transfert immédiat en réanimation",
    ...overrides,
  }
}

function makeDrugRegimen(overrides: Partial<DrugRegimen> = {}): DrugRegimen {
  return {
    drug_name: "Artésunate",
    generic_name: "Artesunate",
    came_available: true,
    dose: "2.4 mg/kg",
    route: "IV",
    frequency: "H0, H12, H24 puis /24h",
    duration_days: 7,
    pregnancy_class: null,
    ddi_warnings: [],
    amr_note: null,
    monitoring: [],
    citations: [],
    ...overrides,
  }
}

// ── Tests ────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockState = makeEmptyState()
  mockSend.mockClear()
  mockAbort.mockClear()
})

describe("ChatStream — streaming event rendering", () => {
  it("renders differential cards when differential items are present", () => {
    mockState = {
      ...makeEmptyState(),
      differential: [
        makeDiagnosisItem({ rank: 1, disease_name: "Paludisme à P. falciparum", confidence: 0.85 }),
        makeDiagnosisItem({ rank: 2, disease_name: "Fièvre typhoïde", icd11_code: "1A07", confidence: 0.6 }),
      ],
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.getByText("Diagnostic différentiel")).toBeInTheDocument()
    expect(screen.getByText("Paludisme à P. falciparum")).toBeInTheDocument()
    expect(screen.getByText("Fièvre typhoïde")).toBeInTheDocument()
  })

  it("renders treatment plan section when treatment data is present", () => {
    mockState = {
      ...makeEmptyState(),
      treatment: {
        first_line: [makeDrugRegimen()],
        second_line: [],
        alternatives: [],
      },
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.getByText("Plan thérapeutique")).toBeInTheDocument()
    expect(screen.getByText("Artésunate")).toBeInTheDocument()
  })

  it("renders emergency banners when emergency flags are present", () => {
    mockState = {
      ...makeEmptyState(),
      emergencies: [
        makeEmergencyFlag({ disease: "Paludisme grave", level: "critical" }),
      ],
    }

    render(<ChatStream sessionId="test-session" />)

    const alert = screen.getByRole("alert")
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveTextContent("URGENCE VITALE")
    expect(alert).toHaveTextContent("Paludisme grave")
  })

  it("renders multiple emergency banners for multiple flags", () => {
    mockState = {
      ...makeEmptyState(),
      emergencies: [
        makeEmergencyFlag({ disease: "Paludisme grave", level: "critical" }),
        makeEmergencyFlag({ disease: "Méningite", level: "urgent", action: "Antibiothérapie empirique" }),
      ],
    }

    render(<ChatStream sessionId="test-session" />)

    const alerts = screen.getAllByRole("alert")
    expect(alerts).toHaveLength(2)
    expect(screen.getByText(/Paludisme grave/)).toBeInTheDocument()
    expect(screen.getByText(/Méningite/)).toBeInTheDocument()
  })

  it("renders all event types together (differential + treatment + emergency)", () => {
    mockState = {
      ...makeEmptyState(),
      emergencies: [makeEmergencyFlag()],
      differential: [makeDiagnosisItem()],
      treatment: {
        first_line: [makeDrugRegimen()],
        second_line: [],
        alternatives: [],
      },
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByText("Diagnostic différentiel")).toBeInTheDocument()
    expect(screen.getByText("Plan thérapeutique")).toBeInTheDocument()
  })

  it("does not render differential section when no items present", () => {
    mockState = makeEmptyState()

    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByText("Diagnostic différentiel")).not.toBeInTheDocument()
  })

  it("does not render treatment section when no treatment data present", () => {
    mockState = makeEmptyState()

    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByText("Plan thérapeutique")).not.toBeInTheDocument()
  })
})
