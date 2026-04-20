# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_dual_write_data_integrity.py
#
# Feature: session-persistence, Property 1: Dual-write data integrity
#
# For any session creation, turn append, or patient context patch operation
# with valid inputs, after DualWriteSessionStore completes the operation,
# both the Redis store and the PostgreSQL repository SHALL contain the
# written data with matching content.
#
# **Validates: Requirements 1.1, 2.1, 6.1**
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

# Turn response sub-structures
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


# ── Fake PG SessionRepository (in-memory) ────────────────────────────────────


class FakePgSessionRepository:
    """In-memory dict that mimics SessionRepository's interface for testing."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.turns: dict[str, dict[str, Any]] = {}

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
        }

    async def upsert_turn(
        self,
        session_id: str,
        turn_id: str,
        turn_index: int,
        query: str,
        response: dict,
    ) -> None:
        self.turns[turn_id] = {
            "turn_id": turn_id,
            "session_id": session_id,
            "turn_index": turn_index,
            "query": query,
            "response": response,
        }

    async def update_patient_context(
        self,
        session_id: str,
        patient_context: dict,
    ) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["patient_context"] = patient_context

    async def get_session_detail(self, session_id: str) -> dict | None:
        if session_id not in self.sessions:
            return None
        s = self.sessions[session_id]
        return {
            "session_id": s["session_id"],
            "patient_context": s["patient_context"],
            "language": s["language"],
            "status": s["status"],
        }

    async def close_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = "closed"


# ── Property tests ───────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    patient_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_dual_write_create_data_integrity(
    patient_context: dict,
    language: str,
    user_id: str,
) -> None:
    """
    **Validates: Requirements 1.1**

    Property 1 (create): After DualWriteSessionStore.create(), both the
    Redis store and the PostgreSQL repository contain the session data
    with matching content.
    """
    # Feature: session-persistence, Property 1: Dual-write data integrity

    redis_store = FakeRedisSessionStore()
    pg_repo = FakePgSessionRepository()
    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    session_id = str(uuid.uuid4())

    await dw.create(session_id, patient_context, language, user_id=user_id)
    # Let fire-and-forget tasks complete
    await asyncio.sleep(0)

    # ── Assert Redis has the session ─────────────────────────────────────
    redis_data = await redis_store.get(session_id)
    assert redis_data, "Session missing from Redis after create()"
    assert redis_data["patient_context"] == patient_context
    assert redis_data["language"] == language

    # ── Assert PG has the session ────────────────────────────────────────
    assert session_id in pg_repo.sessions, "Session missing from PG after create()"
    pg_data = pg_repo.sessions[session_id]
    assert pg_data["patient_context"] == patient_context
    assert pg_data["language"] == language
    assert pg_data["user_id"] == user_id


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
async def test_dual_write_append_turn_data_integrity(
    patient_context: dict,
    language: str,
    user_id: str,
    turn_query: str,
    turn_response: dict,
) -> None:
    """
    **Validates: Requirements 2.1**

    Property 1 (append_turn): After DualWriteSessionStore.append_turn(),
    both the Redis store and the PostgreSQL repository contain the turn
    data with matching content.
    """
    # Feature: session-persistence, Property 1: Dual-write data integrity

    redis_store = FakeRedisSessionStore()
    pg_repo = FakePgSessionRepository()
    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    session_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())

    # Create session first
    await dw.create(session_id, patient_context, language, user_id=user_id)
    await asyncio.sleep(0)

    # Build turn dict matching the orchestrator's turn_record shape
    turn = {
        "turn_id": turn_id,
        "query": turn_query,
        "diag": turn_response["diag"],
        "anti": turn_response["anti"],
        "warnings": turn_response["warnings"],
        "references": turn_response["references"],
    }

    await dw.append_turn(session_id, turn)
    # Let fire-and-forget tasks complete
    await asyncio.sleep(0)

    # ── Assert Redis has the turn ────────────────────────────────────────
    redis_data = await redis_store.get(session_id)
    assert len(redis_data.get("conversation_history", [])) == 1
    redis_turn = redis_data["conversation_history"][0]
    assert redis_turn["turn_id"] == turn_id
    assert redis_turn["query"] == turn_query

    # ── Assert PG has the turn ───────────────────────────────────────────
    assert turn_id in pg_repo.turns, "Turn missing from PG after append_turn()"
    pg_turn = pg_repo.turns[turn_id]
    assert pg_turn["session_id"] == session_id
    assert pg_turn["query"] == turn_query
    assert pg_turn["turn_index"] == 0  # first turn
    # PG response is the extracted sub-dict
    assert pg_turn["response"]["diag"] == turn_response["diag"]
    assert pg_turn["response"]["anti"] == turn_response["anti"]
    assert pg_turn["response"]["warnings"] == turn_response["warnings"]
    assert pg_turn["response"]["references"] == turn_response["references"]


@pytest.mark.property
@given(
    initial_context=patient_context_strategy,
    updated_context=patient_context_strategy,
    language=language_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_dual_write_patch_patient_context_data_integrity(
    initial_context: dict,
    updated_context: dict,
    language: str,
    user_id: str,
) -> None:
    """
    **Validates: Requirements 6.1**

    Property 1 (patch): After DualWriteSessionStore.patch() with
    patient_context, both the Redis store and the PostgreSQL repository
    contain the updated patient context with matching content.
    """
    # Feature: session-persistence, Property 1: Dual-write data integrity

    redis_store = FakeRedisSessionStore()
    pg_repo = FakePgSessionRepository()
    dw = DualWriteSessionStore(redis_store=redis_store, pg_repo=pg_repo)

    session_id = str(uuid.uuid4())

    # Create session first
    await dw.create(session_id, initial_context, language, user_id=user_id)
    await asyncio.sleep(0)

    # Patch patient_context
    await dw.patch(session_id, patient_context=updated_context)
    # Let fire-and-forget tasks complete
    await asyncio.sleep(0)

    # ── Assert Redis has the updated context ─────────────────────────────
    redis_data = await redis_store.get(session_id)
    assert redis_data["patient_context"] == updated_context

    # ── Assert PG has the updated context ────────────────────────────────
    assert session_id in pg_repo.sessions, "Session missing from PG"
    pg_data = pg_repo.sessions[session_id]
    assert pg_data["patient_context"] == updated_context
