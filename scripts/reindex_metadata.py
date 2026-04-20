#!/usr/bin/env python3
"""
Re-extract metadata (disease_tags, drug_tags) for all existing chunks
in PostgreSQL and MongoDB, using the latest keyword dictionaries.

Usage:
    python scripts/reindex_metadata.py

This does NOT re-embed or re-parse — it only updates tags on existing chunks.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.ingestion.metadata import extract_metadata


_PG_URL = os.getenv("DATABASE_URL", "postgresql://tropicare:tropicare@localhost:5432/tropicare")
_MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/tropicare")
_MONGO_DB = os.getenv("MONGODB_DB", "tropicare")


async def main():
    import asyncpg
    import motor.motor_asyncio as motor

    pg_pool = await asyncpg.create_pool(_PG_URL, min_size=1, max_size=4)
    mongo_client = motor.AsyncIOMotorClient(_MONGO_URI)
    mongo_db = mongo_client[_MONGO_DB]
    coll = mongo_db["kb_vectors"]

    # Fetch all chunks from PostgreSQL
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, chunk_text, section, disease_tags, drug_tags FROM kb_chunks"
        )

    print(f"Re-indexing metadata for {len(rows)} chunks...")

    updated_pg = 0
    updated_mongo = 0
    newly_tagged = 0

    async with pg_pool.acquire() as conn:
        for row in rows:
            chunk_id = str(row["id"])
            text = row["chunk_text"]
            section = row["section"] or ""
            old_drug_tags = row["drug_tags"] or []
            old_disease_tags = row["disease_tags"] or []

            meta = extract_metadata(text, section)
            new_drug_tags = meta.get("drug_tags", [])
            new_disease_tags = meta.get("disease_tags", [])

            # Merge old + new (don't lose existing tags)
            merged_drug = list(set(old_drug_tags + new_drug_tags))
            merged_disease = list(set(old_disease_tags + new_disease_tags))

            changed = (
                set(merged_drug) != set(old_drug_tags)
                or set(merged_disease) != set(old_disease_tags)
            )

            if not changed:
                continue

            if new_drug_tags and not old_drug_tags:
                newly_tagged += 1

            # Update PostgreSQL
            await conn.execute(
                "UPDATE kb_chunks SET disease_tags = $1, drug_tags = $2 WHERE id = $3",
                merged_disease, merged_drug, row["id"],
            )
            updated_pg += 1

            # Update MongoDB
            result = await coll.update_one(
                {"chunk_id": chunk_id},
                {"$set": {"disease_tags": merged_disease, "drug_tags": merged_drug}},
            )
            if result.modified_count > 0:
                updated_mongo += 1

    await pg_pool.close()
    mongo_client.close()

    print(f"Done: {updated_pg} chunks updated in PostgreSQL, {updated_mongo} in MongoDB")
    print(f"  {newly_tagged} chunks gained drug_tags for the first time")


if __name__ == "__main__":
    asyncio.run(main())
