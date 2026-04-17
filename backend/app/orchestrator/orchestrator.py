# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

from ..agents.base import MCPClient, AgentSpan
from ..agents.intake import IntakeAgent
from ..agents.diagnostic import DiagnosticAgent
from ..agents.antibiotherapy import AntibiotherapyAgent
from ..agents.validation import ValidationAgent
from ..models.schemas import PatientContext, ConsultationResponse
from .session import SessionStore
from .audit import AuditLogger

log = logging.getLogger("tropicare.orchestrator")


class OrchestratorConfig:
    def __init__(
        self,
        api_key:       str,
        mcp_url:       str,
        session_store: SessionStore,
        audit_logger:  AuditLogger,
        model:         str = "claude-sonnet-4-20250514",
    ):
        self.api_key       = api_key
        self.mcp_url       = mcp_url
        self.session_store = session_store
        self.audit_logger  = audit_logger
        self.model         = model


class Orchestrator:
    """
    Routes clinical queries through the agent pipeline and streams
    SSE events back to the gateway.

    Execution plans:
      auto        →  Intake (if needed) → Diagnostic → [Antibiotherapy] → Validation
      diagnostic  →  Diagnostic → Validation
      antibiotherapy → Antibiotherapy → Validation
    """

    def __init__(self, cfg: OrchestratorConfig):
        self._cfg = cfg
        mcp = MCPClient(cfg.mcp_url)

        self._intake  = IntakeAgent(cfg.api_key, mcp, model=cfg.model)
        self._diag    = DiagnosticAgent(cfg.api_key, mcp, model=cfg.model)
        self._anti    = AntibiotherapyAgent(cfg.api_key, mcp, model=cfg.model)
        self._val     = ValidationAgent(cfg.api_key, mcp, model=cfg.model)

    # ── Public: streaming entry point ─────────────────────────────────────────

    async def handle_turn(
        self,
        session_id:   str,
        turn_id:      str,
        query:        str,
        mode:         str = "auto",
        language:     str = "fr",
    ) -> AsyncIterator[dict]:
        """
        Yields SSE event dicts. Caller serialises to `data: {json}\n\n`.
        """
        t0     = time.monotonic()
        state  = await self._cfg.session_store.get(session_id)
        traces: list[AgentSpan] = []

        try:
            # ── 1. Intake ────────────────────────────────────────────────────
            yield {"type": "thinking", "content": "Analyse du contexte patient…"}

            patient_ctx = state.get("patient_context", {})
            if not patient_ctx or _needs_intake(query, patient_ctx):
                intake_result, intake_span = await self._intake.run(
                    free_text=query,
                    prior_context=patient_ctx or None,
                )
                traces.append(intake_span)

                if intake_result:
                    extracted = intake_result.get("extracted", {})
                    if extracted:
                        patient_ctx = {**patient_ctx, **extracted}
                        await self._cfg.session_store.patch(session_id, patient_context=patient_ctx)

                    # Surface clarifying questions immediately
                    for q in intake_result.get("clarifying_questions", []):
                        yield {"type": "clarifying_question", "content": q}

                    if intake_result.get("clarifying_questions"):
                        # Don't continue to diagnosis yet — wait for clinician reply
                        yield {"type": "done", "turn_id": turn_id, "partial": True}
                        await self._audit(session_id, turn_id, "intake_clarify", intake_result, t0)
                        return

            # ── 2. Emergency pre-check ───────────────────────────────────────
            if _is_emergency_query(query, patient_ctx):
                yield {
                    "type": "thinking",
                    "content": "⚠ Vérification des critères d'urgence…",
                }

            # ── 3. Diagnostic ────────────────────────────────────────────────
            if mode in ("auto", "diagnostic"):
                yield {"type": "thinking", "content": "Raisonnement diagnostique en cours…"}

                history = state.get("conversation_history", [])
                diag_result, diag_span = await self._diag.run(
                    patient_context=patient_ctx,
                    query=query,
                    conversation_history=history,
                )
                traces.append(diag_span)

                if diag_result is None:
                    yield {"type": "error", "message": "Erreur agent diagnostique — résultat partiel"}
                    diag_result = {}

                # Emit emergency flags first
                for flag in diag_result.get("emergency_flags", []):
                    yield {"type": "emergency_flag", "flag": flag}

                # Emit differential items one by one (progressive rendering)
                for item in diag_result.get("differential", []):
                    yield {"type": "differential_item", "item": item}
                    await asyncio.sleep(0)  # yield control to event loop

                # Emit citations
                for cit in diag_result.get("citations", []):
                    yield {"type": "citation", "citation": cit}

                # Validate diagnostic output
                val_result = await self._val.run_validation(
                    agent_output=diag_result,
                    agent_type="diagnostic",
                    source_chunks=[],  # chunks already embedded in diag_result
                    session_language=language,
                    output_type="diagnostic",
                )
                verdict = val_result.get("global_verdict", "PASS")

                if verdict == "BLOCK":
                    yield {
                        "type": "error",
                        "message": f"Réponse bloquée par validation : {val_result.get('block_reason', '?')}",
                    }
                    await self._audit(session_id, turn_id, "blocked", val_result, t0)
                    return

                if val_result.get("annotations"):
                    yield {"type": "validation", "verdict": verdict, "annotations": val_result["annotations"]}

                # ── 4. Antibiotherapy (if top diagnosis has confidence ≥ 0.70) ──
                top1 = diag_result.get("differential", [{}])[0] if diag_result.get("differential") else {}
                should_treat = (
                    mode == "antibiotherapy"
                    or (mode == "auto" and top1.get("confidence", 0) >= 0.70)
                )

                if should_treat and top1:
                    yield {"type": "thinking", "content": "Élaboration du plan thérapeutique…"}

                    anti_result, anti_span = await self._anti.run(
                        patient_context=patient_ctx,
                        confirmed_diagnosis=top1.get("disease_name", ""),
                        icd11_code=top1.get("icd11_code", ""),
                        diagnostic_confidence=top1.get("confidence", 0.0),
                    )
                    traces.append(anti_span)

                    if anti_result:
                        # Validate antibiotherapy
                        anti_val = await self._val.run_validation(
                            agent_output=anti_result,
                            agent_type="antibiotherapy",
                            source_chunks=[],
                            session_language=language,
                            output_type="antibiotherapy",
                        )
                        if anti_val.get("global_verdict") != "BLOCK":
                            for tier in ("first_line", "second_line", "alternatives"):
                                for drug in anti_result.get(tier, []):
                                    yield {"type": "treatment_line", "tier": tier, "drug": drug}
                                    await asyncio.sleep(0)

                            # Antibiotherapy citations (may overlap with diag citations)
                            for cit in anti_result.get("citations", []):
                                yield {"type": "citation", "citation": cit}

                            if anti_val.get("annotations"):
                                yield {
                                    "type": "validation",
                                    "verdict": anti_val["global_verdict"],
                                    "annotations": anti_val["annotations"],
                                }

            # ── 5. Persist turn ──────────────────────────────────────────────
            turn_record = {
                "turn_id": turn_id,
                "query":   query,
                "diag":    diag_result if 'diag_result' in dir() else None,
                "anti":    anti_result if 'anti_result' in dir() else None,
            }
            await self._cfg.session_store.append_turn(session_id, turn_record)
            await self._audit(session_id, turn_id, "ok", turn_record, t0, traces)

            yield {"type": "done", "turn_id": turn_id}

        except asyncio.CancelledError:
            log.info("Turn %s cancelled by client", turn_id)
        except Exception as exc:
            log.error("Orchestrator error on turn %s: %s", turn_id, exc, exc_info=True)
            yield {"type": "error", "message": "Erreur interne — veuillez réessayer"}
            await self._audit(session_id, turn_id, "error", {"error": str(exc)}, t0)

    # ── Antibiotherapy-only mode ──────────────────────────────────────────────

    async def handle_antibiotherapy(
        self,
        session_id: str,
        turn_id:    str,
        diagnosis:  str,
        icd11:      str,
        confidence: float,
        language:   str = "fr",
    ) -> AsyncIterator[dict]:
        state = await self._cfg.session_store.get(session_id)
        ctx   = state.get("patient_context", {})
        t0    = time.monotonic()

        yield {"type": "thinking", "content": "Vérification formulaire CAME et données AMR…"}

        anti_result, anti_span = await self._anti.run(
            patient_context=ctx,
            confirmed_diagnosis=diagnosis,
            icd11_code=icd11,
            diagnostic_confidence=confidence,
        )

        if anti_result:
            for tier in ("first_line", "second_line", "alternatives"):
                for drug in anti_result.get(tier, []):
                    yield {"type": "treatment_line", "tier": tier, "drug": drug}
            for cit in anti_result.get("citations", []):
                yield {"type": "citation", "citation": cit}

        yield {"type": "done", "turn_id": turn_id}
        await self._audit(session_id, turn_id, "antibiotherapy_only", anti_result or {}, t0)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _audit(
        self,
        session_id: str,
        turn_id:    str,
        event_type: str,
        payload:    dict,
        t0:         float,
        traces:     list[AgentSpan] | None = None,
    ) -> None:
        try:
            await self._cfg.audit_logger.log(
                session_id=session_id,
                turn_id=turn_id,
                event_type=event_type,
                payload={
                    **payload,
                    "_latency_ms": int((time.monotonic() - t0) * 1000),
                    "_traces": [t.model_dump() for t in (traces or [])],
                },
            )
        except Exception as e:
            log.warning("Audit log failed: %s", e)


def _needs_intake(query: str, patient_ctx: dict) -> bool:
    """True if mandatory context fields are missing."""
    required = ["age_years", "sex", "chief_complaint", "region"]
    return any(patient_ctx.get(f) is None for f in required)


def _is_emergency_query(query: str, ctx: dict) -> bool:
    emergency_terms = [
        "inconscient", "convulsion", "choc", "détresse", "urgence",
        "inconscience", "purpura", "hémorragie", "dyspnée sévère",
    ]
    text = (query + " ".join(s.get("text", "") for s in ctx.get("symptoms", []))).lower()
    return any(t in text for t in emergency_terms)

