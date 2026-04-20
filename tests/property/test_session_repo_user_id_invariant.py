# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_session_repo_user_id_invariant.py
#
# Feature: session-persistence, Property 9: User ID foreign key invariant
#
# For any session persisted via SessionRepository.create_session(), the stored
# user_id SHALL be non-null and equal to the user_id parameter passed at
# creation time.
#
# **Validates: Requirements 1.3**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis.strategies import text, uuids

from backend.app.orchestrator.session_repository import SessionRepository

# ── Strategies ───────────────────────────────────────────────────────────────

# Non-empty user IDs: either UUID strings or arbitrary non-empty text (no NUL)
user_id_as_uuid = uuids().map(str)
user_id_as_text = text(min_size=1, max_size=100).filter(
    lambda s: "\x00" not in s and s.strip() != ""
)


# ── Mock asyncpg pool/connection ─────────────────────────────────────────────


class FakeAsyncpgPool:
    """In-memory mock that simulates asyncpg + PostgreSQL JSONB behaviour."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}

    @asynccontextmanager
    async def acquire(self):
        yield FakeConnection(self)


class FakeConnection:
    """Minimal asyncpg.Connection mock that routes SQL to in-memory dicts."""

    def __init__(self, pool: FakeAsyncpgPool) -> None:
        self._pool = pool

    async def execute(self, query: str, *args: Any) -> None:
        sql = query.strip().upper()
        if sql.startswith("INSERT INTO SESSIONS"):
            # args: session_id, user_id, patient_context_json, language
            sid, uid, pc_json, lang = args[0], args[1], args[2], args[3]
            now = datetime.now(timezone.utc)
            self._pool.sessions[sid] = {
                "id": sid,
                "user_id": uid,
                "patient_context": pc_json,
                "language": lang,
                "status": "active",
                "created_at": now,
                "closed_at": None,
                "updated_at": now,
            }


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(user_id=user_id_as_uuid)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_user_id_foreign_key_invariant_uuid(user_id: str) -> None:
    """
    **Validates: Requirements 1.3**

    Property 9: User ID foreign key invariant (UUID user IDs).
    For any session created via create_session(), the stored user_id is
    non-null and equals the user_id passed at creation time.
    """
    # Feature: session-persistence, Property 9: User ID foreign key invariant

    pool = FakeAsyncpgPool()
    repo = SessionRepository(pool=pool)  # type: ignore[arg-type]

    session_id = str(uuid.uuid4())

    await repo.create_session(
        session_id=session_id,
        user_id=user_id,
        patient_context={"age_years": 25, "sex": "F"},
        language="en",
    )

    stored = pool.sessions[session_id]
    assert stored["user_id"] is not None, "stored user_id must not be None"
    assert stored["user_id"] == user_id, (
        f"stored user_id {stored['user_id']!r} != passed user_id {user_id!r}"
    )


@pytest.mark.property
@given(user_id=user_id_as_text)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_user_id_foreign_key_invariant_text(user_id: str) -> None:
    """
    **Validates: Requirements 1.3**

    Property 9: User ID foreign key invariant (arbitrary text user IDs).
    For any session created via create_session(), the stored user_id is
    non-null and equals the user_id passed at creation time.
    """
    # Feature: session-persistence, Property 9: User ID foreign key invariant

    pool = FakeAsyncpgPool()
    repo = SessionRepository(pool=pool)  # type: ignore[arg-type]

    session_id = str(uuid.uuid4())

    await repo.create_session(
        session_id=session_id,
        user_id=user_id,
        patient_context={"age_years": 40, "sex": "M"},
        language="fr",
    )

    stored = pool.sessions[session_id]
    assert stored["user_id"] is not None, "stored user_id must not be None"
    assert stored["user_id"] == user_id, (
        f"stored user_id {stored['user_id']!r} != passed user_id {user_id!r}"
    )
