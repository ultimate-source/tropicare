# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_security_headers.py
#
# Property 10: Security headers on every response
# For any valid HTTP request (various methods and paths), the Gateway SHALL
# include all required security headers in the response.
#
# **Validates: Requirements 22.1, 22.2, 22.3, 22.4**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis.strategies import sampled_from, text
from starlette.testclient import TestClient

from backend.app.gateway.middleware import SECURITY_HEADERS, SecurityHeadersMiddleware

# ── Minimal ASGI app with only the security headers middleware ────────────────

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def _ok(request):
    return PlainTextResponse("ok")


_app = Starlette(
    routes=[
        Route("/{path:path}", _ok, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
    ],
)
_app.add_middleware(SecurityHeadersMiddleware)

_client = TestClient(_app, raise_server_exceptions=False)

# ── Strategies ───────────────────────────────────────────────────────────────

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

PATHS = [
    "/",
    "/api/v1/health",
    "/api/v1/sessions",
    "/api/v1/sessions/abc-123/turns",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/admin/documents",
    "/api/v1/admin/analytics",
    "/metrics",
    "/api/v1/feedback",
]


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    method=sampled_from(METHODS),
    path=sampled_from(PATHS),
)
@settings(max_examples=200, deadline=None)
def test_security_headers_present_on_every_response(method: str, path: str) -> None:
    """
    **Validates: Requirements 22.1, 22.2, 22.3, 22.4**

    Property 10: Every HTTP response from the Gateway contains all required
    security headers regardless of method or path.
    """
    response = _client.request(method, path)

    for header_name, expected_value in SECURITY_HEADERS.items():
        actual = response.headers.get(header_name)
        assert actual is not None, (
            f"Missing security header '{header_name}' on {method} {path}"
        )
        assert actual == expected_value, (
            f"Wrong value for '{header_name}' on {method} {path}: "
            f"expected '{expected_value}', got '{actual}'"
        )
