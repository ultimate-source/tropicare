# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_audit_pii_hashing.py
#
# Property 11: PII hashing in audit logs
# For any audit payload containing patient-identifiable fields, the
# anonymize_payload function SHALL replace those fields with SHA-256 hashes
# before persistence.
#
# **Validates: Requirement 23.2**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import hashlib
import re

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    dictionaries,
    floats,
    integers,
    just,
    lists,
    none,
    one_of,
    text,
)

from backend.app.orchestrator.audit import PII_FIELDS, anonymize_payload

# ── Helpers ──────────────────────────────────────────────────────────────────

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _is_sha256(value: str) -> bool:
    return bool(SHA256_PATTERN.match(value))


def _expected_hash(value) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=100).filter(lambda s: s.strip() != "")

# Payloads that always contain PII fields
pii_payload = dictionaries(
    keys=just("_extra"),
    values=safe_text,
    min_size=0,
    max_size=0,
).map(lambda _: {
    # Will be overridden by @given draws — this is just a base
})


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    age=integers(min_value=0, max_value=120),
    weight=floats(min_value=0.5, max_value=300.0, allow_nan=False),
    complaint=safe_text,
    allergies=lists(safe_text, min_size=0, max_size=5),
    symptom_texts=lists(safe_text, min_size=0, max_size=5),
)
@settings(max_examples=200, deadline=None)
def test_pii_fields_are_hashed(
    age: int,
    weight: float,
    complaint: str,
    allergies: list[str],
    symptom_texts: list[str],
) -> None:
    """
    **Validates: Requirement 23.2**

    Property 11a: All PII scalar fields (age_years, weight_kg,
    chief_complaint) are replaced with their SHA-256 hash.
    """
    payload = {
        "age_years": age,
        "weight_kg": weight,
        "chief_complaint": complaint,
        "allergies": allergies,
        "symptoms": [{"text": t, "normalized": "x"} for t in symptom_texts],
        "other_field": "should_remain_unchanged",
    }

    result = anonymize_payload(payload)

    # Scalar PII fields are hashed
    assert result["age_years"] == _expected_hash(age)
    assert result["weight_kg"] == _expected_hash(weight)
    assert result["chief_complaint"] == _expected_hash(complaint)

    # List PII field (allergies) — each item hashed
    assert len(result["allergies"]) == len(allergies)
    for original, hashed in zip(allergies, result["allergies"]):
        assert hashed == _expected_hash(original)

    # Symptom text entries are hashed
    assert len(result["symptoms"]) == len(symptom_texts)
    for original_text, symptom in zip(symptom_texts, result["symptoms"]):
        assert symptom["text"] == _expected_hash(original_text)
        # Non-PII symptom fields are preserved
        assert symptom["normalized"] == "x"

    # Non-PII fields are untouched
    assert result["other_field"] == "should_remain_unchanged"


@pytest.mark.property
@given(
    age=integers(min_value=0, max_value=120),
    complaint=safe_text,
)
@settings(max_examples=200, deadline=None)
def test_original_payload_not_mutated(age: int, complaint: str) -> None:
    """
    **Validates: Requirement 23.2**

    Property 11b: The original payload dict is not mutated by anonymization.
    """
    payload = {
        "age_years": age,
        "chief_complaint": complaint,
        "symptoms": [{"text": "headache"}],
    }
    original_age = payload["age_years"]
    original_complaint = payload["chief_complaint"]
    original_symptom_text = payload["symptoms"][0]["text"]

    _ = anonymize_payload(payload)

    assert payload["age_years"] == original_age
    assert payload["chief_complaint"] == original_complaint
    assert payload["symptoms"][0]["text"] == original_symptom_text


@pytest.mark.property
@given(
    extra_key=safe_text.filter(lambda s: s not in PII_FIELDS and s != "symptoms"),
    extra_val=safe_text,
)
@settings(max_examples=200, deadline=None)
def test_non_pii_fields_preserved(extra_key: str, extra_val: str) -> None:
    """
    **Validates: Requirement 23.2**

    Property 11c: Fields that are not in the PII list are passed through
    unchanged.
    """
    payload = {extra_key: extra_val}
    result = anonymize_payload(payload)
    assert result[extra_key] == extra_val
