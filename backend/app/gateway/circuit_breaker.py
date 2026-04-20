# ─────────────────────────────────────────────────────────────────────────────
# backend/app/gateway/circuit_breaker.py — Circuit breaker for LLM + MCP calls
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import time
import threading
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open and requests are rejected."""

    def __init__(self, name: str, recovery_seconds: float):
        self.name = name
        self.recovery_seconds = recovery_seconds
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Service unavailable — retry after {recovery_seconds}s."
        )


class CircuitBreaker:
    """
    States: CLOSED → OPEN → HALF_OPEN → CLOSED
    - CLOSED: requests pass through, failures counted within a rolling window
    - OPEN: requests fail immediately (recovery_seconds cooldown)
    - HALF_OPEN: single probe request allowed; success → CLOSED, failure → OPEN

    Config: failure_threshold=5, window_seconds=60, recovery_seconds=30
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        window_seconds: float = 60,
        recovery_seconds: float = 30,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_seconds = recovery_seconds

        self._state = CircuitState.CLOSED
        self._failures: list[float] = []  # timestamps of failures within window
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.recovery_seconds:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def record_success(self) -> None:
        """Record a successful call. Resets state to CLOSED if in HALF_OPEN."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
            self._failures.clear()

    def record_failure(self) -> None:
        """Record a failed call. May trip the breaker to OPEN."""
        with self._lock:
            now = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — reopen
                self._state = CircuitState.OPEN
                self._opened_at = now
                return

            # Prune old failures outside the window
            cutoff = now - self.window_seconds
            self._failures = [t for t in self._failures if t > cutoff]
            self._failures.append(now)

            if len(self._failures) >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = now

    def check(self) -> None:
        """
        Check if a request is allowed through.
        Raises CircuitBreakerOpenError if the circuit is OPEN.
        """
        current = self.state
        if current == CircuitState.OPEN:
            raise CircuitBreakerOpenError(self.name, self.recovery_seconds)
        # CLOSED or HALF_OPEN — allow the request

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._opened_at = 0.0


# ── Module-level instances ────────────────────────────────────────────────────

llm_breaker = CircuitBreaker(
    name="llm",
    failure_threshold=5,
    window_seconds=60,
    recovery_seconds=30,
)

mcp_breaker = CircuitBreaker(
    name="mcp",
    failure_threshold=5,
    window_seconds=60,
    recovery_seconds=30,
)
