# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/audit.py
# ─────────────────────────────────────────────────────────────────────────────
import asyncpg
import json as _json


class AuditLogger:
    """Immutable append-only audit log writer (PostgreSQL)."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def log(
        self,
        session_id: str,
        turn_id:    str,
        event_type: str,
        payload:    dict,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (event_type, session_id, turn_id, payload)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                event_type,
                session_id,
                turn_id,
                _json.dumps(payload, default=str),
            )
