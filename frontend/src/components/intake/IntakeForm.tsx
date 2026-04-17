// ─────────────────────────────────────────────────────────────────────────────
// components/intake/IntakeForm.tsx
//
// Structured patient intake form.  On submit it produces a PatientContext
// object that maps 1-to-1 with the backend Pydantic model.
//
// Fields are split into three collapsible sections so the form never feels
// overwhelming on a small clinic screen.  Mandatory fields are marked *.
// ─────────────────────────────────────────────────────────────────────────────
"use client"

import { useState, type FormEvent } from "react"
import { cn } from "@/lib/utils"

// ── Types ─────────────────────────────────────────────────────────────────────

export interface LabResult {
  name:  string
  value: string
  unit:  string
}

export interface Medication {
  name:      string
  dose:      string
  frequency: string
}

export interface VitalSigns {
  temp_c:       number | ""
  bp_systolic:  number | ""
  bp_diastolic: number | ""
  hr:           number | ""
  rr:           number | ""
  spo2:         number | ""
  gcs:          number | ""
}

export interface PatientContext {
  age_years:         number
  sex:               "M" | "F"
  weight_kg:         number | null
  region:            string
  chief_complaint:   string
  symptoms:          { text: string }[]
  vital_signs:       Partial<VitalSigns>
  lab_results:       LabResult[]
  current_medications: Medication[]
  allergies:         string[]
  pregnancy_status:  string
  symptom_onset_days: number | null
  travel_history:    string[]
}

interface Props {
  onComplete: (ctx: PatientContext) => void
  language:   "fr" | "en"
}

const REGIONS = ["Maritime", "Plateaux", "Centrale", "Kara", "Savanes"]
const PREGNANCY_OPTIONS = [
  { value: "not_applicable", label: "Non applicable" },
  { value: "not_pregnant",   label: "Non enceinte"   },
  { value: "pregnant_t1",    label: "Enceinte — T1"  },
  { value: "pregnant_t2",    label: "Enceinte — T2"  },
  { value: "pregnant_t3",    label: "Enceinte — T3"  },
  { value: "unknown",        label: "Inconnu"         },
]

// ── Sub-components ────────────────────────────────────────────────────────────

function Section({
  title, open, onToggle, children,
}: {
  title: string; open: boolean; onToggle: () => void; children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
      >
        <span className="text-sm font-medium text-gray-900">{title}</span>
        <span className="text-gray-400 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && <div className="border-t px-4 pb-4 pt-3 space-y-3">{children}</div>}
    </div>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400"

// ── Repeating-row editors ─────────────────────────────────────────────────────

function LabEditor({
  rows, onChange,
}: {
  rows: LabResult[]; onChange: (rows: LabResult[]) => void
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
            placeholder="Examen" className={cn(inputCls, "flex-1")} />
          <input value={r.value} onChange={e => edit(i, "value", e.target.value)}
            placeholder="Résultat" className={cn(inputCls, "w-28")} />
          <input value={r.unit}  onChange={e => edit(i, "unit",  e.target.value)}
            placeholder="Unité"   className={cn(inputCls, "w-20")} />
          <button type="button" onClick={() => remove(i)}
            className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
        </div>
      ))}
      <button type="button" onClick={add}
        className="text-xs text-blue-600 hover:underline">+ Ajouter un résultat</button>
    </div>
  )
}

function MedEditor({
  rows, onChange,
}: {
  rows: Medication[]; onChange: (rows: Medication[]) => void
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
            placeholder="Médicament"  className={cn(inputCls, "flex-1")} />
          <input value={r.dose}      onChange={e => edit(i, "dose",      e.target.value)}
            placeholder="Dose"        className={cn(inputCls, "w-24")} />
          <input value={r.frequency} onChange={e => edit(i, "frequency", e.target.value)}
            placeholder="Fréquence"   className={cn(inputCls, "w-28")} />
          <button type="button" onClick={() => remove(i)}
            className="text-gray-300 hover:text-red-400 text-lg leading-none">×</button>
        </div>
      ))}
      <button type="button" onClick={add}
        className="text-xs text-blue-600 hover:underline">+ Ajouter un médicament</button>
    </div>
  )
}

function TagEditor({
  tags, onChange, placeholder,
}: {
  tags: string[]; onChange: (t: string[]) => void; placeholder: string
}) {
  const [input, setInput] = useState("")
  function add() {
    const v = input.trim()
    if (v && !tags.includes(v)) onChange([...tags, v])
    setInput("")
  }
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); add() } }}
          placeholder={placeholder} className={cn(inputCls, "flex-1")} />
        <button type="button" onClick={add}
          className="rounded-lg border px-3 py-2 text-sm text-gray-600 hover:bg-gray-50">
          +
        </button>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map(t => (
            <span key={t} className="flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-xs text-blue-700">
              {t}
              <button type="button" onClick={() => onChange(tags.filter(x => x !== t))}
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
  const [vitals,      setVitals]      = useState<Partial<VitalSigns>>({})
  const [labs,        setLabs]        = useState<LabResult[]>([])
  const [meds,        setMeds]        = useState<Medication[]>([])
  const [allergies,   setAllergies]   = useState<string[]>([])
  const [travel,      setTravel]      = useState<string[]>([])

  // UI
  const [openSections, setOpenSections] = useState({ vitals: false, labs: false, context: false })
  const [errors,       setErrors]       = useState<string[]>([])

  function toggleSection(key: keyof typeof openSections) {
    setOpenSections(s => ({ ...s, [key]: !s[key] }))
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const errs: string[] = []
    if (!age || isNaN(Number(age)) || Number(age) < 0)
      errs.push("Âge invalide")
    if (!sex)
      errs.push("Sexe requis")
    if (!region)
      errs.push("Région requise")
    if (!complaint.trim())
      errs.push("Motif de consultation requis")

    if (errs.length) { setErrors(errs); return }
    setErrors([])

    const ctx: PatientContext = {
      age_years:         Number(age),
      sex:               sex as "M" | "F",
      weight_kg:         weight ? Number(weight) : null,
      region,
      chief_complaint:   complaint.trim(),
      symptoms:          symptoms.map(s => ({ text: s })),
      vital_signs:       vitals,
      lab_results:       labs.filter(l => l.name.trim()),
      current_medications: meds.filter(m => m.name.trim()),
      allergies,
      pregnancy_status:  pregnancy,
      symptom_onset_days: onset ? Number(onset) : null,
      travel_history:    travel,
    }
    onComplete(ctx)
  }

  return (
    <form onSubmit={handleSubmit} className="h-full overflow-y-auto space-y-3 pb-4">

      {/* Validation errors */}
      {errors.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 space-y-1">
          {errors.map(e => <p key={e} className="text-xs text-red-700">• {e}</p>)}
        </div>
      )}

      {/* ── Mandatory fields (always visible) ──────────────────────────────── */}
      <div className="rounded-xl border bg-white px-4 pb-4 pt-3 space-y-3 shadow-sm">
        <p className="text-sm font-medium text-gray-900">Données patient</p>

        <div className="grid grid-cols-3 gap-3">
          <Field label="Âge (ans)" required>
            <input type="number" min={0} max={120} value={age}
              onChange={e => setAge(e.target.value)}
              className={inputCls} placeholder="32" />
          </Field>
          <Field label="Sexe" required>
            <select value={sex} onChange={e => setSex(e.target.value as "M" | "F")}
              className={inputCls}>
              <option value="">—</option>
              <option value="M">Masculin</option>
              <option value="F">Féminin</option>
            </select>
          </Field>
          <Field label="Poids (kg)">
            <input type="number" min={0} value={weight}
              onChange={e => setWeight(e.target.value)}
              className={inputCls} placeholder="68" />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Région (Togo)" required>
            <select value={region} onChange={e => setRegion(e.target.value)}
              className={inputCls}>
              <option value="">Sélectionner…</option>
              {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Début des symptômes (jours)">
            <input type="number" min={0} value={onset}
              onChange={e => setOnset(e.target.value)}
              className={inputCls} placeholder="3" />
          </Field>
        </div>

        <Field label="Motif de consultation" required>
          <textarea value={complaint} onChange={e => setComplaint(e.target.value)}
            rows={2} className={cn(inputCls, "resize-none")}
            placeholder="Fièvre élevée depuis 3 jours, frissons, céphalées…" />
        </Field>

        <Field label="Symptômes principaux">
          <TagEditor tags={symptoms} onChange={setSymptoms}
            placeholder="Ajouter symptôme (Entrée)" />
        </Field>

        <Field label="Statut grossesse">
          <select value={pregnancy} onChange={e => setPregnancy(e.target.value)}
            className={inputCls}>
            {PREGNANCY_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </Field>
      </div>

      {/* ── Signes vitaux ───────────────────────────────────────────────────── */}
      <Section title="Signes vitaux" open={openSections.vitals}
        onToggle={() => toggleSection("vitals")}>
        <div className="grid grid-cols-4 gap-3">
          {([
            ["Température (°C)", "temp_c",       "38.5"],
            ["TA sys (mmHg)",    "bp_systolic",  "120" ],
            ["TA dia (mmHg)",    "bp_diastolic", "80"  ],
            ["FC (/min)",        "hr",           "90"  ],
            ["FR (/min)",        "rr",           "18"  ],
            ["SpO2 (%)",         "spo2",         "98"  ],
            ["GCS",             "gcs",           "15"  ],
          ] as [string, keyof VitalSigns, string][]).map(([label, key, ph]) => (
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
      <Section title="Résultats biologiques" open={openSections.labs}
        onToggle={() => toggleSection("labs")}>
        <LabEditor rows={labs} onChange={setLabs} />
      </Section>

      {/* ── Contexte clinique ────────────────────────────────────────────────── */}
      <Section title="Contexte — médicaments, allergies, voyages" open={openSections.context}
        onToggle={() => toggleSection("context")}>
        <Field label="Médicaments en cours">
          <MedEditor rows={meds} onChange={setMeds} />
        </Field>
        <Field label="Allergies connues">
          <TagEditor tags={allergies} onChange={setAllergies}
            placeholder="Ex : pénicilline (Entrée)" />
        </Field>
        <Field label="Antécédents de voyage / zone d'exposition">
          <TagEditor tags={travel} onChange={setTravel}
            placeholder="Ex : zone rurale Savanes (Entrée)" />
        </Field>
      </Section>

      {/* Submit */}
      <button type="submit"
        className="w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white hover:bg-blue-700 active:scale-[0.99] transition-all shadow-sm">
        Démarrer la consultation →
      </button>
    </form>
  )
}