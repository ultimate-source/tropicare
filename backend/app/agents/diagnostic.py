# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/diagnostic.py — DiagnosticAgent with full ReAct loop
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import datetime
import json
import logging
import re as _re
from typing import Any

from pydantic import ValidationError

from .base import BaseAgent, MCPClient
from .prompts import (
    DIAGNOSTIC_SYSTEM, DIAGNOSTIC_REACT_PROMPT, DIAGNOSTIC_REFINE_PROMPT,
    format_patient_context, format_chunks, format_epid_priors, render,
)
from ..models.schemas import DiagnosticDifferential, EmergencyFlag, PatientContext

log = logging.getLogger("tropicare.agents")

_MONTH_NAMES_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

# Emergency conditions to detect in patient symptoms/context and LLM output
_EMERGENCY_CONDITIONS = {
    "meningitis": {
        "keywords": [
            "méningite", "meningite", "meningitis",
            "raideur de la nuque", "raideur nuque", "neck stiffness",
            "kernig", "brudzinski", "purpura fulminans",
        ],
        "disease": "Méningite bactérienne",
        "level": "critical",
        "action": "Transfert immédiat — antibiothérapie empirique en urgence (ceftriaxone IV)",
    },
    "severe_malaria": {
        "keywords": [
            "paludisme grave", "paludisme sévère", "severe malaria",
            "neuropaludisme", "cerebral malaria",
            "convulsions fébriles", "coma fébrile",
            "parasitémie élevée", "hyperparasitémie",
            "ictère fébrile", "hémoglobinurie",
        ],
        "disease": "Paludisme grave",
        "level": "critical",
        "action": "Transfert immédiat — artésunate IV en urgence",
    },
    "hemorrhagic_fever": {
        "keywords": [
            "fièvre hémorragique", "hemorrhagic fever",
            "fièvre de lassa", "lassa fever", "lassa",
            "ebola", "marburg", "fièvre de marburg",
            "saignements diffus", "hémorragie", "hemorrhagie",
            "fièvre hémorragique virale",
        ],
        "disease": "Fièvre hémorragique virale",
        "level": "critical",
        "action": "Isolement immédiat — protocole fièvre hémorragique — notifier autorités sanitaires",
    },
    "septic_shock": {
        "keywords": [
            "choc septique", "septic shock", "sepsis sévère",
            "severe sepsis", "hypotension septique",
            "défaillance multi-organes", "multi-organ failure",
            "marbrures", "oligurie fébrile",
        ],
        "disease": "Choc septique",
        "level": "critical",
        "action": "Réanimation immédiate — remplissage vasculaire et antibiothérapie large spectre IV",
    },
}


class DiagnosticAgent(BaseAgent):
    name = "diagnostic"

    # Maximum ReAct iterations before forcing a conclusion
    MAX_REACT_TURNS = 4

    async def _execute(self, **kwargs) -> tuple[Any, dict, list[str]]:
        ctx: dict     = kwargs.get("patient_context", {})
        query: str    = kwargs.get("query", "")
        history: list = kwargs.get("conversation_history", [])
        prior_diff    = kwargs.get("previous_differential")
        new_info      = kwargs.get("new_information")

        tool_calls: list[str] = []
        total_usage: dict     = {"input_tokens": 0, "output_tokens": 0}

        # Track tool failure warnings for graceful degradation
        tool_warnings: list[str] = []

        # ── Step 1: retrieve epidemiological priors ──────────────────────────
        region = ctx.get("region", "Maritime")
        month  = datetime.date.today().month
        epid: dict = {}
        try:
            epid = await self._mcp.call("epid_calendar", region=region, month=month)
            tool_calls.append("epid_calendar")
        except Exception as e:
            log.warning("epid_calendar failed: %s", e)
            tool_warnings.append("Données épidémiologiques indisponibles (epid_calendar)")

        # ── Step 2: hybrid retrieval (3 query expansions) ───────────────────
        symptoms    = [s.get("normalized", s.get("text", "")) for s in ctx.get("symptoms", [])]
        region_str  = ctx.get("region", "")
        q_main      = query
        q_symptoms  = " ".join(symptoms[:4])
        q_epid      = f"maladies tropicales {region_str} Togo saison {'pluies' if month in range(5, 11) else 'sèche'}"

        chunks: list[dict] = []
        for q in [q_main, q_symptoms, q_epid]:
            if not q.strip():
                continue
            try:
                retrieved = await self._mcp.call(
                    "hybrid_retrieve", query=q, k=8, language=None
                )
                chunks.extend(retrieved)
                tool_calls.append("hybrid_retrieve")
            except Exception as e:
                log.warning("hybrid_retrieve failed for q=%r: %s", q[:40], e)
                tool_warnings.append(f"Recherche documentaire partielle (hybrid_retrieve: {q[:30]}…)")

        # Deduplicate chunks by chunk_id, keep highest score
        seen: dict[str, dict] = {}
        for c in chunks:
            cid = c.get("chunk_id", "")
            if cid not in seen or c.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = c
        top_chunks = sorted(seen.values(), key=lambda c: c.get("score", 0), reverse=True)[:8]

        # Empty KB: warn when no evidence was retrieved (Req 33.1)
        if not top_chunks:
            tool_warnings.append(
                "Aucune évidence trouvée dans la base de connaissances — "
                "le différentiel repose uniquement sur les connaissances générales du modèle"
            )

        # ── Step 3: ReAct loop ───────────────────────────────────────────────
        season_ctx   = f"{_MONTH_NAMES_FR[month]} — {'saison des pluies' if month in range(5, 11) else 'saison sèche'}"
        epid_priors  = epid.get("disease_priors", {})
        epid_alerts  = epid.get("outbreak_alerts", [])

        # Build base prompt
        if prior_diff and new_info:
            user_prompt = render(
                DIAGNOSTIC_REFINE_PROMPT,
                previous_differential_json=json.dumps(prior_diff, ensure_ascii=False, indent=2),
                new_information=new_info,
                new_chunks_formatted=format_chunks(top_chunks),
            )
        else:
            user_prompt = render(
                DIAGNOSTIC_REACT_PROMPT,
                patient_context_summary=format_patient_context(ctx),
                region=region,
                season_context=season_ctx,
                month=month,
                epid_priors_formatted=format_epid_priors(epid_priors),
                retrieved_chunks_formatted=format_chunks(top_chunks),
                conversation_history=self._format_history(history),
                query=query,
            )

        messages = [{"role": "user", "content": user_prompt}]

        # Iterative ReAct: if Claude asks for more info, retrieve and continue
        final_raw = ""
        for turn in range(self.MAX_REACT_TURNS):
            raw, usage = await self._call_claude(DIAGNOSTIC_SYSTEM, messages)
            total_usage["input_tokens"]  += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)
            final_raw = raw

            # Check if Claude needs more retrieval (signals "RETRIEVE:" in thought)
            if "RETRIEVE:" in raw and turn < self.MAX_REACT_TURNS - 1:
                retrieval_queries = _re.findall(r"RETRIEVE:\s*(.+)", raw)
                new_chunks: list[dict] = []
                for rq in retrieval_queries[:2]:
                    try:
                        extra = await self._mcp.call("hybrid_retrieve", query=rq.strip(), k=5)
                        new_chunks.extend(extra)
                        tool_calls.append("hybrid_retrieve")
                    except Exception as e:
                        log.warning("ReAct retrieval failed: %s", e)
                        tool_warnings.append(f"Recherche ReAct partielle (hybrid_retrieve: {rq.strip()[:30]}…)")

                if new_chunks:
                    # Add Claude's thinking + new evidence as next turn
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": f"Nouveaux extraits récupérés :\n{format_chunks(new_chunks)}\n\nContinue ton raisonnement et produis le différentiel final.",
                    })
                    continue  # next ReAct iteration

            # No more RETRIEVE signals → we have the final answer
            break

        # ── Step 4: format citations ─────────────────────────────────────────
        citations = []
        try:
            citations = await self._mcp.call("citation_formatter", chunks=top_chunks)
            tool_calls.append("citation_formatter")
        except Exception as e:
            log.warning("citation_formatter failed: %s", e)
            tool_warnings.append("Formatage des citations indisponible (citation_formatter)")

        # ── Step 5: parse output with retry-once on invalid JSON ─────────────
        try:
            result = await self._parse_output(
                final_raw,
                citations=citations,
                epid_alerts=epid_alerts,
                patient_context=ctx,
            )
        except (ValueError, ValidationError):
            # Retry LLM call once with explicit JSON instruction
            log.warning("First parse failed, retrying LLM call with explicit JSON instruction")
            retry_messages = messages.copy()
            retry_messages.append({"role": "assistant", "content": final_raw})
            retry_messages.append({
                "role": "user",
                "content": (
                    "Ta réponse précédente ne contenait pas de JSON valide. "
                    "Retourne UNIQUEMENT un objet JSON valide avec la structure exacte suivante, "
                    "sans texte avant ou après :\n"
                    '{"emergency_flags": [], "differential": [{"rank": 1, "disease_name": "...", '
                    '"icd11_code": "...", "confidence": 0.85, "supporting_evidence": ["..."], '
                    '"confirmatory_tests": [{"name": "...", "priority": "urgent", '
                    '"availability_togo": "disponible"}]}], '
                    '"reasoning_summary": "..."}'
                ),
            })
            try:
                retry_raw, retry_usage = await self._call_claude(DIAGNOSTIC_SYSTEM, retry_messages)
                total_usage["input_tokens"]  += retry_usage.get("input_tokens", 0)
                total_usage["output_tokens"] += retry_usage.get("output_tokens", 0)
                result = await self._parse_output(
                    retry_raw,
                    citations=citations,
                    epid_alerts=epid_alerts,
                    patient_context=ctx,
                )
            except (ValueError, ValidationError):
                # Last resort: lenient extraction of whatever valid fields exist
                log.warning("Retry parse also failed, attempting lenient JSON extraction")
                partial, json_warnings = self._extract_json_lenient(
                    retry_raw if 'retry_raw' in dir() else final_raw,
                    required_fields=["differential"],
                )
                tool_warnings.extend(json_warnings)
                # Build a minimal valid result from partial data
                if not partial.get("differential"):
                    partial["differential"] = []
                partial["emergency_flags"] = partial.get("emergency_flags", [])
                partial["citations"] = citations or []
                partial["reasoning_summary"] = partial.get("reasoning_summary", "")
                result = partial

        # ── Attach tool failure warnings as annotations ──────────────────────
        if tool_warnings:
            existing = result.get("_tool_warnings", []) if isinstance(result, dict) else []
            if isinstance(result, dict):
                result["_tool_warnings"] = existing + tool_warnings

        return result, total_usage, tool_calls

    async def _build_messages(self, **kwargs) -> tuple[str, list[dict]]:
        # Not used directly — _execute builds messages inline
        return DIAGNOSTIC_SYSTEM, []

    async def _parse_output(self, raw: str, citations=None, epid_alerts=None,
                            patient_context=None, **_) -> dict:
        data = self._extract_json(raw)

        # ── Detect emergency conditions from patient symptoms/context ────────
        emergency_flags = list(data.get("emergency_flags", []))
        detected_diseases = {f.get("disease", "").lower() for f in emergency_flags}

        # Check patient context for emergency keywords
        if patient_context:
            searchable_text = self._build_searchable_text(patient_context)
            for condition_key, condition in _EMERGENCY_CONDITIONS.items():
                # Skip if already flagged
                if condition["disease"].lower() in detected_diseases:
                    continue
                for keyword in condition["keywords"]:
                    if keyword.lower() in searchable_text:
                        emergency_flags.append({
                            "disease": condition["disease"],
                            "level": condition["level"],
                            "action": condition["action"],
                        })
                        detected_diseases.add(condition["disease"].lower())
                        break

        # Also scan the LLM raw output for emergency conditions
        raw_lower = raw.lower() if raw else ""
        for condition_key, condition in _EMERGENCY_CONDITIONS.items():
            if condition["disease"].lower() in detected_diseases:
                continue
            for keyword in condition["keywords"]:
                if keyword.lower() in raw_lower:
                    emergency_flags.append({
                        "disease": condition["disease"],
                        "level": condition["level"],
                        "action": condition["action"],
                    })
                    detected_diseases.add(condition["disease"].lower())
                    break

        # Inject outbreak alerts as emergency flags if present
        if epid_alerts:
            for alert in epid_alerts:
                alert_lower = alert.lower() if isinstance(alert, str) else ""
                if alert_lower not in detected_diseases:
                    emergency_flags.append({
                        "disease": alert,
                        "level": "urgent",
                        "action": "Alerte épidémique en cours — notifier district sanitaire",
                    })

        data["emergency_flags"] = emergency_flags
        data["citations"] = citations or []

        # ── Validate through Pydantic model ──────────────────────────────────
        validated = DiagnosticDifferential.model_validate(data)

        # ── Ensure 3–5 differential items ────────────────────────────────────
        if len(validated.differential) > 5:
            log.warning("Differential has %d items, truncating to 5", len(validated.differential))
            validated.differential = validated.differential[:5]
        if len(validated.differential) < 3:
            log.warning("Differential has only %d items (expected 3–5)", len(validated.differential))

        return validated.model_dump()

    @staticmethod
    def _build_searchable_text(ctx: dict) -> str:
        """Build a lowercase searchable string from patient context for emergency detection."""
        parts = []
        parts.append(ctx.get("chief_complaint", ""))
        for s in ctx.get("symptoms", []):
            parts.append(s.get("text", ""))
            parts.append(s.get("normalized", "") or "")
        for lab in ctx.get("lab_results", []):
            parts.append(lab.get("name", ""))
            parts.append(lab.get("value", ""))
        # Include vital signs context for shock detection
        vs = ctx.get("vital_signs", {})
        if vs:
            bp_sys = vs.get("bp_systolic")
            if bp_sys is not None and bp_sys < 90:
                parts.append("hypotension")
            temp = vs.get("temp_c")
            if temp is not None and temp >= 39.0 and bp_sys is not None and bp_sys < 90:
                parts.append("hypotension septique")
        return " ".join(parts).lower()

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        if not history:
            return "Première consultation"
        lines = []
        for turn in history[-4:]:  # last 4 turns only
            role = "Clinicien" if turn.get("role") == "user" else "Système"
            lines.append(f"{role}: {str(turn.get('content', ''))[:200]}")
        return "\n".join(lines)
