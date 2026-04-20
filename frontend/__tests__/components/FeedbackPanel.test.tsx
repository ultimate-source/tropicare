/**
 * Unit tests for FeedbackPanel component
 * Validates: Requirements 15.1, 15.2
 *
 * Tests that FeedbackPanel uses api.feedback.submit and handles errors with retry.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import { FeedbackPanel } from "@/components/chat/FeedbackPanel"

// ── Mock useTranslation ───────────────────────────────────────────────────────
const translations: Record<string, string> = {
  "feedback.question": "Ce diagnostic était-il correct ?",
  "feedback.correct": "Correcte",
  "feedback.partial": "Partielle",
  "feedback.incorrect": "Incorrecte",
  "feedback.correctAriaLabel": "Marquer comme correcte",
  "feedback.partialAriaLabel": "Marquer comme partielle",
  "feedback.incorrectAriaLabel": "Marquer comme incorrecte",
  "feedback.placeholder": "Notes optionnelles…",
  "feedback.submit": "Envoyer",
  "feedback.submitAriaLabel": "Envoyer le feedback",
  "feedback.success": "Merci pour votre retour !",
  "error.feedbackSubmit": "Erreur lors de l'envoi du feedback",
  "error.network": "Erreur réseau",
  "error.networkDescription": "Impossible de contacter le serveur",
  "error.server": "Erreur serveur",
  "error.serverDescription": "Le serveur a rencontré une erreur",
  "error.authentication": "Erreur d'authentification",
  "error.authenticationDescription": "Veuillez vous reconnecter",
  "error.retry": "Réessayer",
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

// ── Mock api.feedback.submit ──────────────────────────────────────────────────
const mockSubmit = jest.fn()

jest.mock("@/lib/api", () => ({
  api: {
    feedback: {
      submit: (...args: unknown[]) => mockSubmit(...args),
    },
  },
}))

// ── Mock categorizeError (used by ApiErrorBanner) ─────────────────────────────
jest.mock("@/lib/errors", () => ({
  categorizeError: (status: number) => {
    if (status === 401 || status === 403) return "authentication"
    if (status === 0) return "network"
    return "server"
  },
}))

describe("FeedbackPanel", () => {
  beforeEach(() => {
    mockSubmit.mockReset()
  })

  describe("Requirement 15.1: Uses api.feedback.submit", () => {
    it("calls api.feedback.submit with correct payload when submitting", async () => {
      mockSubmit.mockResolvedValue(undefined)
      render(<FeedbackPanel turnId="turn-123" />)

      // Select a verdict
      fireEvent.click(screen.getByText("Correcte"))
      // Click submit
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledTimes(1)
        expect(mockSubmit).toHaveBeenCalledWith({
          turn_id: "turn-123",
          verdict: "correct",
          clinician_note: undefined,
        })
      })
    })

    it("includes clinician_note when provided for non-correct verdicts", async () => {
      mockSubmit.mockResolvedValue(undefined)
      render(<FeedbackPanel turnId="turn-456" />)

      // Select "partial" verdict
      fireEvent.click(screen.getByText("Partielle"))
      // Type a note
      const textarea = screen.getByPlaceholderText("Notes optionnelles…")
      fireEvent.change(textarea, { target: { value: "Missing dengue" } })
      // Submit
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith({
          turn_id: "turn-456",
          verdict: "partial",
          clinician_note: "Missing dengue",
        })
      })
    })

    it("shows success message after successful submission", async () => {
      mockSubmit.mockResolvedValue(undefined)
      render(<FeedbackPanel turnId="turn-789" />)

      fireEvent.click(screen.getByText("Correcte"))
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      await waitFor(() => {
        expect(screen.getByText("Merci pour votre retour !")).toBeInTheDocument()
      })
    })
  })

  describe("Requirement 15.2: Error display with retry", () => {
    it("displays error message when submission fails", async () => {
      mockSubmit.mockRejectedValue(new Error("500 Internal Server Error"))
      render(<FeedbackPanel turnId="turn-err" />)

      fireEvent.click(screen.getByText("Incorrecte"))
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument()
      })
    })

    it("shows retry button when submission fails", async () => {
      mockSubmit.mockRejectedValue(new Error("500 Internal Server Error"))
      render(<FeedbackPanel turnId="turn-err" />)

      fireEvent.click(screen.getByText("Correcte"))
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      await waitFor(() => {
        expect(screen.getByText("Réessayer")).toBeInTheDocument()
      })
    })

    it("retries submission when retry button is clicked", async () => {
      mockSubmit
        .mockRejectedValueOnce(new Error("500 Internal Server Error"))
        .mockResolvedValueOnce(undefined)

      render(<FeedbackPanel turnId="turn-retry" />)

      fireEvent.click(screen.getByText("Correcte"))
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      // Wait for error to appear
      await waitFor(() => {
        expect(screen.getByText("Réessayer")).toBeInTheDocument()
      })

      // Click retry
      fireEvent.click(screen.getByText("Réessayer"))

      // Should call submit again
      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledTimes(2)
      })

      // Should show success after retry succeeds
      await waitFor(() => {
        expect(screen.getByText("Merci pour votre retour !")).toBeInTheDocument()
      })
    })

    it("does not show success message while error is displayed", async () => {
      mockSubmit.mockRejectedValue(new Error("Network error"))
      render(<FeedbackPanel turnId="turn-no-success" />)

      fireEvent.click(screen.getByText("Correcte"))
      fireEvent.click(screen.getByRole("button", { name: /envoyer le feedback/i }))

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument()
      })

      expect(screen.queryByText("Merci pour votre retour !")).not.toBeInTheDocument()
    })
  })

  describe("General behavior", () => {
    it("does not submit when no verdict is selected", () => {
      render(<FeedbackPanel turnId="turn-no-verdict" />)

      // Submit button should not be visible without a verdict
      expect(screen.queryByRole("button", { name: /envoyer le feedback/i })).not.toBeInTheDocument()
    })

    it("shows textarea only for non-correct verdicts", () => {
      render(<FeedbackPanel turnId="turn-textarea" />)

      // No textarea initially
      expect(screen.queryByPlaceholderText("Notes optionnelles…")).not.toBeInTheDocument()

      // Select "correct" — no textarea
      fireEvent.click(screen.getByText("Correcte"))
      expect(screen.queryByPlaceholderText("Notes optionnelles…")).not.toBeInTheDocument()

      // Select "incorrect" — textarea appears
      fireEvent.click(screen.getByText("Incorrecte"))
      expect(screen.getByPlaceholderText("Notes optionnelles…")).toBeInTheDocument()
    })
  })
})
