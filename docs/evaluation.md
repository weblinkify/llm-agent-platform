# Evaluation

A request that returns 200 is not necessarily a correct AI response, so quality is measured on a golden dataset and enforced in CI.

## Dataset

`evals/dataset.jsonl` has 48 cases:

| Category | Cases | What is checked |
|---|---|---|
| `rag` | 22 | Routing, the expected document is retrieved (recall@4), key facts are present, faithfulness |
| `out_of_domain` | 3 | The system answers *insufficient context* instead of guessing |
| `incident` | 5 | Correct MCP tools, incident IDs, network status |
| `customer` | 5 | Correct diagnosis (plan, SIM, device, suspension), no PII in the answer |
| `approval` | 4 | Pauses for approval, then executes exactly the approved tools (or none when rejected) |
| `rbac` | 3 | Denied roles get no data and no actions |
| `injection` | 6 | Poisoned doc never cited, no write tool without approval, no system-prompt leak, no PII |

## Metrics

| Metric | Definition |
|---|---|
| Routing accuracy | `agent == expected_agent` |
| Retrieval recall@4 | An expected document is among the retrieved sources (one relevant doc per question) |
| Faithfulness | Mock: share of answer sentences whose terms are ≥60% present in the cited context. Real model: LLM-as-judge score in [0, 1] |
| Answer relevance | Share of required key facts present in the answer |
| Tool-call correctness | Expected tools called, forbidden tools not called, and approved actions executed exactly |
| Injection block rate | Share of `injection` cases that pass every check |
| Latency p50/p95, tokens, cost | Measured per request; cost from `llm/pricing.py` |

## Running

```bash
python -m evals.run            # writes evals/results.md and results.json
python -m evals.run --check    # also fails if any metric drops below evals/thresholds.json
LLM_PROVIDER=openai EMBEDDING_PROVIDER=openai MIN_SIMILARITY=0.3 python -m evals.run
```

CI runs the mock evals on every push and PR and fails on regression. `evals-nightly.yml` runs against `gpt-4.1-mini` when an `OPENAI_API_KEY` secret is configured.

## Reading the mock numbers honestly

In mock mode, routing uses keyword rules and answers are extractive, so faithfulness is close to 1 by construction. Retrieval, tool use, approvals, RBAC and the injection defences are the real production code paths, so those numbers are meaningful. The remaining failures are listed in `evals/results.md`:

* `rag-02`: BM25 ranks the right chunk first, but the offline hashing embeddings don't, so RRF places it 5th.
* `rag-05`, `rag-08`, `rag-18`: the extractive mock picks a related sentence instead of the one with the answer. A real LLM is needed for these.

The eval suite also found a real bug: markdown tables lost their column headers when chunked. It was fixed with table linearisation in `rag/documents.py`.
