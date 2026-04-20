# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/dual_write.py
# ─────────────────────────────────────────────────────────────────────────────
"""Dual-write session store: Redis (blocking) + PostgreSQL (best-effort)."""
from __future__ import annotations

import asyncio
import logging

from .session import SessionStore
from .session_repository import SessionRepository

log = logging.getLogger(__name__)


class DualWriteSessionStore:
    """Writes to Redis (blocking) + PostgreSQL (best-effort via asyncio.create_task)."""

    def __init__(
        self,
        redis_store: SessionStore,
        pg_repo: SessionRepository,
    ):
        self._redis = redis_store
        self._pg = pg_repo

    # ── Fire-and-forget helper ────────────────────────────────────────────────

    def _fire_and_forget(
        self, coro, operation: str, session_id: str, **ctx
    ):
        async def _safe():
            try:
                await coro
            except Exception as exc:
                log.warning(
                    "pg_%s failed session=%s: %s", operation, session_id, exc
                )

        asyncio.create_task(_safe())

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(
        self,
        session_id: str,
        patient_context: dict,
        language: str = "fr",
        user_id: str | None = None,
    ) -> None:
        # Redis write — blocking
        await self._redis.create(session_id, patient_context, language)

        # PG write — fire-and-forget
        if user_id is not None:
            self._fire_and_forget(
                self._pg.create_session(
                    session_id, user_id, patient_context, language
                ),
                "create_session",
                session_id,
            )

    # ── Get (Redis only) ──────────────────────────────────────────────────────

    async def get(self, session_id: str) -> dict:
        return await self._redis.get(session_id)

    # ── Get with PG fallback ─────────────────────────────────────────────────

    async def get_or_fallback(self, session_id: str) -> dict | None:
        """Try Redis first; on miss, fall back to PG. Performs lazy close."""
        data = await self._redis.get(session_id)
        if data:
            return data

        # Redis miss — try PostgreSQL
        detail = await self._pg.get_session_detail(session_id)
        if detail is None:
            return None

        # Lazy close: if PG says 'active' but Redis is empty, session expired
        if detail.get("status") == "active":
            self._fire_and_forget(
                self._pg.close_session(session_id),
                "lazy_close",
                session_id,
            )

        return detail

    # ── Patch ─────────────────────────────────────────────────────────────────

    async def patch(self, session_id: str, **fields) -> None:
        # Redis write — blocking
        await self._redis.patch(session_id, **fields)

        # PG write — fire-and-forget (only if patient_context changed)
        if "patient_context" in fields:
            self._fire_and_forget(
                self._pg.update_patient_context(
                    session_id, fields["patient_context"]
                ),
                "update_patient_context",
                session_id,
            )

    # ── Append turn ───────────────────────────────────────────────────────────

    async def append_turn(self, session_id: str, turn: dict) -> None:
        # Redis write — blocking
        await self._redis.append_turn(session_id, turn)

        # Compute turn_index from Redis conversation history length
        redis_data = await self._redis.get(session_id)
        turn_index = len(redis_data.get("conversation_history", [])) - 1

        # Extract fields for PG
        turn_id = turn.get("turn_id", "")
        query = turn.get("query", "")
        response = {
            "diag": turn.get("diag"),
            "anti": turn.get("anti"),
            "warnings": turn.get("warnings", []),
            "references": turn.get("references", []),
        }

        # PG write — fire-and-forget
        self._fire_and_forget(
            self._pg.upsert_turn(session_id, turn_id, turn_index, query, response),
            "upsert_turn",
            session_id,
        )

    # ── Delegated to Redis store ──────────────────────────────────────────────

    async def register_session(self, user_id: str, session_id: str) -> None:
        await self._redis.register_session(user_id, session_id)

    async def count_user_sessions(self, user_id: str) -> int:
        return await self._redis.count_user_sessions(user_id)
