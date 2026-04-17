# ─────────────────────────────────────────────────────────────────────────────
# tropicare_gateway/main.py  — FastAPI application
# ─────────────────────────────────────────────────────────────────────────────
import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from .routers.auth      import router as auth_router
from .routers.analytics import router as analytics_router
from ..orchestrator.orchestrator import Orchestrator, OrchestratorConfig
from ..orchestrator.session import SessionStore
from ..orchestrator.audit import AuditLogger
from .auth import require_role, get_current_user
from .config import Settings

settings = Settings()
limiter  = Limiter(key_func=get_remote_address)

# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    pg_pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    app.state.pg_pool      = pg_pool
    app.state.session_store = SessionStore(settings.REDIS_URL)
    app.state.audit_logger  = AuditLogger(pg_pool)
    app.state.orchestrator  = Orchestrator(OrchestratorConfig(
        api_key=settings.ANTHROPIC_API_KEY,
        mcp_url=settings.MCP_URL,
        session_store=app.state.session_store,
        audit_logger=app.state.audit_logger,
        model=settings.MODEL,
    ))
    yield
    # Shutdown
    await pg_pool.close()

app = FastAPI(title="TropiCare API", version="1.0.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(analytics_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Dependency ────────────────────────────────────────────────────────────────

def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator

def get_store(request: Request) -> SessionStore:
    return request.app.state.session_store

# ── Request / Response models ─────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    patient_context: dict = {}
    language:        str  = "fr"

class CreateSessionResponse(BaseModel):
    session_id: str

class TurnRequest(BaseModel):
    query:  str
    mode:   str = "auto"  # auto | diagnostic | antibiotherapy

class FeedbackRequest(BaseModel):
    turn_id:        str
    verdict:        str   # correct | partial | incorrect
    clinician_note: str | None = None
    actual_diagnosis: str | None = None

# ── Routes ────────────────────────────────────────────────────────────────────

@app.post(
    "/api/v1/sessions",
    response_model=CreateSessionResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def create_session(
    request:   Request,
    body:      CreateSessionRequest,
    user:      dict = Depends(get_current_user),
    store:     SessionStore = Depends(get_store),
):
    session_id = str(uuid.uuid4())
    await store.create(
        session_id=session_id,
        patient_context=body.patient_context,
        language=body.language,
    )
    return CreateSessionResponse(session_id=session_id)


@app.get("/api/v1/sessions/{session_id}")
async def get_session(
    session_id: str,
    user:       dict = Depends(get_current_user),
    store:      SessionStore = Depends(get_store),
):
    data = await store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@app.post("/api/v1/sessions/{session_id}/turns")
@limiter.limit("60/minute")
async def submit_turn(
    request:      Request,
    session_id:   str,
    body:         TurnRequest,
    user:         dict = Depends(get_current_user),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    store:        SessionStore = Depends(get_store),
):
    state = await store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

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
    user:    dict = Depends(get_current_user),
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


@app.get("/api/v1/metrics")
async def metrics():
    # Prometheus text format — in production use prometheus_client
    return {"note": "mount prometheus_client.make_asgi_app() at /metrics"}


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
    redis = arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.REDIS_URL))
    await redis.enqueue_job("ingest_document", doc_id, raw_path, src_type)

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
