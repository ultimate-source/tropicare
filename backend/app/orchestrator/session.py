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
        import datetime
        data = {
            "session_id":        session_id,
            "patient_context":   patient_context,
            "conversation_history": [],
            "language":          language,
            "created_at":        datetime.datetime.now(datetime.timezone.utc).isoformat(),
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

    # ── User session tracking (concurrent session limits) ─────────────────────

    def _user_sessions_key(self, user_id: str) -> str:
        return f"user_sessions:{user_id}"

    async def register_session(self, user_id: str, session_id: str) -> None:
        """Register a session for a user in their session tracking set."""
        await self._redis.sadd(self._user_sessions_key(user_id), session_id)

    async def unregister_session(self, user_id: str, session_id: str) -> None:
        """Remove a session from a user's tracking set."""
        await self._redis.srem(self._user_sessions_key(user_id), session_id)

    async def count_user_sessions(self, user_id: str) -> int:
        """Count active sessions for a user, cleaning up expired ones."""
        key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(key)
        if not session_ids:
            return 0

        # Filter out expired sessions (those no longer in Redis)
        expired = []
        for sid in session_ids:
            exists = await self._redis.exists(self._key(sid))
            if not exists:
                expired.append(sid)

        # Clean up expired entries from the set
        if expired:
            await self._redis.srem(key, *expired)

        return len(session_ids) - len(expired)

    async def list_user_sessions(self, user_id: str) -> list[dict]:
        """Return summary dicts for all active sessions belonging to a user."""
        key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(key)
        if not session_ids:
            return []

        summaries: list[dict] = []
        expired: list[str] = []

        for sid in session_ids:
            data = await self.get(sid)
            if not data:
                expired.append(sid)
                continue
            history = data.get("conversation_history", [])
            last_query = ""
            for turn in reversed(history):
                q = turn.get("query", "")
                if q:
                    last_query = q
                    break
            summaries.append({
                "id":         sid,
                "created_at": data.get("created_at", ""),
                "language":   data.get("language", "fr"),
                "turn_count": len(history),
                "last_query": last_query,
            })

        if expired:
            await self._redis.srem(key, *expired)

        # Sort by created_at descending (newest first)
        summaries.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return summaries
