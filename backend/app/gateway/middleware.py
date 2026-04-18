# ─────────────────────────────────────────────────────────────────────────────
# backend/app/gateway/middleware.py — Security middleware stack
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import hashlib
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


# ── Security Headers Middleware ───────────────────────────────────────────────

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000",
    "Content-Security-Policy": "default-src 'self'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append protective HTTP headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


# ── CSRF Double-Submit Cookie Middleware ──────────────────────────────────────

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection for state-changing endpoints
    accessed from browser clients.

    - On every response, sets a `csrf_token` cookie with a random token.
    - On state-changing requests (POST/PUT/PATCH/DELETE), verifies that the
      `X-CSRF-Token` header matches the cookie value.
    - Requests without a browser Origin/Referer (e.g. pure API clients using
      Bearer tokens) are exempt.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method not in CSRF_SAFE_METHODS:
            # Only enforce CSRF for browser-originated requests
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin:
                cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
                header_token = request.headers.get(CSRF_HEADER_NAME)
                if not cookie_token or not header_token or not secrets.compare_digest(
                    cookie_token, header_token
                ):
                    return Response(
                        content='{"detail":"CSRF token missing or invalid"}',
                        status_code=403,
                        media_type="application/json",
                    )

        response = await call_next(request)

        # Always set/refresh the CSRF cookie so the client can read it
        if CSRF_COOKIE_NAME not in request.cookies:
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                CSRF_COOKIE_NAME,
                token,
                httponly=False,  # JS must read this cookie
                samesite="lax",
                secure=True,
                max_age=86400,
            )

        return response
