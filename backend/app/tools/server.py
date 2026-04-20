
# All tools are MCP-compliant async functions registered via fastmcp.

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import date
from enum import Enum
from functools import lru_cache
from typing import Any

import httpx
import numpy as np
from fastmcp import FastMCP
from opentelemetry import trace
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

from .config import settings
from .db import get_mongo_db, get_postgres_pool, get_redis
from .embedder import embed_text

log = logging.getLogger(__name__)
tracer = trace.get_tracer("tropicare.tools")

mcp = FastMCP(
    name="tropicare-tools",
    version="1.0.0",
    description="Clinical knowledge tools for tropical disease RAG — Togo/West Africa",
)

# ─────────────────────────────────────────────────────────────
# Shared clients (lazy singletons)
# ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _cross_encoder() -> CrossEncoder:
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# ─────────────────────────────────────────────────────────────
# Shared types (returned by multiple tools)
# ─────────────────────────────────────────────────────────────

class Chunk(BaseModel):
    chunk_id: str
    chunk_text: str
    source_title: str
    source_version: str
    source_date: str
    section: str
    page: int
    language: str
    disease_tags: list[str]
    drug_tags: list[str]
    content_type: str
    score: float

class Citation(BaseModel):
    ref_id: int
    source_title: str
    section: str
    page: int
    version: str
    date: str
    chunk_snippet: str   # ≤ 120 chars for display

class FormularyResult(BaseModel):
    drug_name: str
    generic_name: str
    available: bool
    atc_code: str | None
    dosage_forms: list[str]
    notes: str | None

class AMRProfile(BaseModel):
    drug: str
    pathogen: str
    region: str
    resistance_pct: float | None
    data_source: str
    year: int | None
    confidence: str   # "high" | "medium" | "low" | "no_data"
    recommendation: str

class DDIWarning(BaseModel):
    drug_a: str
    drug_b: str
    severity: str   # "contraindicated" | "major" | "moderate" | "minor"
    mechanism: str
    clinical_effect: str
    management: str

class SafetyClass(BaseModel):
    drug: str
    pregnancy_category: str | None   # A/B/C/D/X or WHO equiv.
    lactation_safe: bool | None
    trimester_notes: str | None
    source: str

class EpidPrior(BaseModel):
    region: str
    month: int
    disease_priors: dict[str, float]   # icd11_code → prior (0–1)
    outbreak_alerts: list[str]
    source: str

# ─────────────────────────────────────────────────────────────
# TOOL 1 — vector-search
# ─────────────────────────────────────────────────────────────

class VectorSearchInput(BaseModel):
    query: str = Field(..., description="Clinical query in French or English")
    k: int = Field(20, ge=1, le=50)
    disease_tags: list[str] | None = Field(None, description="ICD-11 codes to filter by")
    content_type: str | None = Field(None, description="guideline|formulary|amr_data|epidemiology")
    language: str | None = Field(None, description="fr|en — if None, search all")

@mcp.tool(description="Dense ANN search in the TropiCare MongoDB Atlas Vector Search knowledge base")
async def vector_search(input: VectorSearchInput) -> list[Chunk]:
    with tracer.start_as_current_span("tool.vector_search") as span:
        span.set_attribute("query", input.query[:120])
        span.set_attribute("k", input.k)

        vec = await embed_text(input.query)

        # Build pre-filter for $vectorSearch
        vs_filter: dict[str, Any] = {"superseded": {"$eq": False}}
        if input.disease_tags:
            vs_filter["disease_tags"] = {"$in": input.disease_tags}
        if input.content_type:
            vs_filter["content_type"] = {"$eq": input.content_type}
        if input.language:
            vs_filter["language"] = {"$eq": input.language}

        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": vec,
                    "numCandidates": input.k * 10,
                    "limit": input.k,
                    "filter": vs_filter,
                }
            },
            {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        ]

        db = await get_mongo_db()
        collection = db["kb_vectors"]
        results = await collection.aggregate(pipeline).to_list(length=input.k)

        chunks = [
            Chunk(
                chunk_id=str(r.get("chunk_id", r.get("_id", ""))),
                score=r.get("score", 0.0),
                chunk_text=r.get("chunk_text", ""),
                source_title=r.get("source_title", ""),
                source_version=r.get("source_version", ""),
                source_date=str(r.get("source_date", "")),
                section=r.get("section", ""),
                page=r.get("page", 0),
                language=r.get("language", "fr"),
                disease_tags=r.get("disease_tags", []),
                drug_tags=r.get("drug_tags", []),
                content_type=r.get("content_type", "guideline"),
            )
            for r in results
        ]
        span.set_attribute("results_count", len(chunks))
        return chunks

# ─────────────────────────────────────────────────────────────
# TOOL 2 — bm25-search
# ─────────────────────────────────────────────────────────────

class BM25SearchInput(BaseModel):
    query: str
    k: int = Field(20, ge=1, le=50)
    language: str | None = None

@mcp.tool(description="BM25 keyword retrieval from PostgreSQL full-text index")
async def bm25_search(input: BM25SearchInput) -> list[Chunk]:
    with tracer.start_as_current_span("tool.bm25_search"):
        pool = await get_postgres_pool()
        lang_filter = "AND language = $3" if input.language else ""
        params: list[Any] = [input.query, input.k]
        if input.language:
            params.append(input.language)

        rows = await pool.fetch(
            f"""
            SELECT
                c.id, c.chunk_text, c.section, c.page, c.language,
                c.disease_tags, c.drug_tags, c.content_type,
                d.title AS source_title, d.version AS source_version,
                d.published_date::text AS source_date,
                ts_rank_cd(to_tsvector('french', c.chunk_text),
                           plainto_tsquery('french', $1)) AS score
            FROM   kb_chunks c
            JOIN   kb_documents d ON c.document_id = d.id
            WHERE  d.superseded_by IS NULL
              AND  to_tsvector('french', c.chunk_text)
                   @@ plainto_tsquery('french', $1)
            {lang_filter}
            ORDER  BY score DESC
            LIMIT  $2
            """,
            *params,
        )
        return [
            Chunk(
                chunk_id=str(r["id"]),
                chunk_text=r["chunk_text"],
                source_title=r["source_title"],
                source_version=r["source_version"] or "",
                source_date=r["source_date"] or "",
                section=r["section"] or "",
                page=r["page"] or 0,
                language=r["language"],
                disease_tags=r["disease_tags"] or [],
                drug_tags=r["drug_tags"] or [],
                content_type=r["content_type"],
                score=float(r["score"]),
            )
            for r in rows
        ]

# ─────────────────────────────────────────────────────────────
# TOOL 3 — cross-encode-rerank
# ─────────────────────────────────────────────────────────────

class RerankInput(BaseModel):
    query: str
    chunks: list[Chunk]
    top_n: int = Field(8, ge=1, le=30)

@mcp.tool(description="Rerank a merged chunk list using ms-marco cross-encoder")
async def cross_encode_rerank(input: RerankInput) -> list[Chunk]:
    with tracer.start_as_current_span("tool.rerank") as span:
        if not input.chunks:
            return []
        encoder = _cross_encoder()
        pairs = [(input.query, c.chunk_text) for c in input.chunks]
        # Run in thread pool — cross encoder is CPU-bound
        scores = await asyncio.get_event_loop().run_in_executor(
            None, encoder.predict, pairs
        )
        ranked = sorted(
            zip(input.chunks, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        result = []
        for chunk, score in ranked[: input.top_n]:
            chunk.score = float(score)
            result.append(chunk)
        span.set_attribute("input_count", len(input.chunks))
        span.set_attribute("output_count", len(result))
        return result

# ─────────────────────────────────────────────────────────────
# TOOL 4 — epid-calendar (Togo epidemiological priors)
# ─────────────────────────────────────────────────────────────

# Static table — update annually from PNLP / WHO AFRO bulletins
# Keys: ICD-11 codes. Values: 0-1 seasonal prior per (region, month).
_EPID_TABLE: dict[str, dict[str, list[float]]] = {
    # Malaria — P. falciparum — peaks June–October (rainy season)
    "1F40": {
        "Savanes":   [.3,.3,.4,.5,.6,.9,.9,.9,.8,.6,.4,.3],
        "Kara":      [.3,.3,.4,.5,.6,.8,.9,.9,.8,.6,.4,.3],
        "Centrale":  [.3,.3,.4,.5,.6,.7,.8,.8,.7,.5,.4,.3],
        "Plateaux":  [.3,.3,.4,.5,.6,.7,.7,.8,.7,.5,.4,.3],
        "Maritime":  [.3,.3,.4,.5,.5,.6,.7,.7,.6,.5,.4,.3],
    },
    # Meningococcal meningitis — dry season peak Jan–April
    "1C1A": {
        "Savanes":   [.9,.8,.7,.6,.3,.2,.2,.2,.3,.4,.6,.8],
        "Kara":      [.8,.7,.6,.5,.3,.2,.2,.2,.3,.4,.5,.7],
        "Centrale":  [.5,.4,.4,.3,.2,.1,.1,.1,.2,.2,.4,.5],
        "Plateaux":  [.3,.3,.3,.2,.2,.1,.1,.1,.2,.2,.3,.3],
        "Maritime":  [.2,.2,.2,.2,.1,.1,.1,.1,.1,.2,.2,.2],
    },
    # Cholera — rainy season risk
    "1A00": {
        "Maritime":  [.2,.2,.2,.3,.4,.6,.7,.7,.6,.4,.3,.2],
        "Plateaux":  [.2,.2,.2,.3,.4,.5,.6,.6,.5,.3,.2,.2],
        "Centrale":  [.1,.1,.1,.2,.3,.4,.5,.5,.4,.2,.2,.1],
        "Kara":      [.1,.1,.1,.2,.3,.4,.4,.4,.3,.2,.1,.1],
        "Savanes":   [.1,.1,.1,.2,.3,.4,.4,.4,.3,.2,.1,.1],
    },
    # Typhoid — endemic, slight rainy-season peak
    "1A07": {
        "_all": [.4,.4,.4,.4,.5,.6,.6,.6,.6,.5,.4,.4],
    },
    # Dengue — rainy season
    "1D2Z": {
        "_all": [.2,.2,.2,.3,.4,.6,.7,.7,.6,.4,.3,.2],
    },
    # Lassa fever — dry season
    "1D6Y": {
        "_all": [.7,.6,.5,.4,.3,.2,.2,.2,.2,.3,.5,.7],
    },
}

_OUTBREAK_ALERTS: dict[str, dict[int, list[str]]] = {
    # region → month → active outbreak ICD-11 codes (populated from AFRO bulletins)
}

class EpidCalendarInput(BaseModel):
    region: str = Field(..., description="Togo region: Maritime|Plateaux|Centrale|Kara|Savanes")
    month: int = Field(..., ge=1, le=12)

@mcp.tool(description="Returns seasonal disease priors and outbreak alerts for a Togo region+month")
async def epid_calendar(input: EpidCalendarInput) -> EpidPrior:
    with tracer.start_as_current_span("tool.epid_calendar"):
        priors: dict[str, float] = {}
        for icd, regions in _EPID_TABLE.items():
            arr = regions.get(input.region) or regions.get("_all")
            if arr:
                priors[icd] = arr[input.month - 1]

        alerts = (
            _OUTBREAK_ALERTS
            .get(input.region, {})
            .get(input.month, [])
        )
        return EpidPrior(
            region=input.region,
            month=input.month,
            disease_priors=priors,
            outbreak_alerts=alerts,
            source="PNLP Togo / WHO AFRO — updated 2024",
        )

# ─────────────────────────────────────────────────────────────
# TOOL 5 — formulary-lookup (CAME Togo)
# ─────────────────────────────────────────────────────────────

class FormularyLookupInput(BaseModel):
    drug_name: str = Field(..., description="Generic or brand name in French or English")

@mcp.tool(description="Check drug availability in the CAME Togo national formulary")
async def formulary_lookup(input: FormularyLookupInput) -> FormularyResult:
    with tracer.start_as_current_span("tool.formulary_lookup"):
        redis = await get_redis()
        cache_key = f"formulary:{hashlib.md5(input.drug_name.lower().encode()).hexdigest()}"
        cached = await redis.get(cache_key)
        if cached:
            return FormularyResult(**json.loads(cached))

        pool = await get_postgres_pool()
        row = await pool.fetchrow(
            """
            SELECT generic_name, brand_names, atc_code, available,
                   dosage_forms, notes
            FROM   came_formulary
            WHERE  lower(generic_name) = lower($1)
               OR  lower($1) = ANY(SELECT lower(b) FROM unnest(brand_names) b)
            LIMIT 1
            """,
            input.drug_name,
        )
        if row is None:
            result = FormularyResult(
                drug_name=input.drug_name,
                generic_name=input.drug_name,
                available=False,
                atc_code=None,
                dosage_forms=[],
                notes="Non répertorié dans la liste CAME — vérifier disponibilité locale",
            )
        else:
            result = FormularyResult(
                drug_name=input.drug_name,
                generic_name=row["generic_name"],
                available=row["available"],
                atc_code=row["atc_code"],
                dosage_forms=row["dosage_forms"] or [],
                notes=row["notes"],
            )

        await redis.setex(cache_key, 3600 * 6, result.model_dump_json())
        return result

# ─────────────────────────────────────────────────────────────
# TOOL 6 — amr-lookup
# ─────────────────────────────────────────────────────────────

class AMRLookupInput(BaseModel):
    drug: str
    pathogen: str = Field(..., description="Pathogen name or WHONET code")
    region: str = Field("Togo", description="Togo | West Africa")

@mcp.tool(description="Return AMR resistance data for a drug-pathogen pair in Togo/West Africa")
async def amr_lookup(input: AMRLookupInput) -> AMRProfile:
    with tracer.start_as_current_span("tool.amr_lookup"):
        pool = await get_postgres_pool()
        row = await pool.fetchrow(
            """
            SELECT drug, pathogen, region, resistance_pct, data_source,
                   year, confidence
            FROM   amr_data
            WHERE  lower(drug) = lower($1)
              AND  lower(pathogen) LIKE lower($2)
              AND  lower(region) = lower($3)
            ORDER BY year DESC
            LIMIT 1
            """,
            input.drug, f"%{input.pathogen}%", input.region,
        )

        if row is None and input.region == "Togo":
            # Fallback to West Africa regional data
            row = await pool.fetchrow(
                """
                SELECT drug, pathogen, region, resistance_pct, data_source,
                       year, confidence
                FROM   amr_data
                WHERE  lower(drug) = lower($1)
                  AND  lower(pathogen) LIKE lower($2)
                  AND  lower(region) = 'west africa'
                ORDER BY year DESC LIMIT 1
                """,
                input.drug, f"%{input.pathogen}%",
            )

        if row is None:
            return AMRProfile(
                drug=input.drug, pathogen=input.pathogen, region=input.region,
                resistance_pct=None, data_source="Aucune donnée disponible",
                year=None, confidence="no_data",
                recommendation="Données AMR indisponibles — utiliser protocole empirique PNLP",
            )

        pct = row["resistance_pct"]
        if pct is None:
            rec = "Données insuffisantes"
        elif pct >= 0.30:
            rec = f"Résistance élevée ({pct:.0%}) — éviter en première intention"
        elif pct >= 0.15:
            rec = f"Résistance modérée ({pct:.0%}) — utiliser avec antibiogramme"
        else:
            rec = f"Résistance faible ({pct:.0%}) — acceptable en première intention"

        return AMRProfile(
            drug=row["drug"], pathogen=row["pathogen"], region=row["region"],
            resistance_pct=pct, data_source=row["data_source"],
            year=row["year"], confidence=row["confidence"],
            recommendation=rec,
        )

# ─────────────────────────────────────────────────────────────
# TOOL 7 — drug-ddi-check
# ─────────────────────────────────────────────────────────────

class DDICheckInput(BaseModel):
    drug_list: list[str] = Field(..., min_length=2, description="List of generic drug names")

@mcp.tool(description="Check pairwise drug-drug interactions for a patient's medication list")
async def drug_ddi_check(input: DDICheckInput) -> list[DDIWarning]:
    with tracer.start_as_current_span("tool.ddi_check") as span:
        pool = await get_postgres_pool()
        normalized = [d.strip().lower() for d in input.drug_list]
        # Generate all pairs
        pairs = [
            (normalized[i], normalized[j])
            for i in range(len(normalized))
            for j in range(i + 1, len(normalized))
        ]
        if not pairs:
            return []

        warnings: list[DDIWarning] = []
        for drug_a, drug_b in pairs:
            row = await pool.fetchrow(
                """
                SELECT drug_a, drug_b, severity, mechanism,
                       clinical_effect, management
                FROM   ddi_interactions
                WHERE (lower(drug_a) = $1 AND lower(drug_b) = $2)
                   OR (lower(drug_a) = $2 AND lower(drug_b) = $1)
                ORDER BY
                  CASE severity
                    WHEN 'contraindicated' THEN 0
                    WHEN 'major'           THEN 1
                    WHEN 'moderate'        THEN 2
                    ELSE                        3
                  END
                LIMIT 1
                """,
                drug_a, drug_b,
            )
            if row:
                warnings.append(DDIWarning(**dict(row)))

        span.set_attribute("pairs_checked", len(pairs))
        span.set_attribute("warnings_found", len(warnings))
        return sorted(
            warnings,
            key=lambda w: ["contraindicated", "major", "moderate", "minor"].index(w.severity),
        )

# ─────────────────────────────────────────────────────────────
# TOOL 8 — safety-classifier (pregnancy / lactation)
# ─────────────────────────────────────────────────────────────

class SafetyClassInput(BaseModel):
    drug: str
    trimester: int | None = Field(None, ge=1, le=3)

@mcp.tool(description="Return pregnancy and lactation safety classification for a drug")
async def safety_classifier(input: SafetyClassInput) -> SafetyClass:
    with tracer.start_as_current_span("tool.safety_classifier"):
        pool = await get_postgres_pool()
        row = await pool.fetchrow(
            """
            SELECT drug, pregnancy_category, lactation_safe,
                   t1_notes, t2_notes, t3_notes, source
            FROM   drug_safety
            WHERE  lower(drug) = lower($1)
            LIMIT 1
            """,
            input.drug,
        )
        if row is None:
            return SafetyClass(
                drug=input.drug,
                pregnancy_category=None,
                lactation_safe=None,
                trimester_notes="Données non disponibles — consulter pharmacien",
                source="Aucune donnée",
            )

        notes_map = {1: row["t1_notes"], 2: row["t2_notes"], 3: row["t3_notes"]}
        trimester_notes = notes_map.get(input.trimester) if input.trimester else None

        return SafetyClass(
            drug=row["drug"],
            pregnancy_category=row["pregnancy_category"],
            lactation_safe=row["lactation_safe"],
            trimester_notes=trimester_notes,
            source=row["source"],
        )

# ─────────────────────────────────────────────────────────────
# TOOL 9 — symptom-extractor
# ─────────────────────────────────────────────────────────────

class ClinicalEntity(BaseModel):
    text: str           # raw text from clinician
    normalized: str     # preferred term (French)
    snomed_code: str | None
    category: str       # symptom|sign|lab_finding|vital_sign

class SymptomExtractorInput(BaseModel):
    free_text: str
    language: str = "fr"

# Static dictionary for offline extraction — augmented by Claude-based extraction in agent
_SYMPTOM_DICT: dict[str, tuple[str, str | None]] = {
    "fièvre": ("Fièvre", "386661006"),
    "fever": ("Fièvre", "386661006"),
    "céphalée": ("Céphalée", "25064002"),
    "maux de tête": ("Céphalée", "25064002"),
    "frissons": ("Frissons", "43724002"),
    "vomissements": ("Vomissements", "422400008"),
    "diarrhée": ("Diarrhée", "62315008"),
    "ictère": ("Ictère", "18165001"),
    "raideur nuque": ("Raideur de la nuque", "57676002"),
    "convulsions": ("Convulsions", "91175000"),
    "trouble conscience": ("Altération de la conscience", "419284004"),
    "dysurie": ("Dysurie", "49650001"),
    "hématurie": ("Hématurie", "34436003"),
    "toux": ("Toux", "49727002"),
    "dyspnée": ("Dyspnée", "230145002"),
    "éruption cutanée": ("Éruption cutanée", "271807003"),
    "prurit": ("Prurit", "418290006"),
}

@mcp.tool(description="Extract and normalize clinical entities from free-text clinical notes (French/English)")
async def symptom_extractor(input: SymptomExtractorInput) -> list[ClinicalEntity]:
    with tracer.start_as_current_span("tool.symptom_extractor"):
        text_lower = input.free_text.lower()
        entities: list[ClinicalEntity] = []
        seen: set[str] = set()
        for term, (normalized, snomed) in _SYMPTOM_DICT.items():
            if term in text_lower and normalized not in seen:
                entities.append(ClinicalEntity(
                    text=term, normalized=normalized,
                    snomed_code=snomed, category="symptom",
                ))
                seen.add(normalized)
        return entities

# ─────────────────────────────────────────────────────────────
# TOOL 10 — citation-formatter
# ─────────────────────────────────────────────────────────────

class CitationFormatterInput(BaseModel):
    chunks: list[Chunk]

@mcp.tool(description="Format raw chunk provenance into numbered display citations")
async def citation_formatter(input: CitationFormatterInput) -> list[Citation]:
    citations = []
    for i, c in enumerate(input.chunks, start=1):
        snippet = c.chunk_text[:120].rstrip()
        if len(c.chunk_text) > 120:
            snippet += "…"
        citations.append(Citation(
            ref_id=i,
            source_title=c.source_title,
            section=c.section,
            page=c.page,
            version=c.source_version,
            date=c.source_date,
            chunk_snippet=snippet,
        ))
    return citations

# ─────────────────────────────────────────────────────────────
# TOOL 11 — hybrid-retrieve (convenience composite)
# Combines vector + BM25 + RRF + rerank in one call
# ─────────────────────────────────────────────────────────────

class HybridRetrieveInput(BaseModel):
    query: str
    k: int = Field(8, ge=1, le=20)
    disease_tags: list[str] | None = None
    language: str | None = None

def _rrf(dense: list[Chunk], sparse: list[Chunk], k: int = 60) -> list[Chunk]:
    """Reciprocal Rank Fusion merging two ranked lists."""
    scores: dict[str, float] = {}
    index: dict[str, Chunk] = {}
    for rank, c in enumerate(dense):
        scores[c.chunk_id] = scores.get(c.chunk_id, 0) + 1 / (k + rank + 1)
        index[c.chunk_id] = c
    for rank, c in enumerate(sparse):
        scores[c.chunk_id] = scores.get(c.chunk_id, 0) + 1 / (k + rank + 1)
        index[c.chunk_id] = c
    ranked_ids = sorted(scores, key=scores.__getitem__, reverse=True)
    merged = []
    for cid in ranked_ids:
        chunk = index[cid]
        chunk.score = scores[cid]
        merged.append(chunk)
    return merged

def _hybrid_cache_key(input: HybridRetrieveInput) -> str:
    """Compute a deterministic Redis cache key for hybrid_retrieve parameters."""
    raw = json.dumps(
        {
            "query": input.query,
            "k": input.k,
            "disease_tags": sorted(input.disease_tags) if input.disease_tags else None,
            "language": input.language,
        },
        sort_keys=True,
    )
    return f"hybrid:{hashlib.sha256(raw.encode()).hexdigest()}"


@mcp.tool(description="Full hybrid retrieval pipeline: dense + BM25 + RRF + cross-encoder rerank")
async def hybrid_retrieve(input: HybridRetrieveInput) -> list[Chunk]:
    with tracer.start_as_current_span("tool.hybrid_retrieve") as span:
        # ── Check Redis cache ─────────────────────────────────────
        cache_key = _hybrid_cache_key(input)
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached is not None:
                span.set_attribute("cache_hit", True)
                return [Chunk(**c) for c in json.loads(cached)]
        except Exception:
            log.debug("Redis unavailable for hybrid_retrieve cache lookup — proceeding without cache")

        span.set_attribute("cache_hit", False)

        # ── Attempt dense vector search; fall back to BM25-only if MongoDB is unreachable
        dense: list[Chunk] = []
        vector_fallback = False
        try:
            dense = await vector_search(VectorSearchInput(
                query=input.query, k=20,
                disease_tags=input.disease_tags, language=input.language,
            ))
        except Exception as exc:
            vector_fallback = True
            log.error(
                "MongoDB vector search unreachable — falling back to BM25-only retrieval. "
                "MongoDB URI: %s, error: %s",
                settings.MONGODB_URI,
                exc,
            )
            span.set_attribute("vector_fallback", True)

        sparse = await bm25_search(BM25SearchInput(
            query=input.query, k=20, language=input.language,
        ))

        if vector_fallback:
            # BM25-only path: rerank sparse results directly
            merged = sparse
        else:
            merged = _rrf(dense, sparse)

        reranked = await cross_encode_rerank(RerankInput(
            query=input.query, chunks=merged[:30], top_n=input.k,
        ))

        # Empty KB: annotate when no results found at all
        if not reranked:
            span.set_attribute("empty_kb", True)
            log.warning(
                "hybrid_retrieve returned 0 chunks for query=%r — knowledge base may be empty",
                input.query[:80],
            )

        # ── Store result in Redis cache (1-hour TTL) ──────────────
        try:
            redis = await get_redis()
            await redis.setex(
                cache_key,
                3600,  # 1-hour TTL
                json.dumps([c.model_dump() for c in reranked]),
            )
        except Exception:
            log.debug("Redis unavailable for hybrid_retrieve cache write — skipping")

        span.set_attribute("results_count", len(reranked))
        span.set_attribute("vector_fallback", vector_fallback)
        return reranked

# ─────────────────────────────────────────────────────────────
# Server entry point — lightweight FastAPI wrapper
# ─────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

_app = FastAPI(title="TropiCare MCP Tools", version="1.0.0")

# Collect all registered tool functions by name, along with their input types
_TOOLS: dict[str, Any] = {}
_TOOL_INPUT_TYPES: dict[str, type[BaseModel] | None] = {}

_TOOL_REGISTRY: list[tuple[str, type[BaseModel] | None]] = [
    ("vector_search",       VectorSearchInput),
    ("bm25_search",         BM25SearchInput),
    ("cross_encode_rerank", RerankInput),
    ("epid_calendar",       EpidCalendarInput),
    ("formulary_lookup",    FormularyLookupInput),
    ("amr_lookup",          AMRLookupInput),
    ("drug_ddi_check",      DDICheckInput),
    ("safety_classifier",   SafetyClassInput),
    ("symptom_extractor",   SymptomExtractorInput),
    ("citation_formatter",  CitationFormatterInput),
    ("hybrid_retrieve",     HybridRetrieveInput),
]

for _name, _input_type in _TOOL_REGISTRY:
    _fn = globals().get(_name)
    if _fn is not None:
        _TOOLS[_name] = _fn
        _TOOL_INPUT_TYPES[_name] = _input_type


@_app.get("/health")
async def health():
    return {"status": "ok", "service": "tropicare-tools"}


@_app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    fn = _TOOLS.get(tool_name)
    if fn is None:
        return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=404)
    kwargs = await request.json()
    input_type = _TOOL_INPUT_TYPES.get(tool_name)
    if input_type is not None:
        inp = input_type(**kwargs)
        result = await fn(inp)
    else:
        result = await fn(**kwargs)
    # Serialize result
    if isinstance(result, list):
        return [item.model_dump() if hasattr(item, "model_dump") else item for item in result]
    elif hasattr(result, "model_dump"):
        return result.model_dump()
    else:
        return result


app = _app