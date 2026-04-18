# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/pipeline.py
# Full pipeline: file → parse → chunk → embed → metadata → store
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from pathlib import Path

import asyncpg
from motor.motor_asyncio import AsyncIOMotorDatabase

from .parser   import parse
from .chunker  import chunk_sections
from .metadata import extract_metadata
from .embedder import embed_batch, content_hash
from .store    import upsert_chunks

log = logging.getLogger("tropicare.ingestion.pipeline")


async def run_pipeline(
    document_id:     str,
    file_path:       str,
    source_type:     str,
    source_title:    str,
    source_version:  str,
    source_date:     str,
    pg_pool:         asyncpg.Pool,
    mongo_db:        AsyncIOMotorDatabase,
    openai_api_key:  str,
) -> dict:
    """
    Full ingestion pipeline for a single document.
    Returns summary: {document_id, chunks_processed, chunks_inserted, status}
    """
    log.info("Pipeline start: doc=%s file=%s", document_id, file_path)

    try:
        # ── 1. Parse ──────────────────────────────────────────────────────────
        sections = parse(file_path)
        if not sections:
            return {"document_id": document_id, "status": "empty", "chunks_inserted": 0}

        # ── 2. Chunk ──────────────────────────────────────────────────────────
        raw_chunks = chunk_sections(sections, max_tokens=512, overlap_tokens=64)
        log.info("  %d sections → %d chunks", len(sections), len(raw_chunks))

        # ── 3. Metadata extraction ────────────────────────────────────────────
        enriched = []
        for c in raw_chunks:
            meta = extract_metadata(c.text, c.section)
            enriched.append({
                "chunk_text":     c.text,
                "section":        c.section,
                "page":           c.page,
                "language":       meta.get("language", c.language),
                "content_type":   source_type or meta.get("content_type", "guideline"),
                "disease_tags":   meta.get("disease_tags", []),
                "drug_tags":      meta.get("drug_tags", []),
                "token_count":    c.token_count,
                "content_hash":   content_hash(c.text),
                "source_title":   source_title,
                "source_version": source_version,
                "source_date":    source_date,
            })

        # ── 4. Embed (batched) ────────────────────────────────────────────────
        texts   = [c["chunk_text"] for c in enriched]
        vectors = await embed_batch(texts, api_key=openai_api_key)
        for chunk, vec in zip(enriched, vectors):
            chunk["vector"] = vec

        # ── 5. Store ──────────────────────────────────────────────────────────
        inserted = await upsert_chunks(
            document_id=document_id,
            chunks=enriched,
            pg_pool=pg_pool,
            mongo_db=mongo_db,
        )

        # ── 6. Update document record ─────────────────────────────────────────
        async with pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE kb_documents SET chunk_count = $1 WHERE id = $2",
                inserted, document_id,
            )

        log.info("Pipeline done: %d chunks inserted for %s", inserted, document_id)
        return {
            "document_id":     document_id,
            "chunks_processed": len(enriched),
            "chunks_inserted":  inserted,
            "status":          "ok",
        }

    except Exception as exc:
        log.error("Pipeline failed for %s: %s", document_id, exc, exc_info=True)
        async with pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE kb_documents SET ingestion_error = $1 WHERE id = $2",
                str(exc), document_id,
            )
        return {"document_id": document_id, "status": "error", "error": str(exc)}
