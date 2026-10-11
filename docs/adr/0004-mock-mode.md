# ADR-0004: A deterministic mock LLM as a first-class provider

**Status:** accepted

## Context

Anyone evaluating the project should be able to run it with `docker compose up`, with no API key and no cost. CI needs deterministic results for the eval regression gate.

## Decision

`LLM_PROVIDER=mock` is the default. The mock is an explicit test double, not a fake model:

* routing uses keyword rules,
* knowledge answers are **extractive** (the best-supported sentences from the retrieved documents, with their IDs),
* customer and incident answers are the agents' fact-based drafts,
* action plans are parsed with regular expressions.

Everything else (retrieval, MCP, RBAC, approvals, guards, audit and tracing) is the production code path.

## Consequences

* Mock eval numbers measure the platform's plumbing and safety, not language quality. `docs/evaluation.md` says this explicitly, and real-model evals run nightly when a key is configured.
* `MOCK_TOKEN_DELAY_MS` adds labelled, simulated token pacing so the demo UI visibly streams.
