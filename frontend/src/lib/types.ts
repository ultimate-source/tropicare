// ─────────────────────────────────────────────────────────────────────────────
// lib/types.ts — consolidated shared domain types
// ─────────────────────────────────────────────────────────────────────────────

// ── Patient Context ───────────────────────────────────────────────────────────

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
  temp_c:       number | null
  bp_systolic:  number | null
  bp_diastolic: number | null
  hr:           number | null
  rr:           number | null
  spo2:         number | null
  gcs:          number | null
}

export interface PatientContext {
  age_years:          number
  sex:                "M" | "F"
  weight_kg:          number | null
  region:             string
  chief_complaint:    string
  symptoms:           { text: string; normalized?: string }[]
  vital_signs?:       Partial<VitalSigns>
  lab_results:        LabResult[]
  current_medications: Medication[]
  allergies:          string[]
  pregnancy_status:   string
  symptom_onset_days: number | null
  travel_history:     string[]
}

// ── Diagnostic ────────────────────────────────────────────────────────────────

export type Severity = "contraindicated" | "major" | "moderate" | "minor"
export type Verdict  = "PASS" | "WARN" | "BLOCK"

export interface DiagnosticTest {
  name: string
  priority: "urgent" | "standard" | "optional"
  availability_togo: "disponible" | "limité" | "indisponible"
  interpretation: string
}

export interface DiagnosisItem {
  rank: number
  disease_name: string
  icd11_code: string
  confidence: number           // 0–1
  supporting_evidence: string[]
  against_evidence: string[]
  confirmatory_tests: DiagnosticTest[]
  red_flags: string[]
  citations: number[]
}

// ── Urgences ──────────────────────────────────────────────────────────────────

export interface EmergencyFlag {
  disease: string
  level: "critical" | "urgent"
  action: string
}

// ── Treatment ─────────────────────────────────────────────────────────────────

export interface DrugRegimen {
  drug_name: string
  generic_name: string
  came_available: boolean
  dose: string
  route: string
  frequency: string
  duration_days: number | null
  pregnancy_class: string | null
  ddi_warnings: string[]
  amr_note: string | null
  monitoring: string[]
  citations: number[]
}

export interface TreatmentPlanData {
  target_disease: string
  clinical_rationale: string
  first_line: DrugRegimen[]
  second_line: DrugRegimen[]
  alternatives: DrugRegimen[]
  contraindicated: { drug: string; reason: string }[]
  supportive_care: string[]
  follow_up_guidance: string
  referral_criteria: string
  disclaimer: string
}

// ── Citations ─────────────────────────────────────────────────────────────────

export interface Citation {
  ref_id: number
  source_title: string
  section: string
  page: number
  version: string
  date: string
  chunk_snippet: string
}

// ── SSE event discriminated union ─────────────────────────────────────────────

export type SSEEvent =
  | { type: "thinking";          content: string }
  | { type: "emergency_flag";    flag: EmergencyFlag }
  | { type: "differential_item"; item: DiagnosisItem }
  | { type: "treatment_line";    tier: string; drug: DrugRegimen }
  | { type: "citation";          citation: Citation }
  | { type: "validation";        verdict: Verdict; annotations: string[] }
  | { type: "error";             message: string }
  | { type: "done";              turn_id: string }
