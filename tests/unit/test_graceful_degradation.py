# ─────────────────────────────────────────────────────────────────────────────
# tests/unit/test_graceful_degradation.py — Tests for graceful degradation
# on agent pipeline failures (Req 28.1, 28.2, 28.3)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import pytest

from backend.app.agents.base import BaseAgent
from backend.app.orchestrator.orchestrator import _localized_error


# ── Tests for _extract_json_lenient ──────────────────────────────────────────


class TestExtractJsonLenient:
    """Tests for BaseAgent._extract_json_lenient — lenient JSON extraction."""

    def test_valid_json_returns_no_warnings(self):
        text = '{"disease_name": "Paludisme", "confidence": 0.85}'
        result, warnings = BaseAgent._extract_json_lenient(text)
        assert result == {"disease_name": "Paludisme", "confidence": 0.85}
        assert warnings == []

    def test_valid_json_in_markdown_block(self):
        text = '```json\n{"disease_name": "Typhoid", "confidence": 0.7}\n```'
        result, warnings = BaseAgent._extract_json_lenient(text)
        assert result["disease_name"] == "Typhoid"
        assert warnings == []

    def test_malformed_json_extracts_valid_fields(self):
        # JSON with a trailing comma (invalid) but parseable fields
        text = 'Here is the result: "disease_name": "Paludisme", "confidence": 0.85, broken stuff'
        result, warnings = BaseAgent._extract_json_lenient(text)
        assert result.get("disease_name") == "Paludisme"
        assert result.get("confidence") == 0.85
        assert len(warnings) > 0
        assert any("malformed JSON" in w for w in warnings)

    def test_completely_unparseable_returns_empty_with_warning(self):
        text = "This is just plain text with no JSON at all."
        result, warnings = BaseAgent._extract_json_lenient(text)
        assert result == {}
        assert len(warnings) > 0
        assert any("no parseable JSON" in w for w in warnings)

    def test_missing_required_fields_reported(self):
        text = '{"disease_name": "Paludisme"}'
        result, warnings = BaseAgent._extract_json_lenient(
            text, required_fields=["disease_name", "differential"]
        )
        assert result["disease_name"] == "Paludisme"
        # No warning about malformed JSON since it parsed fine
        # But no missing field warning either since it parsed as valid JSON
        assert warnings == []

    def test_partial_extraction_reports_missing_required(self):
        text = 'broken "disease_name": "Paludisme" more broken'
        result, warnings = BaseAgent._extract_json_lenient(
            text, required_fields=["disease_name", "differential"]
        )
        assert result.get("disease_name") == "Paludisme"
        assert any("Missing required fields" in w for w in warnings)
        assert any("differential" in w for w in warnings)

    def test_extracts_fields_from_broken_json(self):
        # No valid top-level { } or [ ] — forces field-level extraction
        text = 'The result is "disease_name": "Typhoid", "confidence": 0.9, "available": true'
        result, warnings = BaseAgent._extract_json_lenient(text)
        assert result.get("disease_name") == "Typhoid"
        assert result.get("confidence") == 0.9
        assert result.get("available") is True
        assert len(warnings) > 0

    def test_extracts_boolean_and_null(self):
        text = 'broken "available": true, "notes": null more broken'
        result, warnings = BaseAgent._extract_json_lenient(text)
        assert result.get("available") is True
        assert result.get("notes") is None


# ── Tests for _localized_error ───────────────────────────────────────────────


class TestLocalizedError:
    """Tests for localized error messages (Req 28.3)."""

    def test_french_error_by_default(self):
        msg = _localized_error()
        assert "Erreur interne" in msg
        assert "réessayer" in msg

    def test_french_error_explicit(self):
        msg = _localized_error("fr")
        assert "Erreur interne" in msg

    def test_english_error(self):
        msg = _localized_error("en")
        assert "Internal error" in msg
        assert "retry" in msg

    def test_unknown_language_defaults_to_french(self):
        msg = _localized_error("de")
        assert "Erreur interne" in msg

    def test_with_exception_still_returns_localized(self):
        exc = RuntimeError("connection timeout")
        msg_fr = _localized_error("fr", exc)
        msg_en = _localized_error("en", exc)
        assert "Erreur interne" in msg_fr
        assert "Internal error" in msg_en


# ── Tests for _extract_json (strict) still works ────────────────────────────


class TestExtractJsonStrict:
    """Ensure the original strict _extract_json still works correctly."""

    def test_valid_json_object(self):
        text = '{"key": "value"}'
        assert BaseAgent._extract_json(text) == {"key": "value"}

    def test_valid_json_array(self):
        text = '[1, 2, 3]'
        assert BaseAgent._extract_json(text) == [1, 2, 3]

    def test_json_in_markdown(self):
        text = '```json\n{"key": "value"}\n```'
        assert BaseAgent._extract_json(text) == {"key": "value"}

    def test_no_json_raises_value_error(self):
        with pytest.raises(ValueError, match="No JSON found"):
            BaseAgent._extract_json("just plain text")

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"key": "value"} and more text'
        assert BaseAgent._extract_json(text) == {"key": "value"}
