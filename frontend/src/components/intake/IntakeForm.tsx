// ─────────────────────────────────────────────────────────────────────────────
// components/intake/IntakeForm.tsx
//
// Structured patient intake form. On submit it produces a PatientContext
// object that maps 1-to-1 with the backend Pydantic model.
//
// Fields are split into three collapsible sections so the form never feels
// overwhelming on a small clinic screen. Mandatory fields are marked *.
//
// Requirements: 2.1, 2.2, 2.3, 6.1–6.5, 7.1, 7.2, 8.1, 8.2, 9.1, 9.3,
//               27.1, 27.2, 30.1, 30.2
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState, useId, type FormEvent } from "react"
import { cn } from "@/lib/utils"
import { useTranslation } from "@/lib/i18n"
import { SummaryPreview } from "./SummaryPreview"
import type { PatientContext, LabResult, Medication, VitalSigns } from "@/lib/types"

// Re-export for backward compatibility
export type { PatientContext, LabResult, Medication, VitalSigns }

// ── Inline validation types ──────────────────────────────────────────────────

type FieldErrors = Partial<Record<"age" | "sex" | "region" | "complaint", string>>

// ── Local form-specific VitalSigns (allows empty string for unset fields) ────

interface FormVitalSigns {
  temp_c:       number | ""
  bp_systolic:  number | ""
  bp_diastolic: number | ""
  hr:           number | ""
  rr:           number | ""
  spo2:        number | ""
  gcs:          number | ""
}

interface Props {
  onComplete: (ctx: PatientContext) => void
  language:   "fr" | "en"
}

const REGIONS = ["Maritime", "Plateaux", "Centrale", "Kara", "Savanes"]

// ── Sub-components ────────────────────────────────────────────────────────────

export function Section({
  title, open, onToggle, children, id,
}: {
  title: string; open: boolean; onToggle: () => void; children: React.ReactNode; id: string
}) {
  const contentId = `${id}-content`
  return (
    <div className="rounded-xl border bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={contentId}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
      >
        <span className="text-sm font-medium text-gray-900">{title}</span>
        <span
          aria-hidden="true"
          className={cn(
            "inline-block h-2 w-2 border-r-2 border-b-2 border-gray-400 transition-transform duration-200",
            open ? "-rotate-[135deg]" : "rotate-45"
          )}
        />
      </button>
      {open && (
        <div id={contentId} className="border-t px-4 pb-4 pt-3 space-y-3">
          {children}
        </div>
      )}
    </div>
  )
}

function Field({
  label, required, htmlFor, children, error, errorId,
}: {
  label: string; required?: boolean; htmlFor?: string; children: React.ReactNode; error?: string; errorId?: string
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-xs font-medium text-gray-600 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && errorId && (
        <p id={errorId} className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400"

// ── Repeating-row editors ─────────────────────────────────────────────────────

function LabEditor({
  rows, onChange, t,
}: {
  rows: LabResult[]; onChange: (rows: LabResult[]) => void; t: (key: string) => string
}) {
  function add()    { onChange([...rows, { name: "", value: "", unit: "" }]) }
  function remove(i: number) { onChange(rows.filter((_, j) => j !== i)) }
  function edit(i: number, field: keyof LabResult, val: string) {
    onChange(rows.map((r, j) => j === i ? { ...r, [field]: val } : r))
  }
  return (
    <div className="space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input value={r.name}  onChange={e => edit(i, "name",  e.target.value)}
            placeholder={t("intake.labName")} className={cn(inputCls, "flex-1")} />
          <input value={r.value} onChange={e => edit(i, "value", e.target.value)}
            placeholder={t("intake.labValue")} className={cn(inputCls, "w-28")} />
          <input value={r.unit}  onChange={e => edit(i, "unit",  e.target.value)}
            placeholder={t("intake.labUnit")}   className={cn(inputCls, "w-20")} />
          <button type="button" onClick={() => remove(i)}
            aria-label={`${t("intake.labRemove")} ${r.name || ""}`}
            className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
        </div>
      ))}
      <button type="button" onClick={add}
        aria-label={t("intake.labAdd")}
        className="text-xs text-blue-600 hover:underline">{t("intake.labAdd")}</button>
    </div>
  )
}

function MedEditor({
  rows, onChange, t,
}: {
  rows: Medication[]; onChange: (rows: Medication[]) => void; t: (key: string) => string
}) {
  function add()    { onChange([...rows, { name: "", dose: "", frequency: "" }]) }
  function remove(i: number) { onChange(rows.filter((_, j) => j !== i)) }
  function edit(i: number, field: keyof Medication, val: string) {
    onChange(rows.map((r, j) => j === i ? { ...r, [field]: val } : r))
  }
  return (
    <div className="space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input value={r.name}      onChange={e => edit(i, "name",      e.target.value)}
            placeholder={t("intake.medName")}  className={cn(inputCls, "flex-1")} />
          <input value={r.dose}      onChange={e => edit(i, "dose",      e.target.value)}
            placeholder={t("intake.medDose")}        className={cn(inputCls, "w-24")} />
          <input value={r.frequency} onChange={e => edit(i, "frequency", e.target.value)}
            placeholder={t("intake.medFrequency")}   className={cn(inputCls, "w-28")} />
          <button type="button" onClick={() => remove(i)}
            aria-label={`${t("intake.medRemove")} ${r.name || ""}`}
            className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
        </div>
      ))}
      <button type="button" onClick={add}
        aria-label={t("intake.medAdd")}
        className="text-xs text-blue-600 hover:underline">{t("intake.medAdd")}</button>
    </div>
  )
}

function TagEditor({
  tags, onChange, placeholder, t, hintId,
}: {
  tags: string[]; onChange: (t: string[]) => void; placeholder: string; t: (key: string) => string; hintId: string
}) {
  const [input, setInput] = useState("")
  function add() {
    const v = input.trim()
    if (v && !tags.includes(v)) onChange([...tags, v])
    setInput("")
  }
  return (
    <div className="space-y-1">
      <div className="flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add() } }}
          placeholder={placeholder} className={cn(inputCls, "flex-1")}
          aria-describedby={hintId} />
        <button type="button" onClick={add}
          aria-label={t("intake.tagAdd")}
          className="rounded-lg border px-3 py-2 text-sm text-gray-600 hover:bg-gray-50">
          +
        </button>
      </div>
      <p id={hintId} className="text-xs text-gray-500">{t("intake.tagHint")}</p>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map(tag => (
            <span key={tag} className="flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-xs text-blue-700">
              {tag}
              <button type="button" onClick={() => onChange(tags.filter(x => x !== tag))}
                aria-label={`${t("intake.tagRemove")} ${tag}`}
                className="text-blue-400 hover:text-blue-600">×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main form ─────────────────────────────────────────────────────────────────

export function IntakeForm({ onComplete }: Props) {
  const { t } = useTranslation()
  const formId = useId()

  // Mandatory
  const [age,         setAge]         = useState<string>("")
  const [sex,         setSex]         = useState<"M" | "F" | "">("")
  const [region,      setRegion]      = useState("")
  const [complaint,   setComplaint]   = useState("")
  const [onset,       setOnset]       = useState<string>("")
  const [symptoms,    setSymptoms]    = useState<string[]>([])
  const [pregnancy,   setPregnancy]   = useState("not_applicable")

  // Optional
  const [weight,      setWeight]      = useState<string>("")
  const [vitals,      setVitals]      = useState<Partial<FormVitalSigns>>({})
  const [labs,        setLabs]        = useState<LabResult[]>([])
  const [meds,        setMeds]        = useState<Medication[]>([])
  const [allergies,   setAllergies]   = useState<string[]>([])
  const [travel,      setTravel]      = useState<string[]>([])

  // UI
  const [openSections, setOpenSections] = useState({ vitals: false, labs: false, context: false })
  const [fieldErrors,  setFieldErrors]  = useState<FieldErrors>({})
  const [showSummary,  setShowSummary]  = useState(false)
  const [pendingCtx,   setPendingCtx]   = useState<PatientContext | null>(null)

  function toggleSection(key: keyof typeof openSections) {
    setOpenSections(s => ({ ...s, [key]: !s[key] }))
  }

  // ── Validation helpers ────────────────────────────────────────────────────

  function validateField(field: keyof FieldErrors): string | undefined {
    switch (field) {
      case "age":
        if (!age || isNaN(Number(age)) || Number(age) < 0) return t("intake.errorAge")
        break
      case "sex":
        if (!sex) return t("intake.errorSex")
        break
      case "region":
        if (!region) return t("intake.errorRegion")
        break
      case "complaint":
        if (!complaint.trim()) return t("intake.errorComplaint")
        break
    }
    return undefined
  }

  function handleBlur(field: keyof FieldErrors) {
    const error = validateField(field)
    setFieldErrors(prev => {
      if (error) return { ...prev, [field]: error }
      const { [field]: _omitted, ...rest } = prev
      return rest
    })
  }

  function handleFieldChange(field: keyof FieldErrors) {
    // Clear error on correction
    if (fieldErrors[field]) {
      setFieldErrors(prev => {
        const { [field]: _omitted, ...rest } = prev
        return rest
      })
    }
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  function handleSubmit(e: FormEvent) {
    e.preventDefault()

    // Validate all required fields
    const errs: FieldErrors = {}
    const ageErr = validateField("age")
    const sexErr = validateField("sex")
    const regionErr = validateField("region")
    const complaintErr = validateField("complaint")
    if (ageErr) errs.age = ageErr
    if (sexErr) errs.sex = sexErr
    if (regionErr) errs.region = regionErr
    if (complaintErr) errs.complaint = complaintErr

    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs)
      return
    }
    setFieldErrors({})

    const ctx: PatientContext = {
      age_years:         Number(age),
      sex:               sex as "M" | "F",
      weight_kg:         weight ? Number(weight) : null,
      region,
      chief_complaint:   complaint.trim(),
      symptoms:          symptoms.map(s => ({ text: s })),
      vital_signs:       Object.fromEntries(
        Object.entries(vitals).map(([k, v]) => [k, v === "" ? null : v]),
      ) as Partial<VitalSigns>,
      lab_results:       labs.filter(l => l.name.trim()),
      current_medications: meds.filter(m => m.name.trim()),
      allergies,
      pregnancy_status:  pregnancy,
      symptom_onset_days: onset ? Number(onset) : null,
      travel_history:    travel,
    }

    // Show summary preview instead of calling onComplete directly
    setPendingCtx(ctx)
    setShowSummary(true)
  }

  function handleConfirm() {
    if (pendingCtx) {
      onComplete(pendingCtx)
    }
    setShowSummary(false)
  }

  function handleEdit() {
    setShowSummary(false)
  }

  // ── Error id helpers ──────────────────────────────────────────────────────

  const errorId = (field: string) => `${formId}-error-${field}`

  // ── Pregnancy options (i18n) ──────────────────────────────────────────────

  const PREGNANCY_OPTIONS = [
    { value: "not_applicable", label: t("intake.pregnancyNA") },
    { value: "not_pregnant",   label: t("intake.pregnancyNo") },
    { value: "pregnant_t1",    label: t("intake.pregnancyT1") },
    { value: "pregnant_t2",    label: t("intake.pregnancyT2") },
    { value: "pregnant_t3",    label: t("intake.pregnancyT3") },
    { value: "unknown",        label: t("intake.pregnancyUnknown") },
  ]

  // ── Vital signs config ────────────────────────────────────────────────────

  const VITAL_FIELDS: [string, keyof FormVitalSigns, string][] = [
    [t("intake.vitalTemp"),   "temp_c",       "38.5"],
    [t("intake.vitalBPSys"),  "bp_systolic",  "120" ],
    [t("intake.vitalBPDia"),  "bp_diastolic", "80"  ],
    [t("intake.vitalHR"),     "hr",           "90"  ],
    [t("intake.vitalRR"),     "rr",           "18"  ],
    [t("intake.vitalSpO2"),   "spo2",         "98"  ],
    [t("intake.vitalGCS"),    "gcs",          "15"  ],
  ]

  return (
    <>
      <form onSubmit={handleSubmit} className="h-full overflow-y-auto space-y-3 pb-4">

        {/* ── Mandatory fields (always visible) ──────────────────────────────── */}
        <div className="rounded-xl border bg-white px-4 pb-4 pt-3 space-y-3 shadow-sm">
          <p className="text-sm font-medium text-gray-900">{t("intake.title")}</p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Field label={t("intake.age")} required htmlFor="intake-age"
              error={fieldErrors.age} errorId={errorId("age")}>
              <input id="intake-age" type="number" min={0} max={120} value={age}
                onChange={e => { setAge(e.target.value); handleFieldChange("age") }}
                onBlur={() => handleBlur("age")}
                aria-invalid={!!fieldErrors.age || undefined}
                aria-describedby={fieldErrors.age ? errorId("age") : undefined}
                className={inputCls} placeholder={t("intake.agePlaceholder")} />
            </Field>
            <Field label={t("intake.sex")} required htmlFor="intake-sex"
              error={fieldErrors.sex} errorId={errorId("sex")}>
              <select id="intake-sex" value={sex}
                onChange={e => { setSex(e.target.value as "M" | "F"); handleFieldChange("sex") }}
                onBlur={() => handleBlur("sex")}
                aria-invalid={!!fieldErrors.sex || undefined}
                aria-describedby={fieldErrors.sex ? errorId("sex") : undefined}
                className={inputCls}>
                <option value="">—</option>
                <option value="M">{t("intake.sexMale")}</option>
                <option value="F">{t("intake.sexFemale")}</option>
              </select>
            </Field>
            <Field label={t("intake.weight")} htmlFor="intake-weight">
              <input id="intake-weight" type="number" min={0} value={weight}
                onChange={e => setWeight(e.target.value)}
                className={inputCls} placeholder={t("intake.weightPlaceholder")} />
            </Field>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label={t("intake.region")} required htmlFor="intake-region"
              error={fieldErrors.region} errorId={errorId("region")}>
              <select id="intake-region" value={region}
                onChange={e => { setRegion(e.target.value); handleFieldChange("region") }}
                onBlur={() => handleBlur("region")}
                aria-invalid={!!fieldErrors.region || undefined}
                aria-describedby={fieldErrors.region ? errorId("region") : undefined}
                className={inputCls}>
                <option value="">{t("intake.selectPlaceholder")}</option>
                {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </Field>
            <Field label={t("intake.onset")} htmlFor="intake-onset">
              <input id="intake-onset" type="number" min={0} value={onset}
                onChange={e => setOnset(e.target.value)}
                className={inputCls} placeholder={t("intake.onsetPlaceholder")} />
            </Field>
          </div>

          <Field label={t("intake.complaint")} required htmlFor="intake-complaint"
            error={fieldErrors.complaint} errorId={errorId("complaint")}>
            <textarea id="intake-complaint" value={complaint}
              onChange={e => { setComplaint(e.target.value); handleFieldChange("complaint") }}
              onBlur={() => handleBlur("complaint")}
              aria-invalid={!!fieldErrors.complaint || undefined}
              aria-describedby={fieldErrors.complaint ? errorId("complaint") : undefined}
              rows={2} className={cn(inputCls, "resize-none")}
              placeholder={t("intake.complaintPlaceholder")} />
          </Field>

          <Field label={t("intake.symptoms")}>
            <TagEditor tags={symptoms} onChange={setSymptoms}
              placeholder={t("intake.symptomsPlaceholder")}
              t={t} hintId={`${formId}-hint-symptoms`} />
          </Field>

          <Field label={t("intake.pregnancy")} htmlFor="intake-pregnancy">
            <select id="intake-pregnancy" value={pregnancy} onChange={e => setPregnancy(e.target.value)}
              className={inputCls}>
              {PREGNANCY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </Field>
        </div>

        {/* ── Signes vitaux ───────────────────────────────────────────────────── */}
        <Section title={t("intake.sectionVitals")} open={openSections.vitals}
          onToggle={() => toggleSection("vitals")} id={`${formId}-vitals`}>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {VITAL_FIELDS.map(([label, key, ph]) => (
              <Field key={key} label={label}>
                <input type="number" step="0.1"
                  value={vitals[key] ?? ""}
                  onChange={e => setVitals(v => ({ ...v, [key]: e.target.value === "" ? "" : Number(e.target.value) }))}
                  className={inputCls} placeholder={ph} />
              </Field>
            ))}
          </div>
        </Section>

        {/* ── Biologie ────────────────────────────────────────────────────────── */}
        <Section title={t("intake.sectionLabs")} open={openSections.labs}
          onToggle={() => toggleSection("labs")} id={`${formId}-labs`}>
          <LabEditor rows={labs} onChange={setLabs} t={t} />
        </Section>

        {/* ── Contexte clinique ────────────────────────────────────────────────── */}
        <Section title={t("intake.sectionContext")} open={openSections.context}
          onToggle={() => toggleSection("context")} id={`${formId}-context`}>
          <Field label={t("intake.contextMeds")}>
            <MedEditor rows={meds} onChange={setMeds} t={t} />
          </Field>
          <Field label={t("intake.contextAllergies")}>
            <TagEditor tags={allergies} onChange={setAllergies}
              placeholder={t("intake.allergyPlaceholder")}
              t={t} hintId={`${formId}-hint-allergies`} />
          </Field>
          <Field label={t("intake.contextTravel")}>
            <TagEditor tags={travel} onChange={setTravel}
              placeholder={t("intake.travelPlaceholder")}
              t={t} hintId={`${formId}-hint-travel`} />
          </Field>
        </Section>

        {/* Submit */}
        <button type="submit"
          aria-label={t("intake.submit")}
          className="w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white hover:bg-blue-700 active:scale-[0.99] transition-all shadow-sm">
          {t("intake.submit")}
        </button>
      </form>

      {/* Summary preview modal */}
      {showSummary && pendingCtx && (
        <SummaryPreview
          context={pendingCtx}
          onConfirm={handleConfirm}
          onEdit={handleEdit}
        />
      )}
    </>
  )
}
