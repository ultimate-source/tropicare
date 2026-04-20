# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_dual_write_lazy_close.py
#
# Feature: session-persistence, Property 7: Lazy session close
#
# For any session with status 'active' in PostgreSQL that is not present in
# Redis, when the session is accessed via the list or detail endpoint, the
# SessionRepository SHALL update the session status to 'closed' and set
# closed_at to a non-null UTC timestamp.
#
# **Validates: Requirements 10.1**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    booleans,
    dictionaries,
    floats,
    integers,
    none,
    one_of,
    sampled_from,
    text,
)

from backend.app.orchestrator.dual_write import DualWriteSessionStore

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=40).filter(
    lambda s: "\x00" not in s and s.strip() != ""
)

json_leaf = one_of(
    safe_text,
    integers(min_value=-10_000, max_value=10_000),
    floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    booleans(),
    none(),
)

patient_context_strategy = dictionaries(
    keys=sampled_from(["age_years", "sex", "chief_complaint", "region", "symptoms", "allergies"]),
    values=json_leaf,
    min_size=1,
    max_size=4,
)

language_strategy = sampled_from(["fr", "en", "es"])

user_id_strategy = text(min_size=1, max_size=20).filter(
    lambda s: "\x00" not in s and s.strip() != ""
)


# ── Fake Redis SessionStore (EMPTY — always returns {} on get) ───────────────


class FakeRedisSessionStore:
    """In-memory Redis stub that is always empty — simulates Redis miss."""

    async def create(
        self, session_id: str, patient_context: dict, language: str = "fr"
    ) -> None:
        pass

    async def get(self, session_id: str) -> dict:
        return {}

    async def patch(self, session_id: str, **fields: Any) -> None:
        pass

    async def append_turn(self, session_id: str, turn: dict) -> None:
        pass

    async def register_session(self, user_id: str, session_id: str) -> None:
        pass

    async def count_user_sessions(self, user_id: str) -> int:
        return 0


# ── Fake PG SessionRepository (pre-populated with session data) ──────────────


class FakePgSessionRepository:
    """In-memory PG stub with sessions pre-populated directly."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.closed_sessions: list[str] = []

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        patient_context: dict,
        language: str,
    ) -> None:
        self.sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "patient_context": patient_context,
            "language": language,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "closed_at": None,
        }

    async def get_session_detail(self, session_id: str) -> dict | None:
        if session_id not in self.sessions:
            return None
        s = self.sessions[session_id]
        return {
            "session_id": s["session_id"],
            "patient_context": s["patient_context"],
            "language": s["language"],
            "status": s["status"],
            "created_at": s["created_at"].isoformat()
            if isinstance(s["created_at"], datetime)
            else s["created_at"],
            "conversation_history": [],
        }

    async def close_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = "closed"
            self.sessions[session_id]["closed_at"] = datetime.now(timezone.utc)
            self.closed_sessions.append(session_id)

    async def upsert_turn(
        self, session_id: str, turn_id: str, turn_index: int, query: str, response: dict
    ) -> None:
        pass

    async def update_patient_context(
        self, session_id: str, patient_context: dict
    ) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["patient_context"] = patient_context


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    patient_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_lazy_close_triggered_for_active_session_missing_from_redis(
    patient_context: dict,
    language: str,
    user_id: str,
) -> None:
    """
    **Validates: Requirements 10.1**

    Property 7: For any session with status 'active' in PostgreSQL that is
    not present in Redis, when the session is accessed via get_or_fallback(),
    the SessionRepository SHALL update the session status to 'closed' and
    set closed_at to a non-null UTC timestamp.
    """
    # Feature: session-persistence, Property 7: Lazy session close

    redis_store = FakeRedisSessionStore()
    pg_repo = FakePgSessionRepository()

    session_id = str(uuid.uuid4())

    # Pre-populate PG with an active session (not in Redis)
    pg_repo.sessions[session_id] = {
        "session_id": session_id,
        "user_id": user_id,
        "patient_context": patient_context,
        "language": language,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "closed_at": None,
    }

    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    # ── Act ──────────────────────────────────────────────────────────────
    result = await dw.get_or_fallback(session_id)

    # Let fire-and-forget tasks complete
    await asyncio.sleep(0)

    # ── Assert: result returned (not 404) ────────────────────────────────
    assert result is not None

    # ── Assert: lazy close was triggered ─────────────────────────────────
    assert session_id in pg_repo.closed_sessions, (
        f"close_session was not called for active session {session_id} "
        "that is missing from Redis — lazy close should have been triggered"
    )
    assert pg_repo.sessions[session_id]["status"] == "closed", (
        f"Session {session_id} status should be 'closed' after lazy close"
    )
    assert pg_repo.sessions[session_id]["closed_at"] is not None, (
        f"Session {session_id} closed_at should be set to a non-null UTC "
        "timestamp after lazy close"
    )


@pytest.mark.property
@given(
    patient_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_no_double_close_for_already_closed_session(
    patient_context: dict,
    language: str,
    user_id: str,
) -> None:
    """
    **Validates: Requirements 10.1**

    Property 7 (corollary): For any session with status 'closed' in
    PostgreSQL that is not present in Redis, get_or_fallback() SHALL NOT
    trigger another close_session call (no double-close).
    """
    # Feature: session-persistence, Property 7: Lazy session close

    redis_store = FakeRedisSessionStore()
    pg_repo = FakePgSessionRepository()

    session_id = str(uuid.uuid4())

    # Pre-populate PG with an already-closed session (not in Redis)
    pg_repo.sessions[session_id] = {
        "session_id": session_id,
        "user_id": user_id,
        "patient_context": patient_context,
        "language": language,
        "status": "closed",
        "created_at": datetime.now(timezone.utc),
        "closed_at": datetime.now(timezone.utc),
    }

    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    # ── Act ──────────────────────────────────────────────────────────────
    result = await dw.get_or_fallback(session_id)

    # Let fire-and-forget tasks complete
    await asyncio.sleep(0)

    # ── Assert: result returned ──────────────────────────────────────────
    assert result is not None

    # ── Assert: close_session was NOT called again ───────────────────────
    assert session_id not in pg_repo.closed_sessions, (
        f"close_session was called for already-closed session {session_id} "
        "— should not double-close"
    )
