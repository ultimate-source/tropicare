# ─────────────────────────────────────────────────────────────────────────────
# tests/unit/agents/test_diagnostic_agent.py — Unit tests for DiagnosticAgent
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.agents.diagnostic import DiagnosticAgent, _EMERGENCY_CONDITIONS


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_valid_differential_json(
    diseases: list[dict] | None = None,
    emergency_flags: list[dict] | None = None,
) -> str:
    """Return a valid JSON string matching DiagnosticDifferential schema."""
    if diseases is None:
        diseases = [
            {
                "rank": i,
                "disease_name": f"Disease {i}",
                "icd11_code": f"1F4{i}",
                "confidence": round(0.9 - i * 0.1, 2),
                "supporting_evidence": [f"chunk-{i}"],
                "confirmatory_tests": [
                    {
                        "name": f"Test {i}",
                        "priority": "urgent",
                        "availability_togo": "disponible",
                    }
                ],
            }
            for i in range(1, 4)
        ]
    data = {
        "emergency_flags": emergency_flags or [],
        "differential": diseases,
        "reasoning_summary": "Test reasoning",
    }
    return json.dumps(data)


def _make_agent(mcp_mock: AsyncMock | None = None) -> DiagnosticAgent:
    """Create a DiagnosticAgent with mocked dependencies."""
    mcp = mcp_mock or AsyncMock()
    return DiagnosticAgent(api_key="test-key", mcp=mcp)


def _base_patient_context() -> dict:
    return {
        "age_years": 35,
        "sex": "M",
        "region": "Maritime",
        "chief_complaint": "Fièvre depuis 3 jours",
        "symptoms": [
            {"text": "fièvre", "normalized": "fièvre"},
            {"text": "céphalées", "normalized": "céphalées"},
        ],
        "vital_signs": {"temp_c": 39.2, "bp_systolic": 120},
        "lab_results": [],
    }


# ── Test: _parse_output validates through Pydantic ───────────────────────────


@pytest.mark.asyncio
async def test_parse_output_returns_validated_dict():
    """_parse_output should return a dict validated through DiagnosticDifferential."""
    agent = _make_agent()
    raw = _make_valid_differential_json()
    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context={})

    assert isinstance(result, dict)
    assert "differential" in result
    assert "emergency_flags" in result
    assert len(result["differential"]) == 3
    for item in result["differential"]:
        assert "disease_name" in item
        assert "icd11_code" in item
        assert 0.0 <= item["confidence"] <= 1.0
        assert len(item["supporting_evidence"]) >= 1


@pytest.mark.asyncio
async def test_parse_output_rejects_invalid_confidence():
    """Confidence outside [0.0, 1.0] should raise ValidationError."""
    agent = _make_agent()
    diseases = [
        {
            "rank": 1,
            "disease_name": "Bad Disease",
            "icd11_code": "1F40",
            "confidence": 1.5,  # Invalid!
            "supporting_evidence": ["chunk-1"],
        }
    ]
    raw = _make_valid_differential_json(diseases=diseases)
    with pytest.raises(Exception):  # ValidationError from Pydantic
        await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context={})


@pytest.mark.asyncio
async def test_parse_output_truncates_to_5_items():
    """Differential with >5 items should be truncated to 5."""
    agent = _make_agent()
    diseases = [
        {
            "rank": i,
            "disease_name": f"Disease {i}",
            "icd11_code": f"1F4{i}",
            "confidence": round(0.95 - i * 0.05, 2),
            "supporting_evidence": [f"chunk-{i}"],
        }
        for i in range(1, 8)  # 7 items
    ]
    raw = _make_valid_differential_json(diseases=diseases)
    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context={})
    assert len(result["differential"]) == 5


# ── Test: Emergency flag detection from patient context ──────────────────────


@pytest.mark.asyncio
async def test_emergency_detection_meningitis_from_symptoms():
    """Meningitis keywords in patient symptoms should trigger emergency flag."""
    agent = _make_agent()
    ctx = _base_patient_context()
    ctx["symptoms"].append({"text": "raideur de la nuque", "normalized": "raideur nuque"})

    raw = _make_valid_differential_json()
    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context=ctx)

    flags = result["emergency_flags"]
    meningitis_flags = [f for f in flags if "méningite" in f["disease"].lower()]
    assert len(meningitis_flags) >= 1
    assert meningitis_flags[0]["level"] == "critical"


@pytest.mark.asyncio
async def test_emergency_detection_severe_malaria_from_symptoms():
    """Severe malaria keywords in patient context should trigger emergency flag."""
    agent = _make_agent()
    ctx = _base_patient_context()
    ctx["chief_complaint"] = "Paludisme grave avec convulsions"

    raw = _make_valid_differential_json()
    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context=ctx)

    flags = result["emergency_flags"]
    malaria_flags = [f for f in flags if "paludisme" in f["disease"].lower()]
    assert len(malaria_flags) >= 1


@pytest.mark.asyncio
async def test_emergency_detection_hemorrhagic_fever_from_llm_output():
    """Hemorrhagic fever keywords in LLM output should trigger emergency flag."""
    agent = _make_agent()
    diseases = [
        {
            "rank": 1,
            "disease_name": "Fièvre de Lassa",
            "icd11_code": "1D6Y",
            "confidence": 0.75,
            "supporting_evidence": ["chunk-1"],
        },
    ]
    # The raw output mentions "fièvre hémorragique virale"
    raw_json = _make_valid_differential_json(diseases=diseases)
    raw = f"Pensée: Le patient présente une fièvre hémorragique virale possible.\n{raw_json}"

    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context={})

    flags = result["emergency_flags"]
    vhf_flags = [f for f in flags if "hémorragique" in f["disease"].lower()]
    assert len(vhf_flags) >= 1


@pytest.mark.asyncio
async def test_emergency_detection_septic_shock_from_vitals():
    """Hypotension + fever in vital signs should trigger septic shock detection."""
    agent = _make_agent()
    ctx = _base_patient_context()
    ctx["vital_signs"] = {"temp_c": 40.0, "bp_systolic": 75}  # Hypotension + fever

    raw = _make_valid_differential_json()
    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context=ctx)

    flags = result["emergency_flags"]
    shock_flags = [f for f in flags if "septique" in f["disease"].lower()]
    assert len(shock_flags) >= 1


@pytest.mark.asyncio
async def test_emergency_no_duplicates():
    """If LLM already flagged an emergency, patient context detection should not duplicate it."""
    agent = _make_agent()
    ctx = _base_patient_context()
    ctx["symptoms"].append({"text": "raideur de la nuque"})

    existing_flags = [{"disease": "Méningite bactérienne", "level": "critical", "action": "Transfert"}]
    raw = _make_valid_differential_json(emergency_flags=existing_flags)
    result = await agent._parse_output(raw, citations=[], epid_alerts=[], patient_context=ctx)

    meningitis_flags = [f for f in result["emergency_flags"] if "méningite" in f["disease"].lower()]
    assert len(meningitis_flags) == 1  # No duplicate


@pytest.mark.asyncio
async def test_epid_alerts_injected_as_emergency_flags():
    """Epidemiological outbreak alerts should be injected as emergency flags."""
    agent = _make_agent()
    raw = _make_valid_differential_json()
    result = await agent._parse_output(
        raw, citations=[], epid_alerts=["Choléra"], patient_context={}
    )

    flags = result["emergency_flags"]
    cholera_flags = [f for f in flags if "Choléra" in f["disease"]]
    assert len(cholera_flags) == 1
    assert cholera_flags[0]["level"] == "urgent"


# ── Test: JSON retry logic ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_output_raises_on_invalid_json():
    """_parse_output should raise ValueError on non-JSON input."""
    agent = _make_agent()
    with pytest.raises(ValueError):
        await agent._parse_output("This is not JSON at all", citations=[], patient_context={})


@pytest.mark.asyncio
async def test_execute_retries_on_invalid_json():
    """_execute should retry LLM call once when first output is invalid JSON."""
    mcp = AsyncMock()
    mcp.call = AsyncMock(side_effect=lambda tool, **kw: {
        "epid_calendar": {"disease_priors": {}, "outbreak_alerts": []},
        "hybrid_retrieve": [],
        "citation_formatter": [],
    }.get(tool, {}))

    agent = _make_agent(mcp)

    valid_json = _make_valid_differential_json()
    # First call returns garbage, second returns valid JSON
    agent._call_claude = AsyncMock(side_effect=[
        ("Not valid JSON here", {"input_tokens": 10, "output_tokens": 10}),
        (valid_json, {"input_tokens": 10, "output_tokens": 10}),
    ])

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        query="Diagnostic différentiel",
    )

    assert result is not None
    assert "differential" in result
    assert agent._call_claude.call_count == 2  # Initial + retry


@pytest.mark.asyncio
async def test_execute_degrades_gracefully_after_retry_failure():
    """_execute should return partial result with warnings when both attempts produce invalid JSON."""
    mcp = AsyncMock()
    mcp.call = AsyncMock(side_effect=lambda tool, **kw: {
        "epid_calendar": {"disease_priors": {}, "outbreak_alerts": []},
        "hybrid_retrieve": [],
        "citation_formatter": [],
    }.get(tool, {}))

    agent = _make_agent(mcp)

    # Both calls return garbage
    agent._call_claude = AsyncMock(return_value=(
        "Still not JSON", {"input_tokens": 10, "output_tokens": 10}
    ))

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        query="Diagnostic différentiel",
    )

    # Should return a partial result instead of raising
    assert result is not None
    assert isinstance(result, dict)
    # Should have tool warnings about the JSON parsing failure
    assert "_tool_warnings" in result
    assert len(result["_tool_warnings"]) > 0


# ── Test: ReAct loop ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_react_loop_retrieves_on_signal():
    """ReAct loop should perform additional retrieval when RETRIEVE: signal is detected."""
    mcp = AsyncMock()
    call_count = {"hybrid_retrieve": 0}

    async def mock_mcp_call(tool, **kw):
        if tool == "epid_calendar":
            return {"disease_priors": {}, "outbreak_alerts": []}
        if tool == "hybrid_retrieve":
            call_count["hybrid_retrieve"] += 1
            return [{"chunk_id": f"c{call_count['hybrid_retrieve']}", "score": 0.8, "chunk_text": "test"}]
        if tool == "citation_formatter":
            return []
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    valid_json = _make_valid_differential_json()
    # First call has RETRIEVE signal, second returns final answer
    agent._call_claude = AsyncMock(side_effect=[
        (
            "Pensée 1: Je dois chercher plus.\nRETRIEVE: paludisme traitement Togo\n",
            {"input_tokens": 10, "output_tokens": 10},
        ),
        (valid_json, {"input_tokens": 10, "output_tokens": 10}),
    ])

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        query="Diagnostic",
    )

    assert result is not None
    # Should have initial 3 hybrid_retrieve calls + 1 ReAct retrieval
    react_retrieves = [tc for tc in tool_calls if tc == "hybrid_retrieve"]
    assert len(react_retrieves) >= 3  # At least the initial 2 + 1 ReAct


# ── Test: hybrid_retrieve with ≥2 query expansions ──────────────────────────


@pytest.mark.asyncio
async def test_hybrid_retrieve_at_least_2_expansions():
    """hybrid_retrieve should be called with at least 2 query expansions (symptom + epid)."""
    mcp = AsyncMock()
    retrieve_queries = []

    async def mock_mcp_call(tool, **kw):
        if tool == "epid_calendar":
            return {"disease_priors": {}, "outbreak_alerts": []}
        if tool == "hybrid_retrieve":
            retrieve_queries.append(kw.get("query", ""))
            return []
        if tool == "citation_formatter":
            return []
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    valid_json = _make_valid_differential_json()
    agent._call_claude = AsyncMock(return_value=(
        valid_json, {"input_tokens": 10, "output_tokens": 10}
    ))

    await agent._execute(
        patient_context=_base_patient_context(),
        query="Fièvre et céphalées",
    )

    # Should have at least 2 queries: symptom-based and epidemiological
    assert len(retrieve_queries) >= 2
    # One should contain symptom text, another should contain epidemiological context
    all_queries = " ".join(retrieve_queries)
    assert "Togo" in all_queries or "saison" in all_queries  # epid query


# ── Test: Full _execute flow with mocked MCP produces valid ICD-11 + confidence (Req 16.1) ──


@pytest.mark.asyncio
async def test_execute_happy_path_produces_valid_icd11_and_confidence():
    """Full _execute with mocked MCP tools should return differential with valid ICD-11 codes and confidence scores."""
    mcp = AsyncMock()

    async def mock_mcp_call(tool, **kw):
        if tool == "epid_calendar":
            return {
                "disease_priors": {"Paludisme": 0.6, "Typhoïde": 0.2},
                "outbreak_alerts": [],
            }
        if tool == "hybrid_retrieve":
            return [
                {"chunk_id": "chunk-001", "score": 0.92, "chunk_text": "Paludisme à P. falciparum — fièvre, céphalées, frissons"},
                {"chunk_id": "chunk-002", "score": 0.85, "chunk_text": "Fièvre typhoïde — fièvre prolongée, douleurs abdominales"},
            ]
        if tool == "citation_formatter":
            return [{"ref_id": 1, "source_title": "OMS Guidelines", "section": "Paludisme"}]
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    # LLM returns a well-formed differential with ICD-11 codes
    diseases = [
        {
            "rank": 1,
            "disease_name": "Paludisme à P. falciparum",
            "icd11_code": "1F40",
            "confidence": 0.85,
            "supporting_evidence": ["chunk-001"],
            "confirmatory_tests": [
                {"name": "TDR Paludisme", "priority": "urgent", "availability_togo": "disponible"}
            ],
        },
        {
            "rank": 2,
            "disease_name": "Fièvre typhoïde",
            "icd11_code": "1A07",
            "confidence": 0.60,
            "supporting_evidence": ["chunk-002"],
            "confirmatory_tests": [
                {"name": "Hémoculture", "priority": "standard", "availability_togo": "limité"}
            ],
        },
        {
            "rank": 3,
            "disease_name": "Dengue",
            "icd11_code": "1D20",
            "confidence": 0.30,
            "supporting_evidence": ["chunk-001"],
        },
    ]
    valid_json = _make_valid_differential_json(diseases=diseases)
    agent._call_claude = AsyncMock(return_value=(
        valid_json, {"input_tokens": 100, "output_tokens": 200}
    ))

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        query="Fièvre depuis 3 jours avec céphalées",
    )

    # Verify result structure
    assert result is not None
    assert "differential" in result
    assert "emergency_flags" in result
    assert len(result["differential"]) == 3

    # Verify each diagnosis has valid ICD-11 code and confidence score
    for item in result["differential"]:
        assert "icd11_code" in item
        assert isinstance(item["icd11_code"], str)
        assert len(item["icd11_code"]) >= 3  # ICD-11 codes are at least 3 chars
        assert "confidence" in item
        assert 0.0 <= item["confidence"] <= 1.0
        assert "disease_name" in item
        assert len(item["disease_name"]) > 0
        assert "supporting_evidence" in item
        assert len(item["supporting_evidence"]) >= 1

    # Verify MCP tools were called
    assert "epid_calendar" in tool_calls
    assert "hybrid_retrieve" in tool_calls
    assert "citation_formatter" in tool_calls

    # Verify usage tracking
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0
