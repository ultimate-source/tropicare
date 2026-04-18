# ─────────────────────────────────────────────────────────────────────────────
# backend/app/observability/metrics.py — Prometheus metrics + ASGI middleware
# ─────────────────────────────────────────────────────────────────────────────
"""
Exposes Prometheus counters and histograms for the TropiCare gateway.

``metrics_app`` is a standalone ASGI app (from ``prometheus_client``) that
serves the ``/metrics`` endpoint in Prometheus text format.

``MetricsMiddleware`` is a Starlette middleware that records per-request
counters and latency, plus agent-level histograms.
"""
from __future__ import annotations

import time

from prometheus_client import (
    Counter,
    Histogram,
    make_asgi_app,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ── Prometheus ASGI app (mounted at /metrics) ─────────────────────────────────
metrics_app = make_asgi_app()

# ── Request-level metrics ─────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "tropicare_http_requests_total",
    "Total HTTP requests by endpoint and status code",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "tropicare_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Agent-level metrics ──────────────────────────────────────────────────────

AGENT_LATENCY = Histogram(
    "tropicare_agent_latency_seconds",
    "Agent execution latency in seconds (p50, p95, p99 via histogram)",
    ["agent_name"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

AGENT_ERROR_COUNT = Counter(
    "tropicare_agent_errors_total",
    "Total agent errors by agent name",
    ["agent_name"],
)


def record_agent_metrics(agent_name: str, latency_s: float, verdict: str) -> None:
    """Record Prometheus metrics for a completed agent execution."""
    AGENT_LATENCY.labels(agent_name=agent_name).observe(latency_s)
    if verdict == "error":
        AGENT_ERROR_COUNT.labels(agent_name=agent_name).inc()


# ── Starlette middleware ──────────────────────────────────────────────────────

def _normalise_path(path: str) -> str:
    """Collapse path parameters to reduce cardinality.

    ``/api/v1/sessions/abc-123/turns`` → ``/api/v1/sessions/{id}/turns``
    """
    parts = path.strip("/").split("/")
    normalised = []
    for i, part in enumerate(parts):
        # Heuristic: UUIDs and hex strings are path params
        if len(part) >= 8 and any(c.isdigit() for c in part):
            normalised.append("{id}")
        else:
            normalised.append(part)
    return "/" + "/".join(normalised)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count and latency for every HTTP request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip the /metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        endpoint = _normalise_path(request.url.path)
        method = request.method

        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=response.status_code,
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint,
        ).observe(elapsed)

        return response
