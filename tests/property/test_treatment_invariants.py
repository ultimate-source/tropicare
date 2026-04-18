# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_treatment_invariants.py
#
# Property 4: Treatment disclaimer invariant
# For any valid TreatmentPlan output produced by the AntibiotherapyAgent,
# the disclaimer field SHALL be present and SHALL contain the mandatory
# regulatory disclaimer text starting with
# "⚠️ AIDE À LA DÉCISION UNIQUEMENT".
#
# **Validates: Requirements 10.4, 17.7**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    booleans,
    builds,
    composite,
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

from backend.app.agents.antibiotherapy import AntibiotherapyAgent, MANDATORY_DISCLAIMER, _AMR_RESISTANCE_THRESHOLD
from backend.app.agents.base import MCPClient
from backend.app.models.schemas import (
    Contraindication,
    DrugRegimen,
    TreatmentPlan,
)

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=50).filter(lambda s: s.strip() != "")

# JSON-safe text avoids characters that confuse BaseAgent._extract_json's
# naive brace-matching parser (it doesn't track JSON string escaping).
_JSON_UNSAFE = set('{}[]"\\')
json_safe_text = text(min_size=1, max_size=50).filter(
    lambda s: s.strip() != "" and not any(c in _JSON_UNSAFE for c in s)
)

drug_regimens = builds(
    DrugRegimen,
    drug_name=safe_text,
    generic_name=safe_text,
    came_available=booleans(),
    dose=safe_text,
    dose_mg_per_kg=one_of(none(), safe_text),
    route=sampled_from(["PO", "IV", "IM", "SC", "topique"]),
    frequency=safe_text,
    duration_days=integers(min_value=1, max_value=30),
    pregnancy_class=one_of(none(), sampled_from(["A", "B", "C", "D", "X"])),
    ddi_warnings=lists(safe_text, min_size=0, max_size=2),
    amr_note=one_of(none(), safe_text),
    monitoring=lists(safe_text, min_size=0, max_size=2),
    citations=lists(integers(min_value=1, max_value=100), min_size=0, max_size=3),
)

# Drug regimens with JSON-safe text for use in _parse_output tests where
# the raw JSON string goes through _extract_json's brace-matching parser.
json_safe_drug_regimens = builds(
    DrugRegimen,
    drug_name=json_safe_text,
    generic_name=json_safe_text,
    came_available=booleans(),
    dose=json_safe_text,
    dose_mg_per_kg=one_of(none(), json_safe_text),
    route=sampled_from(["PO", "IV", "IM", "SC", "topique"]),
    frequency=json_safe_text,
    duration_days=integers(min_value=1, max_value=30),
    pregnancy_class=one_of(none(), sampled_from(["A", "B", "C", "D", "X"])),
    ddi_warnings=lists(json_safe_text, min_size=0, max_size=2),
    amr_note=one_of(none(), json_safe_text),
    monitoring=lists(json_safe_text, min_size=0, max_size=2),
    citations=lists(integers(min_value=1, max_value=100), min_size=0, max_size=3),
)

contraindications = builds(
    Contraindication,
    drug=safe_text,
    reason=safe_text,
)

treatment_plans = builds(
    TreatmentPlan,
    target_disease=safe_text,
    clinical_rationale=safe_text,
    first_line=lists(drug_regimens, min_size=1, max_size=3),
    second_line=lists(drug_regimens, min_size=0, max_size=2),
    alternatives=lists(drug_regimens, min_size=0, max_size=2),
    contraindicated=lists(contraindications, min_size=0, max_size=2),
    supportive_care=lists(safe_text, min_size=0, max_size=3),
    follow_up_guidance=safe_text,
    referral_criteria=safe_text,
    disclaimer=just(MANDATORY_DISCLAIMER),
)


# ── Property test: TreatmentPlan model disclaimer via builds() ───────────────


@pytest.mark.property
@given(tp=treatment_plans)
@settings(max_examples=200, deadline=None)
def test_treatment_plan_disclaimer_present(tp: TreatmentPlan) -> None:
    """
    **Validates: Requirements 10.4, 17.7**

    Property 4 (model-level): Treatment disclaimer invariant.
    Every TreatmentPlan object SHALL have a disclaimer field that is present
    and starts with "⚠️ AIDE À LA DÉCISION UNIQUEMENT".
    """
    assert tp.disclaimer is not None, "disclaimer field must be present"
    assert tp.disclaimer.startswith("⚠️ AIDE À LA DÉCISION UNIQUEMENT"), (
        f"disclaimer must start with mandatory prefix, got: {tp.disclaimer[:80]!r}"
    )
    assert tp.disclaimer == MANDATORY_DISCLAIMER, (
        f"disclaimer must match MANDATORY_DISCLAIMER exactly"
    )


# ── Property test: _parse_output always overwrites disclaimer ────────────────

def _make_antibiotherapy_agent() -> AntibiotherapyAgent:
    """Create an AntibiotherapyAgent with a mock MCP client (no real API calls)."""
    mock_mcp = MCPClient(base_url="http://test-mcp:8001")
    mock_mcp.call = AsyncMock(return_value={})
    return AntibiotherapyAgent(
        api_key="test-key",
        mcp=mock_mcp,
    )


# Strategy: generate random disclaimer strings that the LLM might return,
# then verify _parse_output always overwrites them with MANDATORY_DISCLAIMER.

random_disclaimers = one_of(
    just(""),
    just("Some random disclaimer"),
    just("Warning: not real"),
    just(MANDATORY_DISCLAIMER),
    json_safe_text,
)


def _build_treatment_json(
    target_disease: str,
    clinical_rationale: str,
    first_line: list[DrugRegimen],
    disclaimer: str,
) -> str:
    """Build a valid TreatmentPlan JSON string with the given disclaimer."""
    drugs = []
    for drug in first_line:
        drugs.append({
            "drug_name": drug.drug_name,
            "generic_name": drug.generic_name,
            "came_available": drug.came_available,
            "dose": drug.dose,
            "route": drug.route,
            "frequency": drug.frequency,
            "duration_days": drug.duration_days,
        })
    # Ensure at least one drug
    if not drugs:
        drugs.append({
            "drug_name": "Amoxicilline",
            "generic_name": "amoxicilline",
            "came_available": True,
            "dose": "500mg",
            "route": "PO",
            "frequency": "3x/jour",
            "duration_days": 7,
        })
    return json.dumps({
        "target_disease": target_disease,
        "clinical_rationale": clinical_rationale,
        "first_line": drugs,
        "second_line": [],
        "alternatives": [],
        "contraindicated": [],
        "supportive_care": [],
        "follow_up_guidance": "Controle a J3",
        "referral_criteria": "Si aggravation",
        "disclaimer": disclaimer,
    })


_agent = _make_antibiotherapy_agent()


@pytest.mark.property
@pytest.mark.asyncio
@given(
    target_disease=json_safe_text,
    clinical_rationale=json_safe_text,
    first_line=lists(json_safe_drug_regimens, min_size=1, max_size=3),
    disclaimer=random_disclaimers,
)
@settings(max_examples=200, deadline=None)
async def test_parse_output_always_overwrites_disclaimer(
    target_disease: str,
    clinical_rationale: str,
    first_line: list[DrugRegimen],
    disclaimer: str,
) -> None:
    """
    **Validates: Requirements 10.4, 17.7**

    Property 4 (parser-level): Treatment disclaimer invariant.
    For any random TreatmentPlan JSON string fed through
    AntibiotherapyAgent._parse_output, the resulting disclaimer field
    SHALL always be the MANDATORY_DISCLAIMER, regardless of what the
    LLM originally returned.
    """
    raw_json = _build_treatment_json(
        target_disease=target_disease,
        clinical_rationale=clinical_rationale,
        first_line=first_line,
        disclaimer=disclaimer,
    )

    result = await _agent._parse_output(
        raw_json,
        citations=None,
        ddi_warnings=None,
        amr_results=None,
        safety_classes=None,
        patient_context=None,
    )

    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"
    assert "disclaimer" in result, "disclaimer field must be present in parsed output"
    assert result["disclaimer"] == MANDATORY_DISCLAIMER, (
        f"_parse_output must overwrite disclaimer with MANDATORY_DISCLAIMER.\n"
        f"Input disclaimer was: {disclaimer!r}\n"
        f"Got: {result['disclaimer']!r}"
    )
    assert result["disclaimer"].startswith("⚠️ AIDE À LA DÉCISION UNIQUEMENT"), (
        f"disclaimer must start with mandatory prefix"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Property 6: High-resistance drug exclusion from first-line
#
# For any treatment plan where AMR data indicates resistance above 30% for a
# drug in the patient's region, that drug SHALL NOT appear in the first_line
# list of the TreatmentPlan output.
#
# **Validates: Requirement 9.3**
# ─────────────────────────────────────────────────────────────────────────────


# Strategy: generate a list of unique drug generic names for the treatment plan
_DRUG_POOL = [
    "amoxicilline", "ciprofloxacine", "ceftriaxone", "azithromycine",
    "doxycycline", "metronidazole", "cotrimoxazole", "chloroquine",
    "quinine", "rifampicine", "isoniazide", "fluconazole",
    "albendazole", "ivermectine", "praziquantel", "mebendazole",
]


@composite
def drug_names_with_high_resistance(draw):
    """Generate a list of drug names and a subset with >30% resistance.

    Returns (all_drug_names, high_resistance_amr_results) where:
    - all_drug_names: list of 1-5 unique drug generic names
    - high_resistance_amr_results: AMR results with resistance_pct > 30%
      for at least one of those drugs
    """
    # Pick 2-5 unique drugs for the treatment plan
    num_drugs = draw(integers(min_value=2, max_value=5))
    all_drugs = draw(
        lists(
            sampled_from(_DRUG_POOL),
            min_size=num_drugs,
            max_size=num_drugs,
            unique=True,
        )
    )

    # Pick at least 1 drug to mark as high-resistance
    num_resistant = draw(integers(min_value=1, max_value=len(all_drugs)))
    resistant_drugs = all_drugs[:num_resistant]

    # Build AMR results for the resistant drugs
    amr_results = []
    for drug in resistant_drugs:
        resistance_pct = draw(floats(min_value=30.1, max_value=100.0, allow_nan=False))
        amr_results.append({
            "drug": drug,
            "resistance_pct": resistance_pct,
            "pathogen": "Bacteria",
            "region": "Togo",
            "confidence": "high",
            "data_source": "test",
            "year": 2024,
            "recommendation": "Avoid",
        })

    return all_drugs, resistant_drugs, amr_results


def _build_treatment_json_with_drugs(drug_names: list[str]) -> str:
    """Build a valid TreatmentPlan JSON with the given drugs in first_line."""
    drugs = []
    for name in drug_names:
        drugs.append({
            "drug_name": name.capitalize(),
            "generic_name": name,
            "came_available": True,
            "dose": "500mg",
            "route": "PO",
            "frequency": "3x/jour",
            "duration_days": 7,
        })
    return json.dumps({
        "target_disease": "Infection bacterienne",
        "clinical_rationale": "Traitement empirique",
        "first_line": drugs,
        "second_line": [],
        "alternatives": [],
        "contraindicated": [],
        "supportive_care": [],
        "follow_up_guidance": "Controle a J3",
        "referral_criteria": "Si aggravation",
        "disclaimer": "placeholder",
    })


@pytest.mark.property
@pytest.mark.asyncio
@given(data=drug_names_with_high_resistance())
@settings(max_examples=200, deadline=None)
async def test_high_resistance_drugs_excluded_from_first_line(
    data: tuple[list[str], list[str], list[dict]],
) -> None:
    """
    **Validates: Requirement 9.3**

    Property 6: High-resistance drug exclusion from first-line.
    For any treatment plan where AMR data indicates resistance above 30%
    for a drug, that drug SHALL NOT appear in the first_line list of the
    TreatmentPlan output after _parse_output processing.
    """
    all_drugs, resistant_drugs, amr_results = data

    raw_json = _build_treatment_json_with_drugs(all_drugs)

    result = await _agent._parse_output(
        raw_json,
        citations=None,
        ddi_warnings=None,
        amr_results=amr_results,
        safety_classes=None,
        patient_context=None,
    )

    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"

    # Extract generic names from first_line in the result
    first_line_generics = {
        (drug.get("generic_name") or drug.get("drug_name") or "").lower()
        for drug in result.get("first_line", [])
    }

    # Verify no high-resistance drug appears in first_line
    resistant_set = {d.lower() for d in resistant_drugs}
    overlap = first_line_generics & resistant_set
    assert not overlap, (
        f"High-resistance drugs found in first_line: {overlap}\n"
        f"Resistant drugs (>{_AMR_RESISTANCE_THRESHOLD}%): {resistant_drugs}\n"
        f"AMR data: {amr_results}\n"
        f"first_line generics: {first_line_generics}"
    )

    # Additionally verify the demoted drugs moved to alternatives
    alternatives_generics = {
        (drug.get("generic_name") or drug.get("drug_name") or "").lower()
        for drug in result.get("alternatives", [])
    }
    for drug in resistant_drugs:
        assert drug.lower() in alternatives_generics, (
            f"High-resistance drug '{drug}' was removed from first_line but "
            f"not found in alternatives. alternatives: {alternatives_generics}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Property 7: Pregnancy safety filtering
#
# For any treatment plan generated for a patient with pregnancy_status
# indicating pregnancy (pregnant_t1, pregnant_t2, or pregnant_t3), all drugs
# in first_line, second_line, and alternatives SHALL have a pregnancy_class
# of "A", "B", or "C" (never "D" or "X").
#
# **Validates: Requirement 10.2**
# ─────────────────────────────────────────────────────────────────────────────

_SAFE_PREGNANCY_CATEGORIES = {"A", "B", "C"}
_ALL_FDA_CATEGORIES = ["A", "B", "C", "D", "X"]


@composite
def pregnancy_treatment_data(draw):
    """Generate a treatment plan with drugs across tiers and safety class data.

    Returns (drug_names_by_tier, safety_classes, pregnancy_status) where:
    - drug_names_by_tier: dict mapping tier name to list of drug generic names
    - safety_classes: list of dicts with drug + pregnancy_category for each drug
    - pregnancy_status: one of pregnant_t1, pregnant_t2, pregnant_t3
    """
    # Pick unique drugs for each tier
    num_first = draw(integers(min_value=1, max_value=4))
    num_second = draw(integers(min_value=0, max_value=3))
    num_alts = draw(integers(min_value=0, max_value=3))
    total_needed = num_first + num_second + num_alts

    all_drugs = draw(
        lists(
            sampled_from(_DRUG_POOL),
            min_size=max(total_needed, 1),
            max_size=max(total_needed, 1),
            unique=True,
        )
    )

    first_line_drugs = all_drugs[:num_first]
    second_line_drugs = all_drugs[num_first:num_first + num_second]
    alt_drugs = all_drugs[num_first + num_second:num_first + num_second + num_alts]

    drug_names_by_tier = {
        "first_line": first_line_drugs,
        "second_line": second_line_drugs,
        "alternatives": alt_drugs,
    }

    # Assign a random FDA category to EVERY drug so we have known safety data
    safety_classes = []
    for drug in all_drugs:
        cat = draw(sampled_from(_ALL_FDA_CATEGORIES))
        safety_classes.append({
            "drug": drug,
            "pregnancy_category": cat,
        })

    pregnancy_status = draw(sampled_from(["pregnant_t1", "pregnant_t2", "pregnant_t3"]))

    return drug_names_by_tier, safety_classes, pregnancy_status


def _build_treatment_json_multi_tier(drug_names_by_tier: dict[str, list[str]]) -> str:
    """Build a valid TreatmentPlan JSON with drugs in first_line, second_line, and alternatives."""
    tiers = {}
    for tier_key in ("first_line", "second_line", "alternatives"):
        drugs = []
        for name in drug_names_by_tier.get(tier_key, []):
            drugs.append({
                "drug_name": name.capitalize(),
                "generic_name": name,
                "came_available": True,
                "dose": "500mg",
                "route": "PO",
                "frequency": "3x/jour",
                "duration_days": 7,
            })
        tiers[tier_key] = drugs

    # Ensure first_line has at least one drug
    if not tiers["first_line"]:
        tiers["first_line"] = [{
            "drug_name": "Amoxicilline",
            "generic_name": "amoxicilline",
            "came_available": True,
            "dose": "500mg",
            "route": "PO",
            "frequency": "3x/jour",
            "duration_days": 7,
        }]

    return json.dumps({
        "target_disease": "Infection bacterienne",
        "clinical_rationale": "Traitement empirique",
        "first_line": tiers["first_line"],
        "second_line": tiers["second_line"],
        "alternatives": tiers["alternatives"],
        "contraindicated": [],
        "supportive_care": [],
        "follow_up_guidance": "Controle a J3",
        "referral_criteria": "Si aggravation",
        "disclaimer": "placeholder",
    })


@pytest.mark.property
@pytest.mark.asyncio
@given(data=pregnancy_treatment_data())
@settings(max_examples=200, deadline=None)
async def test_pregnancy_safety_filtering_removes_d_x_drugs(
    data: tuple[dict[str, list[str]], list[dict], str],
) -> None:
    """
    **Validates: Requirement 10.2**

    Property 7: Pregnancy safety filtering.
    For any treatment plan generated for a pregnant patient, all drugs
    remaining in first_line, second_line, and alternatives SHALL have
    pregnancy_class in {"A", "B", "C"}. No drug with known category
    "D" or "X" should remain in any tier.
    """
    drug_names_by_tier, safety_classes, pregnancy_status = data

    raw_json = _build_treatment_json_multi_tier(drug_names_by_tier)

    patient_context = {
        "age_years": 28,
        "sex": "F",
        "pregnancy_status": pregnancy_status,
    }

    result = await _agent._parse_output(
        raw_json,
        citations=None,
        ddi_warnings=None,
        amr_results=None,
        safety_classes=safety_classes,
        patient_context=patient_context,
    )

    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"

    # Build a lookup from drug name → assigned category
    safety_map = {
        entry["drug"].lower(): entry["pregnancy_category"].upper()
        for entry in safety_classes
    }

    # Check all tiers: no drug with known D or X category should remain
    for tier_key in ("first_line", "second_line", "alternatives"):
        tier_drugs = result.get(tier_key, [])
        for drug in tier_drugs:
            generic = (drug.get("generic_name") or drug.get("drug_name") or "").lower()
            assigned_cat = safety_map.get(generic, "")
            assert assigned_cat in _SAFE_PREGNANCY_CATEGORIES or assigned_cat == "", (
                f"Unsafe drug '{generic}' with pregnancy category '{assigned_cat}' "
                f"found in {tier_key} for pregnant patient ({pregnancy_status}).\n"
                f"Safety classes: {safety_classes}\n"
                f"Tier drugs: {[d.get('generic_name') for d in tier_drugs]}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Property 5: Citation deduplication invariant
#
# For all ConsultationResponse objects produced by the Orchestrator, the
# references list SHALL contain no duplicate entries when compared by
# (source_title, section) tuple.
#
# **Validates: Requirements 12.4, 17.9**
# ─────────────────────────────────────────────────────────────────────────────

from backend.app.orchestrator.orchestrator import deduplicate_citations

# Strategy: generate citation dicts with potential duplicates

_SOURCE_TITLES = [
    "OMS Guidelines Paludisme 2023",
    "PNLP Togo Protocole National",
    "MSF Clinical Guide Tropical",
    "WHO Antibiotic Resistance Report",
    "Guide Thérapeutique Standard",
    "PNLP Directives Antipaludiques",
    "Médecins Sans Frontières Handbook",
]

_SECTIONS = [
    "Diagnostic",
    "Traitement",
    "Posologie",
    "Résistance",
    "Prévention",
    "Suivi",
    "Urgences",
]


@composite
def citation_dicts(draw):
    """Generate a single citation dict."""
    return {
        "ref_id": draw(integers(min_value=1, max_value=100)),
        "source_title": draw(sampled_from(_SOURCE_TITLES)),
        "section": draw(sampled_from(_SECTIONS)),
        "page": draw(integers(min_value=1, max_value=500)),
        "version": draw(sampled_from(["v1.0", "v2.0", "v3.0", "2023", "2024"])),
        "date": draw(sampled_from(["2023-01-01", "2023-06-15", "2024-01-01"])),
        "chunk_snippet": draw(safe_text),
    }


# Generate lists with potential duplicates (same source_title + section)
citation_lists_with_dupes = lists(citation_dicts(), min_size=0, max_size=20)


@pytest.mark.property
@given(citations=citation_lists_with_dupes)
@settings(max_examples=200, deadline=None)
def test_citation_deduplication_uniqueness(citations: list[dict]) -> None:
    """
    **Validates: Requirements 12.4, 17.9**

    Property 5: Citation deduplication invariant.
    After passing through deduplicate_citations, no two citations in the
    output should share the same (source_title, section) pair.
    """
    deduped = deduplicate_citations(citations)

    # Collect (source_title, section) tuples from the output
    keys = [
        (cit.get("source_title", ""), cit.get("section", ""))
        for cit in deduped
    ]

    # Verify uniqueness
    assert len(keys) == len(set(keys)), (
        f"Duplicate (source_title, section) pairs found in deduplicated output.\n"
        f"Keys: {keys}\n"
        f"Unique keys: {set(keys)}\n"
        f"Input count: {len(citations)}, Output count: {len(deduped)}"
    )

    # Output should never be larger than input
    assert len(deduped) <= len(citations), (
        f"Deduplication increased count: input={len(citations)}, output={len(deduped)}"
    )

    # Every output citation should have a 'source' attribution field
    for cit in deduped:
        assert "source" in cit, (
            f"Citation missing 'source' attribution: {cit}"
        )
        assert cit["source"] in ("OMS", "PNLP", "MSF", "Autre"), (
            f"Invalid source attribution: {cit['source']!r}"
        )

    # All unique (source_title, section) pairs from input should be in output
    input_keys = set()
    for cit in citations:
        input_keys.add((cit.get("source_title", ""), cit.get("section", "")))
    output_keys = set(keys)
    assert input_keys == output_keys, (
        f"Deduplication lost unique keys.\n"
        f"Input unique keys: {input_keys}\n"
        f"Output keys: {output_keys}"
    )
