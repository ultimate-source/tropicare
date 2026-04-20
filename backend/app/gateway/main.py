# ─────────────────────────────────────────────────────────────────────────────
# tropicare_gateway/main.py  — FastAPI application
# ─────────────────────────────────────────────────────────────────────────────
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import redis.exceptions
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from .routers.auth      import router as auth_router
from .routers.analytics import router as analytics_router
from .middleware import SecurityHeadersMiddleware, CSRFMiddleware
from ..orchestrator.orchestrator import Orchestrator, OrchestratorConfig
from ..orchestrator.session import SessionStore
from ..orchestrator.session_repository import SessionRepository
from ..orchestrator.dual_write import DualWriteSessionStore
from ..orchestrator.audit import AuditLogger
from .auth import require_role
from .config import Settings
from ..observability.tracing import init_tracing
from ..observability.metrics import (
    metrics_app,
)
from ..observability.logging import configure_logging

settings = Settings()
limiter  = Limiter(key_func=get_remote_address)

# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Observability bootstrap ───────────────────────────────────────────────
    configure_logging()
    provider = init_tracing(service_name="tropicare-gateway")

    # Startup
    pg_pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    app.state.pg_pool       = pg_pool
    session_store           = SessionStore(settings.REDIS_URL)
    session_repo            = SessionRepository(pg_pool, settings.SESSION_RETENTION_DAYS)
    dual_write_store        = DualWriteSessionStore(session_store, session_repo)
    app.state.session_store = dual_write_store
    app.state.session_repo  = session_repo
    app.state.audit_logger  = AuditLogger(pg_pool)
    app.state.orchestrator  = Orchestrator(OrchestratorConfig(
        api_key=settings.ANTHROPIC_API_KEY,
        mcp_url=settings.MCP_URL,
        session_store=dual_write_store,
        audit_logger=app.state.audit_logger,
        model=settings.MODEL,
    ))
    yield
    # Shutdown
    provider.shutdown()
    await pg_pool.close()

app = FastAPI(title="TropiCare API", version="1.0.0", lifespan=lifespan)

# ── OpenTelemetry auto-instrumentation for FastAPI ────────────────────────────
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402
FastAPIInstrumentor.instrument_app(app)

app.include_router(auth_router)
app.include_router(analytics_router)

# ── Mount Prometheus /metrics endpoint ────────────────────────────────────────
app.mount("/metrics", metrics_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers on every response (Requirements 22.1–22.4)
app.add_middleware(SecurityHeadersMiddleware)

# CSRF double-submit cookie for browser clients (Requirement 23.6)
app.add_middleware(CSRFMiddleware)

# ── Request metrics middleware ────────────────────────────────────────────────
from ..observability.metrics import MetricsMiddleware  # noqa: E402
app.add_middleware(MetricsMiddleware)

# ── Dependency ────────────────────────────────────────────────────────────────

def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator

def get_store(request: Request) -> SessionStore:
    return request.app.state.session_store

def get_repo(request: Request) -> SessionRepository:
    return request.app.state.session_repo

# ── Request / Response models ─────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    patient_context: dict = {}
    language:        str  = Field(default="fr", max_length=5000)

class CreateSessionResponse(BaseModel):
    session_id: str

class TurnRequest(BaseModel):
    query:  str = Field(max_length=5000)
    mode:   str = Field(default="auto", max_length=5000)  # auto | diagnostic | antibiotherapy

class FeedbackRequest(BaseModel):
    turn_id:        str = Field(max_length=5000)
    verdict:        str = Field(max_length=5000)  # correct | partial | incorrect
    clinician_note: str | None = Field(default=None, max_length=5000)
    actual_diagnosis: str | None = Field(default=None, max_length=5000)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/sessions")
async def list_sessions(
    request: Request,
    user:    dict = Depends(require_role("clinician")),
    store:   SessionStore = Depends(get_store),
    repo:    SessionRepository = Depends(get_repo),
    include_archived: bool = False,
    limit:   int = 50,
    offset:  int = 0,
):
    user_id = user["sub"]

    # Archive sessions older than retention policy
    await repo.archive_expired(user_id)

    sessions, total = await repo.list_sessions(
        user_id, include_archived=include_archived, limit=limit, offset=offset,
    )

    # Lazy close: for each 'active' session, check Redis existence
    for s in sessions:
        if s.get("status") == "active":
            redis_data = await store.get(s["id"])
            if not redis_data:
                # Session expired from Redis — close it in PG
                await repo.close_session(s["id"])
                s["status"] = "closed"

    return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}


@app.post(
    "/api/v1/sessions",
    response_model=CreateSessionResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def create_session(
    request:   Request,
    body:      CreateSessionRequest,
    user:      dict = Depends(require_role("clinician")),
    store:     SessionStore = Depends(get_store),
):
    user_id = user["sub"]
    session_id = str(uuid.uuid4())
    try:
        # Enforce concurrent session limit (Requirement 34.2)
        active_count = await store.count_user_sessions(user_id)
        if active_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Maximum 5 concurrent sessions",
            )

        await store.create(
            session_id=session_id,
            patient_context=body.patient_context,
            language=body.language,
            user_id=user_id,
        )
        await store.register_session(user_id, session_id)
    except HTTPException:
        raise
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Session service temporarily unavailable",
        ) from exc
    return CreateSessionResponse(session_id=session_id)


@app.get("/api/v1/sessions/{session_id}")
async def get_session(
    session_id: str,
    user:       dict = Depends(require_role("clinician")),
    store:      SessionStore = Depends(get_store),
):
    try:
        data = await store.get_or_fallback(session_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Session service temporarily unavailable")
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@app.post("/api/v1/sessions/{session_id}/turns")
@limiter.limit("60/minute")
async def submit_turn(
    request:      Request,
    session_id:   str,
    body:         TurnRequest,
    user:         dict = Depends(require_role("clinician")),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    store:        SessionStore = Depends(get_store),
):
    try:
        state = await store.get(session_id)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Session could not be loaded",
        ) from exc

    if not state:
        raise HTTPException(status_code=404, detail="Session expired or not found")

    language = state.get("language", "fr")
    turn_id  = str(uuid.uuid4())

    async def ndjson_stream() -> AsyncIterator[bytes]:
        """
        Emit one JSON object per line (NDJSON).
        \n is the only record separator — no SSE envelope.
        Client reads with fetch() + ReadableStream, not EventSource.
        """
        try:
            async for event in orchestrator.handle_turn(
                session_id=session_id,
                turn_id=turn_id,
                query=body.query,
                mode=body.mode,
                language=language,
            ):
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        except asyncio.CancelledError:
            pass  # client disconnected — stop iteration silently

    return StreamingResponse(
        ndjson_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",   # tell nginx not to buffer
            "Transfer-Encoding": "chunked",
        },
    )


@app.post("/api/v1/feedback", status_code=201)
async def submit_feedback(
    body:    FeedbackRequest,
    user:    dict = Depends(require_role("clinician")),
    request: Request = None,
):
    async with request.app.state.pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO feedback (turn_id, verdict, clinician_note, actual_diagnosis, user_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            body.turn_id, body.verdict,
            body.clinician_note, body.actual_diagnosis,
            user["sub"],
        )
    return {"status": "accepted"}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "tropicare-gateway"}


# ── Admin routes (role: admin) ────────────────────────────────────────────────

@app.get("/api/v1/admin/documents")
async def list_documents(
    user:    dict = Depends(require_role("admin")),
    request: Request = None,
):
    rows = await request.app.state.pg_pool.fetch(
        """
        SELECT id, title, source_type, version, published_date,
               ingested_at, chunk_count, superseded_by IS NOT NULL AS superseded
        FROM kb_documents
        ORDER BY ingested_at DESC
        LIMIT 100
        """
    )
    return [dict(r) for r in rows]


@app.post("/api/v1/admin/documents", status_code=202)
async def upload_document(
    user:    dict = Depends(require_role("admin")),
    request: Request = None,
):
    """
    Accepts multipart/form-data with fields:
      file      — binary PDF/DOCX
      title     — document title
      source_type — guideline|formulary|amr_data|epidemiology
      version   — e.g. "2023"
    Returns document_id and enqueues background ingestion.
    """
    form    = await request.form()
    file    = form.get("file")
    title   = form.get("title", "Untitled")
    src_type = form.get("source_type", "guideline")
    version = form.get("version", "")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    content = await file.read()
    doc_id  = str(uuid.uuid4())

    # Write raw file to object storage (stub — replace with S3/MinIO client)
    import os
    os.makedirs("/tmp/kb_raw", exist_ok=True)
    raw_path = f"/tmp/kb_raw/{doc_id}_{file.filename}"
    with open(raw_path, "wb") as f:
        f.write(content)

    # Insert document record
    async with request.app.state.pg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO kb_documents (id, title, source_type, version, raw_path)
            VALUES ($1, $2, $3, $4, $5)
            """,
            doc_id, title, src_type, version, raw_path,
        )

    # Enqueue ingestion job via Redis ARQ
    import arq
    redis_pool = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.REDIS_URL))
    await redis_pool.enqueue_job("ingest_document", doc_id, raw_path, src_type)

    return {"document_id": doc_id, "status": "queued"}


@app.delete("/api/v1/admin/documents/{doc_id}", status_code=204)
async def supersede_document(
    doc_id:    str,
    reason_id: str,
    user:      dict = Depends(require_role("admin")),
    request:   Request = None,
):
    """Soft-delete: marks document as superseded, excludes from retrieval."""
    async with request.app.state.pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE kb_documents SET superseded_by = $1 WHERE id = $2",
            reason_id, doc_id,
        )
