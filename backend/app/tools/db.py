# ─────────────────────────────────────────────────────────────────────────────
# backend/app/tools/db.py — Database singletons: MongoDB, PostgreSQL, Redis
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncpg
import motor.motor_asyncio as motor
import redis.asyncio as aioredis

from .config import settings

# ── MongoDB ───────────────────────────────────────────────────────────────────

_mongo_client: motor.AsyncIOMotorClient | None = None


async def get_mongo_db() -> motor.AsyncIOMotorDatabase:
    """Return a Motor database handle (lazy singleton)."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = motor.AsyncIOMotorClient(
            settings.MONGODB_URI,
            maxPoolSize=20,
            minPoolSize=2,
            serverSelectionTimeoutMS=5000,
        )
    return _mongo_client[settings.MONGODB_DB]


# ── PostgreSQL ────────────────────────────────────────────────────────────────

_pg_pool: asyncpg.Pool | None = None


async def get_postgres_pool() -> asyncpg.Pool:
    """Return an asyncpg connection pool (lazy singleton)."""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=2,
            max_size=10,
        )
    return _pg_pool


# ── Redis ─────────────────────────────────────────────────────────────────────

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return a Redis async client (lazy singleton)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis
