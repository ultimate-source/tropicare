# ─────────────────────────────────────────────────────────────────────────────
# tests/unit/tools/test_performance_caching.py
# Unit tests for performance caching (Requirement 30)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import hashlib
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Stub heavy dependencies before importing application modules ──────────────

def _ensure_stubs():
    """Stub out heavy/unavailable dependencies so server.py can be imported."""
    class _FakeMCP:
        def __init__(self, **kw):
            pass

        def tool(self, **kw):
            def decorator(fn):
                return fn
            return decorator

        def get_asgi_app(self):
            return MagicMock()

    for mod_name in ["sentence_transformers"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()
    sys.modules["sentence_transformers"].CrossEncoder = MagicMock()

    fake_fastmcp = MagicMock()
    fake_fastmcp.FastMCP = _FakeMCP
    sys.modules["fastmcp"] = fake_fastmcp


_ensure_stubs()

from backend.app.tools.server import (
    Chunk,
    HybridRetrieveInput,
    _hybrid_cache_key,
    hybrid_retrieve,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_chunk(**overrides) -> Chunk:
    defaults = dict(
        chunk_id="c1",
        chunk_text="sample text",
        source_title="Guide PNLP",
        source_version="2024",
        source_date="2024-01-01",
        section="Paludisme",
        page=1,
        language="fr",
        disease_tags=["1F40"],
        drug_tags=[],
        content_type="guideline",
        score=0.9,
    )
    defaults.update(overrides)
    return Chunk(**defaults)


# ── Tests: hybrid_retrieve cache key ─────────────────────────────────────────

def test_hybrid_cache_key_deterministic():
    """Same inputs produce the same cache key."""
    inp = HybridRetrieveInput(query="fièvre", k=8, disease_tags=["1F40"], language="fr")
    assert _hybrid_cache_key(inp) == _hybrid_cache_key(inp)


def test_hybrid_cache_key_different_queries():
    """Different queries produce different cache keys."""
    a = HybridRetrieveInput(query="fièvre", k=8)
    b = HybridRetrieveInput(query="diarrhée", k=8)
    assert _hybrid_cache_key(a) != _hybrid_cache_key(b)


def test_hybrid_cache_key_tag_order_independent():
    """Disease tags in different order produce the same key (sorted internally)."""
    a = HybridRetrieveInput(query="q", disease_tags=["1F40", "1C1A"])
    b = HybridRetrieveInput(query="q", disease_tags=["1C1A", "1F40"])
    assert _hybrid_cache_key(a) == _hybrid_cache_key(b)


def test_hybrid_cache_key_prefix():
    """Cache key starts with 'hybrid:' prefix."""
    inp = HybridRetrieveInput(query="test")
    assert _hybrid_cache_key(inp).startswith("hybrid:")


# ── Tests: hybrid_retrieve Redis cache hit ────────────────────────────────────

@pytest.mark.asyncio
async def test_hybrid_retrieve_returns_cached_result():
    """When Redis has a cached result, hybrid_retrieve returns it without calling vector/bm25."""
    chunk = _make_chunk()
    cached_json = json.dumps([chunk.model_dump()])

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached_json)

    with patch("backend.app.tools.server.get_redis", return_value=mock_redis), \
         patch("backend.app.tools.server.vector_search") as mock_vs, \
         patch("backend.app.tools.server.bm25_search") as mock_bm:

        inp = HybridRetrieveInput(query="fièvre", k=8)
        result = await hybrid_retrieve(inp)

        assert len(result) == 1
        assert result[0].chunk_id == "c1"
        mock_vs.assert_not_called()
        mock_bm.assert_not_called()


# ── Tests: hybrid_retrieve Redis cache miss → stores result ───────────────────

@pytest.mark.asyncio
async def test_hybrid_retrieve_stores_result_on_cache_miss():
    """On cache miss, hybrid_retrieve executes pipeline and caches result with 1h TTL."""
    chunk = _make_chunk()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    with patch("backend.app.tools.server.get_redis", return_value=mock_redis), \
         patch("backend.app.tools.server.vector_search", new_callable=AsyncMock, return_value=[chunk]), \
         patch("backend.app.tools.server.bm25_search", new_callable=AsyncMock, return_value=[chunk]), \
         patch("backend.app.tools.server.cross_encode_rerank", new_callable=AsyncMock, return_value=[chunk]):

        inp = HybridRetrieveInput(query="fièvre", k=8)
        result = await hybrid_retrieve(inp)

        assert len(result) == 1
        # Verify setex was called with 3600s TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # 1-hour TTL


# ── Tests: hybrid_retrieve graceful Redis failure ─────────────────────────────

@pytest.mark.asyncio
async def test_hybrid_retrieve_works_when_redis_unavailable():
    """When Redis raises an exception, hybrid_retrieve still returns results."""
    chunk = _make_chunk()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis down"))

    with patch("backend.app.tools.server.get_redis", return_value=mock_redis), \
         patch("backend.app.tools.server.vector_search", new_callable=AsyncMock, return_value=[chunk]), \
         patch("backend.app.tools.server.bm25_search", new_callable=AsyncMock, return_value=[chunk]), \
         patch("backend.app.tools.server.cross_encode_rerank", new_callable=AsyncMock, return_value=[chunk]):

        inp = HybridRetrieveInput(query="fièvre", k=8)
        result = await hybrid_retrieve(inp)

        assert len(result) == 1
        assert result[0].chunk_id == "c1"


# ── Tests: embed_text caching ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_text_returns_cached_embedding():
    """When Redis has a cached embedding, embed_text returns it without calling OpenAI."""
    from backend.app.tools.embedder import embed_text

    fake_embedding = [0.1, 0.2, 0.3]
    cached_json = json.dumps(fake_embedding)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=cached_json)

    with patch("backend.app.tools.embedder.get_redis", return_value=mock_redis), \
         patch("httpx.AsyncClient") as mock_client_cls:

        result = await embed_text("test query")

        assert result == fake_embedding
        mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_embed_text_caches_result_on_miss():
    """On cache miss, embed_text calls OpenAI and caches with 24h TTL."""
    from backend.app.tools.embedder import embed_text

    fake_embedding = [0.1, 0.2, 0.3]

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": fake_embedding}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.tools.embedder.get_redis", return_value=mock_redis), \
         patch("httpx.AsyncClient", return_value=mock_client):

        result = await embed_text("test query")

        assert result == fake_embedding
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 86_400  # 24h TTL


@pytest.mark.asyncio
async def test_embed_text_works_when_redis_unavailable():
    """When Redis is down, embed_text still returns the embedding from OpenAI."""
    from backend.app.tools.embedder import embed_text

    fake_embedding = [0.4, 0.5, 0.6]

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis down"))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": fake_embedding}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.tools.embedder.get_redis", return_value=mock_redis), \
         patch("httpx.AsyncClient", return_value=mock_client):

        result = await embed_text("test query")
        assert result == fake_embedding


@pytest.mark.asyncio
async def test_embed_text_cache_key_uses_sha256():
    """Verify the cache key is based on SHA-256 of the input text."""
    from backend.app.tools.embedder import embed_text

    query = "fièvre depuis 3 jours"
    expected_hash = hashlib.sha256(query.encode()).hexdigest()
    expected_key = f"embed:{expected_hash}"

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps([0.1]))

    with patch("backend.app.tools.embedder.get_redis", return_value=mock_redis):
        await embed_text(query)
        mock_redis.get.assert_called_once_with(expected_key)


# ── Tests: session store TTL and history limit (verification) ─────────────────

def test_session_store_ttl_is_24h():
    """Req 30.2: SessionStore.TTL is 86400 seconds (24 hours)."""
    from backend.app.orchestrator.session import SessionStore
    assert SessionStore.TTL == 86_400


@pytest.mark.asyncio
async def test_session_store_limits_history_to_20():
    """Req 30.2: append_turn truncates conversation history to 20 entries."""
    from backend.app.orchestrator.session import SessionStore

    mock_redis = AsyncMock()
    store = SessionStore.__new__(SessionStore)
    store._redis = mock_redis

    # Simulate a session with 25 turns already
    existing_data = {
        "session_id": "test-session",
        "patient_context": {},
        "conversation_history": [{"turn": i} for i in range(25)],
        "language": "fr",
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(existing_data))
    mock_redis.set = AsyncMock()

    await store.append_turn("test-session", {"turn": 25})

    # Verify the stored data has at most 20 turns
    call_args = mock_redis.set.call_args
    stored_data = json.loads(call_args[0][1])
    assert len(stored_data["conversation_history"]) == 20


# ── Tests: database connection pool config (verification) ─────────────────────

def test_postgres_pool_config():
    """Req 30.3: get_postgres_pool uses min_size=2, max_size=10."""
    import inspect
    from backend.app.tools.db import get_postgres_pool

    source = inspect.getsource(get_postgres_pool)
    assert "min_size=2" in source
    assert "max_size=10" in source
