# ─────────────────────────────────────────────────────────────────────────────
# tests/unit/test_circuit_breaker.py — Unit tests for CircuitBreaker
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from backend.app.gateway.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    llm_breaker,
    mcp_breaker,
)


class TestCircuitBreakerStates:
    """Test state transitions: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_raises_error_on_check(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.check()
        assert "test" in str(exc_info.value)

    def test_transitions_to_half_open_after_recovery(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_seconds=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_check(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_seconds=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        # Should not raise
        cb.check()

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_seconds=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_seconds=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerWindow:
    """Test that failures outside the window are pruned."""

    def test_old_failures_are_pruned(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, window_seconds=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        # Old failures should be pruned; one new failure shouldn't trip
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_failures_within_window_accumulate(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, window_seconds=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerReset:
    """Test manual reset."""

    def test_reset_returns_to_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        # Should not raise after reset
        cb.check()


class TestModuleInstances:
    """Test that module-level breaker instances are configured correctly."""

    def test_llm_breaker_config(self):
        assert llm_breaker.name == "llm"
        assert llm_breaker.failure_threshold == 5
        assert llm_breaker.window_seconds == 60
        assert llm_breaker.recovery_seconds == 30

    def test_mcp_breaker_config(self):
        assert mcp_breaker.name == "mcp"
        assert mcp_breaker.failure_threshold == 5
        assert mcp_breaker.window_seconds == 60
        assert mcp_breaker.recovery_seconds == 30
