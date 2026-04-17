# tropicare_eval/generate_benchmark.py
#
# Generates the remaining 160 benchmark cases using Claude as a medical
# case author. Existing seed cases are passed as few-shot examples to
# guarantee schema compliance and clinical realism.
#
# Usage:
#   python -m tropicare_eval.generate_benchmark \
#       --seed    tropicare_eval/data/benchmark_v1_seed.json \
#       --output  tropicare_eval/data/benchmark_v1.json \
#       --target  200
#
# Review workflow:
#   1. Generator writes → benchmark_v1_DRAFT.json
#   2. Clinician validator reviews each case via review CLI (--review flag)
#   3. Approved cases are merged into benchmark_v1.json

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("tropicare.benchmark_gen")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# Generation targets
# These match the PRD category distribution for 200 total cases.
# ─────────────────────────────────────────────────────────────────────────────

GENERATION_PLAN = [
    # (category, difficulty, disease_focus, quantity)
    # ── Malaria (50 total, 12 in seed → need 38 more)
    ("malaria",    "easy",        "paludisme simple enfant <5 ans",                                      4),
    ("malaria",    "easy",        "paludisme simple adulte — traitement ambulatoire",                    4),
    ("malaria",    "medium",      "paludisme — présentation atypique (pas de fièvre)",                   3),
    ("malaria",    "medium",      "paludisme — comorbidité drépanocytose",                               3),
    ("malaria",    "medium",      "paludisme — recrudescence / rechute",                                 3),
    ("malaria",    "hard",        "paludisme grave — hyperparasitémie",                                  3),
    ("malaria",    "hard",        "paludisme grave — détresse respiratoire",                             3),
    ("malaria",    "hard",        "paludisme — diagnostic différentiel encéphalite",                     3),
    ("malaria",    "medium",      "paludisme — nourrisson 0-12 mois",                                    3),
    ("malaria",    "adversarial", "paludisme — double infection, autre pathologie masquante",            3),
    ("malaria",    "medium",      "paludisme vivax retour voyage",                                       3),
    ("malaria",    "medium",      "paludisme — TDR faux négatif, forte suspicion clinique",              3),

    # ── Bacterial (50 total, 10 in seed → need 40 more)
    ("bacterial",  "easy",        "otite moyenne aiguë enfant",                                          3),
    ("bacterial",  "easy",        "pneumonie communautaire adulte — non sévère",                         4),
    ("bacterial",  "medium",      "pneumonie sévère — critères hospitalisation",                         4),
    ("bacterial",  "medium",      "péritonite secondaire — perforation typhoïde",                        3),
    ("bacterial",  "hard",        "sepsis d'origine urinaire — choc septique",                           3),
    ("bacterial",  "medium",      "abcès hépatique amibien",                                             3),
    ("bacterial",  "medium",      "borréliose (fièvre récurrente à tiques) — Savanes",                   3),
    ("bacterial",  "easy",        "infection cutanée — impétigo, cellulite — enfant",                    3),
    ("bacterial",  "hard",        "méningite tuberculeuse",                                              3),
    ("bacterial",  "medium",      "arthrite septique — enfant drépanocytaire",                           3),
    ("bacterial",  "hard",        "tétanos — plaie souillée non vacciné",                                3),
    ("bacterial",  "medium",      "gonorrhée + chlamydia — IST coïnfection",                             3),
    ("bacterial",  "adversarial", "antibiorésistance totale — souche BLSE",                              3),

    # ── NTD (38 total, 8 in seed → need 30 more)
    ("NTD",        "easy",        "ankylostomose — anémie microcytaire, agriculteur",                    4),
    ("NTD",        "medium",      "schistosomiase intestinale (S. mansoni) — splénomégalie",             4),
    ("NTD",        "hard",        "trypanosomiase — stade 1 (absence LCR positif)",                      3),
    ("NTD",        "medium",      "pian (Treponema pallidum pertenue) — enfant",                         3),
    ("NTD",        "easy",        "gale — prurit nocturne, sillons",                                     3),
    ("NTD",        "medium",      "loase — œdème de Calabar + microfilarémie",                           3),
    ("NTD",        "hard",        "dracunculose — éruption cutanée avec ver visible",                    3),
    ("NTD",        "medium",      "échinococcose hépatique — masse kystique",                             3),
    ("NTD",        "adversarial", "multiparasitisme — patient VIH+ avec 3 NTDs simultanés",             4),

    # ── Viral (32 total, 6 in seed → need 26 more)
    ("viral",      "easy",        "dengue classique — thrombopénie, TDR dengue disponible",              4),
    ("viral",      "hard",        "dengue hémorragique — critères sévérité",                              3),
    ("viral",      "medium",      "fièvre jaune — ictère + hémorragie",                                  3),
    ("viral",      "medium",      "hépatite B chronique — réactivation",                                  3),
    ("viral",      "medium",      "varicelle compliquée — enfant immunodéprimé",                          3),
    ("viral",      "hard",        "encéphalite virale — diagnostic différentiel méningite bactérienne",  3),
    ("viral",      "medium",      "SIDA stade C — infections opportunistes multiples",                   3),
    ("viral",      "hard",        "fièvre de Lassa — contact familial malade",                           4),

    # ── Fungal (12 total, 2 in seed → need 10 more)
    ("fungal",     "easy",        "candidose vaginale récidivante — femme diabétique",                   2),
    ("fungal",     "medium",      "histoplasmose pulmonaire — VIH CD4 <100",                             2),
    ("fungal",     "hard",        "aspergillose invasive — post-grippe sévère",                          2),
    ("fungal",     "medium",      "dermatophytie étendue — tinea corporis + pedis",                      2),
    ("fungal",     "hard",        "mucormycose rhino-orbitaire — diabétique cétoacidosique",              2),

    # ── Edge / Adversarial (18 total, 2 in seed → need 16 more)
    ("edge",       "adversarial", "double diagnostic paludisme + méningite simultanés",                  3),
    ("edge",       "adversarial", "allergie pénicilline + méningocoque — choix antibiotique",            2),
    ("edge",       "adversarial", "femme enceinte T1 — paludisme grave + tétanos",                       2),
    ("edge",       "adversarial", "hors scope — demande diagnostic cancer, chirurgie",                   2),
    ("edge",       "adversarial", "patient déjà traité 3 antibiotiques — re-évaluation",                 2),
    ("edge",       "adversarial", "nourrisson 1 mois — fièvre sans foyer évident",                       3),
    ("edge",       "adversarial", "intoxication médicamenteuse présentée comme infection",               2),
]

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Tu es un médecin spécialiste en maladies tropicales et en médecine interne africaine, \
avec une expertise particulière au Togo et en Afrique de l'Ouest. Tu génères des cas \
cliniques réalistes pour un benchmark d'évaluation d'un système d'aide au diagnostic.

EXIGENCES ABSOLUES :
1. Chaque cas doit être cliniquement cohérent et réaliste pour le contexte togolais.
2. Les codes ICD-11 doivent être exacts.
3. Les valeurs biologiques doivent être dans des plages cliniquement plausibles.
4. Les drugs dans ground_truth_treatment doivent être des noms génériques français.
5. Retourne UNIQUEMENT un JSON valide. Aucun texte avant ou après.
6. Le champ case_id doit suivre le format {PREFIX}-{NUMBER:03d}.
7. Varie les régions, âges, sexes et présentations cliniques.
8. Les cas adversariaux doivent représenter des pièges diagnostiques RÉELS et fréquents.
"""

GENERATION_PROMPT = """\
EXEMPLES DE CAS EXISTANTS (pour comprendre le format exact) :
{few_shot_examples}

─────────────────────────────────────────────────────────────────────────────
TÂCHE : Génère {n} cas cliniques NOUVEAUX et DIFFÉRENTS des exemples ci-dessus.
Catégorie : {category}
Difficulté : {difficulty}
Focus clinique : {disease_focus}
Prochain case_id : {next_id}

SCHÉMA JSON requis pour chaque cas (reprends exactement cette structure) :
{{
  "case_id": "string",
  "description": "string",
  "category": "string",
  "difficulty": "easy|medium|hard|adversarial",
  "patient_context": {{
    "age_years": number,
    "sex": "M|F",
    "weight_kg": number,
    "region": "Maritime|Plateaux|Centrale|Kara|Savanes",
    "chief_complaint": "string",
    "symptoms": [
      {{"text": "string", "normalized": "string", "snomed_code": "string|null", "category": "symptom|sign|lab_finding|vital_sign"}}
    ],
    "vital_signs": {{
      "temp_c": number, "bp_systolic": number, "bp_diastolic": number,
      "hr": number, "rr": number, "spo2": number, "gcs": number
    }},
    "lab_results": [
      {{"name": "string", "value": "number|string", "unit": "string"}}
    ],
    "current_medications": [
      {{"name": "string", "dose": "string", "frequency": "string"}}
    ],
    "allergies": ["string"],
    "pregnancy_status": "not_applicable|not_pregnant|pregnant_t1|pregnant_t2|pregnant_t3|unknown",
    "symptom_onset_days": number,
    "travel_history": ["string"]
  }},
  "free_text_query": "string — question réaliste qu'un clinicien togolais poserait au système",
  "ground_truth_diagnoses": [
    {{
      "icd11_code": "string",
      "disease_name": "string",
      "rank_expected": number
    }}
  ],
  "ground_truth_treatment": {{
    "first_line_drugs": ["string (noms génériques)"],
    "must_exclude": ["string"],
    "came_available_expected": boolean
  }},
  "emergency_expected": boolean,
  "expected_clarifying_questions": boolean,
  "notes": "string — note clinique pour le validateur médical"
}}

Retourne un JSON array contenant exactement {n} cas : [ {{...}}, {{...}} ]
"""

# ─────────────────────────────────────────────────────────────────────────────
# Claude API caller
# ─────────────────────────────────────────────────────────────────────────────

async def call_claude(
    system: str,
    user: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 8000,
    retries: int = 3,
) -> str:
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "temperature": 0.7,   # some variation but not too wild
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                r.raise_for_status()
                return r.json()["content"][0]["text"]
        except Exception as e:
            wait = 2 ** attempt
            log.warning("Attempt %d/%d failed: %s — retrying in %ds", attempt + 1, retries, e, wait)
            await asyncio.sleep(wait)
    raise RuntimeError(f"Claude API failed after {retries} attempts")


def extract_json_array(text: str) -> list[dict]:
    """Extract JSON array from Claude response, stripping markdown fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find first [ to last ]
    start = text.find("[")
    end   = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in:\n{text[:500]}")
    return json.loads(text[start:end])


# ─────────────────────────────────────────────────────────────────────────────
# Few-shot selector
# ─────────────────────────────────────────────────────────────────────────────

def select_few_shot(
    seed_cases: list[dict],
    category: str,
    difficulty: str,
    n_examples: int = 2,
) -> str:
    # Prefer same category + difficulty, else same category, else random
    same_both = [c for c in seed_cases if c["category"] == category and c["difficulty"] == difficulty]
    same_cat  = [c for c in seed_cases if c["category"] == category]
    pool = same_both or same_cat or seed_cases
    selected = random.sample(pool, min(n_examples, len(pool)))
    return json.dumps(selected, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Validator — structural checks before accepting a generated case
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "case_id", "description", "category", "difficulty",
    "patient_context", "free_text_query", "ground_truth_diagnoses",
    "emergency_expected", "expected_clarifying_questions", "notes",
}
REQUIRED_CONTEXT_FIELDS = {
    "age_years", "sex", "region", "chief_complaint",
    "symptoms", "vital_signs", "lab_results",
    "current_medications", "allergies",
    "pregnancy_status", "symptom_onset_days",
}
VALID_REGIONS   = {"Maritime", "Plateaux", "Centrale", "Kara", "Savanes"}
VALID_SEX       = {"M", "F"}
VALID_PREGNANCY = {"not_applicable", "not_pregnant", "pregnant_t1", "pregnant_t2", "pregnant_t3", "unknown"}
VALID_DIFF      = {"easy", "medium", "hard", "adversarial"}

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]

def validate_case(case: dict) -> ValidationResult:
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(case.keys())
    if missing:
        errors.append(f"Missing top-level fields: {missing}")
        return ValidationResult(False, errors)

    ctx = case.get("patient_context", {})
    missing_ctx = REQUIRED_CONTEXT_FIELDS - set(ctx.keys())
    if missing_ctx:
        errors.append(f"Missing patient_context fields: {missing_ctx}")

    if ctx.get("region") not in VALID_REGIONS:
        errors.append(f"Invalid region: {ctx.get('region')}")
    if ctx.get("sex") not in VALID_SEX:
        errors.append(f"Invalid sex: {ctx.get('sex')}")
    if ctx.get("pregnancy_status") not in VALID_PREGNANCY:
        errors.append(f"Invalid pregnancy_status: {ctx.get('pregnancy_status')}")
    if case.get("difficulty") not in VALID_DIFF:
        errors.append(f"Invalid difficulty: {case.get('difficulty')}")
    if not isinstance(ctx.get("age_years"), (int, float)):
        errors.append("age_years must be numeric")
    if not isinstance(ctx.get("vital_signs"), dict):
        errors.append("vital_signs must be a dict")

    diag = case.get("ground_truth_diagnoses", [])
    if not diag and case.get("category") != "edge":
        errors.append("ground_truth_diagnoses is empty (non-edge case)")
    for d in diag:
        if not d.get("icd11_code"):
            errors.append("ground_truth_diagnoses entry missing icd11_code")
        if d.get("rank_expected", 0) < 1:
            errors.append("rank_expected must be >= 1")

    if not case.get("free_text_query", "").strip():
        errors.append("free_text_query is empty")
    if not case.get("notes", "").strip():
        errors.append("notes is empty")

    return ValidationResult(len(errors) == 0, errors)


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────────────────────

def is_duplicate(new_case: dict, existing_cases: list[dict]) -> bool:
    """Reject if same chief_complaint + same region + same primary ICD-11."""
    new_complaint = new_case.get("patient_context", {}).get("chief_complaint", "").lower()
    new_region    = new_case.get("patient_context", {}).get("region", "")
    new_diag      = new_case.get("ground_truth_diagnoses", [{}])[0].get("icd11_code", "")

    for ex in existing_cases:
        ex_ctx = ex.get("patient_context", {})
        ex_complaint = ex_ctx.get("chief_complaint", "").lower()
        ex_region    = ex_ctx.get("region", "")
        ex_diag      = ex.get("ground_truth_diagnoses", [{}])[0].get("icd11_code", "")

        if new_diag == ex_diag and new_region == ex_region and new_complaint == ex_complaint:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Case ID counters
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_PREFIX = {
    "malaria":   "MAL",
    "bacterial": "BAC",
    "NTD":       "NTD",
    "viral":     "VIR",
    "fungal":    "FNG",
    "edge":      "EDGE",
}

def next_case_id(category: str, existing: list[dict]) -> str:
    prefix = CATEGORY_PREFIX.get(category, "GEN")
    existing_ids = {c["case_id"] for c in existing if c["case_id"].startswith(prefix)}
    n = 1
    while f"{prefix}-{n:03d}" in existing_ids:
        n += 1
    return f"{prefix}-{n:03d}"


# ─────────────────────────────────────────────────────────────────────────────
# Generator — one batch per plan entry
# ─────────────────────────────────────────────────────────────────────────────

async def generate_batch(
    plan_entry: tuple,
    seed_cases: list[dict],
    all_cases: list[dict],
    api_key: str,
    concurrency: asyncio.Semaphore,
) -> list[dict]:
    category, difficulty, disease_focus, quantity = plan_entry

    async with concurrency:
        few_shot = select_few_shot(seed_cases, category, difficulty, n_examples=2)
        nid      = next_case_id(category, all_cases)

        prompt = GENERATION_PROMPT.format(
            few_shot_examples=few_shot,
            n=quantity,
            category=category,
            difficulty=difficulty,
            disease_focus=disease_focus,
            next_id=nid,
        )

        log.info("Generating %d %s/%s cases: %s", quantity, category, difficulty, disease_focus)
        t0  = time.monotonic()
        raw = await call_claude(SYSTEM_PROMPT, prompt, api_key, max_tokens=8000)
        elapsed = time.monotonic() - t0
        log.info("  → Claude responded in %.1fs", elapsed)

        try:
            cases = extract_json_array(raw)
        except (ValueError, json.JSONDecodeError) as e:
            log.error("JSON parse failed for %s/%s: %s\nRaw: %s", category, difficulty, e, raw[:400])
            return []

        accepted: list[dict] = []
        for case in cases:
            vr = validate_case(case)
            if not vr.valid:
                log.warning("Case %s rejected — validation errors: %s",
                            case.get("case_id", "?"), vr.errors)
                continue
            if is_duplicate(case, all_cases + accepted):
                log.warning("Case %s rejected — duplicate of existing case", case.get("case_id", "?"))
                continue
            accepted.append(case)

        log.info("  → Accepted %d/%d cases", len(accepted), len(cases))
        return accepted


# ─────────────────────────────────────────────────────────────────────────────
# Review CLI — interactive validation by clinician
# ─────────────────────────────────────────────────────────────────────────────

def review_benchmark(draft_path: str, output_path: str) -> None:
    """Interactive CLI for a clinician to review and approve generated cases."""
    draft  = json.loads(Path(draft_path).read_text())
    cases  = draft["cases"]
    approved: list[dict] = []
    rejected: list[dict] = []

    print(f"\n{'═'*70}")
    print(f" TropiCare Benchmark Review — {len(cases)} cases to review")
    print(f" Commands: [a]ccept  [r]eject  [e]dit note  [q]uit")
    print(f"{'═'*70}\n")

    for i, case in enumerate(cases, 1):
        ctx = case["patient_context"]
        print(f"[{i}/{len(cases)}] {case['case_id']} — {case['description']}")
        print(f"  Category: {case['category']} | Difficulty: {case['difficulty']}")
        print(f"  Patient: {ctx['age_years']}y {ctx['sex']} | Region: {ctx['region']} | Pregnancy: {ctx['pregnancy_status']}")
        print(f"  Chief complaint: {ctx['chief_complaint']}")
        print(f"  Query: {case['free_text_query'][:100]}…")
        print(f"  GT diagnoses: {[f\"{d['rank_expected']}. {d['disease_name']}\" for d in case['ground_truth_diagnoses']]}")
        if case.get("ground_truth_treatment"):
            print(f"  GT treatment: {case['ground_truth_treatment']['first_line_drugs']}")
        print(f"  Emergency: {case['emergency_expected']} | Notes: {case['notes'][:80]}…")
        print()

        while True:
            cmd = input("  → ").strip().lower()
            if cmd == "a":
                approved.append(case)
                print("  ✓ Accepted\n")
                break
            elif cmd == "r":
                reason = input("  Reason for rejection: ").strip()
                case["_rejection_reason"] = reason
                rejected.append(case)
                print("  ✗ Rejected\n")
                break
            elif cmd == "e":
                new_note = input("  New note: ").strip()
                if new_note:
                    case["notes"] = new_note
                print("  Note updated")
            elif cmd == "q":
                print("Review interrupted.")
                break
            else:
                print("  Unknown command")

    print(f"\n{'═'*70}")
    print(f" Review complete: {len(approved)} approved, {len(rejected)} rejected")
    print(f"{'═'*70}")

    output = {
        "meta": {**draft.get("meta", {}), "total_cases": len(approved), "reviewed": True},
        "cases": approved,
    }
    Path(output_path).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f" Approved benchmark saved to: {output_path}")

    rejected_path = Path(output_path).with_suffix(".rejected.json")
    rejected_path.write_text(json.dumps({"cases": rejected}, ensure_ascii=False, indent=2))
    print(f" Rejected cases saved to: {rejected_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main(
    seed_path: str,
    output_path: str,
    target: int,
    api_key: str,
    concurrency: int,
    dry_run: bool,
) -> None:
    seed_data  = json.loads(Path(seed_path).read_text())
    seed_cases = seed_data["cases"]
    all_cases  = list(seed_cases)  # working set starts from seed

    log.info("Seed cases: %d | Target: %d | To generate: %d",
             len(seed_cases), target, target - len(seed_cases))

    if dry_run:
        total = sum(q for _, _, _, q in GENERATION_PLAN)
        log.info("DRY RUN — would generate %d cases across %d batches", total, len(GENERATION_PLAN))
        for entry in GENERATION_PLAN:
            log.info("  %s/%s × %d — %s", entry[0], entry[1], entry[3], entry[2])
        return

    sem      = asyncio.Semaphore(concurrency)
    tasks    = [generate_batch(entry, seed_cases, all_cases, api_key, sem)
                for entry in GENERATION_PLAN]

    for batch_coro in asyncio.as_completed(tasks):
        batch = await batch_coro
        for case in batch:
            # Fix case_id to avoid collisions (re-generate with correct counter)
            case["case_id"] = next_case_id(case["category"], all_cases)
            all_cases.append(case)
        log.info("Running total: %d cases", len(all_cases))

        # Save checkpoint every 10 new cases
        if len(all_cases) % 10 == 0:
            draft_path = Path(output_path).with_suffix(".DRAFT.json")
            _save(all_cases, seed_data, draft_path)
            log.info("Checkpoint saved to %s", draft_path)

    # Final save
    draft_path = Path(output_path).with_suffix(".DRAFT.json")
    _save(all_cases, seed_data, draft_path)
    log.info("Draft benchmark: %d cases → %s", len(all_cases), draft_path)
    log.info("Run with --review to validate with a clinician before finalising.")


def _save(cases: list[dict], seed_data: dict, path: Path) -> None:
    meta = dict(seed_data.get("meta", {}))
    meta["total_cases"] = len(cases)
    meta["reviewed"] = False
    output = {"meta": meta, "cases": cases}
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(description="TropiCare benchmark generator")
    parser.add_argument("--seed",        default="tropicare_eval/data/benchmark_v1_seed.json")
    parser.add_argument("--output",      default="tropicare_eval/data/benchmark_v1.json")
    parser.add_argument("--target",      type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel Claude API calls")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--review",      action="store_true", help="Run interactive review CLI")
    args = parser.parse_args()

    if args.review:
        draft = Path(args.output).with_suffix(".DRAFT.json")
        review_benchmark(str(draft), args.output)
    else:
        asyncio.run(main(
            seed_path=args.seed,
            output_path=args.output,
            target=args.target,
            api_key=os.environ["ANTHROPIC_API_KEY"],
            concurrency=args.concurrency,
            dry_run=args.dry_run,
        ))