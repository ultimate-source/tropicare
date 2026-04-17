# ─────────────────────────────────────────────────────────────────────────────
# backend/app/models/schemas.py — Consolidated Pydantic domain models
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Patient Context ──────────────────────────────────────────────────────────


class LabResult(BaseModel):
    name: str
    value: str
    unit: str


class Medication(BaseModel):
    name: str
    dose: str
    frequency: str


class VitalSigns(BaseModel):
    temp_c: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    hr: int | None = None
    rr: int | None = None
    spo2: int | None = None
    gcs: int | None = None


class Symptom(BaseModel):
    text: str
    normalized: str | None = None
    snomed_code: str | None = None


class PatientContext(BaseModel):
    age_years: int
    sex: Literal["M", "F"]
    weight_kg: float | None = None
    region: str  # Maritime | Plateaux | Centrale | Kara | Savanes
    chief_complaint: str
    symptoms: list[Symptom] = []
    vital_signs: VitalSigns | None = None
    lab_results: list[LabResult] = []
    current_medications: list[Medication] = []
    allergies: list[str] = []
    pregnancy_status: str = "not_applicable"
    symptom_onset_days: int | None = None
    travel_history: list[str] = []


# ── Diagnostic Output ────────────────────────────────────────────────────────


class ConfirmatoryTest(BaseModel):
    name: str
    priority: Literal["urgent", "standard", "optional"]
    availability_togo: Literal["disponible", "limité", "indisponible"]
    interpretation: str | None = None


class DiagnosisItem(BaseModel):
    rank: int
    disease_name: str
    icd11_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str]
    against_evidence: list[str] = []
    confirmatory_tests: list[ConfirmatoryTest] = []
    red_flags: list[str] = []
    citations: list[int] = []


class EmergencyFlag(BaseModel):
    disease: str
    level: Literal["critical", "urgent"]
    action: str


class DiagnosticDifferential(BaseModel):
    emergency_flags: list[EmergencyFlag] = []
    differential: list[DiagnosisItem]
    clarifying_questions: list[str] = []
    reasoning_summary: str = ""
    citations: list[dict] = []


# ── Treatment Output ─────────────────────────────────────────────────────────


class DrugRegimen(BaseModel):
    drug_name: str
    generic_name: str
    came_available: bool
    dose: str
    dose_mg_per_kg: str | None = None
    route: Literal["PO", "IV", "IM", "SC", "topique"]
    frequency: str
    duration_days: int
    pregnancy_class: str | None = None
    ddi_warnings: list[str] = []
    amr_note: str | None = None
    monitoring: list[str] = []
    citations: list[int] = []


class Contraindication(BaseModel):
    drug: str
    reason: str


class TreatmentPlan(BaseModel):
    target_disease: str
    clinical_rationale: str
    first_line: list[DrugRegimen]
    second_line: list[DrugRegimen] = []
    alternatives: list[DrugRegimen] = []
    contraindicated: list[Contraindication] = []
    supportive_care: list[str] = []
    follow_up_guidance: str = ""
    referral_criteria: str = ""
    disclaimer: str  # Mandatory regulatory disclaimer


# ── AMR / DDI / Safety ───────────────────────────────────────────────────────


class AMRProfile(BaseModel):
    drug: str
    pathogen: str
    region: str
    resistance_pct: float | None
    data_source: str
    year: int | None
    confidence: Literal["high", "medium", "low", "no_data"]
    recommendation: str


class DDIWarning(BaseModel):
    drug_a: str
    drug_b: str
    severity: Literal["contraindicated", "major", "moderate", "minor"]
    mechanism: str
    clinical_effect: str
    management: str


# ── Consultation Response (full pipeline output) ─────────────────────────────


class ConsultationResponse(BaseModel):
    diagnostic: DiagnosticDifferential
    treatments: list[TreatmentPlan] = []
    warnings: list[str] = []
    references: list[dict] = []


# ── Admin Analytics ──────────────────────────────────────────────────────────


class AnalyticsSummary(BaseModel):
    total_sessions: int
    total_turns: int
    avg_latency_ms: float
    top_diagnoses: list[dict]  # [{disease_name, count, avg_confidence}]
    emergency_rate: float  # fraction of turns with emergency flags
    feedback_summary: dict  # {correct: int, partial: int, incorrect: int}
    active_users_24h: int
    cache_hit_rate: float
    period_start: str  # ISO 8601 date
    period_end: str  # ISO 8601 date
