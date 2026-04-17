# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/session.py
# ─────────────────────────────────────────────────────────────────────────────
import json
from typing import Any

import redis.asyncio as aioredis


class SessionStore:
    """Redis-backed session store with 24h TTL."""

    TTL = 86_400  # 24 hours

    def __init__(self, redis_url: str):
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create(self, session_id: str, patient_context: dict, language: str = "fr") -> None:
        data = {
            "session_id":        session_id,
            "patient_context":   patient_context,
            "conversation_history": [],
            "language":          language,
        }
        await self._redis.set(self._key(session_id), json.dumps(data), ex=self.TTL)

    async def get(self, session_id: str) -> dict:
        raw = await self._redis.get(self._key(session_id))
        if not raw:
            return {}
        return json.loads(raw)

    async def patch(self, session_id: str, **fields: Any) -> None:
        data = await self.get(session_id)
        data.update(fields)
        await self._redis.set(self._key(session_id), json.dumps(data), ex=self.TTL)

    async def append_turn(self, session_id: str, turn: dict) -> None:
        data = await self.get(session_id)
        history = data.get("conversation_history", [])
        history.append(turn)
        data["conversation_history"] = history[-20:]  # keep last 20 turns
        await self._redis.set(self._key(session_id), json.dumps(data), ex=self.TTL)

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))
