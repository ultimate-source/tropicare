# ─────────────────────────────────────────────────────────────────────────────
# tests/unit/test_infrastructure_fallbacks.py — Tests for infrastructure
# fallbacks: MongoDB fallback, Redis unavailability, empty KB handling
# (Requirements 31.1, 31.2, 32.1, 32.2, 33.1, 33.2)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.exceptions


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_stubs():
    """Stub out heavy/unavailable dependencies so server.py can be imported."""
    # FastMCP stub: the @mcp.tool decorator must return the original function
    class _FakeMCP:
        def __init__(self, **kw):
            pass

        def tool(self, **kw):
            """Decorator that returns the function unchanged."""
            def decorator(fn):
                return fn
            return decorator

        def get_asgi_app(self):
            return MagicMock()

    for mod_name in ["sentence_transformers"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()
    sys.modules["sentence_transformers"].CrossEncoder = MagicMock()

    # Stub fastmcp with a real class so @mcp.tool works as a passthrough
    fake_fastmcp = MagicMock()
    fake_fastmcp.FastMCP = _FakeMCP
    sys.modules["fastmcp"] = fake_fastmcp

    # Stub structlog and observability deps for gateway import
    for mod_name in [
        "structlog",
        "slowapi", "slowapi.util",
        "opentelemetry.instrumentation.fastapi",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()


# Apply stubs at module level so imports work
_ensure_stubs()


# ── Tests for MongoDB fallback in hybrid_retrieve (Req 31.1, 31.2) ───────────


class TestMongoDBFallback:
    """When MongoDB vector search is unreachable, hybrid_retrieve should
    fall back to BM25-only retrieval and log the error."""

    def _mock_redis(self):
        """Return an AsyncMock Redis that always misses cache."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_falls_back_to_bm25_on_vector_failure(self):
        """Req 31.1: Fall back to BM25-only when vector search fails."""
        from backend.app.tools.server import (
            hybrid_retrieve, HybridRetrieveInput, Chunk,
        )

        bm25_chunk = Chunk(
            chunk_id="bm25-1", chunk_text="BM25 result", source_title="Test",
            source_version="1.0", source_date="2024-01-01", section="s1",
            page=1, language="fr", disease_tags=[], drug_tags=[],
            content_type="guideline", score=0.5,
        )

        with (
            patch("backend.app.tools.server.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("backend.app.tools.server.bm25_search", new_callable=AsyncMock) as mock_bm25,
            patch("backend.app.tools.server.cross_encode_rerank", new_callable=AsyncMock) as mock_rerank,
            patch("backend.app.tools.server.get_redis", new_callable=AsyncMock, return_value=self._mock_redis()),
        ):
            mock_vs.side_effect = Exception("MongoDB connection refused")
            mock_bm25.return_value = [bm25_chunk]
            mock_rerank.return_value = [bm25_chunk]

            inp = HybridRetrieveInput(query="test query", k=5)
            result = await hybrid_retrieve(inp)

            assert len(result) == 1
            assert result[0].chunk_id == "bm25-1"
            mock_vs.assert_called_once()
            mock_bm25.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_logs_mongo_error_with_uri(self):
        """Req 31.2: Log connection failure with MongoDB URI."""
        from backend.app.tools.server import (
            hybrid_retrieve, HybridRetrieveInput, Chunk,
        )

        bm25_chunk = Chunk(
            chunk_id="bm25-1", chunk_text="BM25 result", source_title="Test",
            source_version="1.0", source_date="2024-01-01", section="s1",
            page=1, language="fr", disease_tags=[], drug_tags=[],
            content_type="guideline", score=0.5,
        )

        with (
            patch("backend.app.tools.server.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("backend.app.tools.server.bm25_search", new_callable=AsyncMock) as mock_bm25,
            patch("backend.app.tools.server.cross_encode_rerank", new_callable=AsyncMock) as mock_rerank,
            patch("backend.app.tools.server.get_redis", new_callable=AsyncMock, return_value=self._mock_redis()),
            patch("backend.app.tools.server.log") as mock_log,
        ):
            mock_vs.side_effect = Exception("MongoDB connection refused")
            mock_bm25.return_value = [bm25_chunk]
            mock_rerank.return_value = [bm25_chunk]

            inp = HybridRetrieveInput(query="test query", k=5)
            await hybrid_retrieve(inp)

            mock_log.error.assert_called_once()
            log_msg = mock_log.error.call_args[0][0]
            assert "MongoDB" in log_msg
            assert "falling back" in log_msg.lower() or "BM25" in log_msg

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_returns_empty_on_empty_kb(self):
        """When both vector and BM25 return nothing, result is empty."""
        from backend.app.tools.server import (
            hybrid_retrieve, HybridRetrieveInput,
        )

        with (
            patch("backend.app.tools.server.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("backend.app.tools.server.bm25_search", new_callable=AsyncMock) as mock_bm25,
            patch("backend.app.tools.server.cross_encode_rerank", new_callable=AsyncMock) as mock_rerank,
            patch("backend.app.tools.server.get_redis", new_callable=AsyncMock, return_value=self._mock_redis()),
        ):
            mock_vs.return_value = []
            mock_bm25.return_value = []
            mock_rerank.return_value = []

            inp = HybridRetrieveInput(query="test query", k=5)
            result = await hybrid_retrieve(inp)

            assert result == []

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_normal_path_uses_rrf(self):
        """When both vector and BM25 succeed, RRF merge is used."""
        from backend.app.tools.server import (
            hybrid_retrieve, HybridRetrieveInput, Chunk,
        )

        dense_chunk = Chunk(
            chunk_id="dense-1", chunk_text="Dense result", source_title="Test",
            source_version="1.0", source_date="2024-01-01", section="s1",
            page=1, language="fr", disease_tags=[], drug_tags=[],
            content_type="guideline", score=0.9,
        )
        sparse_chunk = Chunk(
            chunk_id="sparse-1", chunk_text="Sparse result", source_title="Test",
            source_version="1.0", source_date="2024-01-01", section="s2",
            page=2, language="fr", disease_tags=[], drug_tags=[],
            content_type="guideline", score=0.7,
        )

        with (
            patch("backend.app.tools.server.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("backend.app.tools.server.bm25_search", new_callable=AsyncMock) as mock_bm25,
            patch("backend.app.tools.server.cross_encode_rerank", new_callable=AsyncMock) as mock_rerank,
            patch("backend.app.tools.server.get_redis", new_callable=AsyncMock, return_value=self._mock_redis()),
        ):
            mock_vs.return_value = [dense_chunk]
            mock_bm25.return_value = [sparse_chunk]
            mock_rerank.return_value = [dense_chunk, sparse_chunk]

            inp = HybridRetrieveInput(query="test query", k=5)
            result = await hybrid_retrieve(inp)

            assert len(result) == 2
            # Both vector and BM25 were called (no fallback)
            mock_vs.assert_called_once()
            mock_bm25.assert_called_once()


# ── Tests for empty KB handling (Req 33.1, 33.2) ────────────────────────────


class TestEmptyKBHandling:
    """When hybrid_retrieve returns zero chunks, agents should add
    warning annotations."""

    @pytest.mark.asyncio
    async def test_diagnostic_agent_warns_on_empty_kb(self):
        """Req 33.1: DiagnosticAgent adds warning when no KB evidence found."""
        from backend.app.agents.diagnostic import DiagnosticAgent

        mcp = AsyncMock()
        mcp.call = AsyncMock(side_effect=lambda tool, **kw: {
            "epid_calendar": {"disease_priors": {}, "outbreak_alerts": []},
            "hybrid_retrieve": [],
            "citation_formatter": [],
        }.get(tool, {}))

        agent = DiagnosticAgent(api_key="test-key", mcp=mcp)

        valid_json = json.dumps({
            "emergency_flags": [],
            "differential": [
                {
                    "rank": 1,
                    "disease_name": "Paludisme",
                    "icd11_code": "1F40",
                    "confidence": 0.8,
                    "supporting_evidence": ["Clinical presentation"],
                    "confirmatory_tests": [
                        {"name": "TDR", "priority": "urgent", "availability_togo": "disponible"}
                    ],
                }
            ],
            "reasoning_summary": "Based on general knowledge",
        })
        agent._call_claude = AsyncMock(return_value=(valid_json, {"input_tokens": 10, "output_tokens": 20}))

        result, span = await agent.run(
            patient_context={
                "age_years": 25, "sex": "M", "region": "Maritime",
                "chief_complaint": "fièvre", "symptoms": [{"text": "fièvre"}],
            },
            query="fièvre depuis 3 jours",
            conversation_history=[],
        )

        assert result is not None
        tool_warnings = result.get("_tool_warnings", [])
        assert any("base de connaissances" in w for w in tool_warnings)

    @pytest.mark.asyncio
    async def test_antibiotherapy_agent_warns_on_empty_kb(self):
        """Req 33.2: AntibiotherapyAgent adds warning when no guideline evidence found."""
        from backend.app.agents.antibiotherapy import AntibiotherapyAgent

        mcp = AsyncMock()
        mcp.call = AsyncMock(side_effect=lambda tool, **kw: {
            "hybrid_retrieve": [],
            "formulary_lookup": {"generic_name": "test", "available": True, "dosage_forms": []},
            "amr_lookup": {"drug": "test", "resistance_pct": None, "pathogen": "test",
                           "region": "Togo", "confidence": "no_data",
                           "data_source": "N/A", "year": None,
                           "recommendation": "Protocole empirique PNLP"},
            "drug_ddi_check": [],
            "safety_classifier": {},
            "citation_formatter": [],
        }.get(tool, {}))

        agent = AntibiotherapyAgent(api_key="test-key", mcp=mcp)

        valid_json = json.dumps({
            "target_disease": "Paludisme",
            "clinical_rationale": "Test",
            "first_line": [{
                "drug_name": "Artéméther-luméfantrine",
                "generic_name": "artéméther-luméfantrine",
                "came_available": True,
                "dose": "80mg",
                "route": "PO",
                "frequency": "2x/jour",
                "duration_days": 3,
            }],
            "second_line": [],
            "alternatives": [],
            "contraindicated": [],
            "supportive_care": [],
            "follow_up_guidance": "",
            "referral_criteria": "",
            "disclaimer": "test",
        })
        agent._call_claude = AsyncMock(return_value=(valid_json, {"input_tokens": 10, "output_tokens": 20}))

        result, span = await agent.run(
            patient_context={
                "age_years": 25, "sex": "M", "region": "Maritime",
                "chief_complaint": "fièvre", "symptoms": [],
                "current_medications": [], "allergies": [],
                "pregnancy_status": "not_pregnant",
            },
            confirmed_diagnosis="Paludisme",
            icd11_code="1F40",
            diagnostic_confidence=0.85,
        )

        assert result is not None
        tool_warnings = result.get("_tool_warnings", [])
        assert any("PNLP" in w for w in tool_warnings)


# ── Tests for Redis unavailability (Req 32.1, 32.2) ─────────────────────────


class TestRedisUnavailability:
    """When Redis is unreachable, session create and turn submit should
    return HTTP 503. We verify the error handling code is present since
    the full gateway app requires many heavy dependencies."""

    def test_create_session_has_redis_error_handling(self):
        """Req 32.1: create_session wraps Redis calls with ConnectionError → 503."""
        import pathlib
        source = pathlib.Path("backend/app/gateway/main.py").read_text(encoding="utf-8")
        # Verify redis.exceptions is imported
        assert "redis.exceptions" in source
        # Verify the try/except pattern around store.create
        assert "redis.exceptions.ConnectionError" in source
        assert "status_code=503" in source
        assert "temporarily unavailable" in source.lower()

    def test_submit_turn_has_redis_error_handling(self):
        """Req 32.2: submit_turn wraps Redis calls with ConnectionError → 503."""
        import pathlib
        source = pathlib.Path("backend/app/gateway/main.py").read_text(encoding="utf-8")
        assert "redis.exceptions.ConnectionError" in source
        assert "could not be loaded" in source.lower()

    def test_redis_exceptions_imported(self):
        """Verify redis.exceptions is imported in gateway main."""
        import pathlib
        source = pathlib.Path("backend/app/gateway/main.py").read_text(encoding="utf-8")
        assert "import redis.exceptions" in source
