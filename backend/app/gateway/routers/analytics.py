# ─────────────────────────────────────────────────────────────────────────────
# tropicare_gateway/routers/analytics.py
# ─────────────────────────────────────────────────────────────────────────────

import json
from datetime import date, timedelta

import asyncpg
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ..auth import require_role

router = APIRouter(prefix="/api/v1/admin", tags=["analytics"])

# ── Response models ───────────────────────────────────────────────────────────

class DiseaseCount(BaseModel):
    disease: str
    count:   int

class DailyVolume(BaseModel):
    date:     str
    sessions: int
    turns:    int

class FeedbackBreakdown(BaseModel):
    correct:   int
    partial:   int
    incorrect: int
    total:     int

class AnalyticsSummary(BaseModel):
    total_sessions:     int
    total_turns:        int
    active_users_7d:    int
    top_diseases:       list[DiseaseCount]
    daily_volume:       list[DailyVolume]
    p50_latency_ms:     float
    p95_latency_ms:     float
    citation_rate:      float
    feedback:           FeedbackBreakdown
    guideline_adherence: float | None    # from eval reports if available
    emergency_rate:     float            # % of turns that raised an emergency flag

# ── Helper ────────────────────────────────────────────────────────────────────

def _pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pg_pool

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=AnalyticsSummary)
async def get_analytics(
    request: Request,
    days:    int = Query(default=30, ge=1, le=365),
    _user:   dict = Depends(require_role("admin")),
):
    pool  = _pool(request)
    since = date.today() - timedelta(days=days)

    # Run all queries concurrently
    (
        session_count,
        turn_count,
        active_users,
        top_diseases,
        daily_volume,
        latency_rows,
        citation_rows,
        feedback_rows,
        emergency_rows,
    ) = await asyncpg.gather_queries(pool, [

        # ── Total sessions ────────────────────────────────────────────────────
        (
            "SELECT COUNT(*) FROM sessions WHERE created_at >= $1",
            [since],
        ),

        # ── Total turns ───────────────────────────────────────────────────────
        (
            "SELECT COUNT(*) FROM turns WHERE created_at >= $1",
            [since],
        ),

        # ── Active users (distinct) last 7 days ───────────────────────────────
        (
            """
            SELECT COUNT(DISTINCT s.user_id)
            FROM   turns t
            JOIN   sessions s ON t.session_id = s.id
            WHERE  t.created_at >= NOW() - INTERVAL '7 days'
            """,
            [],
        ),

        # ── Top diseases from differential JSONB ──────────────────────────────
        # Each turn stores response JSONB with differential[].disease_name
        (
            """
            SELECT
                d->>'disease_name' AS disease,
                COUNT(*)           AS cnt
            FROM
                turns t,
                jsonb_array_elements(
                    COALESCE(t.response->'differential', '[]'::jsonb)
                ) AS d
            WHERE
                t.created_at >= $1
                AND d->>'rank' = '1'           -- top-1 only
                AND d->>'disease_name' IS NOT NULL
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 15
            """,
            [since],
        ),

        # ── Daily session + turn volume ───────────────────────────────────────
        (
            """
            WITH days AS (
                SELECT generate_series($1::date, CURRENT_DATE, '1 day') AS day
            )
            SELECT
                d.day::text                                                AS date,
                COUNT(DISTINCT s.id)                                       AS sessions,
                COUNT(t.id)                                                AS turns
            FROM
                days d
                LEFT JOIN sessions s ON s.created_at::date = d.day
                LEFT JOIN turns    t ON t.session_id = s.id
            GROUP BY 1
            ORDER BY 1
            """,
            [since],
        ),

        # ── Latency percentiles ───────────────────────────────────────────────
        (
            """
            SELECT
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95
            FROM turns
            WHERE created_at >= $1
              AND latency_ms IS NOT NULL
            """,
            [since],
        ),

        # ── Citation rate ─────────────────────────────────────────────────────
        # A turn "has citations" if response->citations is a non-empty array.
        (
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(
                        COALESCE(response->'citations', '[]'::jsonb)
                    ) > 0
                )::float / NULLIF(COUNT(*), 0) AS rate
            FROM turns
            WHERE created_at >= $1
            """,
            [since],
        ),

        # ── Feedback breakdown ────────────────────────────────────────────────
        (
            """
            SELECT
                COUNT(*) FILTER (WHERE verdict = 'correct')   AS correct,
                COUNT(*) FILTER (WHERE verdict = 'partial')   AS partial,
                COUNT(*) FILTER (WHERE verdict = 'incorrect') AS incorrect,
                COUNT(*)                                       AS total
            FROM feedback f
            JOIN turns t ON f.turn_id = t.id
            WHERE t.created_at >= $1
            """,
            [since],
        ),

        # ── Emergency flag rate ───────────────────────────────────────────────
        (
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(
                        COALESCE(response->'emergency_flags', '[]'::jsonb)
                    ) > 0
                )::float / NULLIF(COUNT(*), 0) AS rate
            FROM turns
            WHERE created_at >= $1
            """,
            [since],
        ),
    ])

    lat   = dict(latency_rows[0])   if latency_rows   else {}
    cit   = dict(citation_rows[0])  if citation_rows  else {}
    fb    = dict(feedback_rows[0])  if feedback_rows  else {}
    emerg = dict(emergency_rows[0]) if emergency_rows else {}

    return AnalyticsSummary(
        total_sessions   = session_count[0][0],
        total_turns      = turn_count[0][0],
        active_users_7d  = active_users[0][0],
        top_diseases     = [DiseaseCount(disease=r["disease"], count=r["cnt"]) for r in top_diseases],
        daily_volume     = [DailyVolume(**dict(r)) for r in daily_volume],
        p50_latency_ms   = float(lat.get("p50") or 0),
        p95_latency_ms   = float(lat.get("p95") or 0),
        citation_rate    = float(cit.get("rate") or 0),
        feedback         = FeedbackBreakdown(
            correct   = fb.get("correct",   0),
            partial   = fb.get("partial",   0),
            incorrect = fb.get("incorrect", 0),
            total     = fb.get("total",     0),
        ),
        guideline_adherence = None,   # populated from eval reports (see below)
        emergency_rate      = float(emerg.get("rate") or 0),
    )


@router.get("/analytics/sessions")
async def sessions_detail(
    request: Request,
    days:    int   = Query(default=7, ge=1, le=90),
    page:    int   = Query(default=1, ge=1),
    limit:   int   = Query(default=20, ge=1, le=100),
    _user:   dict  = Depends(require_role("admin")),
):
    """Paginated list of recent sessions with turn count and last query."""
    pool   = _pool(request)
    since  = date.today() - timedelta(days=days)
    offset = (page - 1) * limit

    rows = await pool.fetch(
        """
        SELECT
            s.id,
            u.email                       AS user_email,
            s.language,
            s.created_at,
            COUNT(t.id)                   AS turn_count,
            MAX(t.query)                  AS last_query,
            AVG(t.latency_ms)             AS avg_latency_ms
        FROM   sessions s
        JOIN   users    u ON u.id = s.user_id
        LEFT JOIN turns t ON t.session_id = s.id
        WHERE  s.created_at >= $1
        GROUP BY s.id, u.email, s.language, s.created_at
        ORDER BY s.created_at DESC
        LIMIT  $2 OFFSET $3
        """,
        since, limit, offset,
    )

    total = await pool.fetchval(
        "SELECT COUNT(*) FROM sessions WHERE created_at >= $1", since
    )

    return {
        "total":    total,
        "page":     page,
        "limit":    limit,
        "sessions": [
            {
                "id":             str(r["id"]),
                "user_email":     r["user_email"],
                "language":       r["language"],
                "created_at":     r["created_at"].isoformat(),
                "turn_count":     r["turn_count"],
                "last_query":     (r["last_query"] or "")[:120],
                "avg_latency_ms": round(r["avg_latency_ms"] or 0),
            }
            for r in rows
        ],
    }


@router.get("/analytics/feedback")
async def feedback_detail(
    request: Request,
    days:    int  = Query(default=30, ge=1, le=365),
    verdict: str  = Query(default="incorrect"),
    _user:   dict = Depends(require_role("admin")),
):
    """List individual feedback entries — useful for error analysis."""
    pool  = _pool(request)
    since = date.today() - timedelta(days=days)

    rows = await pool.fetch(
        """
        SELECT
            f.id,
            f.verdict,
            f.clinician_note,
            f.actual_diagnosis,
            f.created_at,
            t.query,
            t.response->'differential'->0->>'disease_name' AS top1_disease
        FROM   feedback f
        JOIN   turns    t ON t.id = f.turn_id
        WHERE  f.created_at >= $1
          AND  f.verdict     = $2
        ORDER BY f.created_at DESC
        LIMIT 100
        """,
        since, verdict,
    )

    return [
        {
            "id":               str(r["id"]),
            "verdict":          r["verdict"],
            "clinician_note":   r["clinician_note"],
            "actual_diagnosis": r["actual_diagnosis"],
            "top1_disease":     r["top1_disease"],
            "query":            (r["query"] or "")[:200],
            "created_at":       r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.get("/analytics/eval-reports")
async def list_eval_reports(
    request: Request,
    _user:   dict = Depends(require_role("admin")),
):
    """Return the latest eval report from the eval_reports/ directory."""
    import os, json as _json
    from pathlib import Path

    report_dir = Path(os.getenv("EVAL_REPORTS_DIR", "eval_reports"))
    if not report_dir.exists():
        return {"reports": []}

    reports = sorted(report_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    result  = []

    for rpath in reports[:10]:
        try:
            data = _json.loads(rpath.read_text())
            result.append({
                "run_id":            data.get("run_id"),
                "timestamp":         data.get("timestamp"),
                "model_version":     data.get("model_version"),
                "total_cases":       data.get("total_cases"),
                "top1_accuracy":     data.get("top1_accuracy"),
                "top3_accuracy":     data.get("top3_accuracy"),
                "citation_rate":     data.get("citation_rate_mean"),
                "guideline_adherence": data.get("guideline_adherence"),
                "hallucination_rate": data.get("hallucination_rate"),
                "p95_latency_ms":    data.get("p95_latency_ms"),
            })
        except Exception:
            continue

    return {"reports": result}

