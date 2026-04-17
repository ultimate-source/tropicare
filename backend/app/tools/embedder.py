# ─────────────────────────────────────────────────────────────────────────────
# backend/app/tools/embedder.py — Single-text embedding for MCP tools server
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import httpx

from .config import settings

_MODEL = "text-embedding-3-large"


async def embed_text(query: str) -> list[float]:
    """Embed a single text string using OpenAI text-embedding-3-large."""
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
        data = r.json()["data"]
        return data[0]["embedding"]
