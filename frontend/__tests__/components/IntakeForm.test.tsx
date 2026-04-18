/**
 * Component tests for IntakeForm
 * Validates: Requirements 17.1
 *
 * Tests that mandatory field validation rejects submissions
 * missing age, sex, region, or chief complaint.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import "@testing-library/jest-dom"
import { IntakeForm } from "@/components/intake/IntakeForm"

function renderForm(onComplete = jest.fn()) {
  return {
    onComplete,
    ...render(<IntakeForm onComplete={onComplete} language="fr" />),
  }
}

function getSubmitButton() {
  return screen.getByRole("button", { name: /démarrer la consultation/i })
}

async function fillField(label: string, value: string) {
  const el = screen.getByLabelText(new RegExp(label, "i"))
  await userEvent.clear(el)
  await userEvent.type(el, value)
}

async function selectField(label: string, value: string) {
  const el = screen.getByLabelText(new RegExp(label, "i"))
  await userEvent.selectOptions(el, value)
}

describe("IntakeForm — mandatory field validation", () => {
  it("rejects submission when all mandatory fields are empty", async () => {
    const { onComplete } = renderForm()

    fireEvent.click(getSubmitButton())

    expect(screen.getByText(/âge invalide/i)).toBeInTheDocument()
    expect(screen.getByText(/sexe requis/i)).toBeInTheDocument()
    expect(screen.getByText(/région requise/i)).toBeInTheDocument()
    expect(screen.getByText(/motif de consultation requis/i)).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("rejects submission when age is missing", async () => {
    const { onComplete } = renderForm()

    await selectField("sexe", "M")
    await selectField("région", "Maritime")
    await fillField("motif de consultation", "Fièvre depuis 3 jours")

    fireEvent.click(getSubmitButton())

    expect(screen.getByText(/âge invalide/i)).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("rejects submission when sex is missing", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "32")
    await selectField("région", "Maritime")
    await fillField("motif de consultation", "Fièvre depuis 3 jours")

    fireEvent.click(getSubmitButton())

    expect(screen.getByText(/sexe requis/i)).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("rejects submission when region is missing", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "32")
    await selectField("sexe", "M")
    await fillField("motif de consultation", "Fièvre depuis 3 jours")

    fireEvent.click(getSubmitButton())

    expect(screen.getByText(/région requise/i)).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("rejects submission when chief complaint is missing", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "32")
    await selectField("sexe", "M")
    await selectField("région", "Maritime")

    fireEvent.click(getSubmitButton())

    expect(screen.getByText(/motif de consultation requis/i)).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("accepts submission when all mandatory fields are filled", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "32")
    await selectField("sexe", "M")
    await selectField("région", "Maritime")
    await fillField("motif de consultation", "Fièvre depuis 3 jours")

    fireEvent.click(getSubmitButton())

    expect(screen.queryByText(/âge invalide/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sexe requis/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/région requise/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/motif de consultation requis/i)).not.toBeInTheDocument()
    expect(onComplete).toHaveBeenCalledTimes(1)

    const ctx = onComplete.mock.calls[0][0]
    expect(ctx.age_years).toBe(32)
    expect(ctx.sex).toBe("M")
    expect(ctx.region).toBe("Maritime")
    expect(ctx.chief_complaint).toBe("Fièvre depuis 3 jours")
  })
})
