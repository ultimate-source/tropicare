# tropicare_eval/
# ├── harness.py          ← orchestrates full benchmark run
# ├── metrics.py          ← all metric computations
# ├── benchmark.py        ← benchmark case schema + loader
# ├── judges.py           ← LLM-as-judge evaluators
# ├── report.py           ← HTML/JSON report generation
# └── conftest.py         ← pytest fixtures for CI integration
#
# Run:  python -m tropicare_eval.harness --benchmark data/benchmark_v1.json
# CI:   pytest tropicare_eval/ -m eval --tb=short

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

log = logging.getLogger("tropicare.eval")

# ═══════════════════════════════════════════════════════════════
# benchmark.py — Case schema and loader
# ═══════════════════════════════════════════════════════════════

class GroundTruthDiagnosis(BaseModel):
    icd11_code: str
    disease_name: str
    rank_expected: int   # expected position in differential (1 = top)

class GroundTruthTreatment(BaseModel):
    first_line_drugs: list[str]    # generic names
    must_exclude: list[str]        # drugs that must NOT appear (e.g. contraindicated)
    came_available_expected: bool  # at least one first-line drug available at CAME

class BenchmarkCase(BaseModel):
    case_id: str
    description: str
    category: str   # malaria|bacterial|NTD|viral|fungal|edge
    difficulty: str  # easy|medium|hard|adversarial
    patient_context: dict[str, Any]
    free_text_query: str
    ground_truth_diagnoses: list[GroundTruthDiagnosis]
    ground_truth_treatment: GroundTruthTreatment | None
    emergency_expected: bool
    expected_clarifying_questions: bool   # True if intake should ask Qs
    notes: str = ""

def load_benchmark(path: str | Path) -> list[BenchmarkCase]:
    data = json.loads(Path(path).read_text())
    return [BenchmarkCase(**c) for c in data["cases"]]

# ═══════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse, os

    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark",    default="tropicare_eval/data/benchmark_v1.json")
    parser.add_argument("--gateway-url",  default=os.getenv("EVAL_GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--model",        default=os.getenv("MODEL_VERSION", "claude-sonnet-4-20250514"))
    parser.add_argument("--concurrency",  type=int, default=5)
    parser.add_argument("--no-judges",    action="store_true")
    parser.add_argument("--output-dir",   default="eval_reports")
    args = parser.parse_args()

    cases   = load_benchmark(args.benchmark)
    harness = EvalHarness(
        gateway_url=args.gateway_url,
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        concurrency=args.concurrency,
        enable_llm_judges=not args.no_judges,
    )
    report = asyncio.run(harness.run(cases, model_version=args.model))
    print_report(report)
    path = save_report(report, args.output_dir)
    print(f"Full report: {path}")

    # Exit 1 if any threshold breached (for CI)
    failed = any([
        report.top1_accuracy       < THRESHOLDS["top1_accuracy"],
        report.top3_accuracy       < THRESHOLDS["top3_accuracy"],
        report.citation_rate_mean  < THRESHOLDS["citation_rate_mean"],
        report.guideline_adherence < THRESHOLDS["guideline_adherence"],
        report.disclaimer_rate     < 1.0,
        report.hallucination_rate  > THRESHOLDS["hallucination_rate"],
        report.p95_latency_ms      > THRESHOLDS["p95_latency_ms"],
    ])
    raise SystemExit(1 if failed else 0)