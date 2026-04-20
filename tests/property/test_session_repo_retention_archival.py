# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_session_repo_retention_archival.py
#
# Feature: session-persistence, Property 8: Retention-based archival
#
# For any session with created_at older than SESSION_RETENTION_DAYS days,
# when archive_expired is called, the session's status SHALL be updated to
# 'archived' in PostgreSQL.
#
# **Validates: Requirements 9.2**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    composite,
    integers,
    lists,
    sampled_from,
)

from backend.app.orchestrator.session_repository import SessionRepository

# ── Strategies ───────────────────────────────────────────────────────────────

status_strategy = sampled_from(["active", "closed", "archived"])


@composite
def session_strategy(draw, user_id: str = "user-target"):
    """Generate a session with a random age and status."""
    days_ago = draw(integers(min_value=0, max_value=2000))
    status = draw(status_strategy)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "session_id": str(uuid.uuid4()),
        "user_id": user_id,
        "status": status,
        "created_at": created_at,
    }


# ── Mock asyncpg pool/connection ─────────────────────────────────────────────


class FakeAsyncpgPool:
    """In-memory mock that simulates asyncpg for archive_expired testing."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}

    @asynccontextmanager
    async def acquire(self):
        yield FakeConnection(self)


class FakeConnection:
    """Minimal asyncpg.Connection mock that handles the archive UPDATE query."""

    def __init__(self, pool: FakeAsyncpgPool) -> None:
        self._pool = pool

    async def execute(self, query: str, *args: Any) -> None:
        sql = query.strip().upper()
        # Handle: UPDATE sessions SET status='archived' WHERE user_id=$1
        #         AND created_at < $2 AND status != 'archived'
        if sql.startswith("UPDATE SESSIONS") and "ARCHIVED" in sql:
            user_id = args[0]
            cutoff = args[1]
            for s in self._pool.sessions.values():
                if (
                    s["user_id"] == user_id
                    and s["created_at"] < cutoff
                    and s["status"] != "archived"
                ):
                    s["status"] = "archived"
                    s["updated_at"] = datetime.now(timezone.utc)

    async def fetchrow(self, query: str, *args: Any) -> dict | None:
        return None

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        return []

    async def fetchval(self, query: str, *args: Any) -> Any:
        return 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _seed_pool(pool: FakeAsyncpgPool, sessions_data: list[dict]) -> None:
    """Directly seed the fake pool with pre-built session data."""
    for s in sessions_data:
        pool.sessions[s["session_id"]] = {
            "id": s["session_id"],
            "user_id": s["user_id"],
            "patient_context": json.dumps({"age_years": 30}),
            "language": "fr",
            "status": s["status"],
            "created_at": s["created_at"],
            "closed_at": None,
            "updated_at": s["created_at"],
        }


# ── Property test ────────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    retention_days=integers(min_value=1, max_value=1000),
    sessions_data=lists(session_strategy(), min_size=1, max_size=10),
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_retention_based_archival(
    retention_days: int,
    sessions_data: list[dict],
) -> None:
    """
    **Validates: Requirements 9.2**

    Property 8: Retention-based archival.

    For any session with created_at older than SESSION_RETENTION_DAYS days,
    when archive_expired is called, the session's status SHALL be updated
    to 'archived' in PostgreSQL. Sessions within the retention window or
    already archived remain unchanged.
    """
    # Feature: session-persistence, Property 8: Retention-based archival

    pool = FakeAsyncpgPool()
    _seed_pool(pool, sessions_data)
    repo = SessionRepository(pool=pool, retention_days=retention_days)  # type: ignore[arg-type]

    # Snapshot original statuses before archival
    original_statuses = {
        s["session_id"]: s["status"] for s in sessions_data
    }

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    user_id = "user-target"

    # Call archive_expired
    await repo.archive_expired(user_id)

    # Verify each session
    for s in sessions_data:
        sid = s["session_id"]
        stored = pool.sessions[sid]
        original_status = original_statuses[sid]

        if s["created_at"] < cutoff and original_status != "archived":
            # Sessions older than retention_days should now be archived
            assert stored["status"] == "archived", (
                f"Session {sid} (created {s['created_at']}, cutoff {cutoff}) "
                f"should be archived but has status={stored['status']!r}"
            )
        elif original_status == "archived":
            # Already-archived sessions remain archived
            assert stored["status"] == "archived", (
                f"Session {sid} was already archived but status changed to {stored['status']!r}"
            )
        else:
            # Sessions within retention window keep their original status
            assert stored["status"] == original_status, (
                f"Session {sid} (created {s['created_at']}, cutoff {cutoff}) "
                f"should keep status={original_status!r} but got {stored['status']!r}"
            )
