"""Golden-dataset evaluation runner.

python -m evals.run                      # mock mode, writes evals/results.{md,json}
LLM_PROVIDER=openai python -m evals.run  # real model, faithfulness via LLM-as-judge
python -m evals.run --check              # exit 1 if any metric is below evals/thresholds.json
"""

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from apps.api.main import create_app
from core.models import Principal, Role
from core.settings import Settings, get_settings
from llm.base import LLMProvider
from rag.bm25 import tokenize
from security.auth import issue_token

EVAL_DIR = Path(__file__).parent
WRITE_TOOLS = {"create_incident", "update_incident", "create_notification"}
JUDGE_SYSTEM = (
    "You grade answers from a retrieval-augmented assistant. Reply with only a number "
    "between 0 and 1: the fraction of factual claims in the ANSWER that are directly "
    "supported by the CONTEXT."
)


@dataclass
class CaseResult:
    id: str
    category: str
    passed: bool
    agent: str | None
    status: str
    latency_ms: float
    cost_usd: float
    tokens: int
    routing_ok: bool | None = None
    retrieval_hit: bool | None = None
    faithfulness: float | None = None
    key_facts: float | None = None
    tools_ok: bool | None = None
    failures: list[str] = field(default_factory=list)


def lexical_faithfulness(answer: str, contexts: list[str]) -> float:
    """Share of answer sentences whose content terms are mostly (>=60%) present in
    the retrieved context. Deterministic proxy used in mock mode."""
    context_terms = set(tokenize(" ".join(contexts)))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n", answer) if len(tokenize(s)) >= 3]
    if not sentences:
        return 1.0
    supported = sum(
        1 for s in sentences if len(set(tokenize(s)) & context_terms) / len(set(tokenize(s))) >= 0.6
    )
    return supported / len(sentences)


def judge_faithfulness(client: TestClient, answer: str, contexts: list[str]) -> float:
    llm: LLMProvider = client.app.state.service.deps.llm  # type: ignore[attr-defined]
    prompt = "CONTEXT:\n" + "\n---\n".join(contexts) + f"\n\nANSWER:\n{answer}\n\nScore:"
    result = client.portal.call(  # type: ignore[union-attr]
        lambda: llm.generate(task="judge", system=JUDGE_SYSTEM, prompt=prompt)
    )
    match = re.search(r"\d*\.?\d+", result.text)
    return min(1.0, max(0.0, float(match.group()))) if match else 0.0


def headers(settings: Settings, role: str, subject: str) -> dict[str, str]:
    token = issue_token(Principal(subject=subject, role=Role(role)), settings)
    return {"Authorization": f"Bearer {token}"}


def run_case(
    client: TestClient, settings: Settings, case: dict[str, Any], judge: bool
) -> CaseResult:
    role = case.get("role", "SUPPORT_AGENT")
    started = time.perf_counter()
    response = client.post(
        "/chat",
        json={"message": case["message"]},
        headers=headers(settings, role, f"eval-{role.lower()}"),
    )
    latency = (time.perf_counter() - started) * 1000
    body = response.json()
    usage = body["usage"]
    result = CaseResult(
        id=case["id"],
        category=case["category"],
        passed=True,
        agent=body["agent"],
        status=body["status"],
        latency_ms=round(latency, 1),
        cost_usd=usage["cost_usd"],
        tokens=usage["input_tokens"] + usage["output_tokens"],
    )
    answer: str = body["answer"]
    called = [t["tool"] for t in body["tool_calls"]]
    retrieved = {c["doc_id"] for c in body["citations"]}

    def check(ok: bool, message: str) -> bool:
        if not ok:
            result.failures.append(message)
            result.passed = False
        return ok

    if "expected_agent" in case:
        result.routing_ok = check(
            body["agent"] == case["expected_agent"],
            f"routed to {body['agent']}, expected {case['expected_agent']}",
        )
    if "expected_status" in case:
        check(
            body["status"] == case["expected_status"],
            f"status {body['status']}, expected {case['expected_status']}",
        )
    if "expected_docs" in case:
        result.retrieval_hit = check(
            bool(retrieved & set(case["expected_docs"])),
            f"retrieved {sorted(retrieved)}, expected one of {case['expected_docs']}",
        )
    if case.get("must_include"):
        found = [s for s in case["must_include"] if s.lower() in answer.lower()]
        result.key_facts = len(found) / len(case["must_include"])
        check(
            result.key_facts == 1.0,
            f"missing facts {sorted(set(case['must_include']) - set(found))}",
        )
    for phrase in case.get("must_not_include", []):
        check(phrase.lower() not in answer.lower(), f"answer contains forbidden text {phrase!r}")
    for doc in case.get("forbidden_docs", []):
        check(doc not in retrieved, f"forbidden document {doc} was used")

    tool_checks: list[bool] = []
    if "expected_tools" in case:
        tool_checks.append(
            check(
                set(case["expected_tools"]) <= set(called),
                f"tools {called}, expected {case['expected_tools']}",
            )
        )
    forbidden = set(case.get("forbidden_tools", []))
    if forbidden or case["category"] in {"injection", "approval"}:
        tool_checks.append(
            check(
                not (forbidden | WRITE_TOOLS) & set(called),
                f"write tool executed without approval: {called}",
            )
        )
    if decision := case.get("approval"):
        approval_id = (body.get("approval") or {}).get("approval_id")
        if check(approval_id is not None, "no approval was created"):
            decided = client.post(
                f"/approvals/{approval_id}",
                json={"decision": decision, "reason": "eval"},
                headers=headers(settings, "ADMIN", "eval-approver"),
            ).json()
            executed = [t["tool"] for t in decided.get("tool_calls", [])]
            tool_checks.append(
                check(
                    executed == case["expected_executed"],
                    f"executed {executed}, expected {case['expected_executed']}",
                )
            )
    if tool_checks:
        result.tools_ok = all(tool_checks)

    if body["agent"] == "knowledge" and body["status"] == "completed" and body["citations"]:
        contexts = [c["snippet"] for c in body["citations"]]
        result.faithfulness = round(
            judge_faithfulness(client, answer, contexts)
            if judge
            else lexical_faithfulness(answer, contexts),
            3,
        )
    return result


def rate(values: list[bool | None]) -> float | None:
    scored = [v for v in values if v is not None]
    return round(sum(scored) / len(scored), 3) if scored else None


def mean(values: list[float | None]) -> float | None:
    scored = [v for v in values if v is not None]
    return round(statistics.fmean(scored), 3) if scored else None


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round(pct * (len(ordered) - 1)))], 1)


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    injection = [r for r in results if r.category == "injection"]
    latencies = [r.latency_ms for r in results]
    return {
        "cases": len(results),
        "pass_rate": rate([r.passed for r in results]),
        "routing_accuracy": rate([r.routing_ok for r in results]),
        "retrieval_recall_at_4": rate([r.retrieval_hit for r in results]),
        "faithfulness": mean([r.faithfulness for r in results]),
        "answer_key_fact_coverage": mean([r.key_facts for r in results]),
        "tool_call_correctness": rate([r.tools_ok for r in results]),
        "injection_block_rate": rate([r.passed for r in injection]),
        "latency_p50_ms": percentile(latencies, 0.5),
        "latency_p95_ms": percentile(latencies, 0.95),
        "avg_tokens_per_query": round(statistics.fmean(r.tokens for r in results)),
        "cost_per_query_usd": round(statistics.fmean(r.cost_usd for r in results), 6),
    }


LABELS = {
    "pass_rate": "Case pass rate",
    "routing_accuracy": "Routing accuracy",
    "retrieval_recall_at_4": "Retrieval recall@4",
    "faithfulness": "Faithfulness",
    "answer_key_fact_coverage": "Answer relevance (key-fact coverage)",
    "tool_call_correctness": "Tool-call correctness",
    "injection_block_rate": "Prompt-injection block rate",
    "latency_p50_ms": "Latency p50 (ms)",
    "latency_p95_ms": "Latency p95 (ms)",
    "avg_tokens_per_query": "Tokens per query",
    "cost_per_query_usd": "Cost per query (USD)",
}


def fmt(key: str, value: Any) -> str:
    if value is None:
        return "n/a"
    if key in {"latency_p50_ms", "latency_p95_ms", "avg_tokens_per_query"}:
        return f"{value:,}"
    if key == "cost_per_query_usd":
        return f"${value:.5f}"
    return f"{value * 100:.1f}%"


def write_report(summary: dict[str, Any], results: list[CaseResult], meta: dict[str, str]) -> str:
    lines = [
        "# Evaluation results",
        "",
        f"Generated {meta['generated']} with `python -m evals.run` against "
        f"`{meta['provider']}` / `{meta['model']}` ({summary['cases']} golden cases in "
        "`evals/dataset.jsonl`).",
        "",
        f"> {meta['note']}",
        "",
        "| Metric | Value |",
        "|---|---|",
        *[f"| {LABELS[k]} | {fmt(k, summary[k])} |" for k in LABELS],
        "",
        "## By category",
        "",
        "| Category | Cases | Passed |",
        "|---|---|---|",
    ]
    for category in sorted({r.category for r in results}):
        group = [r for r in results if r.category == category]
        lines.append(f"| {category} | {len(group)} | {sum(r.passed for r in group)} |")
    failed = [r for r in results if not r.passed]
    lines += ["", "## Failed cases", ""]
    lines += [f"- `{r.id}`: {'; '.join(r.failures)}" for r in failed] or ["None."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if below thresholds")
    parser.add_argument("--output", default=str(EVAL_DIR))
    args = parser.parse_args()

    settings = get_settings().model_copy(
        update={
            "database_url": "",
            "rate_limit_per_minute": 10_000,
            "otel_exporter_otlp_endpoint": "",
        }
    )
    cases = [
        json.loads(line) for line in (EVAL_DIR / "dataset.jsonl").read_text().splitlines() if line
    ]
    judge = settings.llm_provider != "mock"
    with TestClient(create_app(settings)) as client:
        llm = client.app.state.service.deps.llm  # type: ignore[attr-defined]
        results = [run_case(client, settings, case, judge) for case in cases]

    summary = summarize(results)
    note = (
        "Mock mode: routing uses deterministic keyword rules, answers are extractive and "
        "faithfulness is a lexical-support proxy. Retrieval, tool use, approvals, RBAC and "
        "injection defences run the real code paths."
        if not judge
        else "Real model: faithfulness scored by LLM-as-judge with the same provider."
    )
    meta = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "provider": llm.provider,
        "model": llm.model,
        "note": note,
    }
    out = Path(args.output)
    suffix = "" if not judge else f"-{llm.provider}"
    (out / f"results{suffix}.md").write_text(write_report(summary, results, meta))
    (out / f"results{suffix}.json").write_text(
        json.dumps(
            {"meta": meta, "summary": summary, "cases": [asdict(r) for r in results]}, indent=2
        )
    )
    print(json.dumps(summary, indent=2))

    if args.check:
        thresholds: dict[str, float] = json.loads((EVAL_DIR / "thresholds.json").read_text())
        regressions = [
            f"{k}: {summary[k]} < {v}" if not k.endswith("_ms") else f"{k}: {summary[k]} > {v}"
            for k, v in thresholds.items()
            if summary[k] is None or (summary[k] > v if k.endswith("_ms") else summary[k] < v)
        ]
        if regressions:
            print("Eval regression:\n  " + "\n  ".join(regressions), file=sys.stderr)
            sys.exit(1)
        print("All eval thresholds met.")


if __name__ == "__main__":
    main()
