# ═══════════════════════════════════════════════════════════════
# harness.py — Orchestrates the full benchmark run
# ═══════════════════════════════════════════════════════════════

@dataclass
class BenchmarkReport:
    run_id: str
    timestamp: str
    model_version: str
    total_cases: int
    results: list[CaseResult]

    # Aggregate metrics
    top1_accuracy:        float = 0.0
    top3_accuracy:        float = 0.0
    top5_accuracy:        float = 0.0
    mrr:                  float = 0.0
    emergency_recall:     float = 0.0
    citation_rate_mean:   float = 0.0
    guideline_adherence:  float = 0.0
    came_coverage:        float = 0.0
    disclaimer_rate:      float = 0.0
    hallucination_rate:   float = 0.0
    p50_latency_ms:       float = 0.0
    p95_latency_ms:       float = 0.0

    # Per-category breakdown
    by_category:  dict[str, dict] = field(default_factory=dict)
    by_difficulty: dict[str, dict] = field(default_factory=dict)

    # Judge outputs
    citation_judge_results:     list[dict] = field(default_factory=list)
    hallucination_judge_results: list[dict] = field(default_factory=list)

class EvalHarness:
    def __init__(
        self,
        gateway_url: str,
        anthropic_api_key: str,
        concurrency: int = 5,
        enable_llm_judges: bool = True,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key     = anthropic_api_key
        self.sem         = asyncio.Semaphore(concurrency)
        self.llm_judges  = enable_llm_judges

    async def _run_case(self, case: BenchmarkCase) -> CaseResult:
        async with self.sem:
            try:
                # 1. Create session
                async with httpx.AsyncClient(timeout=30) as client:
                    sr = await client.post(
                        f"{self.gateway_url}/api/v1/sessions",
                        json={
                            "patient_context": case.patient_context,
                            "language": "fr",
                        },
                    )
                    sr.raise_for_status()
                    session_id = sr.json()["session_id"]

                # 2. Submit turn and collect full SSE stream
                t0 = time.monotonic()
                response = await self._stream_turn(session_id, case.free_text_query)
                latency_ms = int((time.monotonic() - t0) * 1000)

                # 3. Compute structural metrics
                diag = compute_diagnostic_metrics(case, response, latency_ms)
                tx   = compute_antibiotherapy_metrics(case, response, latency_ms)

                return CaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    difficulty=case.difficulty,
                    diagnostic=diag,
                    antibiotherapy=tx,
                    raw_response=response,
                )
            except Exception as exc:
                log.error("Case %s failed: %s", case.case_id, exc)
                return CaseResult(
                    case_id=case.case_id,
                    category=case.category,
                    difficulty=case.difficulty,
                    diagnostic=None,
                    antibiotherapy=None,
                    raw_response={},
                    error=str(exc),
                )

    async def _stream_turn(self, session_id: str, query: str) -> dict:
        """Consume SSE stream and assemble complete response object."""
        assembled: dict[str, Any] = {
            "differential": [],
            "treatment": {"first_line": [], "second_line": [], "alternatives": []},
            "citations": [],
            "emergency_flags": [],
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.gateway_url}/api/v1/sessions/{session_id}/turns",
                json={"query": query},
                headers={"Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                        t  = ev.get("type")
                        if t == "differential_item":
                            assembled["differential"].append(ev["item"])
                        elif t == "treatment_line":
                            tier = ev.get("tier", "first_line")
                            assembled["treatment"].setdefault(tier, []).append(ev["drug"])
                        elif t == "citation":
                            assembled["citations"].append(ev["citation"])
                        elif t == "emergency_flag":
                            assembled["emergency_flags"].append(ev["flag"])
                        elif t == "done":
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
        # Sort differential by rank
        assembled["differential"].sort(key=lambda d: d.get("rank", 99))
        return assembled

    def _aggregate(self, results: list[CaseResult]) -> dict[str, float]:
        diag_results = [r for r in results if r.diagnostic and not r.error]
        tx_results   = [r for r in results if r.antibiotherapy and not r.error]
        emergency_cases = [r for r in diag_results
                           if r.case_id in {c.case_id for c in [] if c.emergency_expected}]

        def safe_mean(vals: list[float]) -> float:
            return statistics.mean(vals) if vals else 0.0

        latencies = [r.diagnostic.latency_ms for r in diag_results]
        sorted_lat = sorted(latencies) if latencies else [0]
        p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)

        return {
            "top1_accuracy":       safe_mean([float(r.diagnostic.top1_correct) for r in diag_results]),
            "top3_accuracy":       safe_mean([float(r.diagnostic.top3_correct) for r in diag_results]),
            "top5_accuracy":       safe_mean([float(r.diagnostic.top5_correct) for r in diag_results]),
            "mrr":                 safe_mean([r.diagnostic.mrr for r in diag_results]),
            "emergency_recall":    safe_mean([float(r.diagnostic.emergency_flag_correct) for r in diag_results]),
            "citation_rate_mean":  safe_mean([r.diagnostic.citation_rate for r in diag_results]),
            "guideline_adherence": safe_mean([float(r.antibiotherapy.first_line_adherent) for r in tx_results]),
            "came_coverage":       safe_mean([float(r.antibiotherapy.came_available) for r in tx_results]),
            "disclaimer_rate":     safe_mean([float(r.antibiotherapy.disclaimer_present) for r in tx_results]),
            "p50_latency_ms":      float(sorted_lat[len(sorted_lat) // 2]),
            "p95_latency_ms":      float(sorted_lat[p95_idx]),
        }

    def _by_category(self, results: list[CaseResult]) -> dict[str, dict]:
        cats: dict[str, list[CaseResult]] = {}
        for r in results:
            cats.setdefault(r.category, []).append(r)
        return {cat: self._aggregate(rs) for cat, rs in cats.items()}

    async def run(self, cases: list[BenchmarkCase], model_version: str = "unknown") -> BenchmarkReport:
        log.info("Starting eval run: %d cases, concurrency=%d", len(cases), self.sem._value)
        tasks = [self._run_case(c) for c in cases]
        results: list[CaseResult] = await asyncio.gather(*tasks)

        # LLM judge passes (sample 20% to save cost)
        cit_judge_results, hall_judge_results = [], []
        if self.llm_judges:
            sample = [r for r in results if not r.error][::5]  # every 5th = ~20%
            judge_tasks = [
                judge_citation_quality(r.raw_response, self.api_key) for r in sample
            ] + [
                judge_hallucination(r.raw_response, self.api_key) for r in sample
            ]
            judge_outputs = await asyncio.gather(*judge_tasks, return_exceptions=True)
            mid = len(sample)
            cit_judge_results  = [o for o in judge_outputs[:mid] if not isinstance(o, Exception)]
            hall_judge_results = [o for o in judge_outputs[mid:] if not isinstance(o, Exception)]

        hall_fails = [j for j in hall_judge_results if j.get("verdict") in ("FAIL", "WARN")]
        hall_rate  = len(hall_fails) / max(1, len(hall_judge_results))

        agg = self._aggregate(results)
        report = BenchmarkReport(
            run_id=f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            model_version=model_version,
            total_cases=len(cases),
            results=results,
            hallucination_rate=hall_rate,
            citation_judge_results=cit_judge_results,
            hallucination_judge_results=hall_judge_results,
            by_category=self._by_category(results),
            by_difficulty=self._by_category(results),   # reuse grouper
            **agg,
        )
        return report
