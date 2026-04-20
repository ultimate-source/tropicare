# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_session_repo_detail_completeness.py
#
# Feature: session-persistence, Property 5: Session detail completeness and turn ordering
#
# For any session with N turns persisted in PostgreSQL,
# SessionRepository.get_session_detail(session_id) SHALL return a response
# containing session_id, patient_context, language, created_at, and a
# conversation_history array of exactly N turns where turn_index values are
# strictly monotonically increasing.
#
# **Validates: Requirements 2.4, 4.3**
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis.strategies import (
    dictionaries,
    integers,
    lists,
    sampled_from,
    text,
)

from backend.app.orchestrator.session_repository import SessionRepository

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=40).filter(lambda s: "\x00" not in s)

patient_context_strategy = dictionaries(
    keys=sampled_from(["age_years", "sex", "chief_complaint", "region", "allergies"]),
    values=safe_text,
    min_size=1,
    max_size=5,
)

language_strategy = sampled_from(["fr", "en", "es", "ar", "pt"])

# Generate a list of unique turn_index values (0-99) in random order, size 0-10
turn_indices_strategy = (
    lists(
        integers(min_value=0, max_value=99),
        min_size=0,
        max_size=10,
        unique=True,
    )
)


# ── Mock asyncpg pool/connection ─────────────────────────────────────────────


class FakeAsyncpgPool:
    """In-memory mock that simulates asyncpg + PostgreSQL JSONB behaviour."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.turns: dict[str, dict[str, Any]] = {}

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
        elif sql.startswith("INSERT INTO TURNS"):
            tid, sid, tidx, q, resp_json = args
            self._pool.turns[tid] = {
                "id": tid,
                "session_id": sid,
                "turn_index": tidx,
                "query": q,
                "response": resp_json,
                "created_at": datetime.now(timezone.utc),
            }

    async def fetchrow(self, query: str, *args: Any) -> dict | None:
        sql = query.strip().upper()
        if "FROM SESSIONS" in sql:
            sid = args[0]
            row = self._pool.sessions.get(sid)
            if row is None:
                return None
            pc = row["patient_context"]
            if isinstance(pc, str):
                pc = json.loads(pc)
            return {
                "id": row["id"],
                "patient_context": pc,
                "language": row["language"],
                "created_at": row["created_at"],
                "status": row["status"],
            }
        return None

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        sql = query.strip().upper()
        if "FROM TURNS" in sql:
            sid = args[0]
            rows = [
                t for t in self._pool.turns.values()
                if t["session_id"] == sid
            ]
            rows.sort(key=lambda r: r["turn_index"])
            result = []
            for r in rows:
                resp = r["response"]
                if isinstance(resp, str):
                    resp = json.loads(resp)
                result.append({
                    "id": r["id"],
                    "turn_index": r["turn_index"],
                    "query": r["query"],
                    "response": resp,
                    "created_at": r["created_at"],
                })
            return result
        return []

    async def fetchval(self, query: str, *args: Any) -> Any:
        return 0


# ── Property test ────────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    patient_context=patient_context_strategy,
    language=language_strategy,
    turn_indices=turn_indices_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_session_detail_completeness_and_turn_ordering(
    patient_context: dict,
    language: str,
    turn_indices: list[int],
) -> None:
    """
    **Validates: Requirements 2.4, 4.3**

    Property 5: Session detail completeness and turn ordering.
    For any session with N turns (inserted in random order),
    get_session_detail returns all required fields and exactly N turns
    with strictly monotonically increasing turn_index values.
    """
    # Feature: session-persistence, Property 5: Session detail completeness and turn ordering

    pool = FakeAsyncpgPool()
    repo = SessionRepository(pool=pool)  # type: ignore[arg-type]

    session_id = str(uuid.uuid4())
    n = len(turn_indices)

    # 1. Create a session
    await repo.create_session(
        session_id=session_id,
        user_id="test-user",
        patient_context=patient_context,
        language=language,
    )

    # 2. Insert N turns in the random order provided by Hypothesis
    for idx in turn_indices:
        await repo.upsert_turn(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            turn_index=idx,
            query=f"Query for turn {idx}",
            response={"diag": {}, "anti": {}, "warnings": [], "references": []},
        )

    # 3. Read back via get_session_detail
    detail = await repo.get_session_detail(session_id)

    # 4. Assert response is not None
    assert detail is not None

    # 5. Assert all required top-level fields are present
    assert "session_id" in detail
    assert detail["session_id"] == session_id
    assert "patient_context" in detail
    assert detail["patient_context"] == patient_context
    assert "language" in detail
    assert detail["language"] == language
    assert "created_at" in detail
    assert detail["created_at"] is not None
    assert "status" in detail

    # 6. Assert conversation_history has exactly N turns
    history = detail["conversation_history"]
    assert len(history) == n

    # 7. Assert turn_index values are strictly monotonically increasing
    if n > 0:
        returned_indices = [t["turn_index"] for t in history]
        for i in range(1, len(returned_indices)):
            assert returned_indices[i] > returned_indices[i - 1], (
                f"turn_index not strictly increasing: {returned_indices}"
            )

        # Also verify the returned indices match the sorted input
        assert returned_indices == sorted(turn_indices)
