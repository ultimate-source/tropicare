/**
 * Component tests for ChatStream
 * Validates: Requirements 17.2
 *
 * Tests that streaming events render differential cards,
 * treatment plans, and emergency banners.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { ChatStream } from "@/components/chat/ChatStream"
import type { StreamState, Turn } from "@/hooks/useStream"
import type { DiagnosisItem, EmergencyFlag, DrugRegimen, Citation } from "@/lib/types"

// ── Mock useStream hook ──────────────────────────────────────────────────────

let mockState: StreamState

const mockSend = jest.fn()
const mockAbort = jest.fn()
const mockRetry = jest.fn()

jest.mock("@/hooks/useStream", () => ({
  useStream: () => ({
    state: mockState,
    send: mockSend,
    abort: mockAbort,
    retry: mockRetry,
  }),
}))

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (key === "emergency.dismissAnnouncement" && params?.disease) {
        return `Alerte ${params.disease} prise en compte`
      }
      if (key === "chat.turnCount" && params?.count !== undefined) {
        return `Tour ${params.count}`
      }
      if (key === "citation.show" && params?.count !== undefined) {
        return `Afficher ${params.count} source`
      }
      if (key === "citation.showPlural" && params?.count !== undefined) {
        return `Afficher ${params.count} sources`
      }
      const map: Record<string, string> = {
        "emergency.critical": "URGENCE VITALE",
        "emergency.urgent": "URGENCE",
        "emergency.closeAriaLabel": "Fermer l'alerte",
        "emergency.dismiss": "Pris en compte",
        "chat.differential": "Diagnostic différentiel",
        "chat.treatmentPlan": "Plan thérapeutique",
        "chat.placeholder": "Décrivez le tableau clinique ou posez une question…",
        "chat.send": "Envoyer",
        "chat.stop": "Arrêter",
        "chat.inputAriaLabel": "Saisir le tableau clinique ou une question",
        "chat.sendAriaLabel": "Envoyer la question",
        "chat.stopAriaLabel": "Arrêter la génération",
        "chat.submitHint": "Ctrl+Entrée pour envoyer",
        "chat.sending": "Envoi en cours…",
        "chat.scrollToBottom": "Défiler vers le bas",
        "chat.validationWarnings": "⚠ Avertissements de validation",
        "chat.errorPrefix": "Erreur : ",
        "error.retry": "Réessayer",
      }
      return map[key] ?? key
    },
    locale: "fr" as const,
  }),
}))

// ── Mock useAutoScroll ────────────────────────────────────────────────────────
let mockIsAtBottom = true
const mockScrollToBottom = jest.fn()
jest.mock("@/hooks/useAutoScroll", () => ({
  useAutoScroll: () => ({ isAtBottom: mockIsAtBottom, scrollToBottom: mockScrollToBottom }),
}))

// ── Mock useAppStore ──────────────────────────────────────────────────────────
const mockDismissAlert = jest.fn()
jest.mock("@/lib/store", () => ({
  useAppStore: (selector?: (s: any) => any) => {
    const state = {
      dismissedAlerts: [] as string[],
      dismissAlert: mockDismissAlert,
    }
    return selector ? selector(state) : state
  },
}))

// ── Test data factories ──────────────────────────────────────────────────────

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

function makeEmptyState(): StreamState {
  return {
    turns: [],
    currentTurn: makeEmptyTurn(),
    isStreaming: false,
    lastQuery: null,
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
  mockIsAtBottom = true
  mockSend.mockClear()
  mockAbort.mockClear()
  mockRetry.mockClear()
  mockDismissAlert.mockClear()
  mockScrollToBottom.mockClear()
})

describe("ChatStream — streaming event rendering", () => {
  it("renders differential cards when differential items are present", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: {
        ...makeEmptyTurn(),
        differential: [
          makeDiagnosisItem({ rank: 1, disease_name: "Paludisme à P. falciparum", confidence: 0.85 }),
          makeDiagnosisItem({ rank: 2, disease_name: "Fièvre typhoïde", icd11_code: "1A07", confidence: 0.6 }),
        ],
      },
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.getByText("Diagnostic différentiel")).toBeInTheDocument()
    expect(screen.getByText("Paludisme à P. falciparum")).toBeInTheDocument()
    expect(screen.getByText("Fièvre typhoïde")).toBeInTheDocument()
  })

  it("renders treatment plan section when treatment data is present", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: {
        ...makeEmptyTurn(),
        treatment: {
          first_line: [makeDrugRegimen()],
          second_line: [],
          alternatives: [],
        },
      },
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.getByText("Plan thérapeutique")).toBeInTheDocument()
    expect(screen.getByText("Artésunate")).toBeInTheDocument()
  })

  it("renders emergency banners when emergency flags are present", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: {
        ...makeEmptyTurn(),
        emergencies: [
          makeEmergencyFlag({ disease: "Paludisme grave", level: "critical" }),
        ],
      },
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
      currentTurn: {
        ...makeEmptyTurn(),
        emergencies: [
          makeEmergencyFlag({ disease: "Paludisme grave", level: "critical" }),
          makeEmergencyFlag({ disease: "Méningite", level: "urgent", action: "Antibiothérapie empirique" }),
        ],
      },
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
      currentTurn: {
        ...makeEmptyTurn(),
        emergencies: [makeEmergencyFlag()],
        differential: [makeDiagnosisItem()],
        treatment: {
          first_line: [makeDrugRegimen()],
          second_line: [],
          alternatives: [],
        },
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

// ── Tests for Requirement 12: Textarea Submit Behavior ───────────────────────

describe("ChatStream — textarea submit behavior", () => {
  it("Enter key inserts a newline and does NOT submit (Req 12.1)", () => {
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    const textarea = screen.getByRole("textbox")
    fireEvent.change(textarea, { target: { value: "line1" } })
    fireEvent.keyDown(textarea, { key: "Enter" })

    // send should NOT have been called
    expect(mockSend).not.toHaveBeenCalled()
  })

  it("Ctrl+Enter submits the form (Req 12.2)", () => {
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    const textarea = screen.getByRole("textbox")
    fireEvent.change(textarea, { target: { value: "my query" } })
    fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true })

    expect(mockSend).toHaveBeenCalledWith("my query")
  })

  it("Cmd+Enter (metaKey) submits the form on Mac (Req 12.2)", () => {
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    const textarea = screen.getByRole("textbox")
    fireEvent.change(textarea, { target: { value: "mac query" } })
    fireEvent.keyDown(textarea, { key: "Enter", metaKey: true })

    expect(mockSend).toHaveBeenCalledWith("mac query")
  })

  it("Ctrl+Enter does not submit when textarea is empty", () => {
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    const textarea = screen.getByRole("textbox")
    fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true })

    expect(mockSend).not.toHaveBeenCalled()
  })

  it("displays the submit shortcut hint text (Req 12.3)", () => {
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    expect(screen.getByText("Ctrl+Entrée pour envoyer")).toBeInTheDocument()
  })
})

// ── Tests for Requirement 13: Auto-Scroll and Scroll-to-Bottom ───────────────

describe("ChatStream — auto-scroll and scroll-to-bottom button", () => {
  it("does NOT show scroll-to-bottom button when at bottom (Req 13.1)", () => {
    mockIsAtBottom = true
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByLabelText("Défiler vers le bas")).not.toBeInTheDocument()
  })

  it("shows scroll-to-bottom button when user has scrolled up (Req 13.2)", () => {
    mockIsAtBottom = false
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    const btn = screen.getByLabelText("Défiler vers le bas")
    expect(btn).toBeInTheDocument()
  })

  it("clicking scroll-to-bottom button calls scrollToBottom (Req 13.3)", () => {
    mockIsAtBottom = false
    mockState = makeEmptyState()
    render(<ChatStream sessionId="test-session" />)

    const btn = screen.getByLabelText("Défiler vers le bas")
    fireEvent.click(btn)

    expect(mockScrollToBottom).toHaveBeenCalled()
  })
})

// ── Tests for Requirement 23: Loading State Transitions ──────────────────────

describe("ChatStream — loading state transitions", () => {
  it("shows loading indicator when streaming but no content yet (Req 23.1)", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: makeEmptyTurn(),
      isStreaming: true,
      lastQuery: "test query",
    }

    render(<ChatStream sessionId="test-session" />)

    const loading = screen.getByTestId("loading-sending")
    expect(loading).toBeInTheDocument()
    expect(loading).toHaveTextContent("Envoi en cours…")
  })

  it("does NOT show loading indicator when streaming has content (thinking lines)", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: {
        ...makeEmptyTurn(),
        thinking: ["Analyzing symptoms..."],
      },
      isStreaming: true,
      lastQuery: "test query",
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByTestId("loading-sending")).not.toBeInTheDocument()
  })

  it("does NOT show loading indicator when streaming has differential items", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: {
        ...makeEmptyTurn(),
        differential: [makeDiagnosisItem()],
      },
      isStreaming: true,
      lastQuery: "test query",
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByTestId("loading-sending")).not.toBeInTheDocument()
  })

  it("does NOT show loading indicator when not streaming", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: makeEmptyTurn(),
      isStreaming: false,
      lastQuery: null,
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByTestId("loading-sending")).not.toBeInTheDocument()
  })

  it("does NOT show loading indicator when streaming has emergency flags", () => {
    mockState = {
      ...makeEmptyState(),
      currentTurn: {
        ...makeEmptyTurn(),
        emergencies: [makeEmergencyFlag()],
      },
      isStreaming: true,
      lastQuery: "test query",
    }

    render(<ChatStream sessionId="test-session" />)

    expect(screen.queryByTestId("loading-sending")).not.toBeInTheDocument()
  })
})
