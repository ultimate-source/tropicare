"""Integration tests for Gateway endpoints.

Validates: Requirements 16.4, 16.5, 16.6, 16.7
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.gateway.auth import get_current_user


# ── Helpers ───────────────────────────────────────────────────────────────────

CLINICIAN_USER = {"sub": "user-1", "email": "doc@example.com", "roles": ["clinician"]}
ADMIN_USER = {"sub": "admin-1", "email": "admin@example.com", "roles": ["admin", "clinician"]}


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


@pytest.fixture()
def mock_pg_pool():
    """Async mock that behaves like asyncpg.Pool."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool.acquire = _acquire_cm(conn)
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.fixture()
def mock_session_store():
    """Mock SessionStore with sensible defaults."""
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
    return store


@pytest.fixture()
def mock_orchestrator():
    """Mock Orchestrator whose handle_turn yields NDJSON events."""
    orch = AsyncMock()

    async def _fake_handle_turn(**kwargs):
        yield {"type": "thinking", "content": "Analyse…"}
        yield {"type": "differential_item", "item": {"rank": 1, "disease_name": "Paludisme"}}
        yield {"type": "done", "turn_id": "turn-1"}

    orch.handle_turn = MagicMock(side_effect=_fake_handle_turn)
    return orch


def _make_app(pg_pool, session_store, orchestrator, current_user_dict):
    """Build the FastAPI app with mocked state and auth override."""
    from backend.app.gateway.main import app

    app.state.pg_pool = pg_pool
    app.state.session_store = session_store
    app.state.audit_logger = AsyncMock()
    app.state.orchestrator = orchestrator

    async def _fake_current_user():
        return current_user_dict

    app.dependency_overrides[get_current_user] = _fake_current_user
    return app


@pytest.fixture()
def app_clinician(mock_pg_pool, mock_session_store, mock_orchestrator):
    """App with clinician auth."""
    app = _make_app(mock_pg_pool, mock_session_store, mock_orchestrator, CLINICIAN_USER)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def app_admin(mock_pg_pool, mock_session_store, mock_orchestrator):
    """App with admin auth."""
    app = _make_app(mock_pg_pool, mock_session_store, mock_orchestrator, ADMIN_USER)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
async def clinician_client(app_clinician):
    transport = ASGITransport(app=app_clinician, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin_client(app_admin):
    transport = ASGITransport(app=app_admin, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Session creation (Requirement 16.4) ──────────────────────────────────────


class TestSessionCreation:
    """POST /api/v1/sessions → 201 with valid session_id."""

    @pytest.mark.asyncio
    async def test_create_session_returns_201(self, clinician_client, mock_session_store):
        resp = await clinician_client.post(
            "/api/v1/sessions",
            json={"patient_context": {"age_years": 35}, "language": "fr"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "session_id" in body
        assert isinstance(body["session_id"], str)
        assert len(body["session_id"]) > 0

    @pytest.mark.asyncio
    async def test_create_session_calls_store(self, clinician_client, mock_session_store):
        await clinician_client.post(
            "/api/v1/sessions",
            json={"patient_context": {}, "language": "fr"},
        )
        mock_session_store.create.assert_awaited_once()
        mock_session_store.register_session.assert_awaited_once()


# ── Turn submission (Requirement 16.5) ────────────────────────────────────────


class TestTurnSubmission:
    """POST /api/v1/sessions/{id}/turns → NDJSON streaming."""

    @pytest.mark.asyncio
    async def test_submit_turn_returns_ndjson_stream(self, clinician_client):
        resp = await clinician_client.post(
            "/api/v1/sessions/test-session/turns",
            json={"query": "Fièvre depuis 3 jours", "mode": "auto"},
        )
        assert resp.status_code == 200
        assert "application/x-ndjson" in resp.headers.get("content-type", "")

        lines = [l for l in resp.text.strip().split("\n") if l]
        assert len(lines) >= 2  # at least thinking + done

        events = [json.loads(line) for line in lines]
        event_types = [e["type"] for e in events]
        assert "thinking" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_submit_turn_contains_differential(self, clinician_client):
        resp = await clinician_client.post(
            "/api/v1/sessions/test-session/turns",
            json={"query": "Fièvre", "mode": "auto"},
        )
        lines = [l for l in resp.text.strip().split("\n") if l]
        events = [json.loads(line) for line in lines]
        event_types = [e["type"] for e in events]
        assert "differential_item" in event_types

    @pytest.mark.asyncio
    async def test_submit_turn_404_for_missing_session(
        self, clinician_client, mock_session_store
    ):
        mock_session_store.get = AsyncMock(return_value={})
        resp = await clinician_client.post(
            "/api/v1/sessions/nonexistent/turns",
            json={"query": "test", "mode": "auto"},
        )
        assert resp.status_code == 404


# ── Feedback submission (Requirement 16.6) ────────────────────────────────────


class TestFeedbackSubmission:
    """POST /api/v1/feedback → 201."""

    @pytest.mark.asyncio
    async def test_submit_feedback_returns_201(self, clinician_client):
        resp = await clinician_client.post(
            "/api/v1/feedback",
            json={
                "turn_id": "turn-abc",
                "verdict": "correct",
                "clinician_note": "Bon diagnostic",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "accepted"


# ── Admin document endpoints (Requirement 16.7) ──────────────────────────────


class TestAdminDocuments:
    """Admin endpoints: 403 for non-admin, 200/202/204 for admin."""

    @pytest.mark.asyncio
    async def test_list_documents_forbidden_for_clinician(
        self, mock_pg_pool, mock_session_store, mock_orchestrator
    ):
        """Clinician role (no admin) should get 403 on admin endpoints."""
        app = _make_app(mock_pg_pool, mock_session_store, mock_orchestrator, CLINICIAN_USER)
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/admin/documents")
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_documents_ok_for_admin(self, admin_client, mock_pg_pool):
        mock_pg_pool.fetch = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/v1/admin/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_supersede_document_ok_for_admin(self, admin_client):
        resp = await admin_client.delete(
            "/api/v1/admin/documents/doc-123",
            params={"reason_id": "newer-doc-456"},
        )
        assert resp.status_code == 204
