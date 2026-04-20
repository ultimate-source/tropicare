"""Unit tests for updated gateway session routes (session persistence).

Validates: Requirements 1.3, 3.1, 4.1, 4.4, 9.4
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.gateway.auth import get_current_user


# ── Helpers ───────────────────────────────────────────────────────────────────

CLINICIAN_USER = {"sub": "user-1", "email": "doc@example.com", "roles": ["clinician"]}


def _acquire_cm(conn):
    """Build a callable that returns an async context manager yielding *conn*."""
    class _CM:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            return False
    def factory():
        return _CM()
    return factory


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_pg_pool():
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool.acquire = _acquire_cm(conn)
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.fixture()
def mock_session_store():
    store = AsyncMock()
    store.count_user_sessions = AsyncMock(return_value=0)
    store.create = AsyncMock()
    store.register_session = AsyncMock()
    store.get = AsyncMock(return_value={
        "session_id": "test-session",
        "patient_context": {"age_years": 30, "sex": "M"},
        "conversation_history": [],
        "language": "fr",
    })
    store.get_or_fallback = AsyncMock(return_value={
        "session_id": "test-session",
        "patient_context": {"age_years": 30, "sex": "M"},
        "conversation_history": [],
        "language": "fr",
        "status": "closed",
    })
    return store


@pytest.fixture()
def mock_session_repo():
    repo = AsyncMock()
    repo.archive_expired = AsyncMock()
    repo.list_sessions = AsyncMock(return_value=([], 0))
    repo.close_session = AsyncMock()
    repo.get_session_detail = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
def mock_orchestrator():
    return AsyncMock()


def _make_app(pg_pool, session_store, session_repo, orchestrator, current_user_dict):
    from backend.app.gateway.main import app

    app.state.pg_pool = pg_pool
    app.state.session_store = session_store
    app.state.session_repo = session_repo
    app.state.audit_logger = AsyncMock()
    app.state.orchestrator = orchestrator

    async def _fake_current_user():
        return current_user_dict

    app.dependency_overrides[get_current_user] = _fake_current_user
    return app


@pytest.fixture()
def app_clinician(mock_pg_pool, mock_session_store, mock_session_repo, mock_orchestrator):
    app = _make_app(
        mock_pg_pool, mock_session_store, mock_session_repo,
        mock_orchestrator, CLINICIAN_USER,
    )
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(app_clinician):
    transport = ASGITransport(app=app_clinician, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Test: POST /api/v1/sessions passes user_id (Req 1.3) ─────────────────────


class TestCreateSessionUserId:
    """POST /api/v1/sessions should pass user_id to DualWriteSessionStore.create()."""

    @pytest.mark.asyncio
    async def test_create_passes_user_id(self, client, mock_session_store):
        resp = await client.post(
            "/api/v1/sessions",
            json={"patient_context": {"age_years": 40}, "language": "fr"},
        )
        assert resp.status_code == 201
        mock_session_store.create.assert_awaited_once()
        call_kwargs = mock_session_store.create.call_args
        assert call_kwargs.kwargs.get("user_id") == "user-1"

    @pytest.mark.asyncio
    async def test_create_user_id_matches_auth_sub(self, client, mock_session_store):
        await client.post(
            "/api/v1/sessions",
            json={"patient_context": {}, "language": "en"},
        )
        call_kwargs = mock_session_store.create.call_args
        assert call_kwargs.kwargs["user_id"] == CLINICIAN_USER["sub"]


# ── Test: GET /api/v1/sessions reads from PG (Req 3.1) ───────────────────────


class TestListSessions:
    """GET /api/v1/sessions should read from SessionRepository."""

    @pytest.mark.asyncio
    async def test_list_reads_from_pg_repo(self, client, mock_session_repo):
        mock_session_repo.list_sessions.return_value = ([
            {
                "id": "s1", "created_at": "2026-01-01T00:00:00",
                "language": "fr", "turn_count": 2, "last_query": "test",
                "status": "closed",
            },
        ], 1)

        resp = await client.get("/api/v1/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["sessions"]) == 1
        assert body["sessions"][0]["id"] == "s1"
        mock_session_repo.list_sessions.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_excludes_archived_by_default(self, client, mock_session_repo):
        await client.get("/api/v1/sessions")
        call_kwargs = mock_session_repo.list_sessions.call_args
        assert call_kwargs.kwargs.get("include_archived") is False or \
               (len(call_kwargs.args) >= 2 and call_kwargs.args[1] is False)

    @pytest.mark.asyncio
    async def test_list_includes_archived_with_query_param(self, client, mock_session_repo):
        """Req 9.4: include_archived=true should pass through to repo."""
        await client.get("/api/v1/sessions?include_archived=true")
        call_kwargs = mock_session_repo.list_sessions.call_args
        # Check include_archived was True
        assert call_kwargs.kwargs.get("include_archived") is True or \
               (len(call_kwargs.args) >= 2 and call_kwargs.args[1] is True)

    @pytest.mark.asyncio
    async def test_list_returns_paginated_response(self, client, mock_session_repo):
        mock_session_repo.list_sessions.return_value = ([], 0)
        resp = await client.get("/api/v1/sessions?limit=10&offset=5")
        body = resp.json()
        assert body["limit"] == 10
        assert body["offset"] == 5
        assert "total" in body
        assert "sessions" in body

    @pytest.mark.asyncio
    async def test_list_calls_archive_expired(self, client, mock_session_repo):
        """Retention-based archival should be triggered on list."""
        await client.get("/api/v1/sessions")
        mock_session_repo.archive_expired.assert_awaited_once_with("user-1")


# ── Test: GET /api/v1/sessions/{id} fallback (Req 4.1, 4.4) ──────────────────


class TestGetSessionDetail:
    """GET /api/v1/sessions/{id} should try Redis first, fall back to PG."""

    @pytest.mark.asyncio
    async def test_detail_returns_data_from_redis(self, client, mock_session_store):
        """Req 4.1: Redis-first read."""
        resp = await client.get("/api/v1/sessions/test-session")
        assert resp.status_code == 200
        mock_session_store.get_or_fallback.assert_awaited_once_with("test-session")

    @pytest.mark.asyncio
    async def test_detail_returns_404_when_both_miss(self, client, mock_session_store):
        """Req 4.4: 404 when not found in either store."""
        mock_session_store.get_or_fallback.return_value = None
        resp = await client.get("/api/v1/sessions/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"

    @pytest.mark.asyncio
    async def test_detail_returns_503_on_pg_failure(self, client, mock_session_store):
        """503 when PG fails after Redis miss."""
        mock_session_store.get_or_fallback.side_effect = Exception("PG connection error")
        resp = await client.get("/api/v1/sessions/test-session")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_detail_returns_pg_data_on_redis_miss(self, client, mock_session_store):
        """Req 4.2: Falls back to PG when Redis misses."""
        pg_data = {
            "session_id": "pg-session",
            "patient_context": {"age_years": 50},
            "language": "fr",
            "created_at": "2026-01-01T00:00:00",
            "status": "closed",
            "conversation_history": [],
        }
        mock_session_store.get_or_fallback.return_value = pg_data
        resp = await client.get("/api/v1/sessions/pg-session")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "pg-session"


# ── Test: Lazy close on list (Req 10.1, 10.2) ────────────────────────────────


class TestLazyClose:
    """Lazy close should be triggered for active sessions missing from Redis."""

    @pytest.mark.asyncio
    async def test_lazy_close_on_list_for_active_session_missing_from_redis(
        self, client, mock_session_store, mock_session_repo,
    ):
        mock_session_repo.list_sessions.return_value = ([
            {
                "id": "s-active", "created_at": "2026-01-01T00:00:00",
                "language": "fr", "turn_count": 1, "last_query": "test",
                "status": "active",
            },
        ], 1)
        # Redis returns empty for this session
        mock_session_store.get.return_value = {}

        resp = await client.get("/api/v1/sessions")
        assert resp.status_code == 200

        # close_session should have been called for the active session
        mock_session_repo.close_session.assert_awaited_once_with("s-active")

        # The returned status should be updated to 'closed'
        body = resp.json()
        assert body["sessions"][0]["status"] == "closed"

    @pytest.mark.asyncio
    async def test_no_lazy_close_for_already_closed_session(
        self, client, mock_session_store, mock_session_repo,
    ):
        mock_session_repo.list_sessions.return_value = ([
            {
                "id": "s-closed", "created_at": "2026-01-01T00:00:00",
                "language": "fr", "turn_count": 1, "last_query": "test",
                "status": "closed",
            },
        ], 1)

        await client.get("/api/v1/sessions")
        mock_session_repo.close_session.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_lazy_close_when_session_still_in_redis(
        self, client, mock_session_store, mock_session_repo,
    ):
        mock_session_repo.list_sessions.return_value = ([
            {
                "id": "s-active", "created_at": "2026-01-01T00:00:00",
                "language": "fr", "turn_count": 1, "last_query": "test",
                "status": "active",
            },
        ], 1)
        # Redis has data for this session
        mock_session_store.get.return_value = {"session_id": "s-active"}

        resp = await client.get("/api/v1/sessions")
        mock_session_repo.close_session.assert_not_awaited()
        assert resp.json()["sessions"][0]["status"] == "active"
