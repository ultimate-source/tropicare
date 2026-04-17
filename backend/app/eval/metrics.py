# ═══════════════════════════════════════════════════════════════
# metrics.py — All metric computations
# ═══════════════════════════════════════════════════════════════

@dataclass
class DiagnosticMetrics:
    top1_correct:  bool
    top3_correct:  bool
    top5_correct:  bool
    expected_rank: int | None   # actual rank returned (None = not found)
    confidence_at_top1: float
    mrr: float                  # Mean Reciprocal Rank contribution (1/rank or 0)
    emergency_flag_correct: bool
    citation_count: int
    citation_rate: float        # citations / total claims (estimated)
    latency_ms: int

@dataclass
class AntibiotherapyMetrics:
    first_line_adherent: bool     # ≥1 expected drug in first_line
    came_available:      bool
    no_contraindicated:  bool     # none of must_exclude present
    disclaimer_present:  bool
    citation_count:      int
    latency_ms:          int

@dataclass
class CaseResult:
    case_id: str
    category: str
    difficulty: str
    diagnostic: DiagnosticMetrics | None
    antibiotherapy: AntibiotherapyMetrics | None
    raw_response: dict[str, Any]
    error: str | None = None

def compute_diagnostic_metrics(
    case: BenchmarkCase,
    response: dict[str, Any],
    latency_ms: int,
) -> DiagnosticMetrics:
    diff = response.get("differential", [])
    returned_codes = [d.get("icd11_code", "") for d in diff]
    returned_names = [d.get("disease_name", "").lower() for d in diff]

    def matches(gt: GroundTruthDiagnosis) -> int | None:
        """Return 1-indexed rank of match, or None."""
        for i, (code, name) in enumerate(zip(returned_codes, returned_names), 1):
            if gt.icd11_code and code == gt.icd11_code:
                return i
            if gt.disease_name.lower() in name or name in gt.disease_name.lower():
                return i
        return None

    # Primary ground truth = rank_expected == 1
    primary_gts = [g for g in case.ground_truth_diagnoses if g.rank_expected == 1]
    primary_gt  = primary_gts[0] if primary_gts else None

    actual_rank: int | None = None
    if primary_gt:
        actual_rank = matches(primary_gt)

    top1 = actual_rank == 1
    top3 = actual_rank is not None and actual_rank <= 3
    top5 = actual_rank is not None and actual_rank <= 5
    mrr  = (1 / actual_rank) if actual_rank else 0.0

    confidence_top1 = diff[0].get("confidence", 0.0) if diff else 0.0
    citations = response.get("citations", [])
    claims_est = max(1, len(diff) * 3)  # rough estimate: 3 claims per diff item

    emergency_correct = True
    if case.emergency_expected:
        emergency_correct = len(response.get("emergency_flags", [])) > 0

    return DiagnosticMetrics(
        top1_correct=top1,
        top3_correct=top3,
        top5_correct=top5,
        expected_rank=actual_rank,
        confidence_at_top1=confidence_top1,
        mrr=mrr,
        emergency_flag_correct=emergency_correct,
        citation_count=len(citations),
        citation_rate=min(1.0, len(citations) / claims_est),
        latency_ms=latency_ms,
    )

def compute_antibiotherapy_metrics(
    case: BenchmarkCase,
    response: dict[str, Any],
    latency_ms: int,
) -> AntibiotherapyMetrics | None:
    if not case.ground_truth_treatment:
        return None
    gt = case.ground_truth_treatment
    tx = response.get("treatment", {})
    first_line = tx.get("first_line", [])
    fl_names = {d.get("generic_name", "").lower() for d in first_line}
    expected = {d.lower() for d in gt.first_line_drugs}
    excluded  = {d.lower() for d in gt.must_exclude}

    adherent  = bool(fl_names & expected)
    came_ok   = any(d.get("came_available") for d in first_line)
    no_contra = not bool(fl_names & excluded)
    disclaimer= bool(tx.get("disclaimer"))
    citations = response.get("citations", [])

    return AntibiotherapyMetrics(
        first_line_adherent=adherent,
        came_available=came_ok,
        no_contraindicated=no_contra,
        disclaimer_present=disclaimer,
        citation_count=len(citations),
        latency_ms=latency_ms,
    )