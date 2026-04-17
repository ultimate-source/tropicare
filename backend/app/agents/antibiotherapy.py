# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/antibiotherapy.py — AntibiotherapyAgent
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from .base import BaseAgent, MCPClient
from .prompts import (
    ANTIBIOTHERAPY_SYSTEM, ANTIBIOTHERAPY_PROMPT, ANTIBIOTHERAPY_PREGNANCY_ADDENDUM,
    format_patient_context, format_chunks,
    format_ddi_warnings, format_amr_results, format_formulary_results, render,
)
from ..models.schemas import PatientContext, TreatmentPlan

log = logging.getLogger("tropicare.agents")

MANDATORY_DISCLAIMER = (
    "⚠️ AIDE À LA DÉCISION UNIQUEMENT — Cette recommandation est générée par un système "
    "d'intelligence artificielle à partir de guidelines validées. Elle ne remplace pas le "
    "jugement clinique du médecin traitant. Toute prescription doit être validée par un "
    "professionnel de santé habilité."
)


class AntibiotherapyAgent(BaseAgent):
    name = "antibiotherapy"

    async def _execute(self, **kwargs) -> tuple[Any, dict, list[str]]:
        ctx        = kwargs.get("patient_context", {})
        diagnosis  = kwargs.get("confirmed_diagnosis", "")
        icd11      = kwargs.get("icd11_code", "")
        confidence = kwargs.get("diagnostic_confidence", 0.0)

        tool_calls: list[str]  = []
        total_usage            = {"input_tokens": 0, "output_tokens": 0}

        # ── Step 1: retrieve treatment guidelines ────────────────────────────
        chunks: list[dict] = []
        for q in [
            f"traitement {diagnosis} Togo PNLP",
            f"antibiothérapie {diagnosis} Afrique Ouest",
            f"{diagnosis} protocole OMS posologie",
        ]:
            try:
                retrieved = await self._mcp.call("hybrid_retrieve", query=q, k=6)
                chunks.extend(retrieved)
                tool_calls.append("hybrid_retrieve")
            except Exception as e:
                log.warning("Antibiotherapy retrieval failed: %s", e)

        # Deduplicate
        seen: dict[str, dict] = {}
        for c in chunks:
            cid = c.get("chunk_id", "")
            if cid not in seen or c.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = c
        top_chunks = sorted(seen.values(), key=lambda c: c.get("score", 0), reverse=True)[:8]

        # ── Step 2: parallel tool calls ──────────────────────────────────────
        # Extract candidate drugs from retrieved chunks heuristically
        candidate_drugs = self._extract_candidate_drugs(top_chunks, diagnosis)
        current_meds    = [m.get("name", "") for m in ctx.get("current_medications", [])]
        all_drugs       = list(set(candidate_drugs + current_meds))

        # Run formulary, AMR, DDI, safety in parallel
        formulary_results, amr_results, ddi_warnings, safety_classes = await asyncio.gather(
            self._check_formulary(candidate_drugs),
            self._check_amr(candidate_drugs, diagnosis),
            self._check_ddi(all_drugs) if len(all_drugs) >= 2 else asyncio.sleep(0, result=[]),
            self._check_safety(candidate_drugs, ctx.get("pregnancy_status")),
            return_exceptions=True,
        )

        for name, result in [
            ("formulary_lookup", formulary_results),
            ("amr_lookup", amr_results),
            ("drug_ddi_check", ddi_warnings),
            ("safety_classifier", safety_classes),
        ]:
            if isinstance(result, Exception):
                log.warning("%s failed: %s", name, result)
            else:
                tool_calls.append(name)

        formulary_results = formulary_results if not isinstance(formulary_results, Exception) else []
        amr_results       = amr_results       if not isinstance(amr_results, Exception)       else []
        ddi_warnings      = ddi_warnings       if not isinstance(ddi_warnings, Exception)      else []
        safety_classes    = safety_classes     if not isinstance(safety_classes, Exception)    else []

        # ── Step 3: build prompt + call Claude ───────────────────────────────
        preg_status  = ctx.get("pregnancy_status", "not_pregnant")
        trimester    = {"pregnant_t1": 1, "pregnant_t2": 2, "pregnant_t3": 3}.get(preg_status)

        base_prompt = render(
            ANTIBIOTHERAPY_PROMPT,
            confirmed_diagnosis=diagnosis,
            icd11_code=icd11,
            diagnostic_confidence=f"{confidence:.0%}",
            age=ctx.get("age_years", "?"),
            sex=ctx.get("sex", "?"),
            weight_kg=ctx.get("weight_kg", "?"),
            pregnancy_status=preg_status,
            allergies=", ".join(ctx.get("allergies", [])) or "Aucune connue",
            current_medications=", ".join(m.get("name", "") for m in ctx.get("current_medications", [])) or "Aucun",
            formulary_results_formatted=format_formulary_results(formulary_results),
            amr_results_formatted=format_amr_results(amr_results),
            ddi_warnings_formatted=format_ddi_warnings(ddi_warnings),
            safety_classes_formatted=self._format_safety(safety_classes),
            retrieved_chunks_formatted=format_chunks(top_chunks),
        )

        if trimester:
            base_prompt += "\n\n" + render(
                ANTIBIOTHERAPY_PREGNANCY_ADDENDUM, trimester=trimester
            )

        messages = [{"role": "user", "content": base_prompt}]
        raw, usage = await self._call_claude(ANTIBIOTHERAPY_SYSTEM, messages)
        total_usage["input_tokens"]  += usage.get("input_tokens", 0)
        total_usage["output_tokens"] += usage.get("output_tokens", 0)

        # ── Step 4: citations ────────────────────────────────────────────────
        citations = []
        try:
            citations = await self._mcp.call("citation_formatter", chunks=top_chunks)
            tool_calls.append("citation_formatter")
        except Exception as e:
            log.warning("citation_formatter failed: %s", e)

        result = await self._parse_output(raw, citations=citations, ddi_warnings=ddi_warnings)
        return result, total_usage, tool_calls

    async def _build_messages(self, **kwargs) -> tuple[str, list[dict]]:
        return ANTIBIOTHERAPY_SYSTEM, []

    async def _parse_output(self, raw: str, citations=None, ddi_warnings=None, **_) -> dict:
        data = self._extract_json(raw)
        # Guarantee disclaimer is always present
        data["disclaimer"] = MANDATORY_DISCLAIMER
        data["citations"]  = citations or []
        return data

    async def _check_formulary(self, drugs: list[str]) -> list[dict]:
        results = []
        for drug in drugs[:6]:
            try:
                res = await self._mcp.call("formulary_lookup", drug_name=drug)
                results.append(res)
            except Exception:
                pass
        return results

    async def _check_amr(self, drugs: list[str], diagnosis: str) -> list[dict]:
        # Infer likely pathogen from diagnosis name
        pathogen_map = {
            "typhoïde": "Salmonella typhi",
            "choléra":  "Vibrio cholerae",
            "méningite": "Neisseria meningitidis",
            "pneumonie": "Streptococcus pneumoniae",
            "shigell":  "Shigella",
            "urinaire": "Escherichia coli",
        }
        pathogen = next(
            (p for kw, p in pathogen_map.items() if kw in diagnosis.lower()),
            "Bacteria"
        )
        results = []
        for drug in drugs[:4]:
            try:
                res = await self._mcp.call("amr_lookup", drug=drug, pathogen=pathogen, region="Togo")
                results.append(res)
            except Exception:
                pass
        return results

    async def _check_ddi(self, drugs: list[str]) -> list[dict]:
        return await self._mcp.call("drug_ddi_check", drug_list=drugs)

    async def _check_safety(self, drugs: list[str], pregnancy_status: str | None) -> list[dict]:
        if not pregnancy_status or pregnancy_status in ("not_pregnant", "not_applicable"):
            return []
        trimester = {"pregnant_t1": 1, "pregnant_t2": 2, "pregnant_t3": 3}.get(pregnancy_status)
        results = []
        for drug in drugs[:6]:
            try:
                res = await self._mcp.call("safety_classifier", drug=drug, trimester=trimester)
                results.append(res)
            except Exception:
                pass
        return results

    @staticmethod
    def _extract_candidate_drugs(chunks: list[dict], diagnosis: str) -> list[str]:
        """Heuristic drug name extraction from chunk text."""
        known_drugs = [
            "artésunate", "artéméther", "luméfantrine", "artéméther-luméfantrine",
            "quinine", "chloroquine", "primaquine", "doxycycline",
            "ceftriaxone", "amoxicilline", "azithromycine", "ciprofloxacine",
            "rifampicine", "isoniazide", "pyrazinamide", "éthambutol",
            "cotrimoxazole", "métronidazole", "fluconazole", "amphotéricine",
            "ivermectine", "albendazole", "praziquantel", "mébendazole",
        ]
        text = " ".join(c.get("chunk_text", "") for c in chunks).lower()
        return [d for d in known_drugs if d in text]

    @staticmethod
    def _format_safety(safety: list[dict]) -> str:
        if not safety:
            return "Non applicable"
        return "\n".join(
            f"  • {s.get('drug', '?')} : Catégorie {s.get('pregnancy_category', 'N/D')} "
            f"| Allaitement: {'Oui' if s.get('lactation_safe') else 'Non' if s.get('lactation_safe') is False else 'N/D'}"
            for s in safety
        )
