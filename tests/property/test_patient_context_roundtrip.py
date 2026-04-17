# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_patient_context_roundtrip.py
#
# Property 1: PatientContext serialization round-trip
# For any valid PatientContext object, serializing to JSON and deserializing
# back SHALL produce an object equivalent to the original.
#
# **Validates: Requirements 3.3, 17.4**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    builds,
    floats,
    from_type,
    integers,
    just,
    lists,
    none,
    one_of,
    sampled_from,
    text,
)

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.models.schemas import (
    LabResult,
    Medication,
    PatientContext,
    Symptom,
    VitalSigns,
)

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")

lab_results = builds(
    LabResult,
    name=safe_text,
    value=safe_text,
    unit=safe_text,
)

medications = builds(
    Medication,
    name=safe_text,
    dose=safe_text,
    frequency=safe_text,
)

vital_signs = builds(
    VitalSigns,
    temp_c=one_of(none(), floats(min_value=30.0, max_value=45.0, allow_nan=False)),
    bp_systolic=one_of(none(), integers(min_value=50, max_value=250)),
    bp_diastolic=one_of(none(), integers(min_value=30, max_value=150)),
    hr=one_of(none(), integers(min_value=30, max_value=220)),
    rr=one_of(none(), integers(min_value=5, max_value=60)),
    spo2=one_of(none(), integers(min_value=50, max_value=100)),
    gcs=one_of(none(), integers(min_value=3, max_value=15)),
)

symptoms = builds(
    Symptom,
    text=safe_text,
    normalized=one_of(none(), safe_text),
    snomed_code=one_of(none(), safe_text),
)

patient_context = builds(
    PatientContext,
    age_years=integers(min_value=0, max_value=120),
    sex=sampled_from(["M", "F"]),
    weight_kg=one_of(none(), floats(min_value=0.5, max_value=300.0, allow_nan=False)),
    region=sampled_from(["Maritime", "Plateaux", "Centrale", "Kara", "Savanes"]),
    chief_complaint=safe_text,
    symptoms=lists(symptoms, min_size=0, max_size=5),
    vital_signs=one_of(none(), vital_signs),
    lab_results=lists(lab_results, min_size=0, max_size=3),
    current_medications=lists(medications, min_size=0, max_size=3),
    allergies=lists(safe_text, min_size=0, max_size=3),
    pregnancy_status=sampled_from([
        "not_applicable", "not_pregnant",
        "pregnant_t1", "pregnant_t2", "pregnant_t3", "unknown",
    ]),
    symptom_onset_days=one_of(none(), integers(min_value=0, max_value=365)),
    travel_history=lists(safe_text, min_size=0, max_size=3),
)


# ── Property test ────────────────────────────────────────────────────────────


@pytest.mark.property
@given(ctx=patient_context)
@settings(max_examples=200, deadline=None)
def test_patient_context_roundtrip(ctx: PatientContext) -> None:
    """
    **Validates: Requirements 3.3, 17.4**

    Property 1: PatientContext serialization round-trip.
    Serializing a PatientContext to JSON and deserializing back produces
    an equivalent object.
    """
    json_str = ctx.model_dump_json()
    restored = PatientContext.model_validate_json(json_str)
    assert restored == ctx
