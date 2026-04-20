# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_session_repo_turn_roundtrip.py
#
# Feature: session-persistence, Property 3: Turn response JSONB round-trip
#
# For any valid turn response dictionary (containing nested diag, anti,
# warnings, and references structures), writing it to the turns.response
# JSONB column via SessionRepository.upsert_turn() and reading it back via
# SessionRepository.get_session_detail() SHALL produce a dictionary equal
# to the original.
#
# **Validates: Requirements 2.2**
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
    booleans,
    dictionaries,
    floats,
    integers,
    just,
    lists,
    none,
    one_of,
    recursive,
    text,
)

from backend.app.orchestrator.session_repository import SessionRepository

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=0, max_size=60).filter(lambda s: "\x00" not in s)

# JSON-safe leaf values (no NaN/Inf which aren't valid JSON)
json_leaf = one_of(
    safe_text,
    integers(min_value=-10_000, max_value=10_000),
    floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    booleans(),
    none(),
)

# Recursive JSON-like structure (dicts and lists of leaves)
json_value = recursive(
    json_leaf,
    lambda children: one_of(
        lists(children, max_size=5),
        dictionaries(safe_text.filter(lambda s: len(s) > 0), children, max_size=5),
    ),
    max_leaves=20,
)

# Strategy for a single citation dict
citation_strategy = dictionaries(
    keys=safe_text.filter(lambda s: len(s) > 0),
    values=json_leaf,
    min_size=0,
    max_size=4,
)

# Strategy for a reference dict
reference_strategy = dictionaries(
    keys=safe_text.filter(lambda s: len(s) > 0),
    values=json_leaf,
    min_size=0,
    max_size=5,
)

# Strategy for the diag sub-structure
diag_strategy = dictionaries(
    keys=just("differential"),
    values=lists(json_value, max_size=3),
    min_size=0,
    max_size=1,
).flatmap(lambda d: dictionaries(
    keys=just("emergency_flags"),
    values=lists(json_value, max_size=3),
    min_size=0,
    max_size=1,
).map(lambda ef: {**d, **ef})).flatmap(lambda d: lists(
    citation_strategy, max_size=3
).map(lambda cits: {**d, "citations": cits}))

# Strategy for the anti sub-structure
anti_strategy = dictionaries(
    keys=just("first_line"),
    values=lists(json_value, max_size=3),
    min_size=0,
    max_size=1,
).flatmap(lambda d: dictionaries(
    keys=just("second_line"),
    values=lists(json_value, max_size=3),
    min_size=0,
    max_size=1,
).map(lambda sl: {**d, **sl})).flatmap(lambda d: dictionaries(
    keys=just("alternatives"),
    values=lists(json_value, max_size=3),
    min_size=0,
    max_size=1,
).map(lambda alt: {**d, **alt})).flatmap(lambda d: lists(
    citation_strategy, max_size=3
).map(lambda cits: {**d, "citations": cits}))


# Full turn response strategy matching the design doc shape
turn_response_strategy = (
    diag_strategy.flatmap(lambda diag:
        anti_strategy.flatmap(lambda anti:
            lists(safe_text, max_size=5).flatmap(lambda warnings:
                lists(reference_strategy, max_size=4).map(lambda refs: {
                    "diag": diag,
                    "anti": anti,
                    "warnings": warnings,
                    "references": refs,
                })
            )
        )
    )
)


# ── Mock asyncpg pool/connection ─────────────────────────────────────────────


class FakeAsyncpgPool:
    """In-memory mock that simulates asyncpg + PostgreSQL JSONB behaviour.

    On write: receives json.dumps(data) as a string parameter, stores it.
    On read:  returns json.loads(stored_string) — mimicking asyncpg's
              automatic JSONB → Python dict deserialization.
    """

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
            # args: session_id, user_id, patient_context_json, language
            sid, uid, pc_json, lang = args[0], args[1], args[2], args[3]
            now = datetime.now(timezone.utc)
            self._pool.sessions[sid] = {
                "id": sid,
                "user_id": uid,
                "patient_context": pc_json,  # stored as JSON string
                "language": lang,
                "status": "active",
                "created_at": now,
                "closed_at": None,
                "updated_at": now,
            }
        elif sql.startswith("INSERT INTO TURNS"):
            # args: turn_id, session_id, turn_index, query, response_json
            tid, sid, tidx, q, resp_json = args
            self._pool.turns[tid] = {
                "id": tid,
                "session_id": sid,
                "turn_index": tidx,
                "query": q,
                "response": resp_json,  # stored as JSON string
                "created_at": datetime.now(timezone.utc),
            }

    async def fetchrow(self, query: str, *args: Any) -> dict | None:
        sql = query.strip().upper()
        if "FROM SESSIONS" in sql:
            sid = args[0]
            row = self._pool.sessions.get(sid)
            if row is None:
                return None
            # Simulate asyncpg JSONB auto-deserialization
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
                # Simulate asyncpg JSONB auto-deserialization
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
@given(response=turn_response_strategy)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_turn_response_jsonb_roundtrip(response: dict) -> None:
    """
    **Validates: Requirements 2.2**

    Property 3: Turn response JSONB round-trip.
    Writing a turn response dict via upsert_turn() and reading it back via
    get_session_detail() produces a dictionary equal to the original.
    """
    # Feature: session-persistence, Property 3: Turn response JSONB round-trip

    pool = FakeAsyncpgPool()
    repo = SessionRepository(pool=pool)  # type: ignore[arg-type]

    session_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())

    # 1. Create a session
    await repo.create_session(
        session_id=session_id,
        user_id="test-user",
        patient_context={"age_years": 30, "sex": "M"},
        language="fr",
    )

    # 2. Upsert a turn with the generated response
    await repo.upsert_turn(
        session_id=session_id,
        turn_id=turn_id,
        turn_index=0,
        query="Test query",
        response=response,
    )

    # 3. Read back via get_session_detail
    detail = await repo.get_session_detail(session_id)

    assert detail is not None
    assert len(detail["conversation_history"]) == 1

    # 4. Assert round-trip equality
    returned_response = detail["conversation_history"][0]["response"]
    assert returned_response == response
