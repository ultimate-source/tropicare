"""Unit tests for RBAC enforcement on gateway endpoints."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.gateway.auth import require_role


# ── require_role dependency tests ─────────────────────────────────────────────


class TestRequireRole:
    """Tests for the require_role dependency factory."""

    @pytest.mark.asyncio
    async def test_returns_user_when_role_present(self):
        """User with the required role should be returned."""
        checker = require_role("clinician")
        user = {"sub": "u1", "email": "a@b.com", "roles": ["clinician"]}
        result = await checker(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_returns_user_when_multiple_roles(self):
        """User with multiple roles including the required one should pass."""
        checker = require_role("admin")
        user = {"sub": "u1", "email": "a@b.com", "roles": ["clinician", "admin"]}
        result = await checker(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_403_when_role_absent(self):
        """User without the required role should get HTTP 403."""
        checker = require_role("admin")
        user = {"sub": "u1", "email": "a@b.com", "roles": ["clinician"]}
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_403_when_roles_empty(self):
        """User with empty roles list should get HTTP 403."""
        checker = require_role("clinician")
        user = {"sub": "u1", "email": "a@b.com", "roles": []}
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_403_when_roles_missing(self):
        """User with no roles key should get HTTP 403."""
        checker = require_role("clinician")
        user = {"sub": "u1", "email": "a@b.com"}
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403


# ── Endpoint wiring verification ──────────────────────────────────────────────


class TestEndpointRBACWiring:
    """Verify that clinician and admin endpoints use require_role."""

    def test_clinician_endpoints_use_require_role(self):
        """Session, turn, and feedback endpoints must depend on require_role('clinician')."""
        from backend.app.gateway.main import app

        clinician_paths = {
            ("POST", "/api/v1/sessions"),
            ("GET", "/api/v1/sessions/{session_id}"),
            ("POST", "/api/v1/sessions/{session_id}/turns"),
            ("POST", "/api/v1/feedback"),
        }

        for route in app.routes:
            if not hasattr(route, "methods") or not hasattr(route, "dependant"):
                continue
            for method in route.methods:
                key = (method, route.path)
                if key in clinician_paths:
                    dep_names = [
                        d.call.__name__ if hasattr(d.call, "__name__") else str(d.call)
                        for d in route.dependant.dependencies
                    ]
                    assert "check" in dep_names, (
                        f"{method} {route.path} should use require_role('clinician') "
                        f"but dependencies are {dep_names}"
                    )

    def test_admin_endpoints_use_require_role(self):
        """Admin document and analytics endpoints must depend on require_role('admin')."""
        from backend.app.gateway.main import app

        admin_paths = {
            ("GET", "/api/v1/admin/documents"),
            ("POST", "/api/v1/admin/documents"),
            ("DELETE", "/api/v1/admin/documents/{doc_id}"),
        }

        for route in app.routes:
            if not hasattr(route, "methods") or not hasattr(route, "dependant"):
                continue
            for method in route.methods:
                key = (method, route.path)
                if key in admin_paths:
                    dep_names = [
                        d.call.__name__ if hasattr(d.call, "__name__") else str(d.call)
                        for d in route.dependant.dependencies
                    ]
                    assert "check" in dep_names, (
                        f"{method} {route.path} should use require_role('admin') "
                        f"but dependencies are {dep_names}"
                    )
