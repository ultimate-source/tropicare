/**
 * Unit tests for TreatmentPlan component
 * Validates: Requirements 21.1, 22.1, 22.2
 *
 * Tests active tab badge styling, unavailable drug tooltip, and tooltip aria-describedby.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { TreatmentPlan } from "@/components/chat/TreatmentPlan"
import type { TreatmentPlanData, DrugRegimen, Citation } from "@/lib/types"

// ── Mock useTranslation ───────────────────────────────────────────────────────
const translations: Record<string, string> = {
  "treatment.firstLine": "1ère ligne",
  "treatment.secondLine": "2ème ligne",
  "treatment.alternatives": "Alternatives",
  "treatment.showAriaLabel": "Afficher les traitements",
  "treatment.dose": "Dose",
  "treatment.route": "Voie",
  "treatment.frequency": "Fréquence",
  "treatment.duration": "Durée",
  "treatment.durationDay": "{{days}} jour",
  "treatment.durationDays": "{{days}} jours",
  "treatment.cameAvailable": "CAME ✓",
  "treatment.cameUnavailable": "CAME ✗",
  "treatment.pregnancy": "Grossesse",
  "treatment.interactions": "Interactions",
  "treatment.monitoring": "Surveillance",
  "treatment.contraindicated": "Contre-indiqués",
  "treatment.noRegimens": "Aucun traitement dans cette ligne",
  "treatment.cameTooltip": "Non disponible dans le formulaire CAME",
}

jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      let val = translations[key] ?? key
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          val = val.replace(`{{${k}}}`, String(v))
        })
      }
      return val
    },
    locale: "fr" as const,
  }),
}))

// ── Helpers ───────────────────────────────────────────────────────────────────
function makeDrug(overrides: Partial<DrugRegimen> = {}): DrugRegimen {
  return {
    drug_name: "Artémether-Luméfantrine",
    generic_name: "AL",
    came_available: true,
    dose: "80/480mg",
    route: "PO",
    frequency: "2x/jour",
    duration_days: 3,
    pregnancy_class: null,
    ddi_warnings: [],
    amr_note: null,
    monitoring: [],
    citations: [],
    ...overrides,
  }
}

function makePlan(overrides: Partial<TreatmentPlanData> = {}): TreatmentPlanData {
  return {
    target_disease: "Paludisme",
    clinical_rationale: "Traitement de première intention",
    first_line: [makeDrug()],
    second_line: [makeDrug({ drug_name: "Quinine", generic_name: "Quinine sulfate" })],
    alternatives: [],
    contraindicated: [],
    supportive_care: [],
    follow_up_guidance: "",
    referral_criteria: "",
    disclaimer: "",
    ...overrides,
  }
}

const emptyCitations: Citation[] = []

describe("TreatmentPlan", () => {
  describe("Requirement 21.1: Active tab count badge uses high-contrast style", () => {
    it("active tab badge has bg-blue-600 text-white classes", () => {
      const plan = makePlan()
      const { container } = render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      // First tab is active by default
      const tabs = container.querySelectorAll("button")
      const activeTab = tabs[0]
      const badge = activeTab.querySelector("span")

      expect(badge).toBeInTheDocument()
      expect(badge).toHaveClass("bg-blue-600")
      expect(badge).toHaveClass("text-white")
    })

    it("inactive tab badge has bg-muted class (not bg-blue-600)", () => {
      const plan = makePlan()
      const { container } = render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      // Second tab is inactive
      const tabs = container.querySelectorAll("button")
      const inactiveTab = tabs[1]
      const badge = inactiveTab.querySelector("span")

      expect(badge).toBeInTheDocument()
      expect(badge).toHaveClass("bg-muted")
      expect(badge).not.toHaveClass("bg-blue-600")
      expect(badge).not.toHaveClass("text-white")
    })

    it("badge style switches when tab changes", () => {
      const plan = makePlan()
      const { container } = render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      const tabs = container.querySelectorAll("button")

      // Click second tab
      fireEvent.click(tabs[1])

      // Now second tab badge should be active style
      const secondBadge = tabs[1].querySelector("span")
      expect(secondBadge).toHaveClass("bg-blue-600")
      expect(secondBadge).toHaveClass("text-white")

      // First tab badge should be muted
      const firstBadge = tabs[0].querySelector("span")
      expect(firstBadge).toHaveClass("bg-muted")
      expect(firstBadge).not.toHaveClass("bg-blue-600")
    })
  })

  describe("Requirement 22.1: Unavailable drug tooltip displays CAME message", () => {
    it("shows tooltip text for drug with came_available=false", () => {
      const plan = makePlan({
        first_line: [makeDrug({ came_available: false })],
      })
      render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      // The tooltip text should be in the DOM (visually hidden until hover/focus)
      expect(
        screen.getByText("Non disponible dans le formulaire CAME")
      ).toBeInTheDocument()
    })

    it("does not show tooltip for drug with came_available=true", () => {
      const plan = makePlan({
        first_line: [makeDrug({ came_available: true })],
      })
      render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      expect(
        screen.queryByText("Non disponible dans le formulaire CAME")
      ).not.toBeInTheDocument()
    })

    it("tooltip element has role=tooltip", () => {
      const plan = makePlan({
        first_line: [makeDrug({ came_available: false })],
      })
      render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      const tooltip = screen.getByRole("tooltip")
      expect(tooltip).toHaveTextContent("Non disponible dans le formulaire CAME")
    })
  })

  describe("Requirement 22.2: Tooltip accessible via keyboard with aria-describedby", () => {
    it("CAME ✗ badge has aria-describedby referencing tooltip id", () => {
      const plan = makePlan({
        first_line: [makeDrug({ came_available: false })],
      })
      render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      const badge = screen.getByText("CAME ✗")
      const describedBy = badge.getAttribute("aria-describedby")

      expect(describedBy).toBeTruthy()
      // The referenced element should exist and contain the tooltip text
      const tooltipEl = document.getElementById(describedBy!)
      expect(tooltipEl).toBeInTheDocument()
      expect(tooltipEl).toHaveTextContent("Non disponible dans le formulaire CAME")
    })

    it("CAME ✗ badge is focusable (has tabIndex=0)", () => {
      const plan = makePlan({
        first_line: [makeDrug({ came_available: false })],
      })
      render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      const badge = screen.getByText("CAME ✗")
      expect(badge).toHaveAttribute("tabindex", "0")
    })

    it("tooltip id matches aria-describedby value", () => {
      const plan = makePlan({
        first_line: [
          makeDrug({ drug_name: "Drug A", came_available: false }),
          makeDrug({ drug_name: "Drug B", came_available: false }),
        ],
      })
      render(<TreatmentPlan plan={plan} citations={emptyCitations} />)

      const badges = screen.getAllByText("CAME ✗")
      badges.forEach((badge) => {
        const describedBy = badge.getAttribute("aria-describedby")
        expect(describedBy).toBeTruthy()
        const tooltip = document.getElementById(describedBy!)
        expect(tooltip).toBeInTheDocument()
        expect(tooltip).toHaveAttribute("role", "tooltip")
      })
    })
  })
})
