# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/store.py
# Upserts chunks to MongoDB (vectors) and PostgreSQL (metadata + BM25 index).
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

import asyncpg
from motor.motor_asyncio import AsyncIOMotorDatabase

log = logging.getLogger("tropicare.ingestion.store")


async def upsert_chunks(
    document_id: str,
    chunks:      list[dict],      # [{chunk_text, section, page, ...metadata, vector}]
    pg_pool:     asyncpg.Pool,
    mongo_db:    AsyncIOMotorDatabase,
) -> int:
    """
    Insert chunks into both MongoDB (vectors) and PostgreSQL (full-text index).
    Returns number of new chunks inserted (skips duplicates by content hash).
    """
    inserted = 0
    coll = mongo_db["kb_vectors"]

    async with pg_pool.acquire() as conn:
        for chunk in chunks:
            chunk_id   = str(uuid.uuid4())
            chash      = chunk.get("content_hash", "")
            chunk_text = chunk["chunk_text"]

            # Check for duplicate in Postgres
            exists = await conn.fetchval(
                "SELECT 1 FROM kb_chunks WHERE content_hash = $1 LIMIT 1",
                chash,
            )
            if exists:
                log.debug("Skipping duplicate chunk hash %s", chash)
                continue

            # Insert Postgres record
            await conn.execute(
                """
                INSERT INTO kb_chunks
                  (id, document_id, chunk_text, section, page, language,
                   disease_tags, drug_tags, content_type, content_hash,
                   token_count, superseded)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,false)
                """,
                chunk_id, document_id, chunk_text,
                chunk.get("section", ""),
                chunk.get("page", 0),
                chunk.get("language", "fr"),
                chunk.get("disease_tags", []),
                chunk.get("drug_tags", []),
                chunk.get("content_type", "guideline"),
                chash,
                chunk.get("token_count", 0),
            )

            # Upsert MongoDB document
            await coll.update_one(
                {"chunk_id": chunk_id},
                {"$set": {
                    "chunk_id":       chunk_id,
                    "document_id":    document_id,
                    "embedding":      chunk["vector"],
                    "chunk_text":     chunk_text,
                    "section":        chunk.get("section", ""),
                    "page":           chunk.get("page", 0),
                    "language":       chunk.get("language", "fr"),
                    "disease_tags":   chunk.get("disease_tags", []),
                    "drug_tags":      chunk.get("drug_tags", []),
                    "content_type":   chunk.get("content_type", "guideline"),
                    "superseded":     False,
                    "source_title":   chunk.get("source_title", ""),
                    "source_version": chunk.get("source_version", ""),
                    "source_date":    str(chunk.get("source_date", "")),
                    "created_at":     datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            inserted += 1

    log.info("Upserted %d/%d chunks for document %s", inserted, len(chunks), document_id)
    return inserted


async def mark_superseded(
    document_id: str,
    pg_pool:     asyncpg.Pool,
    mongo_db:    AsyncIOMotorDatabase,
) -> None:
    """Mark all chunks of a document as superseded in both stores."""
    # Update Postgres
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE kb_chunks SET superseded = true WHERE document_id = $1",
            document_id,
        )

    # Update MongoDB
    coll = mongo_db["kb_vectors"]
    await coll.update_many(
        {"document_id": document_id},
        {"$set": {"superseded": True}},
    )
