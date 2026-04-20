# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/session_repository.py
# ─────────────────────────────────────────────────────────────────────────────
"""PostgreSQL-backed persistent session and turn storage."""
from __future__ import annotations

import json as _json
from datetime import datetime, timezone, timedelta

import asyncpg


class SessionRepository:
    """PostgreSQL-backed persistent session and turn storage."""

    def __init__(self, pool: asyncpg.Pool, retention_days: int = 365):
        self._pool = pool
        self._retention_days = retention_days

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        patient_context: dict,
        language: str,
    ) -> None:
        """INSERT a new session row with status='active'."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (id, user_id, patient_context, language, status)
                VALUES ($1, $2, $3::jsonb, $4, 'active')
                """,
                session_id,
                user_id,
                _json.dumps(patient_context, default=str),
                language,
            )

    # ── Turns ─────────────────────────────────────────────────────────────────

    async def upsert_turn(
        self,
        session_id: str,
        turn_id: str,
        turn_index: int,
        query: str,
        response: dict,
    ) -> None:
        """INSERT a turn row, updating on conflict (idempotent upsert on PK)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO turns (id, session_id, turn_index, query, response)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                ON CONFLICT (id) DO UPDATE
                    SET turn_index = EXCLUDED.turn_index,
                        query     = EXCLUDED.query,
                        response  = EXCLUDED.response
                """,
                turn_id,
                session_id,
                turn_index,
                query,
                _json.dumps(response, default=str),
            )

    # ── Patient context ───────────────────────────────────────────────────────

    async def update_patient_context(
        self,
        session_id: str,
        patient_context: dict,
    ) -> None:
        """UPDATE the patient_context JSONB and bump updated_at."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                   SET patient_context = $2::jsonb,
                       updated_at     = now()
                 WHERE id = $1
                """,
                session_id,
                _json.dumps(patient_context, default=str),
            )

    # ── Session detail ────────────────────────────────────────────────────────

    async def get_session_detail(self, session_id: str) -> dict | None:
        """SELECT session + JOIN turns ORDER BY turn_index ASC.

        Returns a dict matching the Session Detail Response Shape from the
        design doc, or None if the session does not exist.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, patient_context, language, created_at, status
                  FROM sessions
                 WHERE id = $1
                """,
                session_id,
            )
            if row is None:
                return None

            turns = await conn.fetch(
                """
                SELECT id, turn_index, query, response, created_at
                  FROM turns
                 WHERE session_id = $1
                 ORDER BY turn_index ASC
                """,
                session_id,
            )

        patient_ctx = row["patient_context"]
        if isinstance(patient_ctx, str):
            patient_ctx = _json.loads(patient_ctx)

        conversation_history = []
        for t in turns:
            resp = t["response"]
            if isinstance(resp, str):
                resp = _json.loads(resp)
            conversation_history.append({
                "turn_id":    str(t["id"]),
                "turn_index": t["turn_index"],
                "query":      t["query"],
                "response":   resp,
                "created_at": t["created_at"].isoformat() if t["created_at"] else None,
            })

        return {
            "session_id":           str(row["id"]),
            "patient_context":      patient_ctx,
            "language":             row["language"],
            "created_at":           row["created_at"].isoformat() if row["created_at"] else None,
            "status":               row["status"],
            "conversation_history": conversation_history,
        }

    # ── Session list ──────────────────────────────────────────────────────────

    async def list_sessions(
        self,
        user_id: str,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return (sessions_list, total_count) for pagination.

        Each session summary contains id, created_at, language, turn_count,
        last_query, and status.  Ordered by created_at DESC.
        """
        status_filter = (
            "AND s.status != 'archived'" if not include_archived else ""
        )

        query = f"""
            SELECT s.id,
                   s.created_at,
                   s.language,
                   s.status,
                   (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id)
                       AS turn_count,
                   (SELECT t2.query
                      FROM turns t2
                     WHERE t2.session_id = s.id
                     ORDER BY t2.turn_index DESC
                     LIMIT 1)
                       AS last_query
              FROM sessions s
             WHERE s.user_id = $1
                   {status_filter}
             ORDER BY s.created_at DESC
             LIMIT $2 OFFSET $3
        """

        count_query = f"""
            SELECT COUNT(*)
              FROM sessions s
             WHERE s.user_id = $1
                   {status_filter}
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, user_id, limit, offset)
            total = await conn.fetchval(count_query, user_id)

        sessions = []
        for r in rows:
            sessions.append({
                "id":         str(r["id"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "language":   r["language"],
                "turn_count": r["turn_count"],
                "last_query": r["last_query"] or "",
                "status":     r["status"],
            })

        return sessions, total

    # ── Session lifecycle ─────────────────────────────────────────────────────

    async def close_session(self, session_id: str) -> None:
        """UPDATE status='closed', closed_at=now()."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                   SET status    = 'closed',
                       closed_at = now(),
                       updated_at = now()
                 WHERE id = $1
                """,
                session_id,
            )

    async def archive_expired(self, user_id: str) -> None:
        """UPDATE status='archived' for sessions older than retention_days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                   SET status     = 'archived',
                       updated_at = now()
                 WHERE user_id = $1
                   AND created_at < $2
                   AND status != 'archived'
                """,
                user_id,
                cutoff,
            )

    # ── Turn count ────────────────────────────────────────────────────────────

    async def count_turns(self, session_id: str) -> int:
        """SELECT COUNT from turns for a given session."""
        async with self._pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM turns WHERE session_id = $1",
                session_id,
            )
        return count or 0
