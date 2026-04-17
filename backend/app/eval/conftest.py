# ═══════════════════════════════════════════════════════════════
# conftest.py — pytest integration for CI
# ═══════════════════════════════════════════════════════════════

# In conftest.py:
# import pytest, asyncio, os
# from tropicare_eval.harness import EvalHarness, load_benchmark
#
# @pytest.fixture(scope="session")
# def benchmark():
#     return load_benchmark("tropicare_eval/data/benchmark_v1.json")
#
# @pytest.fixture(scope="session")
# def eval_report(benchmark):
#     harness = EvalHarness(
#         gateway_url=os.environ["EVAL_GATEWAY_URL"],
#         anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
#         concurrency=3,
#         enable_llm_judges=os.getenv("ENABLE_LLM_JUDGES", "0") == "1",
#     )
#     return asyncio.get_event_loop().run_until_complete(
#         harness.run(benchmark, model_version=os.getenv("MODEL_VERSION", "unknown"))
#     )

import pytest

@pytest.mark.eval
def test_top1_accuracy(eval_report):
    assert eval_report.top1_accuracy >= THRESHOLDS["top1_accuracy"], \
        f"top1={eval_report.top1_accuracy:.3f} < {THRESHOLDS['top1_accuracy']}"

@pytest.mark.eval
def test_top3_accuracy(eval_report):
    assert eval_report.top3_accuracy >= THRESHOLDS["top3_accuracy"]

@pytest.mark.eval
def test_citation_rate(eval_report):
    assert eval_report.citation_rate_mean >= THRESHOLDS["citation_rate_mean"], \
        f"citation_rate={eval_report.citation_rate_mean:.3f} < {THRESHOLDS['citation_rate_mean']}"

@pytest.mark.eval
def test_guideline_adherence(eval_report):
    assert eval_report.guideline_adherence >= THRESHOLDS["guideline_adherence"]

@pytest.mark.eval
def test_disclaimer_always_present(eval_report):
    assert eval_report.disclaimer_rate == 1.0, \
        "Every antibiotherapy response must include the disclaimer"

@pytest.mark.eval
def test_hallucination_rate(eval_report):
    assert eval_report.hallucination_rate <= THRESHOLDS["hallucination_rate"], \
        f"hallucination_rate={eval_report.hallucination_rate:.3f} exceeds 2% threshold"

@pytest.mark.eval
def test_p95_latency(eval_report):
    assert eval_report.p95_latency_ms <= THRESHOLDS["p95_latency_ms"], \
        f"p95={eval_report.p95_latency_ms:.0f}ms exceeds 8s threshold"

@pytest.mark.eval
def test_no_missing_emergency_flags(eval_report):
    assert eval_report.emergency_recall >= 1.0, \
        "All emergency cases must trigger emergency_flag"
