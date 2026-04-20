/**
 * Component tests for EmergencyBanner
 * Validates: Requirements 17.3
 *
 * Tests that emergency flags display with urgent visual styling.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { EmergencyBanner } from "@/components/chat/EmergencyBanner"
import type { EmergencyFlag } from "@/lib/types"

// ── Mock useTranslation ───────────────────────────────────────────────────────
const translations: Record<string, string> = {
  "emergency.critical": "URGENCE VITALE",
  "emergency.urgent": "URGENCE",
  "emergency.closeAriaLabel": "Fermer l'alerte",
  "emergency.dismiss": "Pris en compte",
}

jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => translations[key] ?? key,
    locale: "fr" as const,
  }),
}))

function renderBanner(
  flag: EmergencyFlag,
  onDismiss = jest.fn(),
) {
  return {
    onDismiss,
    ...render(<EmergencyBanner flag={flag} onDismiss={onDismiss} />),
  }
}

describe("EmergencyBanner — emergency flag display", () => {
  it("renders critical emergency with URGENCE VITALE label", () => {
    renderBanner({
      disease: "Paludisme grave",
      level: "critical",
      action: "Transfert immédiat en réanimation",
    })

    const alert = screen.getByRole("alert")
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveTextContent("URGENCE VITALE")
    expect(alert).toHaveTextContent("Paludisme grave")
    expect(alert).toHaveTextContent("Transfert immédiat en réanimation")
  })

  it("renders urgent emergency with URGENCE label (not VITALE)", () => {
    renderBanner({
      disease: "Méningite",
      level: "urgent",
      action: "Antibiothérapie empirique immédiate",
    })

    const alert = screen.getByRole("alert")
    expect(alert).toHaveTextContent("URGENCE")
    expect(alert).not.toHaveTextContent("URGENCE VITALE")
    expect(alert).toHaveTextContent("Méningite")
    expect(alert).toHaveTextContent("Antibiothérapie empirique immédiate")
  })

  it("applies urgent visual styling with red border and background", () => {
    renderBanner({
      disease: "Sepsis",
      level: "critical",
      action: "Réanimation urgente",
    })

    const alert = screen.getByRole("alert")
    expect(alert.className).toMatch(/border-red/)
    expect(alert.className).toMatch(/bg-red/)
  })

  it("displays the 🚨 emergency icon", () => {
    renderBanner({
      disease: "Fièvre hémorragique",
      level: "critical",
      action: "Isolement immédiat",
    })

    const alert = screen.getByRole("alert")
    expect(alert).toHaveTextContent("🚨")
  })

  it("calls onDismiss when dismiss button is clicked", () => {
    const { onDismiss } = renderBanner({
      disease: "Paludisme grave",
      level: "critical",
      action: "Transfert immédiat",
    })

    const dismissBtn = screen.getByRole("button", { name: /fermer l'alerte/i })
    fireEvent.click(dismissBtn)

    expect(onDismiss).toHaveBeenCalledTimes(1)
  })
})
