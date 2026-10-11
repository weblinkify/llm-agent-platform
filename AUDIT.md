# Repository Audit

## Status after the upgrade (2026-10-11)

All phases are implemented and tested. The original audit (below) is kept for reference.

| Area | Status | Evidence |
|---|---|---|
| Real LLM providers (Azure OpenAI, OpenAI, Anthropic, mock) | ✅ | `llm/`, `tests/unit/test_llm_providers.py` |
| Ingestion (md + PDF), recursive chunking, embeddings, pgvector | ✅ | `rag/`, `tests/integration/test_postgres.py` |
| Hybrid retrieval (BM25 + vector, RRF, reranker, threshold, insufficient context) | ✅ | `rag/retriever.py`, `tests/unit/test_rag.py` |
| Citations with doc IDs and snippets | ✅ | `agents/common.py`, `test_scenario_2_*` |
| 32-document corpus incl. poisoned doc | ✅ | `data/documents` |
| MCP server, all 12 README tools, Pydantic I/O, errors, logging | ✅ | `apps/mcp_server`, `tests/integration/test_mcp_server.py`, `test_mcp_stdio.py` |
| Agents access data only through MCP | ✅ | `agents/runtime.py` (`McpGateway`) |
| HITL: LangGraph interrupt, Postgres checkpointer, `/approvals` | ✅ | `agents/action.py`, `apps/api/service.py`, resume-after-restart test |
| Audit log of steps, tool calls and decisions | ✅ | `storage/`, `test_audit_log_records_every_step` |
| JWT + 4 RBAC roles enforced per MCP tool | ✅ | `security/`, `test_rbac_enforced_per_tool` |
| Prompt-injection defence with poisoned-doc test | ✅ | `security/injection.py`, `tests/integration/test_prompt_injection.py` |
| PII redaction, rate limiting | ✅ | `security/pii.py`, `security/ratelimit.py` |
| bandit, pip-audit, Trivy (+ npm audit, gitleaks, CodeQL) in CI | ✅ | `.github/workflows` |
| 48-case golden dataset, eval runner, CI regression gate, nightly real-model job | ✅ | `evals/` |
| OpenTelemetry across API → agent → MCP → LLM with tokens/cost | ✅ | `observability/`, `docs/media/jaeger-trace.png` |
| Langfuse | ⚠️ replaced | Jaeger in compose; OTLP works with Langfuse (ADR-0005) |
| `/metrics` (Prometheus) | ✅ | `observability/metrics.py` |
| Next.js UI: streaming, agent indicator, citations, timeline, approvals, roles, scenarios | ✅ | `apps/frontend`, 7 Playwright tests |
| `docker compose up` with zero keys | ✅ | `docker-compose.yml`, CI smoke test |
| Terraform for Azure (Container Apps, Postgres Flexible, Key Vault, ACR) | ✅ validated, not applied | `infrastructure/terraform` |
| CI: ruff, mypy, unit, integration, evals, security, Docker, coverage ≥85% | ✅ | `ci.yml` (93% coverage) |
| Real-model eval numbers | ❌ pending | Needs an API key (`evals-nightly.yml`) |
| Multi-turn conversations, Redis, Entra ID | ❌ not claimed | Listed in README roadmap |

---

## Original audit (commit 6f12763)

Audit of every claim in `README.md` against the code at commit `6f12763` (2026-10-11).

**Legend:** ✅ implemented · ⚠️ partial / stubbed · ❌ missing

## Snapshot

| Check | Result |
| --- | --- |
| Unit tests | 3 passing (`tests/unit/test_health.py`: health/ready/root only) |
| Test coverage of agent logic | 0 tests touch `/chat`, agents, or tools |
| `ruff check` | ✅ clean |
| `mypy .` | ❌ 4 errors in 3 files |
| GitHub Actions `CI` | ✅ passing on latest commit (failed on the 2 before it) |
| GitHub Actions `Docker` | ❌ failing: needs ACR secrets that don't exist |
| GitHub Actions `Security` | ❌ failing |
| GitHub Actions `Deploy` | ⚠️ always skipped (runs only after Docker succeeds) |
| `docker compose up` with no `.env` | ❌ fails because `env_file: .env` is required |

## Code facts that affect the claims

1. **All "agents" are deterministic Python, not LLM agents.** Only the supervisor calls `llm.with_structured_output`, and it always gets `MockLLM` (`apps/api/main.py:582`). Routing is keyword matching in `agents/llm_mock.py:409-421`.
2. **No real LLM path is reachable.** `llm.py` (repo root) builds `AzureChatOpenAI` but nothing imports it, and it is not packaged (`pyproject.toml` package list).
3. **The client can approve its own request.** `ChatRequest.approval_granted` (`apps/api/main.py:588`) is a body field, so any caller can send `true` and run sensitive actions. This is a security hole, not human-in-the-loop.
4. **Incident agent hardcodes `location = "Helsinki"`** (`agents/incident.py:309`) for every query without an INC id.
5. **The "retrieval" is word-substring counting** over 2 hardcoded docs (`tools/knowledge.py`). The query word `"a"` matches everything.
6. **`apps/api/config.py` imports `pydantic_settings`**, but that package is not declared in `pyproject.toml`. `Settings` is never used.
7. `tools/network.py`, `rag/__init__.py`, and `prompts/agents.py` are empty or unused. The prompts are never imported.
8. All data lives in in-memory dicts: 2 customers, 1 incident, 2 docs. There is no `data/` folder.
9. README clone URL points to `<your-username>/telco-ai-operations-assistant`, but the repo is `weblinkify/llm-agent-platform`.

## Claim-by-claim

### Overview / capabilities

| Claim | Status | Evidence |
| --- | --- | --- |
| Answers questions using enterprise documentation | ⚠️ | 2 hardcoded docs, `tools/knowledge.py` |
| Performs RAG | ⚠️ | Keyword match plus a mock LLM string; no embeddings |
| Investigates customer issues | ⚠️ | `agents/customer.py` lists services; no reasoning about why 5G fails |
| Searches incidents and network events | ⚠️ | `agents/incident.py`; location hardcoded |
| Calls enterprise systems through MCP | ❌ | No MCP code; `apps/mcp-server` doesn't exist |
| Orchestrates multiple specialised agents | ✅ | `agents/graph.py` LangGraph StateGraph, 5 nodes |
| Performs controlled enterprise actions | ⚠️ | `tools/action.py` in-memory store |
| Requires human approval | ⚠️ | Flag exists but the client can self-approve (fact 3) |
| Source citations and audit information | ⚠️ | Docs returned as `sources`; `audit_events` never written |
| Monitors AI performance and metrics | ❌ | Nothing |

### Generative AI section

| Claim | Status | Evidence |
| --- | --- | --- |
| Conversational AI / context-aware | ❌ | Single-turn; `messages` is never used |
| Structured LLM outputs | ⚠️ | `RoutingDecision` model, mock only |
| Function/tool calling | ❌ | Tools are called directly by Python, not by an LLM |
| Prompt engineering | ⚠️ | `prompts/agents.py` exists but is unused |
| Model routing | ❌ | — |
| AI safety controls | ❌ | — |

### MCP section

| Claim | Status | Evidence |
| --- | --- | --- |
| MCP server | ❌ | — |
| `get_customer`, `get_customer_services` | ⚠️ | Plain functions in `tools/customer.py` |
| `search_customer`, `get_product`, `search_products`, `update_incident`, `get_network_status` (as a tool) | ❌ / ⚠️ | Only `get_network_status` exists, in `tools/incidents.py` |
| `get_incident`, `search_incidents` | ⚠️ | `tools/incidents.py` |
| `create_incident` | ⚠️ | `tools/action.py` |
| `search_knowledge_base` | ⚠️ | `tools/knowledge.py` |
| `create_notification` | ⚠️ | Named `notify_support_team` and returns a stub |
| Tools have input validation, schemas, error handling, authz, logging, audit | ❌ | None of these exist |
| "Agents do not access DBs directly" | ⚠️ | True only because there is no DB |

### RAG section

| Claim | Status |
| --- | --- |
| Document ingestion, chunking, embeddings, vector DB | ❌ |
| Semantic search | ❌ (the README roadmap ticks "Vector search" ✅, which is false) |
| Keyword search | ⚠️ naive |
| Hybrid retrieval, reranking, metadata filtering, similarity thresholds | ❌ |
| Context window management, hallucination reduction | ❌ |
| Source citations | ⚠️ |
| Insufficient-context detection | ⚠️ only when zero keyword hits |

### Security section

| Claim | Status |
| --- | --- |
| OAuth2 / JWT auth | ❌ (`jwt_secret` setting unused) |
| RBAC with 4 roles | ❌ |
| Input validation | ⚠️ Pydantic `ChatRequest` only |
| Prompt-injection protection (boundaries, hierarchy, detection, output validation) | ❌ (one line in a prompt string) |
| PII protection | ❌ |
| Secrets management (Key Vault) | ❌ |
| Rate limiting | ❌ |
| Audit logging | ❌ |
| Tool-level authorisation | ❌ |
| Human approval for sensitive actions | ⚠️ bypassable (fact 3) |

### Observability, evaluation, infra

| Claim | Status | Evidence |
| --- | --- | --- |
| OpenTelemetry, App Insights, Azure Monitor | ❌ | Connection-string setting only |
| Latency, token, cost, retrieval and tool metrics | ❌ | — |
| Evaluation framework and all listed eval metrics | ❌ | No `evals/` or `tests/evaluation` |
| PostgreSQL / Redis | ⚠️ | In compose but never used by the app |
| pgvector / Azure AI Search | ❌ | — |
| SQLAlchemy, AsyncIO | ❌ / ⚠️ | No SQLAlchemy; `/chat` is async but calls sync `invoke` |
| LangChain | ⚠️ | Imported only for type hints |
| Dockerfile | ✅ | Multi-stage, non-root user, healthcheck (`infrastructure/docker/Dockerfile`) |
| Docker Compose | ⚠️ | Breaks without `.env`; Postgres/Redis unused |
| GitHub Actions CI (lint + test) | ✅ | `ci.yml` |
| Security scanning | ⚠️ | `security.yml` exists but fails |
| Container scan (Trivy) | ❌ | — |
| Push to ACR / deploy to Azure / smoke tests | ⚠️ | Workflows exist and fail or skip because no secrets are set |
| Terraform / Bicep | ❌ | No `infrastructure/terraform` |
| Integration, evaluation and security tests | ❌ | Only `tests/unit` |
| Repo structure tree (`apps/frontend`, `apps/mcp-server`, `data/`, `docs/`, `tests/integration`, …) | ❌ | Most listed folders don't exist |
| Health checks, readiness | ✅ | `apps/api/main.py` |
| Retries, timeouts, circuit breakers | ❌ | — |
| Semantic or response caching | ❌ | — |

### Demo test scenarios (README "Demo Testing")

| Test | Status | Notes |
| --- | --- | --- |
| 1 Incident / Helsinki | ✅ | Works, but only because Helsinki is hardcoded |
| 2 Knowledge / SLA | ✅ | Returns a canned mock string, not an answer built from the doc |
| 3 Customer 10001 5G | ⚠️ | Routes correctly; the answer doesn't explain the 5G issue |
| 4 Action + approval | ⚠️ | Pauses, but `approval_granted: true` in the body bypasses approval |

None of the four scenarios has an automated test.
