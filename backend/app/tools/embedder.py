# ─────────────────────────────────────────────────────────────────────────────
# backend/app/tools/embedder.py — Single-text embedding for MCP tools server
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import hashlib
import json
import logging

import httpx

from .config import settings
from .db import get_redis

log = logging.getLogger(__name__)

_MODEL = "text-embedding-3-large"
_EMBED_CACHE_TTL = 86_400  # 24 hours


async def embed_text(query: str) -> list[float]:
    """Embed a single text string using OpenAI text-embedding-3-large.

    Results are cached in Redis with a 24-hour TTL keyed by content hash
    to avoid re-embedding unchanged text.
    """
    content_hash = hashlib.sha256(query.encode()).hexdigest()
    cache_key = f"embed:{content_hash}"

    # Check Redis cache
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        log.debug("Redis unavailable for embedding cache lookup — proceeding without cache")

    # Call OpenAI API
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"input": query, "model": _MODEL},
        )
        r.raise_for_status()
        embedding = r.json()["data"][0]["embedding"]

    # Store in Redis cache (24-hour TTL)
    try:
        redis = await get_redis()
        await redis.setex(cache_key, _EMBED_CACHE_TTL, json.dumps(embedding))
    except Exception:
        log.debug("Redis unavailable for embedding cache write — skipping")

    return embedding
