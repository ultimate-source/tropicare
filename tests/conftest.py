# ─────────────────────────────────────────────────────────────────────────────
# tests/conftest.py — Shared fixtures for the TropiCare test suite
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.app.agents.base import MCPClient
from backend.app.models.schemas import (
    DiagnosisItem,
    DiagnosticDifferential,
    DrugRegimen,
    EmergencyFlag,
    LabResult,
    Medication,
    PatientContext,
    Symptom,
    TreatmentPlan,
    VitalSigns,
)


# ── Domain object factories ──────────────────────────────────────────────────


@pytest.fixture()
def sample_patient_context() -> PatientContext:
    """Minimal valid PatientContext for a febrile adult in Maritime region."""
    return PatientContext(
        age_years=35,
        sex="M",
        weight_kg=70.0,
        region="Maritime",
        chief_complaint="Fièvre depuis 3 jours avec céphalées",
        symptoms=[Symptom(text="fièvre"), Symptom(text="céphalées")],
        vital_signs=VitalSigns(temp_c=39.2, hr=98, bp_systolic=120, bp_diastolic=75),
        lab_results=[LabResult(name="TDR Paludisme", value="positif", unit="qual")],
        current_medications=[],
        allergies=[],
        pregnancy_status="not_applicable",
        symptom_onset_days=3,
        travel_history=[],
    )


@pytest.fixture()
def sample_pediatric_patient() -> PatientContext:
    """Pediatric patient for dosage-related tests."""
    return PatientContext(
        age_years=4,
        sex="F",
        weight_kg=16.0,
        region="Kara",
        chief_complaint="Fièvre et vomissements",
        symptoms=[Symptom(text="fièvre"), Symptom(text="vomissements")],
        vital_signs=VitalSigns(temp_c=39.8),
        lab_results=[],
        current_medications=[],
        allergies=[],
        pregnancy_status="not_applicable",
        symptom_onset_days=2,
        travel_history=[],
    )


@pytest.fixture()
def sample_pregnant_patient() -> PatientContext:
    """Pregnant patient for safety-filtering tests."""
    return PatientContext(
        age_years=28,
        sex="F",
        weight_kg=62.0,
        region="Plateaux",
        chief_complaint="Infection urinaire",
        symptoms=[Symptom(text="dysurie"), Symptom(text="pollakiurie")],
        pregnancy_status="T2",
    )


@pytest.fixture()
def sample_diagnosis_item() -> DiagnosisItem:
    """Single valid DiagnosisItem."""
    return DiagnosisItem(
        rank=1,
        disease_name="Paludisme à P. falciparum",
        icd11_code="1F40",
        confidence=0.85,
        supporting_evidence=["chunk-abc-123"],
        confirmatory_tests=[],
    )


@pytest.fixture()
def sample_diagnostic_differential(sample_diagnosis_item: DiagnosisItem) -> DiagnosticDifferential:
    """Minimal valid DiagnosticDifferential."""
    return DiagnosticDifferential(differential=[sample_diagnosis_item])


@pytest.fixture()
def sample_drug_regimen() -> DrugRegimen:
    """Single valid DrugRegimen for artemether-lumefantrine."""
    return DrugRegimen(
        drug_name="Coartem",
        generic_name="Artéméther-Luméfantrine",
        came_available=True,
        dose="80/480 mg",
        route="PO",
        frequency="2x/jour pendant 3 jours",
        duration_days=3,
    )


@pytest.fixture()
def sample_treatment_plan(sample_drug_regimen: DrugRegimen) -> TreatmentPlan:
    """Minimal valid TreatmentPlan with mandatory disclaimer."""
    return TreatmentPlan(
        target_disease="Paludisme simple à P. falciparum",
        clinical_rationale="Protocole PNLP première ligne",
        first_line=[sample_drug_regimen],
        disclaimer=(
            "⚠️ AIDE À LA DÉCISION UNIQUEMENT — Ce contenu est généré par "
            "intelligence artificielle et ne remplace pas le jugement clinique."
        ),
    )


@pytest.fixture()
def sample_emergency_flag() -> EmergencyFlag:
    """Emergency flag for severe malaria."""
    return EmergencyFlag(
        disease="Paludisme grave",
        level="critical",
        action="Transfert immédiat et artésunate IV",
    )


# ── Mock services ────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_mcp_client() -> MCPClient:
    """MCPClient with all tool calls mocked via AsyncMock."""
    client = MCPClient(base_url="http://test-mcp:8001")
    client.call = AsyncMock(return_value={})
    return client
