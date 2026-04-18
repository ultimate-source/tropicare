# ─────────────────────────────────────────────────────────────────────────────
# tests/unit/agents/test_antibiotherapy_agent.py — Unit tests for
# AntibiotherapyAgent: AMR deprioritization, pediatric dosage, pregnancy
# safety filtering, DDI severity-tagged warnings, retry-once, disclaimer.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from backend.app.agents.antibiotherapy import (
    AntibiotherapyAgent,
    MANDATORY_DISCLAIMER,
    _AMR_RESISTANCE_THRESHOLD,
    _SAFE_PREGNANCY_CATEGORIES,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_valid_treatment_json(
    first_line: list[dict] | None = None,
    second_line: list[dict] | None = None,
    alternatives: list[dict] | None = None,
) -> str:
    """Return a valid JSON string matching TreatmentPlan schema."""
    if first_line is None:
        first_line = [
            {
                "drug_name": "Coartem",
                "generic_name": "artéméther-luméfantrine",
                "came_available": True,
                "dose": "480 mg",
                "route": "PO",
                "frequency": "2x/jour",
                "duration_days": 3,
            }
        ]
    data = {
        "target_disease": "Paludisme simple",
        "clinical_rationale": "Protocole PNLP première ligne",
        "first_line": first_line,
        "second_line": second_line or [],
        "alternatives": alternatives or [],
        "contraindicated": [],
        "supportive_care": ["Hydratation"],
        "follow_up_guidance": "Contrôle J3",
        "referral_criteria": "",
        "disclaimer": "placeholder",
    }
    return json.dumps(data)


def _make_agent(mcp_mock: AsyncMock | None = None) -> AntibiotherapyAgent:
    mcp = mcp_mock or AsyncMock()
    return AntibiotherapyAgent(api_key="test-key", mcp=mcp)


def _base_patient_context() -> dict:
    return {
        "age_years": 35,
        "sex": "M",
        "weight_kg": 70.0,
        "region": "Maritime",
        "chief_complaint": "Fièvre depuis 3 jours",
        "symptoms": [{"text": "fièvre", "normalized": "fièvre"}],
        "current_medications": [],
        "allergies": [],
        "pregnancy_status": "not_pregnant",
    }


# ── Test: Mandatory disclaimer ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_output_always_sets_mandatory_disclaimer():
    """_parse_output must always set the MANDATORY_DISCLAIMER."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()
    result = await agent._parse_output(raw, patient_context=_base_patient_context())

    assert result["disclaimer"] == MANDATORY_DISCLAIMER
    assert result["disclaimer"].startswith("⚠️ AIDE À LA DÉCISION UNIQUEMENT")


# ── Test: AMR deprioritization (Req 9.3) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_amr_deprioritizes_high_resistance_drugs_from_first_line():
    """Drugs with >30% resistance should be moved from first_line to alternatives."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "Cipro",
            "generic_name": "ciprofloxacine",
            "came_available": True,
            "dose": "500 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 7,
        },
        {
            "drug_name": "Coartem",
            "generic_name": "artéméther-luméfantrine",
            "came_available": True,
            "dose": "480 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 3,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    amr_results = [
        {"drug": "ciprofloxacine", "resistance_pct": 45.0, "pathogen": "E. coli", "region": "Togo"},
    ]

    result = await agent._parse_output(
        raw,
        amr_results=amr_results,
        patient_context=_base_patient_context(),
    )

    first_generics = [d["generic_name"].lower() for d in result["first_line"]]
    alt_generics = [d["generic_name"].lower() for d in result["alternatives"]]

    assert "ciprofloxacine" not in first_generics
    assert "ciprofloxacine" in alt_generics
    assert "artéméther-luméfantrine" in first_generics


@pytest.mark.asyncio
async def test_amr_note_attached_to_high_resistance_drugs():
    """High-resistance drugs should have an amr_note explaining the deprioritization."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "Cipro",
            "generic_name": "ciprofloxacine",
            "came_available": True,
            "dose": "500 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 7,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    amr_results = [
        {"drug": "ciprofloxacine", "resistance_pct": 50.0, "pathogen": "E. coli", "region": "Togo"},
    ]

    result = await agent._parse_output(
        raw,
        amr_results=amr_results,
        patient_context=_base_patient_context(),
    )

    # Drug should be in alternatives with amr_note
    cipro = next(d for d in result["alternatives"] if d["generic_name"].lower() == "ciprofloxacine")
    assert cipro["amr_note"] is not None
    assert "50%" in cipro["amr_note"]


@pytest.mark.asyncio
async def test_amr_below_threshold_stays_in_first_line():
    """Drugs with ≤30% resistance should remain in first_line."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()

    amr_results = [
        {"drug": "artéméther-luméfantrine", "resistance_pct": 10.0, "pathogen": "P. falciparum", "region": "Togo"},
    ]

    result = await agent._parse_output(
        raw,
        amr_results=amr_results,
        patient_context=_base_patient_context(),
    )

    first_generics = [d["generic_name"].lower() for d in result["first_line"]]
    assert "artéméther-luméfantrine" in first_generics


# ── Test: Pediatric dosage calculation (Req 10.1) ────────────────────────────


@pytest.mark.asyncio
async def test_pediatric_dose_calculated_for_child():
    """For pediatric patients (age < 18 with weight), dose_mg_per_kg should be calculated."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()

    ctx = _base_patient_context()
    ctx["age_years"] = 5
    ctx["weight_kg"] = 20.0

    result = await agent._parse_output(raw, patient_context=ctx)

    drug = result["first_line"][0]
    # 480 mg / 20 kg = 24.0 mg/kg
    assert drug["dose_mg_per_kg"] == "24.0 mg/kg"


@pytest.mark.asyncio
async def test_no_pediatric_dose_for_adult():
    """For adult patients (age >= 18), dose_mg_per_kg should not be overwritten."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()

    ctx = _base_patient_context()
    ctx["age_years"] = 35
    ctx["weight_kg"] = 70.0

    result = await agent._parse_output(raw, patient_context=ctx)

    drug = result["first_line"][0]
    assert drug["dose_mg_per_kg"] is None


@pytest.mark.asyncio
async def test_pediatric_dose_no_mg_in_dose_string():
    """If dose string has no mg value, dose_mg_per_kg should be None."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "SRO",
            "generic_name": "sels de réhydratation",
            "came_available": True,
            "dose": "1 sachet",
            "route": "PO",
            "frequency": "après chaque selle",
            "duration_days": 5,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    ctx = _base_patient_context()
    ctx["age_years"] = 3
    ctx["weight_kg"] = 14.0

    result = await agent._parse_output(raw, patient_context=ctx)
    assert result["first_line"][0]["dose_mg_per_kg"] is None


# ── Test: Pregnancy safety filtering (Req 10.2) ──────────────────────────────


@pytest.mark.asyncio
async def test_pregnancy_filters_out_fda_d_and_x_drugs():
    """For pregnant patients, FDA D and X drugs should be removed from all tiers."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "Amoxicilline",
            "generic_name": "amoxicilline",
            "came_available": True,
            "dose": "500 mg",
            "route": "PO",
            "frequency": "3x/jour",
            "duration_days": 7,
        },
        {
            "drug_name": "Doxycycline",
            "generic_name": "doxycycline",
            "came_available": True,
            "dose": "100 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 7,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    safety_classes = [
        {"drug": "amoxicilline", "pregnancy_category": "B", "lactation_safe": True},
        {"drug": "doxycycline", "pregnancy_category": "D", "lactation_safe": False},
    ]

    ctx = _base_patient_context()
    ctx["pregnancy_status"] = "pregnant_t2"

    result = await agent._parse_output(
        raw,
        safety_classes=safety_classes,
        patient_context=ctx,
    )

    first_generics = [d["generic_name"].lower() for d in result["first_line"]]
    assert "amoxicilline" in first_generics
    assert "doxycycline" not in first_generics


@pytest.mark.asyncio
async def test_pregnancy_keeps_abc_drugs():
    """For pregnant patients, FDA A, B, C drugs should remain."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "Amoxicilline",
            "generic_name": "amoxicilline",
            "came_available": True,
            "dose": "500 mg",
            "route": "PO",
            "frequency": "3x/jour",
            "duration_days": 7,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    safety_classes = [
        {"drug": "amoxicilline", "pregnancy_category": "B"},
    ]

    ctx = _base_patient_context()
    ctx["pregnancy_status"] = "pregnant_t1"

    result = await agent._parse_output(
        raw,
        safety_classes=safety_classes,
        patient_context=ctx,
    )

    assert len(result["first_line"]) == 1
    assert result["first_line"][0]["pregnancy_class"] == "B"


@pytest.mark.asyncio
async def test_no_pregnancy_filtering_for_non_pregnant():
    """Non-pregnant patients should not have drugs filtered by pregnancy category."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "Doxycycline",
            "generic_name": "doxycycline",
            "came_available": True,
            "dose": "100 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 7,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    safety_classes = [
        {"drug": "doxycycline", "pregnancy_category": "D"},
    ]

    result = await agent._parse_output(
        raw,
        safety_classes=safety_classes,
        patient_context=_base_patient_context(),
    )

    assert len(result["first_line"]) == 1  # Not filtered


# ── Test: DDI severity-tagged warnings (Req 10.3) ────────────────────────────


@pytest.mark.asyncio
async def test_ddi_warnings_attached_to_drug_regimens():
    """DDI warnings should be attached as severity-tagged strings to relevant drugs."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()

    ddi_warnings = [
        {
            "drug_a": "artéméther-luméfantrine",
            "drug_b": "métronidazole",
            "severity": "major",
            "mechanism": "QT prolongation",
            "clinical_effect": "Risque arythmie",
            "management": "Surveillance ECG",
        },
    ]

    result = await agent._parse_output(
        raw,
        ddi_warnings=ddi_warnings,
        patient_context=_base_patient_context(),
    )

    drug = result["first_line"][0]
    assert len(drug["ddi_warnings"]) >= 1
    warning = drug["ddi_warnings"][0]
    assert "MAJOR" in warning
    assert "⛔" in warning


@pytest.mark.asyncio
async def test_ddi_warnings_include_severity_icon():
    """DDI warnings should include the correct severity icon."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()

    ddi_warnings = [
        {
            "drug_a": "artéméther-luméfantrine",
            "drug_b": "warfarine",
            "severity": "contraindicated",
            "mechanism": "test",
            "clinical_effect": "test effect",
            "management": "test mgmt",
        },
    ]

    result = await agent._parse_output(
        raw,
        ddi_warnings=ddi_warnings,
        patient_context=_base_patient_context(),
    )

    drug = result["first_line"][0]
    assert any("🚫" in w and "CONTRAINDICATED" in w for w in drug["ddi_warnings"])


# ── Test: Retry-once on invalid JSON ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_retries_on_invalid_json():
    """_execute should retry LLM call once when first output is invalid JSON."""
    mcp = AsyncMock()
    mcp.call = AsyncMock(side_effect=lambda tool, **kw: {
        "hybrid_retrieve": [],
        "formulary_lookup": {"generic_name": "test", "available": True, "dosage_forms": []},
        "amr_lookup": {"drug": "test", "resistance_pct": 5.0, "pathogen": "test", "region": "Togo"},
        "drug_ddi_check": [],
        "safety_classifier": {},
        "citation_formatter": [],
    }.get(tool, {}))

    agent = _make_agent(mcp)

    valid_json = _make_valid_treatment_json()
    agent._call_claude = AsyncMock(side_effect=[
        ("Not valid JSON here", {"input_tokens": 10, "output_tokens": 10}),
        (valid_json, {"input_tokens": 10, "output_tokens": 10}),
    ])

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        confirmed_diagnosis="Paludisme simple",
        icd11_code="1F40",
        diagnostic_confidence=0.85,
    )

    assert result is not None
    assert result["disclaimer"] == MANDATORY_DISCLAIMER
    assert agent._call_claude.call_count == 2


@pytest.mark.asyncio
async def test_execute_degrades_gracefully_after_retry_failure():
    """_execute should return partial result with warnings when both attempts produce invalid JSON."""
    mcp = AsyncMock()
    mcp.call = AsyncMock(side_effect=lambda tool, **kw: {
        "hybrid_retrieve": [],
        "formulary_lookup": {},
        "amr_lookup": {},
        "drug_ddi_check": [],
        "safety_classifier": {},
        "citation_formatter": [],
    }.get(tool, {}))

    agent = _make_agent(mcp)
    agent._call_claude = AsyncMock(return_value=(
        "Still not JSON", {"input_tokens": 10, "output_tokens": 10}
    ))

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        confirmed_diagnosis="Paludisme",
        icd11_code="1F40",
        diagnostic_confidence=0.85,
    )

    # Should return a partial result instead of raising
    assert result is not None
    assert isinstance(result, dict)
    # Should have the mandatory disclaimer even in degraded mode
    assert result.get("disclaimer") == MANDATORY_DISCLAIMER
    # Should have tool warnings about the JSON parsing failure
    assert "_tool_warnings" in result
    assert len(result["_tool_warnings"]) > 0


# ── Test: hybrid_retrieve with ≥3 query expansions (Req 9.1) ────────────────


@pytest.mark.asyncio
async def test_hybrid_retrieve_at_least_3_expansions():
    """hybrid_retrieve should be called with ≥3 query expansions (PNLP, guidelines, WHO)."""
    mcp = AsyncMock()
    retrieve_queries = []

    async def mock_mcp_call(tool, **kw):
        if tool == "hybrid_retrieve":
            retrieve_queries.append(kw.get("query", ""))
            return []
        if tool == "citation_formatter":
            return []
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    valid_json = _make_valid_treatment_json()
    agent._call_claude = AsyncMock(return_value=(
        valid_json, {"input_tokens": 10, "output_tokens": 10}
    ))

    await agent._execute(
        patient_context=_base_patient_context(),
        confirmed_diagnosis="Fièvre typhoïde",
        icd11_code="1A07",
        diagnostic_confidence=0.80,
    )

    assert len(retrieve_queries) >= 3
    all_queries = " ".join(retrieve_queries).lower()
    assert "pnlp" in all_queries
    assert "oms" in all_queries or "who" in all_queries or "posologie" in all_queries


# ── Test: Pydantic validation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_output_validates_through_pydantic():
    """_parse_output should validate through TreatmentPlan Pydantic model."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()
    result = await agent._parse_output(raw, patient_context=_base_patient_context())

    assert isinstance(result, dict)
    assert "target_disease" in result
    assert "first_line" in result
    assert "disclaimer" in result


@pytest.mark.asyncio
async def test_parse_output_rejects_invalid_route():
    """Invalid route value should raise ValidationError."""
    agent = _make_agent()
    first_line = [
        {
            "drug_name": "Test",
            "generic_name": "test",
            "came_available": True,
            "dose": "100 mg",
            "route": "INVALID_ROUTE",
            "frequency": "1x/jour",
            "duration_days": 3,
        },
    ]
    raw = _make_valid_treatment_json(first_line=first_line)

    with pytest.raises(Exception):
        await agent._parse_output(raw, patient_context=_base_patient_context())


# ── Test: Resistance Agent logic — West Africa fallback (Req 11.2) ───────────


@pytest.mark.asyncio
async def test_check_amr_falls_back_to_west_africa_when_togo_has_no_data():
    """When Togo-specific AMR data is unavailable, _check_amr should fall back to West Africa."""
    mcp = AsyncMock()

    call_log: list[dict] = []

    async def mock_mcp_call(tool, **kw):
        call_log.append({"tool": tool, **kw})
        if tool == "amr_lookup":
            if kw.get("region") == "Togo":
                # Togo returns no data
                return {"drug": kw["drug"], "pathogen": kw["pathogen"], "region": "Togo",
                        "resistance_pct": None, "confidence": "no_data",
                        "data_source": "", "year": None, "recommendation": ""}
            elif kw.get("region") == "West Africa":
                # West Africa has data
                return {"drug": kw["drug"], "pathogen": kw["pathogen"], "region": "West Africa",
                        "resistance_pct": 25.0, "confidence": "medium",
                        "data_source": "WHO GLASS 2023", "year": 2023,
                        "recommendation": "Utiliser avec prudence"}
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    results = await agent._check_amr(["ciprofloxacine"], "Fièvre typhoïde")

    # Should have results from West Africa fallback
    real_results = [r for r in results if r.get("drug") != "*"]
    assert len(real_results) >= 1
    wa_result = real_results[0]
    assert wa_result["region"] == "West Africa"
    assert wa_result["resistance_pct"] == 25.0
    assert wa_result["confidence"] == "medium"
    assert wa_result["data_source"] == "WHO GLASS 2023"
    assert wa_result["year"] == 2023
    assert wa_result["fallback_region"] is True


@pytest.mark.asyncio
async def test_check_amr_uses_togo_when_data_available():
    """When Togo-specific AMR data exists, it should be used without fallback."""
    mcp = AsyncMock()

    async def mock_mcp_call(tool, **kw):
        if tool == "amr_lookup" and kw.get("region") == "Togo":
            return {"drug": kw["drug"], "pathogen": kw["pathogen"], "region": "Togo",
                    "resistance_pct": 15.0, "confidence": "high",
                    "data_source": "INH Togo 2023", "year": 2023,
                    "recommendation": "Sensible"}
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    results = await agent._check_amr(["amoxicilline"], "Pneumonie")

    real_results = [r for r in results if r.get("drug") != "*"]
    assert len(real_results) >= 1
    assert real_results[0]["region"] == "Togo"
    assert real_results[0]["fallback_region"] is False


# ── Test: Structured response when no AMR data exists (Req 11.4) ─────────────


@pytest.mark.asyncio
async def test_check_amr_returns_pnlp_note_when_no_data_at_all():
    """When no AMR data exists for any pair, a structured note recommending PNLP protocol is returned."""
    mcp = AsyncMock()

    async def mock_mcp_call(tool, **kw):
        if tool == "amr_lookup":
            # Both Togo and West Africa return no data
            return {"drug": kw["drug"], "pathogen": kw["pathogen"],
                    "region": kw.get("region", "Togo"),
                    "resistance_pct": None, "confidence": "no_data",
                    "data_source": "", "year": None, "recommendation": ""}
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    results = await agent._check_amr(["ciprofloxacine"], "Fièvre typhoïde")

    # Should contain the structured unavailability marker
    no_data_entries = [r for r in results if r.get("drug") == "*" and r.get("confidence") == "no_data"]
    assert len(no_data_entries) == 1
    note = no_data_entries[0]
    assert "PNLP" in note["recommendation"]
    assert "protocole empirique" in note["recommendation"]


@pytest.mark.asyncio
async def test_parse_output_attaches_pnlp_note_to_drugs_when_no_amr_data():
    """When AMR results indicate no data, _parse_output should attach the PNLP note to drug amr_note."""
    agent = _make_agent()
    raw = _make_valid_treatment_json()

    amr_results = [
        {"drug": "*", "pathogen": "*", "region": "N/A",
         "resistance_pct": None, "confidence": "no_data",
         "data_source": "N/A", "year": None,
         "recommendation": AntibiotherapyAgent._NO_AMR_DATA_NOTE,
         "fallback_region": False},
    ]

    result = await agent._parse_output(
        raw,
        amr_results=amr_results,
        patient_context=_base_patient_context(),
    )

    # Every drug in first_line should have the PNLP note
    for drug in result["first_line"]:
        assert drug["amr_note"] is not None
        assert "PNLP" in drug["amr_note"]


# ── Test: Multiple pathogen inference (Req 11.1) ─────────────────────────────


@pytest.mark.asyncio
async def test_infer_pathogens_returns_multiple_for_pneumonia():
    """Pneumonia should infer multiple pathogens (S. pneumoniae, H. influenzae, K. pneumoniae)."""
    agent = _make_agent()
    pathogens = agent._infer_pathogens("Pneumonie communautaire")
    assert len(pathogens) >= 2
    assert "Streptococcus pneumoniae" in pathogens
    assert "Haemophilus influenzae" in pathogens


@pytest.mark.asyncio
async def test_infer_pathogens_returns_multiple_for_meningitis():
    """Meningitis should infer multiple pathogens."""
    agent = _make_agent()
    pathogens = agent._infer_pathogens("Méningite bactérienne")
    assert len(pathogens) >= 2
    assert "Neisseria meningitidis" in pathogens
    assert "Streptococcus pneumoniae" in pathogens


@pytest.mark.asyncio
async def test_infer_pathogens_falls_back_to_bacteria():
    """Unknown diagnosis should fall back to generic 'Bacteria'."""
    agent = _make_agent()
    pathogens = agent._infer_pathogens("Maladie inconnue rare")
    assert pathogens == ["Bacteria"]


# ── Test: Fallback source indication in results (Req 11.2, 11.3) ────────────


@pytest.mark.asyncio
async def test_amr_results_include_all_required_fields():
    """AMR results should include resistance_pct, confidence, data_source, year, and fallback_region."""
    mcp = AsyncMock()

    async def mock_mcp_call(tool, **kw):
        if tool == "amr_lookup" and kw.get("region") == "Togo":
            return {"drug": kw["drug"], "pathogen": kw["pathogen"], "region": "Togo",
                    "resistance_pct": None, "confidence": "no_data",
                    "data_source": "", "year": None, "recommendation": ""}
        if tool == "amr_lookup" and kw.get("region") == "West Africa":
            return {"drug": kw["drug"], "pathogen": kw["pathogen"], "region": "West Africa",
                    "resistance_pct": 35.0, "confidence": "high",
                    "data_source": "WHO GLASS 2022", "year": 2022,
                    "recommendation": "Résistance élevée — envisager alternative"}
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    results = await agent._check_amr(["ceftriaxone"], "Fièvre typhoïde")

    real_results = [r for r in results if r.get("drug") != "*"]
    assert len(real_results) >= 1
    r = real_results[0]

    # All required fields present (Req 11.3)
    assert "resistance_pct" in r and r["resistance_pct"] is not None
    assert "confidence" in r and r["confidence"] in ("high", "medium", "low", "no_data")
    assert "data_source" in r and r["data_source"]
    assert "year" in r and r["year"] is not None
    # Fallback indicator (Req 11.2)
    assert "fallback_region" in r
    assert r["fallback_region"] is True


@pytest.mark.asyncio
async def test_check_amr_queries_multiple_pathogens():
    """For diagnoses with multiple pathogens, _check_amr should query each pathogen."""
    mcp = AsyncMock()
    queried_pathogens: list[str] = []

    async def mock_mcp_call(tool, **kw):
        if tool == "amr_lookup":
            queried_pathogens.append(kw.get("pathogen", ""))
            return {"drug": kw["drug"], "pathogen": kw["pathogen"], "region": kw["region"],
                    "resistance_pct": 10.0, "confidence": "medium",
                    "data_source": "test", "year": 2023, "recommendation": "ok"}
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    await agent._check_amr(["amoxicilline"], "Pneumonie")

    # Should have queried multiple pathogens for pneumonia
    unique_pathogens = set(queried_pathogens)
    assert len(unique_pathogens) >= 2
    assert "Streptococcus pneumoniae" in unique_pathogens


# ── Test: Full _execute flow with mocked MCP produces drugs with dosage, route, CAME (Req 16.2) ──


@pytest.mark.asyncio
async def test_execute_happy_path_produces_drugs_with_dosage_route_came():
    """Full _execute with mocked MCP tools should return drug recommendations with dosage, route, and CAME availability."""
    mcp = AsyncMock()

    async def mock_mcp_call(tool, **kw):
        if tool == "hybrid_retrieve":
            return [
                {"chunk_id": "chunk-t1", "score": 0.90, "chunk_text": "Protocole PNLP: artéméther-luméfantrine première ligne paludisme simple"},
            ]
        if tool == "formulary_lookup":
            return {
                "generic_name": kw.get("drug_name", "artéméther-luméfantrine"),
                "available": True,
                "dosage_forms": ["comprimé 20/120mg", "comprimé 80/480mg"],
            }
        if tool == "amr_lookup":
            if kw.get("region") == "Togo":
                return {
                    "drug": kw.get("drug", ""),
                    "pathogen": kw.get("pathogen", ""),
                    "region": "Togo",
                    "resistance_pct": 5.0,
                    "confidence": "high",
                    "data_source": "INH Togo 2023",
                    "year": 2023,
                    "recommendation": "Sensible",
                }
            return {}
        if tool == "drug_ddi_check":
            return []
        if tool == "safety_classifier":
            return {}
        if tool == "citation_formatter":
            return [{"ref_id": 1, "source_title": "PNLP Togo 2023", "section": "Paludisme simple"}]
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    # LLM returns a well-formed treatment plan
    first_line = [
        {
            "drug_name": "Coartem",
            "generic_name": "artéméther-luméfantrine",
            "came_available": True,
            "dose": "480 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 3,
        },
        {
            "drug_name": "Paracétamol",
            "generic_name": "paracétamol",
            "came_available": True,
            "dose": "1000 mg",
            "route": "PO",
            "frequency": "3x/jour",
            "duration_days": 3,
        },
    ]
    valid_json = _make_valid_treatment_json(first_line=first_line)
    agent._call_claude = AsyncMock(return_value=(
        valid_json, {"input_tokens": 150, "output_tokens": 250}
    ))

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        confirmed_diagnosis="Paludisme simple",
        icd11_code="1F40",
        diagnostic_confidence=0.85,
    )

    # Verify result structure
    assert result is not None
    assert "first_line" in result
    assert "disclaimer" in result
    assert result["disclaimer"] == MANDATORY_DISCLAIMER
    assert len(result["first_line"]) >= 1

    # Verify each drug has dosage, route, and CAME availability
    for drug in result["first_line"]:
        assert "dose" in drug
        assert isinstance(drug["dose"], str)
        assert len(drug["dose"]) > 0
        assert "route" in drug
        assert drug["route"] in ("PO", "IV", "IM", "SC", "topique")
        assert "came_available" in drug
        assert isinstance(drug["came_available"], bool)
        assert "frequency" in drug
        assert "duration_days" in drug
        assert "generic_name" in drug

    # Verify MCP tools were called
    assert "hybrid_retrieve" in tool_calls
    assert "citation_formatter" in tool_calls

    # Verify usage tracking
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0


# ── Test: Full _execute flow with AMR data produces resistance profiles (Req 16.3) ──


@pytest.mark.asyncio
async def test_execute_with_amr_data_produces_resistance_profiles():
    """Full _execute with mocked AMR data should produce resistance profiles with percentage and confidence level."""
    mcp = AsyncMock()

    async def mock_mcp_call(tool, **kw):
        if tool == "hybrid_retrieve":
            return [
                {"chunk_id": "chunk-r1", "score": 0.88, "chunk_text": "ciprofloxacine traitement typhoïde Togo"},
            ]
        if tool == "formulary_lookup":
            return {
                "generic_name": kw.get("drug_name", "ciprofloxacine"),
                "available": True,
                "dosage_forms": ["comprimé 500mg"],
            }
        if tool == "amr_lookup":
            drug = kw.get("drug", "")
            pathogen = kw.get("pathogen", "")
            region = kw.get("region", "Togo")
            if region == "Togo" and "cipro" in drug.lower():
                return {
                    "drug": drug,
                    "pathogen": pathogen,
                    "region": "Togo",
                    "resistance_pct": 42.0,
                    "confidence": "high",
                    "data_source": "INH Togo 2023",
                    "year": 2023,
                    "recommendation": "Résistance élevée — envisager alternative",
                }
            if region == "Togo":
                return {
                    "drug": drug,
                    "pathogen": pathogen,
                    "region": "Togo",
                    "resistance_pct": 8.0,
                    "confidence": "medium",
                    "data_source": "INH Togo 2023",
                    "year": 2023,
                    "recommendation": "Sensible",
                }
            return {
                "drug": drug, "pathogen": pathogen, "region": region,
                "resistance_pct": None, "confidence": "no_data",
                "data_source": "", "year": None, "recommendation": "",
            }
        if tool == "drug_ddi_check":
            return []
        if tool == "safety_classifier":
            return {}
        if tool == "citation_formatter":
            return []
        return {}

    mcp.call = AsyncMock(side_effect=mock_mcp_call)
    agent = _make_agent(mcp)

    # LLM returns ciprofloxacine in first_line — should be deprioritized due to 42% resistance
    first_line = [
        {
            "drug_name": "Cipro",
            "generic_name": "ciprofloxacine",
            "came_available": True,
            "dose": "500 mg",
            "route": "PO",
            "frequency": "2x/jour",
            "duration_days": 10,
        },
        {
            "drug_name": "Ceftriaxone",
            "generic_name": "ceftriaxone",
            "came_available": True,
            "dose": "2000 mg",
            "route": "IV",
            "frequency": "1x/jour",
            "duration_days": 14,
        },
    ]
    valid_json = _make_valid_treatment_json(first_line=first_line)
    agent._call_claude = AsyncMock(return_value=(
        valid_json, {"input_tokens": 150, "output_tokens": 250}
    ))

    result, usage, tool_calls = await agent._execute(
        patient_context=_base_patient_context(),
        confirmed_diagnosis="Fièvre typhoïde",
        icd11_code="1A07",
        diagnostic_confidence=0.80,
    )

    # Verify result structure
    assert result is not None

    # Ciprofloxacine should be deprioritized from first_line (42% > 30% threshold)
    first_generics = [d["generic_name"].lower() for d in result["first_line"]]
    assert "ciprofloxacine" not in first_generics

    # Ciprofloxacine should be in alternatives with AMR note
    alt_generics = [d["generic_name"].lower() for d in result["alternatives"]]
    assert "ciprofloxacine" in alt_generics

    cipro = next(d for d in result["alternatives"] if d["generic_name"].lower() == "ciprofloxacine")
    assert cipro["amr_note"] is not None
    assert "42%" in cipro["amr_note"]

    # Ceftriaxone should remain in first_line (8% < 30% threshold)
    assert "ceftriaxone" in first_generics

    # Verify AMR tool was called
    assert "amr_lookup" in tool_calls
