# ─────────────────────────────────────────────────────────────────────────────
# backend/app/models/schemas.py — Consolidated Pydantic domain models
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class TogoRegion(str, Enum):
    """Valid Togo administrative regions."""
    MARITIME = "Maritime"
    PLATEAUX = "Plateaux"
    CENTRALE = "Centrale"
    KARA = "Kara"
    SAVANES = "Savanes"


# ── Patient Context ──────────────────────────────────────────────────────────


class LabResult(BaseModel):
    name: str = Field(max_length=5000)
    value: str = Field(max_length=5000)
    unit: str = Field(max_length=5000)


class Medication(BaseModel):
    name: str = Field(max_length=5000)
    dose: str = Field(max_length=5000)
    frequency: str = Field(max_length=5000)


class VitalSigns(BaseModel):
    temp_c: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    hr: int | None = None
    rr: int | None = None
    spo2: int | None = None
    gcs: int | None = None


class Symptom(BaseModel):
    text: str = Field(max_length=5000)
    normalized: str | None = Field(default=None, max_length=5000)
    snomed_code: str | None = Field(default=None, max_length=5000)


class PatientContext(BaseModel):
    age_years: int
    sex: Literal["M", "F"]
    weight_kg: float | None = None
    region: TogoRegion
    chief_complaint: str = Field(max_length=5000)
    symptoms: list[Symptom] = []
    vital_signs: VitalSigns | None = None
    lab_results: list[LabResult] = []
    current_medications: list[Medication] = []
    allergies: list[str] = []
    pregnancy_status: str = Field(default="not_applicable", max_length=5000)
    symptom_onset_days: int | None = None
    travel_history: list[str] = []


# ── Diagnostic Output ────────────────────────────────────────────────────────


class ConfirmatoryTest(BaseModel):
    name: str = Field(max_length=5000)
    priority: Literal["urgent", "standard", "optional"]
    availability_togo: Literal["disponible", "limité", "indisponible"]
    interpretation: str | None = Field(default=None, max_length=5000)


class DiagnosisItem(BaseModel):
    rank: int
    disease_name: str = Field(max_length=5000)
    icd11_code: str = Field(max_length=5000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str]
    against_evidence: list[str] = []
    confirmatory_tests: list[ConfirmatoryTest] = []
    red_flags: list[str] = []
    citations: list[int] = []


class EmergencyFlag(BaseModel):
    disease: str = Field(max_length=5000)
    level: Literal["critical", "urgent"]
    action: str = Field(max_length=5000)


class DiagnosticDifferential(BaseModel):
    emergency_flags: list[EmergencyFlag] = []
    differential: list[DiagnosisItem]
    clarifying_questions: list[str] = []
    reasoning_summary: str = Field(default="", max_length=5000)
    citations: list[dict] = []


# ── Treatment Output ─────────────────────────────────────────────────────────


class DrugRegimen(BaseModel):
    drug_name: str = Field(max_length=5000)
    generic_name: str = Field(max_length=5000)
    came_available: bool
    dose: str = Field(max_length=5000)
    dose_mg_per_kg: str | None = Field(default=None, max_length=5000)
    route: Literal["PO", "IV", "IM", "SC", "topique"]
    frequency: str = Field(max_length=5000)
    duration_days: int
    pregnancy_class: str | None = Field(default=None, max_length=5000)
    ddi_warnings: list[str] = []
    amr_note: str | None = Field(default=None, max_length=5000)
    monitoring: list[str] = []
    citations: list[int] = []


class Contraindication(BaseModel):
    drug: str = Field(max_length=5000)
    reason: str = Field(max_length=5000)


class TreatmentPlan(BaseModel):
    target_disease: str = Field(max_length=5000)
    clinical_rationale: str = Field(max_length=5000)
    first_line: list[DrugRegimen]
    second_line: list[DrugRegimen] = []
    alternatives: list[DrugRegimen] = []
    contraindicated: list[Contraindication] = []
    supportive_care: list[str] = []
    follow_up_guidance: str = Field(default="", max_length=5000)
    referral_criteria: str = Field(default="", max_length=5000)
    disclaimer: str = Field(max_length=5000)  # Mandatory regulatory disclaimer


# ── AMR / DDI / Safety ───────────────────────────────────────────────────────


class AMRProfile(BaseModel):
    drug: str = Field(max_length=5000)
    pathogen: str = Field(max_length=5000)
    region: str = Field(max_length=5000)
    resistance_pct: float | None
    data_source: str = Field(max_length=5000)
    year: int | None
    confidence: Literal["high", "medium", "low", "no_data"]
    recommendation: str = Field(max_length=5000)


class DDIWarning(BaseModel):
    drug_a: str = Field(max_length=5000)
    drug_b: str = Field(max_length=5000)
    severity: Literal["contraindicated", "major", "moderate", "minor"]
    mechanism: str = Field(max_length=5000)
    clinical_effect: str = Field(max_length=5000)
    management: str = Field(max_length=5000)


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
