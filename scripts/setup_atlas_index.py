#!/usr/bin/env python3
"""
Create the MongoDB Atlas Vector Search index on the kb_vectors collection.

Usage:
    python scripts/setup_atlas_index.py

Requires MONGODB_URI in .env or environment.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/tropicare")
MONGODB_DB = os.getenv("MONGODB_DB", "tropicare")


def main():
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    coll = db["kb_vectors"]

    # Ensure collection exists before creating index
    if "kb_vectors" not in db.list_collection_names():
        db.create_collection("kb_vectors")
        print("Created kb_vectors collection")

    # Check if index already exists
    existing = list(coll.list_search_indexes())
    for idx in existing:
        if idx.get("name") == "vector_index":
            print("vector_index already exists — skipping")
            client.close()
            return

    # Create the vector search index
    index = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 3072,
                    "similarity": "cosine",
                },
                {
                    "type": "filter",
                    "path": "superseded",
                },
                {
                    "type": "filter",
                    "path": "disease_tags",
                },
                {
                    "type": "filter",
                    "path": "language",
                },
            ]
        },
        name="vector_index",
        type="vectorSearch",
    )

    print(f"Creating vector_index on {MONGODB_DB}.kb_vectors...")
    coll.create_search_index(model=index)
    print("Done — index may take a few minutes to build on Atlas.")

    client.close()


if __name__ == "__main__":
    main()
