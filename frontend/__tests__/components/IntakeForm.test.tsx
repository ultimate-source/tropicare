/**
 * Component tests for IntakeForm
 * Validates: Requirements 6.1–6.5, 9.1, 9.3, 27.1
 *
 * Tests that mandatory field validation rejects submissions
 * missing age, sex, region, or chief complaint.
 * Tests inline validation on blur and summary preview modal flow.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import "@testing-library/jest-dom"
import { IntakeForm } from "@/components/intake/IntakeForm"

// ── Mock useTranslation ───────────────────────────────────────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const dict: Record<string, string> = {
        "intake.title": "Données patient",
        "intake.age": "Âge (ans)",
        "intake.sex": "Sexe",
        "intake.weight": "Poids (kg)",
        "intake.region": "Région (Togo)",
        "intake.onset": "Début des symptômes (jours)",
        "intake.complaint": "Motif de consultation",
        "intake.symptoms": "Symptômes principaux",
        "intake.pregnancy": "Statut grossesse",
        "intake.agePlaceholder": "32",
        "intake.weightPlaceholder": "68",
        "intake.onsetPlaceholder": "3",
        "intake.selectPlaceholder": "Sélectionner…",
        "intake.complaintPlaceholder": "Fièvre élevée depuis 3 jours, frissons, céphalées…",
        "intake.symptomsPlaceholder": "Ajouter symptôme (Entrée)",
        "intake.sexMale": "Masculin",
        "intake.sexFemale": "Féminin",
        "intake.pregnancyNA": "Non applicable",
        "intake.pregnancyNo": "Non enceinte",
        "intake.pregnancyT1": "Enceinte — T1",
        "intake.pregnancyT2": "Enceinte — T2",
        "intake.pregnancyT3": "Enceinte — T3",
        "intake.pregnancyUnknown": "Inconnu",
        "intake.sectionVitals": "Signes vitaux",
        "intake.sectionLabs": "Résultats biologiques",
        "intake.sectionContext": "Contexte — médicaments, allergies, voyages",
        "intake.submit": "Démarrer la consultation →",
        "intake.errorAge": "Âge invalide",
        "intake.errorSex": "Sexe requis",
        "intake.errorRegion": "Région requise",
        "intake.errorComplaint": "Motif de consultation requis",
        "intake.tagHint": "Appuyez sur Entrée pour ajouter",
        "intake.tagAdd": "Ajouter un élément",
        "intake.tagRemove": "Supprimer",
        "intake.labName": "Examen",
        "intake.labValue": "Résultat",
        "intake.labUnit": "Unité",
        "intake.labAdd": "+ Ajouter un résultat",
        "intake.labRemove": "Supprimer le résultat",
        "intake.medName": "Médicament",
        "intake.medDose": "Dose",
        "intake.medFrequency": "Fréquence",
        "intake.medAdd": "+ Ajouter un médicament",
        "intake.medRemove": "Supprimer le médicament",
        "intake.contextMeds": "Médicaments en cours",
        "intake.contextAllergies": "Allergies connues",
        "intake.contextTravel": "Antécédents de voyage / zone d'exposition",
        "intake.allergyPlaceholder": "Ex : pénicilline (Entrée)",
        "intake.travelPlaceholder": "Ex : zone rurale Savanes (Entrée)",
        "intake.collapseSection": "Réduire la section",
        "intake.expandSection": "Développer la section",
        "intake.summaryConfirm": "Confirmer",
        "intake.summaryEdit": "Modifier",
        "intake.summaryTitle": "Résumé de la consultation",
        "intake.vitalTemp": "Température (°C)",
        "intake.vitalBPSys": "TA sys (mmHg)",
        "intake.vitalBPDia": "TA dia (mmHg)",
        "intake.vitalHR": "FC (/min)",
        "intake.vitalRR": "FR (/min)",
        "intake.vitalSpO2": "SpO2 (%)",
        "intake.vitalGCS": "GCS",
      }
      return dict[key] ?? key
    },
    locale: "fr" as const,
  }),
}))

// ── Mock useFocusTrap (used by SummaryPreview) ────────────────────────────────
jest.mock("@/hooks/useFocusTrap", () => ({
  useFocusTrap: jest.fn(),
}))

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

  it("shows summary preview when all mandatory fields are filled, then confirms", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "32")
    await selectField("sexe", "M")
    await selectField("région", "Maritime")
    await fillField("motif de consultation", "Fièvre depuis 3 jours")

    fireEvent.click(getSubmitButton())

    // Summary preview should appear
    expect(screen.queryByText(/âge invalide/i)).not.toBeInTheDocument()
    expect(screen.getByText(/résumé de la consultation/i)).toBeInTheDocument()

    // onComplete should NOT have been called yet
    expect(onComplete).not.toHaveBeenCalled()

    // Click "Confirmer" to proceed
    fireEvent.click(screen.getByRole("button", { name: /confirmer/i }))

    expect(onComplete).toHaveBeenCalledTimes(1)
    const ctx = onComplete.mock.calls[0][0]
    expect(ctx.age_years).toBe(32)
    expect(ctx.sex).toBe("M")
    expect(ctx.region).toBe("Maritime")
    expect(ctx.chief_complaint).toBe("Fièvre depuis 3 jours")
  })

  it("shows summary preview then returns to form on 'Modifier'", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "32")
    await selectField("sexe", "M")
    await selectField("région", "Maritime")
    await fillField("motif de consultation", "Fièvre depuis 3 jours")

    fireEvent.click(getSubmitButton())

    // Summary preview should appear
    expect(screen.getByText(/résumé de la consultation/i)).toBeInTheDocument()

    // Click "Modifier" to go back
    fireEvent.click(screen.getByRole("button", { name: /modifier/i }))

    // Summary should disappear, form should still be there
    expect(screen.queryByText(/résumé de la consultation/i)).not.toBeInTheDocument()
    expect(getSubmitButton()).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })
})

describe("IntakeForm — inline validation on blur", () => {
  it("shows error on blur when age field is empty", async () => {
    renderForm()

    const ageInput = screen.getByLabelText(/âge/i)
    fireEvent.blur(ageInput)

    expect(screen.getByText(/âge invalide/i)).toBeInTheDocument()
    expect(ageInput).toHaveAttribute("aria-invalid", "true")
    expect(ageInput).toHaveAttribute("aria-describedby")
  })

  it("clears error when field is corrected", async () => {
    renderForm()

    const ageInput = screen.getByLabelText(/âge/i)
    fireEvent.blur(ageInput)
    expect(screen.getByText(/âge invalide/i)).toBeInTheDocument()

    // Type a valid value
    await userEvent.type(ageInput, "25")
    expect(screen.queryByText(/âge invalide/i)).not.toBeInTheDocument()
  })
})

// ── Requirement 6.1: Required field left empty on blur shows inline error ─────
describe("IntakeForm — Req 6.1: inline error on blur for all required fields", () => {
  it("shows error on blur when sex field is empty", () => {
    renderForm()
    const sexSelect = screen.getByLabelText(/sexe/i)
    fireEvent.blur(sexSelect)
    expect(screen.getByText(/sexe requis/i)).toBeInTheDocument()
  })

  it("shows error on blur when region field is empty", () => {
    renderForm()
    const regionSelect = screen.getByLabelText(/région/i)
    fireEvent.blur(regionSelect)
    expect(screen.getByText(/région requise/i)).toBeInTheDocument()
  })

  it("shows error on blur when complaint field is empty", () => {
    renderForm()
    const complaintInput = screen.getByLabelText(/motif de consultation/i)
    fireEvent.blur(complaintInput)
    expect(screen.getByText(/motif de consultation requis/i)).toBeInTheDocument()
  })
})

// ── Requirement 6.2: Correcting invalid field removes inline error immediately ─
describe("IntakeForm — Req 6.2: error clearance on correction", () => {
  it("clears sex error when a valid option is selected", async () => {
    renderForm()
    const sexSelect = screen.getByLabelText(/sexe/i)
    fireEvent.blur(sexSelect)
    expect(screen.getByText(/sexe requis/i)).toBeInTheDocument()

    await userEvent.selectOptions(sexSelect, "M")
    expect(screen.queryByText(/sexe requis/i)).not.toBeInTheDocument()
  })

  it("clears region error when a valid option is selected", async () => {
    renderForm()
    const regionSelect = screen.getByLabelText(/région/i)
    fireEvent.blur(regionSelect)
    expect(screen.getByText(/région requise/i)).toBeInTheDocument()

    await userEvent.selectOptions(regionSelect, "Maritime")
    expect(screen.queryByText(/région requise/i)).not.toBeInTheDocument()
  })

  it("clears complaint error when text is entered", async () => {
    renderForm()
    const complaintInput = screen.getByLabelText(/motif de consultation/i)
    fireEvent.blur(complaintInput)
    expect(screen.getByText(/motif de consultation requis/i)).toBeInTheDocument()

    await userEvent.type(complaintInput, "Fièvre")
    expect(screen.queryByText(/motif de consultation requis/i)).not.toBeInTheDocument()
  })
})

// ── Requirement 6.3: aria-describedby wiring for all error fields ─────────────
describe("IntakeForm — Req 6.3: aria-describedby wiring", () => {
  it("age input aria-describedby references the error element id", () => {
    renderForm()
    const ageInput = screen.getByLabelText(/âge/i)
    fireEvent.blur(ageInput)

    const describedById = ageInput.getAttribute("aria-describedby")
    expect(describedById).toBeTruthy()
    const errorEl = document.getElementById(describedById!)
    expect(errorEl).toBeInTheDocument()
    expect(errorEl).toHaveTextContent(/âge invalide/i)
  })

  it("sex select aria-describedby references the error element id", () => {
    renderForm()
    const sexSelect = screen.getByLabelText(/sexe/i)
    fireEvent.blur(sexSelect)

    const describedById = sexSelect.getAttribute("aria-describedby")
    expect(describedById).toBeTruthy()
    const errorEl = document.getElementById(describedById!)
    expect(errorEl).toBeInTheDocument()
    expect(errorEl).toHaveTextContent(/sexe requis/i)
  })

  it("region select aria-describedby references the error element id", () => {
    renderForm()
    const regionSelect = screen.getByLabelText(/région/i)
    fireEvent.blur(regionSelect)

    const describedById = regionSelect.getAttribute("aria-describedby")
    expect(describedById).toBeTruthy()
    const errorEl = document.getElementById(describedById!)
    expect(errorEl).toBeInTheDocument()
    expect(errorEl).toHaveTextContent(/région requise/i)
  })

  it("complaint textarea aria-describedby references the error element id", () => {
    renderForm()
    const complaintInput = screen.getByLabelText(/motif de consultation/i)
    fireEvent.blur(complaintInput)

    const describedById = complaintInput.getAttribute("aria-describedby")
    expect(describedById).toBeTruthy()
    const errorEl = document.getElementById(describedById!)
    expect(errorEl).toBeInTheDocument()
    expect(errorEl).toHaveTextContent(/motif de consultation requis/i)
  })

  it("aria-describedby is removed when error is cleared", async () => {
    renderForm()
    const ageInput = screen.getByLabelText(/âge/i)
    fireEvent.blur(ageInput)
    expect(ageInput).toHaveAttribute("aria-describedby")

    await userEvent.type(ageInput, "30")
    expect(ageInput).not.toHaveAttribute("aria-describedby")
  })
})

// ── Requirement 6.4: Invalid fields marked with aria-invalid="true" ───────────
describe("IntakeForm — Req 6.4: aria-invalid attribute", () => {
  it("sex select has aria-invalid when empty on blur", () => {
    renderForm()
    const sexSelect = screen.getByLabelText(/sexe/i)
    fireEvent.blur(sexSelect)
    expect(sexSelect).toHaveAttribute("aria-invalid", "true")
  })

  it("region select has aria-invalid when empty on blur", () => {
    renderForm()
    const regionSelect = screen.getByLabelText(/région/i)
    fireEvent.blur(regionSelect)
    expect(regionSelect).toHaveAttribute("aria-invalid", "true")
  })

  it("complaint textarea has aria-invalid when empty on blur", () => {
    renderForm()
    const complaintInput = screen.getByLabelText(/motif de consultation/i)
    fireEvent.blur(complaintInput)
    expect(complaintInput).toHaveAttribute("aria-invalid", "true")
  })

  it("aria-invalid is removed when field is corrected", async () => {
    renderForm()
    const sexSelect = screen.getByLabelText(/sexe/i)
    fireEvent.blur(sexSelect)
    expect(sexSelect).toHaveAttribute("aria-invalid", "true")

    await userEvent.selectOptions(sexSelect, "F")
    expect(sexSelect).not.toHaveAttribute("aria-invalid", "true")
  })
})

// ── Requirement 6.5 + 9.1: Submission prevention and summary preview ──────────
describe("IntakeForm — Req 6.5/9.1: submission prevention with inline errors", () => {
  it("does not show summary preview when fields have inline errors from blur", async () => {
    const { onComplete } = renderForm()

    // Trigger blur errors on all fields
    fireEvent.blur(screen.getByLabelText(/âge/i))
    fireEvent.blur(screen.getByLabelText(/sexe/i))
    fireEvent.blur(screen.getByLabelText(/région/i))
    fireEvent.blur(screen.getByLabelText(/motif de consultation/i))

    // Try to submit
    fireEvent.click(getSubmitButton())

    // Summary preview should NOT appear
    expect(screen.queryByText(/résumé de la consultation/i)).not.toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("prevents submission and shows errors even after partial correction", async () => {
    const { onComplete } = renderForm()

    // Fill only age and sex, leave region and complaint empty
    await fillField("âge", "25")
    await selectField("sexe", "F")

    fireEvent.click(getSubmitButton())

    // Should show errors for unfilled fields
    expect(screen.getByText(/région requise/i)).toBeInTheDocument()
    expect(screen.getByText(/motif de consultation requis/i)).toBeInTheDocument()
    expect(screen.queryByText(/résumé de la consultation/i)).not.toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("summary preview is shown only after all validation passes (Req 9.1)", async () => {
    const { onComplete } = renderForm()

    await fillField("âge", "45")
    await selectField("sexe", "F")
    await selectField("région", "Kara")
    await fillField("motif de consultation", "Douleurs abdominales")

    fireEvent.click(getSubmitButton())

    // No errors should be present
    expect(screen.queryByText(/âge invalide/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sexe requis/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/région requise/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/motif de consultation requis/i)).not.toBeInTheDocument()

    // Summary preview should appear BEFORE onComplete is called
    expect(screen.getByText(/résumé de la consultation/i)).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })
})
