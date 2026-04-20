// ─────────────────────────────────────────────────────────────────────────────
// Property tests for SummaryPreview component
// Feature: ui-ux-improvements, Property 5: Summary preview displays all filled fields
// **Validates: Requirements 9.2**
// ─────────────────────────────────────────────────────────────────────────────

import * as fc from "fast-check"
import { render } from "@testing-library/react"
import "@testing-library/jest-dom"
import { SummaryPreview } from "@/components/intake/SummaryPreview"
import type { PatientContext, LabResult, Medication, VitalSigns } from "@/lib/types"

// ── Mock useTranslation to return a passthrough t function ────────────────────
jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: "fr" as const,
  }),
}))

// ── Mock useFocusTrap (no-op in tests) ────────────────────────────────────────
jest.mock("@/hooks/useFocusTrap", () => ({
  useFocusTrap: () => {},
}))

// ── Generators ────────────────────────────────────────────────────────────────

const arbNonEmptyString = fc.string({ minLength: 1, maxLength: 30 }).filter((s) => s.trim().length > 0)

const arbLabResult: fc.Arbitrary<LabResult> = fc.record({
  name: arbNonEmptyString,
  value: arbNonEmptyString,
  unit: arbNonEmptyString,
})

const arbMedication: fc.Arbitrary<Medication> = fc.record({
  name: arbNonEmptyString,
  dose: arbNonEmptyString,
  frequency: arbNonEmptyString,
})

const arbVitalSigns: fc.Arbitrary<Partial<VitalSigns>> = fc.record({
  temp_c: fc.option(fc.float({ min: 35, max: 42, noNaN: true }), { nil: null }),
  bp_systolic: fc.option(fc.integer({ min: 60, max: 200 }), { nil: null }),
  bp_diastolic: fc.option(fc.integer({ min: 40, max: 130 }), { nil: null }),
  hr: fc.option(fc.integer({ min: 30, max: 200 }), { nil: null }),
  rr: fc.option(fc.integer({ min: 8, max: 40 }), { nil: null }),
  spo2: fc.option(fc.integer({ min: 70, max: 100 }), { nil: null }),
  gcs: fc.option(fc.integer({ min: 3, max: 15 }), { nil: null }),
})

const arbPatientContext: fc.Arbitrary<PatientContext> = fc.record({
  // Mandatory fields (always filled)
  age_years: fc.integer({ min: 0, max: 120 }),
  sex: fc.constantFrom("M" as const, "F" as const),
  region: fc.constantFrom("Maritime", "Plateaux", "Centrale", "Kara", "Savanes"),
  chief_complaint: arbNonEmptyString,
  // Optional fields
  weight_kg: fc.option(fc.float({ min: 1, max: 200, noNaN: true }), { nil: null }),
  symptoms: fc.array(
    fc.record({ text: arbNonEmptyString, normalized: fc.option(arbNonEmptyString, { nil: undefined }) }),
    { minLength: 0, maxLength: 5 }
  ),
  vital_signs: fc.option(arbVitalSigns, { nil: undefined }),
  lab_results: fc.array(arbLabResult, { minLength: 0, maxLength: 3 }),
  current_medications: fc.array(arbMedication, { minLength: 0, maxLength: 3 }),
  allergies: fc.array(arbNonEmptyString, { minLength: 0, maxLength: 3 }),
  pregnancy_status: fc.constantFrom("not_applicable", "not_pregnant", "pregnant_t1", "pregnant_t2", "pregnant_t3", "unknown"),
  symptom_onset_days: fc.option(fc.integer({ min: 1, max: 365 }), { nil: null }),
  travel_history: fc.array(arbNonEmptyString, { minLength: 0, maxLength: 3 }),
})

// ── Property Test ─────────────────────────────────────────────────────────────

describe("Property 5: Summary preview displays all filled fields", () => {
  it("renders all filled field values in the preview", () => {
    fc.assert(
      fc.property(arbPatientContext, (context) => {
        const { container } = render(
          <SummaryPreview
            context={context}
            onConfirm={() => {}}
            onEdit={() => {}}
          />
        )

        const textContent = container.textContent ?? ""

        // Mandatory fields must always appear
        expect(textContent).toContain(String(context.age_years))
        expect(textContent).toContain(context.sex)
        expect(textContent).toContain(context.region)
        expect(textContent).toContain(context.chief_complaint)

        // Optional: weight
        if (context.weight_kg != null) {
          expect(textContent).toContain(String(context.weight_kg))
        }

        // Optional: symptom onset
        if (context.symptom_onset_days != null) {
          expect(textContent).toContain(String(context.symptom_onset_days))
        }

        // Optional: pregnancy status
        if (context.pregnancy_status) {
          expect(textContent).toContain(context.pregnancy_status)
        }

        // Optional: symptoms
        for (const symptom of context.symptoms) {
          expect(textContent).toContain(symptom.text)
        }

        // Optional: vital signs
        if (context.vital_signs) {
          for (const [, val] of Object.entries(context.vital_signs)) {
            if (val != null) {
              expect(textContent).toContain(String(val))
            }
          }
        }

        // Optional: lab results
        for (const lab of context.lab_results) {
          expect(textContent).toContain(lab.name)
          expect(textContent).toContain(lab.value)
          expect(textContent).toContain(lab.unit)
        }

        // Optional: medications
        for (const med of context.current_medications) {
          expect(textContent).toContain(med.name)
          expect(textContent).toContain(med.dose)
          expect(textContent).toContain(med.frequency)
        }

        // Optional: allergies
        for (const allergy of context.allergies) {
          expect(textContent).toContain(allergy)
        }

        // Optional: travel history
        for (const travel of context.travel_history) {
          expect(textContent).toContain(travel)
        }
      }),
      { numRuns: 100 }
    )
  })
})
