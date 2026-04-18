# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/audit.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import copy
import hashlib
import json as _json

import asyncpg


# ── PII hashing ──────────────────────────────────────────────────────────────

PII_FIELDS = ("age_years", "weight_kg", "chief_complaint", "allergies")


def anonymize_payload(payload: dict) -> dict:
    """SHA-256 hash patient-identifiable fields before persistence.

    Hashed fields: age_years, weight_kg, chief_complaint, allergies,
    and each symptom ``text`` entry.
    """
    result = copy.deepcopy(payload)

    for field in PII_FIELDS:
        if field not in result:
            continue
        value = result[field]
        if isinstance(value, list):
            result[field] = [
                hashlib.sha256(str(item).encode()).hexdigest() for item in value
            ]
        else:
            result[field] = hashlib.sha256(str(value).encode()).hexdigest()

    # Hash symptom text entries
    for symptom in result.get("symptoms", []):
        if isinstance(symptom, dict) and "text" in symptom:
            symptom["text"] = hashlib.sha256(symptom["text"].encode()).hexdigest()

    return result


# ── Audit Logger ─────────────────────────────────────────────────────────────


class AuditLogger:
    """Immutable append-only audit log writer (PostgreSQL)."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def log(
        self,
        session_id: str,
        turn_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        safe_payload = anonymize_payload(payload)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (event_type, session_id, turn_id, payload)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                event_type,
                session_id,
                turn_id,
                _json.dumps(safe_payload, default=str),
            )
