// ─────────────────────────────────────────────────────────────────────────────
// FILE STRUCTURE
// app/(clinic)/chat/page.tsx           — chat page
// components/chat/ChatStream.tsx       — main streaming UI
// components/chat/DifferentialCard.tsx — ranked diagnosis card
// components/chat/TreatmentPlan.tsx    — antibiotherapy plan
// components/chat/EmergencyBanner.tsx  — emergency alert
// components/chat/CitationDrawer.tsx   — source citations
// components/chat/FeedbackPanel.tsx    — clinician feedback
// hooks/useStream.ts                   — SSE consumer hook
// lib/api.ts                           — typed API client
// lib/types.ts                         — shared domain types
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// lib/types.ts
// ─────────────────────────────────────────────────────────────────────────────
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

export interface EmergencyFlag {
  disease: string
  level: "critical" | "urgent"
  action: string
}

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

export interface Citation {
  ref_id: number
  source_title: string
  section: string
  page: number
  version: string
  date: string
  chunk_snippet: string
}

// ── SSE event discriminated union ─────────────────────────────
export type SSEEvent =
  | { type: "thinking";          content: string }
  | { type: "emergency_flag";    flag: EmergencyFlag }
  | { type: "differential_item"; item: DiagnosisItem }
  | { type: "treatment_line";    tier: string; drug: DrugRegimen }
  | { type: "citation";          citation: Citation }
  | { type: "validation";        verdict: Verdict; annotations: string[] }
  | { type: "error";             message: string }
  | { type: "done";              turn_id: string }

// ── Diagnostic différentiel ──

export interface ConfirmatoryTest {
  name: string;
  priority: "urgent" | "standard" | "optional";
  availability_togo: "disponible" | "limité" | "indisponible";
  interpretation: string;
}

export interface Contraindicated {
  drug: string;
  reason: string;
}

// ── Urgences ──
export interface EmergencyFlag {
  disease: string;
  level: "critical" | "urgent";
  action: string;
}

