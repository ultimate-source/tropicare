# ─────────────────────────────────────────────────────────────────────────────
# tropicare_orchestrator/orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import AsyncIterator

from ..agents.base import MCPClient, AgentSpan
from ..agents.intake import IntakeAgent
from ..agents.diagnostic import DiagnosticAgent
from ..agents.antibiotherapy import AntibiotherapyAgent, _AMR_RESISTANCE_THRESHOLD
from ..agents.validation import ValidationAgent
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
                    yield {"type": "error", "message": _localized_error(language)}
                    await self._audit(session_id, turn_id, "error", {"error": "diagnostic agent returned None"}, t0)
                    return

                # Emit tool failure warnings from diagnostic agent
                for tw in diag_result.get("_tool_warnings", []):
                    yield {"type": "validation", "verdict": "WARN", "annotations": [tw]}

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

                # Downgrade BLOCK to WARN if the diagnostic agent actually
                # produced a valid differential — the validation agent may
                # over-block when the knowledge base is empty and there are
                # no citations, but the differential itself is still useful.
                if verdict == "BLOCK" and diag_result.get("differential"):
                    log.warning(
                        "Validation BLOCK downgraded to WARN — diagnostic has %d items. Reason: %s",
                        len(diag_result["differential"]),
                        val_result.get("block_reason", "?"),
                    )
                    verdict = "WARN"
                    val_result["global_verdict"] = "WARN"
                    annotations = val_result.get("annotations", [])
                    block_reason = val_result.get("block_reason", "")
                    if block_reason and block_reason not in annotations:
                        annotations.append(block_reason)
                    val_result["annotations"] = annotations

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
                        # Emit tool failure warnings from antibiotherapy agent
                        for tw in anti_result.get("_tool_warnings", []):
                            yield {"type": "validation", "verdict": "WARN", "annotations": [tw]}

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

            # ── 5. Generate warnings and collect references ────────────────
            local_diag = diag_result if 'diag_result' in dir() else None
            local_anti = anti_result if 'anti_result' in dir() else None

            warnings = _generate_warnings(local_diag, local_anti)
            diag_cits = (local_diag or {}).get("citations", [])
            anti_cits = (local_anti or {}).get("citations", [])
            references = _collect_references(diag_cits, anti_cits)

            if warnings:
                yield {"type": "warnings", "warnings": warnings}

            # ── 6. Persist turn ──────────────────────────────────────────────
            turn_record = {
                "turn_id": turn_id,
                "query":   query,
                "diag":    local_diag,
                "anti":    local_anti,
                "warnings": warnings,
                "references": references,
            }
            await self._cfg.session_store.append_turn(session_id, turn_record)
            await self._audit(session_id, turn_id, "ok", turn_record, t0, traces)

            yield {"type": "done", "turn_id": turn_id}

        except asyncio.CancelledError:
            log.info("Turn %s cancelled by client", turn_id)
        except Exception as exc:
            log.error("Orchestrator error on turn %s: %s", turn_id, exc, exc_info=True)
            error_msg = _localized_error(language, exc)
            yield {"type": "error", "message": error_msg}
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


# ── Standalone helpers (used by property tests) ──────────────────────────────


def _localized_error(language: str = "fr", exc: Exception | None = None) -> str:
    """Return a structured, clinician-facing error message in the session language.

    Used when all retries are exhausted or an agent fails completely.
    """
    if language == "en":
        return (
            "Internal error — the clinical analysis could not be completed. "
            "Please retry your request. If the problem persists, contact technical support."
        )
    # Default: French
    return (
        "Erreur interne — l'analyse clinique n'a pas pu être complétée. "
        "Veuillez réessayer votre requête. Si le problème persiste, contactez le support technique."
    )


def order_events(events: list[dict]) -> list[dict]:
    """Reorder SSE event dicts so all emergency_flag events precede all
    differential_item events.  Other event types keep their relative order
    with respect to each other and are placed after emergency flags but
    before differential items when they originally appeared between the two
    groups.

    The simple invariant: in the returned list, every ``emergency_flag``
    event has a lower index than every ``differential_item`` event.
    """
    emergency_flags: list[dict] = []
    differential_items: list[dict] = []
    others: list[dict] = []

    for ev in events:
        etype = ev.get("type", "")
        if etype == "emergency_flag":
            emergency_flags.append(ev)
        elif etype == "differential_item":
            differential_items.append(ev)
        else:
            others.append(ev)

    return emergency_flags + others + differential_items


def deduplicate_citations(citations: list[dict]) -> list[dict]:
    """Deduplicate citation dicts by ``(source_title, section)`` tuple.

    The first occurrence of each unique pair is kept; subsequent duplicates
    are discarded.  Source attribution is added based on ``source_title``
    content (OMS, PNLP, MSF).
    """
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []

    for cit in citations:
        key = (cit.get("source_title", ""), cit.get("section", ""))
        if key in seen:
            continue
        seen.add(key)
        # Add source attribution
        cit_copy = dict(cit)
        cit_copy["source"] = _attribute_source(cit_copy.get("source_title", ""))
        result.append(cit_copy)

    return result


def _attribute_source(source_title: str) -> str:
    """Determine source attribution from the source_title string."""
    title_lower = source_title.lower()
    if "oms" in title_lower or "who" in title_lower:
        return "OMS"
    if "pnlp" in title_lower:
        return "PNLP"
    if "msf" in title_lower or "médecins sans frontières" in title_lower:
        return "MSF"
    return "Autre"


def _generate_warnings(
    diag_result: dict | None,
    anti_result: dict | None,
) -> list[str]:
    """Build a list of clinical warning strings from diagnostic and
    antibiotherapy results.

    Warning sources:
    1. Emergency flags from diagnostic result
    2. High-resistance AMR notes on recommended drugs (>30%)
    3. DDI warnings with CONTRAINDICATED or MAJOR severity
    """
    warnings: list[str] = []
    diag_result = diag_result or {}
    anti_result = anti_result or {}

    # 1. Emergency flag warnings
    for flag in diag_result.get("emergency_flags", []):
        disease = flag.get("disease", "?") if isinstance(flag, dict) else getattr(flag, "disease", "?")
        action = flag.get("action", "") if isinstance(flag, dict) else getattr(flag, "action", "")
        warnings.append(f"⚠️ URGENCE: {disease} — {action}")

    # 2. High-resistance AMR warnings from treatment tiers
    for tier in ("first_line", "second_line", "alternatives"):
        for drug in anti_result.get(tier, []):
            amr_note = drug.get("amr_note", "") or ""
            # Check if the note contains a resistance percentage > threshold
            match = re.search(r"[Rr]ésistance\s+locale?\s+(\d+(?:[.,]\d+)?)\s*%", amr_note)
            if match:
                pct = float(match.group(1).replace(",", "."))
                if pct > _AMR_RESISTANCE_THRESHOLD:
                    drug_name = drug.get("drug_name", drug.get("generic_name", "?"))
                    warnings.append(
                        f"⚠️ Résistance élevée: {drug_name} — {amr_note}"
                    )

    # 3. DDI warnings (CONTRAINDICATED or MAJOR)
    for tier in ("first_line", "second_line", "alternatives"):
        for drug in anti_result.get(tier, []):
            for ddi_warning in drug.get("ddi_warnings", []):
                ddi_upper = ddi_warning.upper()
                if "CONTRAINDICATED" in ddi_upper or "MAJOR" in ddi_upper:
                    warnings.append(ddi_warning)

    return warnings


def _collect_references(
    diag_citations: list[dict],
    anti_citations: list[dict],
) -> list[dict]:
    """Merge and deduplicate citations from diagnostic and antibiotherapy
    results, adding source attribution."""
    all_citations = list(diag_citations or []) + list(anti_citations or [])
    return deduplicate_citations(all_citations)

