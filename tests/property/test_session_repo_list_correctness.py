# ─────────────────────────────────────────────────────────────────────────────
# tests/property/test_session_repo_list_correctness.py
#
# Feature: session-persistence, Property 4: Session list correctness
#
# For any set of sessions belonging to multiple users with mixed statuses
# (active, closed, archived) and varying turn counts, calling
# SessionRepository.list_sessions(user_id, include_archived=False) SHALL
# return only non-archived sessions belonging to that user, ordered by
# created_at descending, where each summary's turn_count equals the actual
# number of persisted turns and last_query equals the query of the turn
# with the highest turn_index.
#
# **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 9.3**
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
    text,
)

from backend.app.orchestrator.session_repository import SessionRepository

# ── Strategies ───────────────────────────────────────────────────────────────

safe_text = text(min_size=1, max_size=40).filter(lambda s: "\x00" not in s and s.strip() != "")

user_id_strategy = sampled_from(["user-alice", "user-bob", "user-carol"])
status_strategy = sampled_from(["active", "closed", "archived"])


@composite
def turn_strategy(draw):
    """Generate a single turn dict with a turn_index and query."""
    return {
        "turn_id": str(uuid.uuid4()),
        "turn_index": draw(integers(min_value=0, max_value=100)),
        "query": draw(safe_text),
    }


@composite
def session_strategy(draw):
    """Generate a session with random user, status, created_at, and turns."""
    user_id = draw(user_id_strategy)
    status = draw(status_strategy)
    # Spread created_at across a wide range so ordering is meaningful
    days_ago = draw(integers(min_value=0, max_value=500))
    created_at = datetime(2025, 6, 1, tzinfo=timezone.utc) - timedelta(days=days_ago)
    turns = draw(lists(turn_strategy(), min_size=0, max_size=5))
    # Ensure turn_index values are unique within a session
    seen_indices: set[int] = set()
    unique_turns = []
    for t in turns:
        if t["turn_index"] not in seen_indices:
            seen_indices.add(t["turn_index"])
            unique_turns.append(t)
    return {
        "session_id": str(uuid.uuid4()),
        "user_id": user_id,
        "status": status,
        "created_at": created_at,
        "language": "fr",
        "patient_context": {"age_years": 30, "sex": "M"},
        "turns": unique_turns,
    }


# ── Mock asyncpg pool/connection ─────────────────────────────────────────────


class FakeAsyncpgPool:
    """In-memory mock that simulates asyncpg + PostgreSQL for list_sessions.

    Stores sessions and turns in dicts, and the FakeConnection routes SQL
    patterns to the correct in-memory logic.
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

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """Handle the list_sessions SELECT with subqueries."""
        sql = query.strip().upper()

        # Detect the list_sessions main query (has turn_count and last_query subqueries)
        if "TURN_COUNT" in sql and "LAST_QUERY" in sql:
            user_id = args[0]
            limit = args[1]
            offset = args[2]
            include_archived = "ARCHIVED" not in sql  # no filter = include all

            matching = []
            for s in self._pool.sessions.values():
                if s["user_id"] != user_id:
                    continue
                if not include_archived and s["status"] == "archived":
                    continue
                # Compute turn_count
                session_turns = [
                    t for t in self._pool.turns.values()
                    if t["session_id"] == s["id"]
                ]
                turn_count = len(session_turns)
                # Compute last_query: query of turn with highest turn_index
                last_query = None
                if session_turns:
                    best = max(session_turns, key=lambda t: t["turn_index"])
                    last_query = best["query"]
                matching.append({
                    "id": s["id"],
                    "created_at": s["created_at"],
                    "language": s["language"],
                    "status": s["status"],
                    "turn_count": turn_count,
                    "last_query": last_query,
                })

            # ORDER BY created_at DESC
            matching.sort(key=lambda r: r["created_at"], reverse=True)
            # Apply LIMIT / OFFSET
            return matching[offset: offset + limit]

        # Fallback: turns query for get_session_detail
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

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Handle the COUNT query for list_sessions total."""
        sql = query.strip().upper()
        if "COUNT" in sql and "FROM SESSIONS" in sql:
            user_id = args[0]
            include_archived = "ARCHIVED" not in sql
            count = 0
            for s in self._pool.sessions.values():
                if s["user_id"] != user_id:
                    continue
                if not include_archived and s["status"] == "archived":
                    continue
                count += 1
            return count
        return 0


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_pool(pool: FakeAsyncpgPool, sessions_data: list[dict]) -> None:
    """Directly seed the fake pool with pre-built session/turn data.

    This bypasses SessionRepository.create_session so we can set arbitrary
    status and created_at values that the repository normally doesn't expose.
    """
    for s in sessions_data:
        pool.sessions[s["session_id"]] = {
            "id": s["session_id"],
            "user_id": s["user_id"],
            "patient_context": json.dumps(s["patient_context"]),
            "language": s["language"],
            "status": s["status"],
            "created_at": s["created_at"],
            "closed_at": None,
            "updated_at": s["created_at"],
        }
        for t in s["turns"]:
            pool.turns[t["turn_id"]] = {
                "id": t["turn_id"],
                "session_id": s["session_id"],
                "turn_index": t["turn_index"],
                "query": t["query"],
                "response": json.dumps({"diag": {}, "anti": {}}),
                "created_at": s["created_at"],
            }


# ── Property test ────────────────────────────────────────────────────────────


@pytest.mark.property
@given(
    all_sessions=lists(session_strategy(), min_size=1, max_size=12),
    target_user=user_id_strategy,
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_session_list_correctness(
    all_sessions: list[dict],
    target_user: str,
) -> None:
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 9.3**

    Property 4: Session list correctness.

    For any set of sessions belonging to multiple users with mixed statuses
    and varying turn counts, list_sessions returns only non-archived sessions
    belonging to the queried user, ordered by created_at descending, with
    correct turn_count and last_query.
    """
    # Feature: session-persistence, Property 4: Session list correctness

    pool = FakeAsyncpgPool()
    await _seed_pool(pool, all_sessions)
    repo = SessionRepository(pool=pool)  # type: ignore[arg-type]

    # ── Test with include_archived=False (default) ───────────────────────
    results, total = await repo.list_sessions(
        user_id=target_user, include_archived=False, limit=100, offset=0,
    )

    # Build expected set: sessions for target_user that are NOT archived
    expected = [
        s for s in all_sessions
        if s["user_id"] == target_user and s["status"] != "archived"
    ]

    # 1. Only sessions belonging to the queried user_id are returned
    for r in results:
        assert r["id"] in {s["session_id"] for s in all_sessions if s["user_id"] == target_user}, (
            f"Session {r['id']} does not belong to {target_user}"
        )

    # 2. No archived sessions when include_archived=False
    for r in results:
        assert r["status"] != "archived", (
            f"Archived session {r['id']} should not appear with include_archived=False"
        )

    # 3. Count matches expected
    assert len(results) == len(expected), (
        f"Expected {len(expected)} sessions, got {len(results)}"
    )
    assert total == len(expected)

    # 4. Sessions are ordered by created_at descending
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["created_at"] >= results[i + 1]["created_at"], (
                f"Sessions not ordered by created_at DESC: "
                f"{results[i]['created_at']} < {results[i + 1]['created_at']}"
            )

    # 5. Each session's turn_count matches the actual number of turns
    for r in results:
        matching_session = next(
            s for s in all_sessions if s["session_id"] == r["id"]
        )
        assert r["turn_count"] == len(matching_session["turns"]), (
            f"Session {r['id']}: expected turn_count={len(matching_session['turns'])}, "
            f"got {r['turn_count']}"
        )

    # 6. Each session's last_query matches the query of the turn with highest turn_index
    for r in results:
        matching_session = next(
            s for s in all_sessions if s["session_id"] == r["id"]
        )
        turns = matching_session["turns"]
        if turns:
            best_turn = max(turns, key=lambda t: t["turn_index"])
            assert r["last_query"] == best_turn["query"], (
                f"Session {r['id']}: expected last_query={best_turn['query']!r}, "
                f"got {r['last_query']!r}"
            )
        else:
            assert r["last_query"] == "", (
                f"Session {r['id']} has no turns but last_query={r['last_query']!r}"
            )

    # ── Test with include_archived=True ──────────────────────────────────
    results_all, total_all = await repo.list_sessions(
        user_id=target_user, include_archived=True, limit=100, offset=0,
    )

    expected_all = [
        s for s in all_sessions if s["user_id"] == target_user
    ]

    # 3b. Archived sessions ARE returned when include_archived=True
    assert len(results_all) == len(expected_all)
    assert total_all == len(expected_all)

    # Verify archived sessions are present
    archived_ids = {
        s["session_id"] for s in all_sessions
        if s["user_id"] == target_user and s["status"] == "archived"
    }
    returned_ids = {r["id"] for r in results_all}
    assert archived_ids.issubset(returned_ids), (
        f"Archived sessions {archived_ids - returned_ids} missing from include_archived=True"
    )
