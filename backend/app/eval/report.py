# ═══════════════════════════════════════════════════════════════
# report.py — JSON + console report
# ═══════════════════════════════════════════════════════════════

THRESHOLDS = {
    "top1_accuracy":       0.82,
    "top3_accuracy":       0.94,
    "citation_rate_mean":  0.95,
    "guideline_adherence": 0.90,
    "disclaimer_rate":     1.00,
    "hallucination_rate":  0.02,  # max allowed
    "p95_latency_ms":  8000.0,
}

def print_report(report: BenchmarkReport) -> None:
    print(f"\n{'═'*60}")
    print(f" TropiCare Eval — {report.run_id}")
    print(f" Model: {report.model_version} | Cases: {report.total_cases}")
    print(f"{'═'*60}")

    metrics = {
        "top1_accuracy":       report.top1_accuracy,
        "top3_accuracy":       report.top3_accuracy,
        "mrr":                 report.mrr,
        "citation_rate_mean":  report.citation_rate_mean,
        "guideline_adherence": report.guideline_adherence,
        "disclaimer_rate":     report.disclaimer_rate,
        "hallucination_rate":  report.hallucination_rate,
        "p95_latency_ms":      report.p95_latency_ms,
    }

    all_pass = True
    for key, val in metrics.items():
        threshold = THRESHOLDS.get(key)
        if threshold is None:
            status = "  "
        elif key == "hallucination_rate" or key == "p95_latency_ms":
            # Lower is better
            status = "✅" if val <= threshold else "❌"
            if val > threshold: all_pass = False
        else:
            status = "✅" if val >= threshold else "❌"
            if val < threshold: all_pass = False

        thresh_str = f"(threshold: {'≤' if key in ('hallucination_rate','p95_latency_ms') else '≥'}{threshold})" if threshold else ""
        print(f" {status}  {key:<28} {val:.3f}  {thresh_str}")

    print(f"\n Category breakdown:")
    for cat, m in report.by_category.items():
        print(f"   {cat:<16} top1={m.get('top1_accuracy',0):.2f}  "
              f"top3={m.get('top3_accuracy',0):.2f}  "
              f"cit={m.get('citation_rate_mean',0):.2f}")

    errors = [r for r in report.results if r.error]
    if errors:
        print(f"\n ⚠ {len(errors)} cases failed:")
        for r in errors[:5]:
            print(f"   {r.case_id}: {r.error}")

    print(f"\n Overall: {'✅ PASS' if all_pass else '❌ FAIL — see failures above'}")
    print(f"{'═'*60}\n")

def save_report(report: BenchmarkReport, output_dir: str = "eval_reports") -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{report.run_id}.json"
    path.write_text(json.dumps(asdict(report), indent=2, default=str))
    log.info("Report saved to %s", path)
    return path