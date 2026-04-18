# ─────────────────────────────────────────────────────────────────────────────
# tropicare_ingestion/worker.py
# ARQ background worker — processes ingestion jobs from Redis queue.
# Run: arq tropicare_ingestion.worker.WorkerSettings
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import os

import asyncpg
from arq import cron
from arq.connections import RedisSettings
import motor.motor_asyncio as motor

from .pipeline import run_pipeline

_PG_URL      = os.getenv("DATABASE_URL", "postgresql://tropicare:tropicare@localhost:5432/tropicare")
_REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
_MONGODB_DB  = os.getenv("MONGODB_DB", "tropicare")
_OPENAI      = os.getenv("OPENAI_API_KEY", "")


async def startup(ctx: dict) -> None:
    ctx["pg_pool"] = await asyncpg.create_pool(_PG_URL, min_size=1, max_size=4)
    ctx["mongo_client"] = motor.AsyncIOMotorClient(_MONGODB_URI)
    ctx["mongo_db"] = ctx["mongo_client"][_MONGODB_DB]


async def shutdown(ctx: dict) -> None:
    await ctx["pg_pool"].close()
    ctx["mongo_client"].close()


async def ingest_document(
    ctx:            dict,
    document_id:    str,
    file_path:      str,
    source_type:    str   = "guideline",
    source_title:   str   = "",
    source_version: str   = "",
    source_date:    str   = "",
) -> dict:
    """ARQ job function — called by the gateway after file upload."""
    return await run_pipeline(
        document_id=document_id,
        file_path=file_path,
        source_type=source_type,
        source_title=source_title,
        source_version=source_version,
        source_date=source_date,
        pg_pool=ctx["pg_pool"],
        mongo_db=ctx["mongo_db"],
        openai_api_key=_OPENAI,
    )


class WorkerSettings:
    functions      = [ingest_document]
    on_startup     = startup
    on_shutdown    = shutdown
    redis_settings = RedisSettings.from_dsn(_REDIS_URL)
    max_jobs       = 4       # process 4 documents in parallel
    job_timeout    = 600     # 10 minutes per document
    retry_jobs     = True
    max_tries      = 3
