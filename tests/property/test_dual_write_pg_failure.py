# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_dual_write_pg_failure.py
#
# Feature: session-persistence, Property 2: PostgreSQL failure resilience
#
# For any dual-write operation (create, append_turn, patch) where the
# PostgreSQL write raises an exception, the Redis write SHALL succeed and
# no exception SHALL propagate to the caller.
#
# **Validates: Requirements 1.2, 2.3**
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
    fixed_dictionaries,
    floats,
    integers,
    lists,
    none,
    one_of,
    recursive,
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

json_value = recursive(
    json_leaf,
    lambda children: one_of(
        lists(children, max_size=3),
        dictionaries(safe_text, children, max_size=3),
    ),
    max_leaves=10,
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

turn_response_strategy = fixed_dictionaries({
    "diag": json_value,
    "anti": json_value,
    "warnings": lists(safe_text, max_size=3),
    "references": lists(
        dictionaries(safe_text, json_leaf, max_size=3),
        max_size=3,
    ),
})


# ── Fake Redis SessionStore (in-memory) ──────────────────────────────────────


class FakeRedisSessionStore:
    """In-memory dict that mimics SessionStore's interface for testing."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    async def create(
        self, session_id: str, patient_context: dict, language: str = "fr"
    ) -> None:
        self.store[session_id] = {
            "session_id": session_id,
            "patient_context": patient_context,
            "conversation_history": [],
            "language": language,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get(self, session_id: str) -> dict:
        return self.store.get(session_id, {})

    async def patch(self, session_id: str, **fields: Any) -> None:
        data = self.store.get(session_id, {})
        data.update(fields)
        self.store[session_id] = data

    async def append_turn(self, session_id: str, turn: dict) -> None:
        data = self.store.get(session_id, {})
        history = data.get("conversation_history", [])
        history.append(turn)
        data["conversation_history"] = history[-20:]
        self.store[session_id] = data

    async def register_session(self, user_id: str, session_id: str) -> None:
        pass

    async def count_user_sessions(self, user_id: str) -> int:
        return 0


# ── Failing PG SessionRepository ─────────────────────────────────────────────


class FailingPgSessionRepository:
    """SessionRepository stub that raises RuntimeError on all write methods."""

    async def create_session(
        self, session_id: str, user_id: str, patient_context: dict, language: str
    ) -> None:
        raise RuntimeError("PG create_session failure")

    async def upsert_turn(
        self, session_id: str, turn_id: str, turn_index: int, query: str, response: dict
    ) -> None:
        raise RuntimeError("PG upsert_turn failure")

    async def update_patient_context(
        self, session_id: str, patient_context: dict
    ) -> None:
        raise RuntimeError("PG update_patient_context failure")

    async def get_session_detail(self, session_id: str) -> dict | None:
        raise RuntimeError("PG get_session_detail failure")

    async def close_session(self, session_id: str) -> None:
        raise RuntimeError("PG close_session failure")


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    patient_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_pg_failure_create_does_not_propagate(
    patient_context: dict,
    language: str,
    user_id: str,
) -> None:
    """
    **Validates: Requirements 1.2**

    Property 2 (create): When PG raises an exception during create(),
    the Redis write succeeds and no exception propagates to the caller.
    """
    # Feature: session-persistence, Property 2: PostgreSQL failure resilience

    redis_store = FakeRedisSessionStore()
    pg_repo = FailingPgSessionRepository()
    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    session_id = str(uuid.uuid4())

    # Should NOT raise despite PG failure
    await dw.create(session_id, patient_context, language, user_id=user_id)
    # Let fire-and-forget task run (and fail silently)
    await asyncio.sleep(0)

    # Redis must have the session data
    redis_data = await redis_store.get(session_id)
    assert redis_data, "Session missing from Redis after create() with PG failure"
    assert redis_data["patient_context"] == patient_context
    assert redis_data["language"] == language


@pytest.mark.property
@given(
    patient_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
    turn_query=safe_text,
    turn_response=turn_response_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_pg_failure_append_turn_does_not_propagate(
    patient_context: dict,
    language: str,
    user_id: str,
    turn_query: str,
    turn_response: dict,
) -> None:
    """
    **Validates: Requirements 2.3**

    Property 2 (append_turn): When PG raises an exception during
    append_turn(), the Redis write succeeds and no exception propagates
    to the caller.
    """
    # Feature: session-persistence, Property 2: PostgreSQL failure resilience

    redis_store = FakeRedisSessionStore()
    pg_repo = FailingPgSessionRepository()
    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    session_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())

    # Create session (PG fire-and-forget will fail, but Redis succeeds)
    await dw.create(session_id, patient_context, language, user_id=user_id)
    await asyncio.sleep(0)

    turn = {
        "turn_id": turn_id,
        "query": turn_query,
        "diag": turn_response["diag"],
        "anti": turn_response["anti"],
        "warnings": turn_response["warnings"],
        "references": turn_response["references"],
    }

    # Should NOT raise despite PG failure
    await dw.append_turn(session_id, turn)
    # Let fire-and-forget task run (and fail silently)
    await asyncio.sleep(0)

    # Redis must have the turn
    redis_data = await redis_store.get(session_id)
    history = redis_data.get("conversation_history", [])
    assert len(history) == 1, "Turn missing from Redis after append_turn() with PG failure"
    assert history[0]["turn_id"] == turn_id
    assert history[0]["query"] == turn_query


@pytest.mark.property
@given(
    initial_context=patient_context_strategy,
    updated_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_pg_failure_patch_does_not_propagate(
    initial_context: dict,
    updated_context: dict,
    language: str,
    user_id: str,
) -> None:
    """
    **Validates: Requirements 1.2, 2.3**

    Property 2 (patch): When PG raises an exception during patch() with
    patient_context, the Redis write succeeds and no exception propagates
    to the caller.
    """
    # Feature: session-persistence, Property 2: PostgreSQL failure resilience

    redis_store = FakeRedisSessionStore()
    pg_repo = FailingPgSessionRepository()
    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    session_id = str(uuid.uuid4())

    # Create session (PG fire-and-forget will fail, but Redis succeeds)
    await dw.create(session_id, initial_context, language, user_id=user_id)
    await asyncio.sleep(0)

    # Should NOT raise despite PG failure
    await dw.patch(session_id, patient_context=updated_context)
    # Let fire-and-forget task run (and fail silently)
    await asyncio.sleep(0)

    # Redis must have the updated context
    redis_data = await redis_store.get(session_id)
    assert redis_data["patient_context"] == updated_context
