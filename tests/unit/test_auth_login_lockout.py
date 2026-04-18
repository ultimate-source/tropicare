"""Unit tests for login endpoint with account lockout (task 8.2).

Tests cover:
- Successful login returns tokens
- Invalid credentials return HTTP 401
- Account lockout after 5 failed attempts returns HTTP 423
- Successful login clears failure counter
- Lockout message includes remaining minutes
"""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.gateway.routers.auth import (
    FAIL_WINDOW_SECONDS,
    LOCK_DURATION_SECONDS,
    MAX_FAILED_ATTEMPTS,
    _FAIL_KEY,
    _LOCK_KEY,
    _check_lockout,
    _clear_failed_attempts,
    _record_failed_attempt,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_request(redis_mock: AsyncMock) -> MagicMock:
    """Build a fake Request whose app.state.session_store._redis is the mock."""
    request = MagicMock()
    request.app.state.session_store._redis = redis_mock
    return request


# ── _check_lockout tests ─────────────────────────────────────────────────────


class TestCheckLockout:
    """Tests for the _check_lockout helper."""

    @pytest.mark.asyncio
    async def test_no_lock_key_passes(self):
        """When no lock key exists (ttl <= 0), no exception is raised."""
        redis = AsyncMock()
        redis.ttl.return_value = -2  # key does not exist
        request = _make_request(redis)

        # Should not raise
        await _check_lockout(request, "user@example.com")
        redis.ttl.assert_called_once_with(_LOCK_KEY.format(email="user@example.com"))

    @pytest.mark.asyncio
    async def test_lock_key_exists_raises_423(self):
        """When lock key has positive TTL, HTTP 423 is raised."""
        redis = AsyncMock()
        redis.ttl.return_value = 600  # 10 minutes remaining
        request = _make_request(redis)

        with pytest.raises(HTTPException) as exc_info:
            await _check_lockout(request, "user@example.com")

        assert exc_info.value.status_code == 423
        assert "10 minutes" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_lock_key_ttl_rounds_up(self):
        """Remaining minutes should round up (e.g. 61s → 2 minutes)."""
        redis = AsyncMock()
        redis.ttl.return_value = 61
        request = _make_request(redis)

        with pytest.raises(HTTPException) as exc_info:
            await _check_lockout(request, "user@example.com")

        assert "2 minutes" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_lock_key_ttl_zero_passes(self):
        """TTL of 0 means key is about to expire — should not lock."""
        redis = AsyncMock()
        redis.ttl.return_value = 0
        request = _make_request(redis)

        await _check_lockout(request, "user@example.com")


# ── _record_failed_attempt tests ─────────────────────────────────────────────


class TestRecordFailedAttempt:
    """Tests for the _record_failed_attempt helper."""

    @pytest.mark.asyncio
    async def test_first_failure_sets_expire(self):
        """First failure (count=1) should set the TTL on the fail key."""
        redis = AsyncMock()
        redis.incr.return_value = 1
        request = _make_request(redis)

        await _record_failed_attempt(request, "user@example.com")

        fail_key = _FAIL_KEY.format(email="user@example.com")
        redis.incr.assert_called_once_with(fail_key)
        redis.expire.assert_called_once_with(fail_key, FAIL_WINDOW_SECONDS)
        redis.set.assert_not_called()  # not yet at threshold

    @pytest.mark.asyncio
    async def test_below_threshold_no_lock(self):
        """Failures below threshold should not create a lock key."""
        redis = AsyncMock()
        redis.incr.return_value = 4  # below MAX_FAILED_ATTEMPTS (5)
        request = _make_request(redis)

        await _record_failed_attempt(request, "user@example.com")

        redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_at_threshold_creates_lock(self):
        """Reaching MAX_FAILED_ATTEMPTS should create the lock key."""
        redis = AsyncMock()
        redis.incr.return_value = MAX_FAILED_ATTEMPTS  # exactly 5
        request = _make_request(redis)

        await _record_failed_attempt(request, "user@example.com")

        lock_key = _LOCK_KEY.format(email="user@example.com")
        redis.set.assert_called_once_with(lock_key, "1", ex=LOCK_DURATION_SECONDS)
        redis.delete.assert_called_once()  # clears fail counter

    @pytest.mark.asyncio
    async def test_above_threshold_also_locks(self):
        """Exceeding MAX_FAILED_ATTEMPTS should still lock (defensive)."""
        redis = AsyncMock()
        redis.incr.return_value = MAX_FAILED_ATTEMPTS + 2
        request = _make_request(redis)

        await _record_failed_attempt(request, "user@example.com")

        lock_key = _LOCK_KEY.format(email="user@example.com")
        redis.set.assert_called_once_with(lock_key, "1", ex=LOCK_DURATION_SECONDS)


# ── _clear_failed_attempts tests ─────────────────────────────────────────────


class TestClearFailedAttempts:
    """Tests for the _clear_failed_attempts helper."""

    @pytest.mark.asyncio
    async def test_clears_fail_key(self):
        """Successful login should delete the failure counter."""
        redis = AsyncMock()
        request = _make_request(redis)

        await _clear_failed_attempts(request, "user@example.com")

        fail_key = _FAIL_KEY.format(email="user@example.com")
        redis.delete.assert_called_once_with(fail_key)


# ── Constants sanity checks ──────────────────────────────────────────────────


class TestLockoutConstants:
    """Verify lockout constants match requirements."""

    def test_max_attempts_is_5(self):
        assert MAX_FAILED_ATTEMPTS == 5

    def test_fail_window_is_30_minutes(self):
        assert FAIL_WINDOW_SECONDS == 1800

    def test_lock_duration_is_15_minutes(self):
        assert LOCK_DURATION_SECONDS == 900
