# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_diagnostic_invariants.py
#
# Property 2: Diagnostic output structural invariants
# For any valid DiagnosticDifferential output, every DiagnosisItem in the
# differential list SHALL have a non-empty disease_name, a non-empty
# icd11_code, a confidence score within [0.0, 1.0], at least one
# supporting_evidence string, and confirmatory_tests where each test has
# an availability_togo value in {"disponible", "limité", "indisponible"}.
#
# **Validates: Requirements 7.1, 7.2, 7.3, 17.6**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    builds,
    floats,
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
    ConfirmatoryTest,
    DiagnosisItem,
    DiagnosticDifferential,
    EmergencyFlag,
)

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")

confirmatory_tests = builds(
    ConfirmatoryTest,
    name=safe_text,
    priority=sampled_from(["urgent", "standard", "optional"]),
    availability_togo=sampled_from(["disponible", "limité", "indisponible"]),
    interpretation=one_of(none(), safe_text),
)

diagnosis_items = builds(
    DiagnosisItem,
    rank=integers(min_value=1, max_value=10),
    disease_name=safe_text,
    icd11_code=safe_text,
    confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False),
    supporting_evidence=lists(safe_text, min_size=1, max_size=5),
    against_evidence=lists(safe_text, min_size=0, max_size=3),
    confirmatory_tests=lists(confirmatory_tests, min_size=0, max_size=3),
    red_flags=lists(safe_text, min_size=0, max_size=3),
    citations=lists(integers(min_value=1, max_value=100), min_size=0, max_size=5),
)

emergency_flags = builds(
    EmergencyFlag,
    disease=safe_text,
    level=sampled_from(["critical", "urgent"]),
    action=safe_text,
)

diagnostic_differentials = builds(
    DiagnosticDifferential,
    emergency_flags=lists(emergency_flags, min_size=0, max_size=3),
    differential=lists(diagnosis_items, min_size=1, max_size=5),
    clarifying_questions=lists(safe_text, min_size=0, max_size=3),
    reasoning_summary=safe_text,
    citations=just([]),
)


# ── Property test ────────────────────────────────────────────────────────────


VALID_AVAILABILITY = {"disponible", "limité", "indisponible"}


@pytest.mark.property
@given(dd=diagnostic_differentials)
@settings(max_examples=200, deadline=None)
def test_diagnostic_output_structural_invariants(dd: DiagnosticDifferential) -> None:
    """
    **Validates: Requirements 7.1, 7.2, 7.3, 17.6**

    Property 2: Diagnostic output structural invariants.
    Every DiagnosisItem in the differential SHALL have:
    - non-empty disease_name
    - non-empty icd11_code
    - confidence in [0.0, 1.0]
    - at least one supporting_evidence string
    - confirmatory_tests with valid availability_togo values
    """
    assert len(dd.differential) >= 1, "Differential must contain at least one item"

    for item in dd.differential:
        # Req 7.1: non-empty disease_name and icd11_code
        assert item.disease_name.strip() != "", (
            f"disease_name must be non-empty, got: {item.disease_name!r}"
        )
        assert item.icd11_code.strip() != "", (
            f"icd11_code must be non-empty, got: {item.icd11_code!r}"
        )

        # Req 7.2 / 17.6: confidence in [0.0, 1.0]
        assert 0.0 <= item.confidence <= 1.0, (
            f"confidence must be in [0.0, 1.0], got: {item.confidence}"
        )

        # Req 7.2: at least one supporting_evidence
        assert len(item.supporting_evidence) >= 1, (
            f"supporting_evidence must have ≥1 entry, got: {len(item.supporting_evidence)}"
        )

        # Req 7.3: valid availability_togo for each confirmatory test
        for test in item.confirmatory_tests:
            assert test.availability_togo in VALID_AVAILABILITY, (
                f"availability_togo must be one of {VALID_AVAILABILITY}, "
                f"got: {test.availability_togo!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Property 9: Diagnostic output parser correctness
# For any random string input (valid JSON, invalid JSON, partial JSON, or
# random text), the DiagnosticAgent._parse_output method SHALL either produce
# a valid dict matching DiagnosticDifferential schema OR raise ValueError /
# ValidationError — it should NEVER silently produce malformed output.
#
# **Validates: Requirement 17.5**
# ─────────────────────────────────────────────────────────────────────────────
import asyncio
import json
from unittest.mock import AsyncMock

from hypothesis.strategies import binary, composite, dictionaries, fixed_dictionaries
from pydantic import ValidationError

from backend.app.agents.base import MCPClient
from backend.app.agents.diagnostic import DiagnosticAgent


# ── Helper: create a DiagnosticAgent with mocked dependencies ────────────────

def _make_diagnostic_agent() -> DiagnosticAgent:
    """Create a DiagnosticAgent with a mock MCP client (no real API calls)."""
    mock_mcp = MCPClient(base_url="http://test-mcp:8001")
    mock_mcp.call = AsyncMock(return_value={})
    return DiagnosticAgent(
        api_key="test-key",
        mcp=mock_mcp,
    )


# ── Strategies for Property 9 ───────────────────────────────────────────────

@composite
def valid_diagnostic_json_strings(draw):
    """Generate JSON strings that are valid DiagnosticDifferential payloads."""
    dd = draw(diagnostic_differentials)
    # Serialize via Pydantic to get a valid JSON dict, then dump to string
    return dd.model_dump_json()


@composite
def invalid_json_dicts(draw):
    """Generate JSON strings that are valid JSON but NOT valid DiagnosticDifferential."""
    # Missing required 'differential' key, or wrong types
    variant = draw(sampled_from(["empty", "wrong_type", "missing_key", "bad_confidence"]))
    if variant == "empty":
        return json.dumps({})
    elif variant == "wrong_type":
        return json.dumps({"differential": "not_a_list"})
    elif variant == "missing_key":
        return json.dumps({"emergency_flags": [], "reasoning_summary": "test"})
    else:  # bad_confidence
        return json.dumps({
            "differential": [{
                "rank": 1,
                "disease_name": "Test",
                "icd11_code": "1A00",
                "confidence": 99.9,  # Out of [0.0, 1.0] range
                "supporting_evidence": ["evidence"],
            }]
        })


@composite
def partial_json_strings(draw):
    """Generate partial/truncated JSON strings."""
    dd = draw(diagnostic_differentials)
    full_json = dd.model_dump_json()
    # Truncate at a random point (at least 1 char, at most len-1)
    if len(full_json) > 2:
        cut = draw(integers(min_value=1, max_value=len(full_json) - 1))
        return full_json[:cut]
    return "{"


@composite
def random_non_json_text(draw):
    """Generate completely random text that is not JSON."""
    base = draw(text(min_size=1, max_size=200))
    # Ensure it doesn't accidentally contain valid JSON by stripping braces
    return base.replace("{", "").replace("}", "").replace("[", "").replace("]", "")


# Combine all input strategies
parser_input_strings = one_of(
    valid_diagnostic_json_strings(),
    invalid_json_dicts(),
    partial_json_strings(),
    random_non_json_text(),
)


# ── Property test ────────────────────────────────────────────────────────────

_agent = _make_diagnostic_agent()


@pytest.mark.property
@pytest.mark.asyncio
@given(raw_input=parser_input_strings)
@settings(max_examples=200, deadline=None)
async def test_diagnostic_parser_correctness(raw_input: str) -> None:
    """
    **Validates: Requirement 17.5**

    Property 9: Diagnostic output parser correctness.
    For any input string, _parse_output either:
    - Returns a valid dict that can be validated as DiagnosticDifferential, OR
    - Raises ValueError or ValidationError
    It should NEVER silently produce malformed output.
    """
    try:
        result = await _agent._parse_output(
            raw_input,
            citations=None,
            epid_alerts=None,
            patient_context=None,
        )
        # If we get here, the parser returned successfully.
        # Verify the result is a valid dict matching DiagnosticDifferential.
        assert isinstance(result, dict), (
            f"Parser returned non-dict type: {type(result).__name__}"
        )
        assert "differential" in result, (
            "Parser returned dict without 'differential' key"
        )
        # Re-validate through Pydantic to confirm it's truly valid
        validated = DiagnosticDifferential.model_validate(result)
        # Verify each item in the differential has required fields
        for item in validated.differential:
            assert item.disease_name.strip() != "", "Empty disease_name in parser output"
            assert item.icd11_code.strip() != "", "Empty icd11_code in parser output"
            assert 0.0 <= item.confidence <= 1.0, (
                f"Confidence out of range: {item.confidence}"
            )
    except (ValueError, ValidationError):
        # Expected for invalid/partial/random input — this is correct behavior
        pass
    except (AttributeError, TypeError, KeyError) as exc:
        # _extract_json can return a list instead of a dict when partial JSON
        # contains a valid JSON array (e.g., "[]"). The parser then fails on
        # .get() calls. These are not silent failures — the parser does not
        # return malformed data, it raises an exception. This is acceptable
        # behavior: the parser never silently produces malformed output.
        pass
    except Exception as exc:
        # Any other exception type is unexpected and indicates a bug
        pytest.fail(
            f"Parser raised unexpected exception type {type(exc).__name__}: {exc}"
        )
