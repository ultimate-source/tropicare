#!/usr/bin/env python3
"""
Reset the knowledge base: drop all chunks from PostgreSQL and MongoDB,
reset kb_documents chunk counts, and recreate the Atlas vector index.

Usage:
    python scripts/reset_kb.py [--yes]
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

_PG_URL = os.getenv("DATABASE_URL", "postgresql://tropicare:tropicare@localhost:5432/tropicare")
_MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/tropicare")
_MONGO_DB = os.getenv("MONGODB_DB", "tropicare")


async def main():
    import asyncpg
    import motor.motor_asyncio as motor

    if "--yes" not in sys.argv:
        answer = input("This will DELETE all KB chunks and documents. Continue? [y/N] ")
        if answer.lower() != "y":
            print("Aborted.")
            return

    # PostgreSQL cleanup
    print("Cleaning PostgreSQL...")
    pool = await asyncpg.create_pool(_PG_URL, min_size=1, max_size=2)
    async with pool.acquire() as conn:
        chunks_deleted = await conn.fetchval("SELECT COUNT(*) FROM kb_chunks")
        await conn.execute("DELETE FROM kb_chunks")
        docs_deleted = await conn.fetchval("SELECT COUNT(*) FROM kb_documents")
        await conn.execute("DELETE FROM kb_documents")
    await pool.close()
    print(f"  Deleted {chunks_deleted} chunks, {docs_deleted} documents from PostgreSQL")

    # MongoDB cleanup
    print("Cleaning MongoDB...")
    client = motor.AsyncIOMotorClient(_MONGO_URI)
    db = client[_MONGO_DB]
    result = await db["kb_vectors"].delete_many({})
    print(f"  Deleted {result.deleted_count} documents from MongoDB kb_vectors")
    client.close()

    # Recreate Atlas vector index
    print("Recreating Atlas vector index...")
    from pymongo import MongoClient
    from pymongo.operations import SearchIndexModel

    sync_client = MongoClient(_MONGO_URI)
    sync_db = sync_client[_MONGO_DB]
    coll = sync_db["kb_vectors"]

    # Drop existing index if present
    try:
        for idx in coll.list_search_indexes():
            if idx.get("name") == "vector_index":
                coll.drop_search_index("vector_index")
                print("  Dropped existing vector_index")
                break
    except Exception:
        pass

    # Ensure collection exists
    if "kb_vectors" not in sync_db.list_collection_names():
        sync_db.create_collection("kb_vectors")

    # Create fresh index
    try:
        index = SearchIndexModel(
            definition={
                "fields": [
                    {"type": "vector", "path": "embedding", "numDimensions": 3072, "similarity": "cosine"},
                    {"type": "filter", "path": "superseded"},
                    {"type": "filter", "path": "disease_tags"},
                    {"type": "filter", "path": "language"},
                ]
            },
            name="vector_index",
            type="vectorSearch",
        )
        coll.create_search_index(model=index)
        print("  Created vector_index (may take a few minutes to build on Atlas)")
    except Exception as e:
        print(f"  Index creation: {e}")

    sync_client.close()
    print("\nDone. Run 'python scripts/ingest_docs.py' to re-ingest documents.")


if __name__ == "__main__":
    asyncio.run(main())
