# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/embedder.py
# Async embedding with OpenAI (primary) and local Nomic fallback.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Callable

import httpx
import numpy as np

log = logging.getLogger("tropicare.ingestion.embedder")

_BATCH_SIZE = 32       # OpenAI text-embedding-3-large batch limit
_EMBED_DIM  = 3072     # text-embedding-3-large dimension


async def embed_batch(
    texts:   list[str],
    api_key: str,
    model:   str = "text-embedding-3-large",
) -> list[list[float]]:
    """Embed a batch of texts, returning list of float vectors."""
    if not texts:
        return []

    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i:i + _BATCH_SIZE]
        try:
            vectors = await _openai_embed(batch, api_key, model)
        except Exception as e:
            log.warning("OpenAI embedding failed (%s) — falling back to Nomic", e)
            vectors = await _nomic_embed(batch)
        all_vectors.extend(vectors)

    return all_vectors


async def _openai_embed(texts: list[str], api_key: str, model: str) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": model},
        )
        r.raise_for_status()
        data = r.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]


async def _nomic_embed(texts: list[str]) -> list[list[float]]:
    """Local Nomic embed via sentence-transformers (CPU fallback)."""
    from sentence_transformers import SentenceTransformer
    import asyncio

    model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)
    loop = asyncio.get_event_loop()
    vecs = await loop.run_in_executor(None, model.encode, texts)
    return [v.tolist() for v in vecs]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

