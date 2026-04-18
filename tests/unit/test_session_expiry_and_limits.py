"""Unit tests for session expiry (HTTP 404) and concurrent session limits (HTTP 429).

Validates: Requirements 34.1, 34.2
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.app.orchestrator.session import SessionStore


# ── SessionStore.count_user_sessions tests ────────────────────────────────────


class TestCountUserSessions:
    """Tests for counting active sessions per user with expired cleanup."""

    @pytest.fixture()
    def store(self):
        """SessionStore with mocked Redis client."""
        s = SessionStore.__new__(SessionStore)
        s._redis = AsyncMock()
        return s

    @pytest.mark.asyncio
    async def test_no_sessions(self, store):
        """User with no sessions returns 0."""
        store._redis.smembers = AsyncMock(return_value=set())
        count = await store.count_user_sessions("user-1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_all_active(self, store):
        """All sessions still exist in Redis → count equals set size."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2", "s3"})
        store._redis.exists = AsyncMock(return_value=1)
        count = await store.count_user_sessions("user-1")
        assert count == 3

    @pytest.mark.asyncio
    async def test_some_expired(self, store):
        """Expired sessions are cleaned up and not counted."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2", "s3"})

        async def exists_side_effect(key):
            # s2 has expired
            return 0 if key == "session:s2" else 1

        store._redis.exists = AsyncMock(side_effect=exists_side_effect)
        store._redis.srem = AsyncMock()

        count = await store.count_user_sessions("user-1")
        assert count == 2
        store._redis.srem.assert_called_once_with("user_sessions:user-1", "s2")

    @pytest.mark.asyncio
    async def test_all_expired(self, store):
        """All sessions expired → count is 0 and all cleaned up."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2"})
        store._redis.exists = AsyncMock(return_value=0)
        store._redis.srem = AsyncMock()

        count = await store.count_user_sessions("user-1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_exactly_five_active(self, store):
        """Exactly 5 active sessions returns 5 (the limit boundary)."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2", "s3", "s4", "s5"})
        store._redis.exists = AsyncMock(return_value=1)
        count = await store.count_user_sessions("user-1")
        assert count == 5


# ── SessionStore.register_session / unregister_session tests ──────────────────


class TestRegisterUnregisterSession:

    @pytest.fixture()
    def store(self):
        s = SessionStore.__new__(SessionStore)
        s._redis = AsyncMock()
        return s

    @pytest.mark.asyncio
    async def test_register_session(self, store):
        store._redis.sadd = AsyncMock()
        await store.register_session("user-1", "sess-abc")
        store._redis.sadd.assert_called_once_with("user_sessions:user-1", "sess-abc")

    @pytest.mark.asyncio
    async def test_unregister_session(self, store):
        store._redis.srem = AsyncMock()
        await store.unregister_session("user-1", "sess-abc")
        store._redis.srem.assert_called_once_with("user_sessions:user-1", "sess-abc")


# ── Session expiry logic tests (Requirement 34.1) ────────────────────────────


class TestSessionExpiry:
    """Verify that expired/missing sessions return empty dict from store.get()."""

    @pytest.fixture()
    def store(self):
        s = SessionStore.__new__(SessionStore)
        s._redis = AsyncMock()
        return s

    @pytest.mark.asyncio
    async def test_get_returns_empty_for_missing_session(self, store):
        """When Redis returns None (expired TTL), store.get() returns {}."""
        store._redis.get = AsyncMock(return_value=None)
        result = await store.get("expired-session-id")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_returns_data_for_active_session(self, store):
        """When session exists, store.get() returns the session data."""
        import json
        data = {"session_id": "s1", "patient_context": {}, "language": "fr"}
        store._redis.get = AsyncMock(return_value=json.dumps(data))
        result = await store.get("s1")
        assert result == data
        assert result  # truthy — won't trigger 404


# ── Concurrent session limit logic tests (Requirement 34.2) ──────────────────


class TestConcurrentSessionLimit:
    """Verify the concurrent session limit logic that the gateway uses."""

    @pytest.fixture()
    def store(self):
        s = SessionStore.__new__(SessionStore)
        s._redis = AsyncMock()
        return s

    @pytest.mark.asyncio
    async def test_under_limit_allows_creation(self, store):
        """With fewer than 5 sessions, creation should proceed."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2"})
        store._redis.exists = AsyncMock(return_value=1)
        count = await store.count_user_sessions("user-1")
        assert count < 5

    @pytest.mark.asyncio
    async def test_at_limit_blocks_creation(self, store):
        """With 5 active sessions, the gateway should block creation (429)."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2", "s3", "s4", "s5"})
        store._redis.exists = AsyncMock(return_value=1)
        count = await store.count_user_sessions("user-1")
        assert count >= 5  # gateway would return 429

    @pytest.mark.asyncio
    async def test_expired_sessions_free_up_slots(self, store):
        """If some of 5 sessions expired, user can create new ones."""
        store._redis.smembers = AsyncMock(return_value={"s1", "s2", "s3", "s4", "s5"})

        async def exists_side_effect(key):
            # s4 and s5 expired
            return 0 if key in ("session:s4", "session:s5") else 1

        store._redis.exists = AsyncMock(side_effect=exists_side_effect)
        store._redis.srem = AsyncMock()

        count = await store.count_user_sessions("user-1")
        assert count == 3  # only 3 active, under limit

    @pytest.mark.asyncio
    async def test_register_then_count(self, store):
        """After registering a session, it appears in the count."""
        store._redis.sadd = AsyncMock()
        store._redis.smembers = AsyncMock(return_value={"new-session"})
        store._redis.exists = AsyncMock(return_value=1)

        await store.register_session("user-1", "new-session")
        count = await store.count_user_sessions("user-1")
        assert count == 1
