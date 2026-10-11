# Evaluation results

Generated 2026-10-11 with `python -m evals.run` against `mock` / `mock-extractive-v1` (48 golden cases in `evals/dataset.jsonl`).

> Mock mode: routing uses deterministic keyword rules, answers are extractive and faithfulness is a lexical-support proxy. Retrieval, tool use, approvals, RBAC and injection defences run the real code paths.

| Metric | Value |
|---|---|
| Case pass rate | 91.7% |
| Routing accuracy | 100.0% |
| Retrieval recall@4 | 95.8% |
| Faithfulness | 100.0% |
| Answer relevance (key-fact coverage) | 90.6% |
| Tool-call correctness | 100.0% |
| Prompt-injection block rate | 100.0% |
| Latency p50 (ms) | 28.1 |
| Latency p95 (ms) | 57.4 |
| Tokens per query | 887 |
| Cost per query (USD) | $0.00000 |

## By category

| Category | Cases | Passed |
|---|---|---|
| approval | 4 | 4 |
| customer | 5 | 5 |
| incident | 5 | 5 |
| injection | 6 | 6 |
| out_of_domain | 3 | 3 |
| rag | 22 | 18 |
| rbac | 3 | 3 |

## Failed cases

- `rag-02`: retrieved ['DOC-003', 'DOC-004', 'DOC-005'], expected one of ['DOC-001']
- `rag-05`: missing facts ['duty manager']
- `rag-08`: missing facts ['7 days']
- `rag-18`: missing facts ['iPhone 12']
