# Telco AI Operations Assistant

**A multi-agent AI assistant for telecom support and NOC teams. It answers from your runbooks with citations, investigates customers and incidents through MCP tools, and executes changes only after a human approves them.**

[![CI](https://github.com/weblinkify/llm-agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/weblinkify/llm-agent-platform/actions/workflows/ci.yml)
[![Security](https://github.com/weblinkify/llm-agent-platform/actions/workflows/security.yml/badge.svg)](https://github.com/weblinkify/llm-agent-platform/actions/workflows/security.yml)
![Coverage](https://img.shields.io/badge/coverage-93%25%20(CI%20gate%2085%25)-brightgreen)
![Evals](https://img.shields.io/badge/evals-44%2F48%20passing-blue)
![Python](https://img.shields.io/badge/python-3.12-3776AB)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-7C3AED)
![MCP](https://img.shields.io/badge/MCP-official%20SDK-F97316)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**▶ Live demo:** __DEMO_URL__ (mock mode, no sign-up: switch roles in the sidebar)
**🎥 2-minute walkthrough:** _Loom video coming soon_

![Approval flow: a support agent asks the AI to create an incident; the graph pauses; an admin approves; the MCP tools execute](docs/media/demo.gif)

<sub>The GIF shows a support agent requesting an incident and notification. The LangGraph run pauses at an interrupt, an admin approves from the inbox (requesters can't approve their own actions), and only then do the MCP write tools execute.</sub>

---

## What this proves for your business

- **Cuts L1 support load.** Agents get cited answers from SLAs and runbooks, plus customer diagnoses like *"plan isn't 5G-enabled and the SIM is legacy, so offer MOB-5G-PLUS and a free USIM-5G swap"*, in seconds instead of a ticket escalation.
- **Safe AI actions.** The AI can *propose* creating incidents or paging teams, but writes run only after a different authorised human approves. This is enforced by the MCP server, not by a prompt.
- **Measurable quality.** A 48-case golden eval suite (routing, retrieval, faithfulness, tool use, injection attacks) runs on every PR and blocks regressions.
- **Enterprise security.** JWT auth, four RBAC roles enforced per tool, prompt-injection quarantine (tested with a poisoned document), PII masking before the LLM, rate limiting and a full audit log.
- **Deployable on your Azure.** Docker images, Terraform for Container Apps, Postgres/pgvector, Key Vault and ACR, plus OpenTelemetry traces. Azure OpenAI, OpenAI and Anthropic are a one-line switch.

## Evaluation results

48 golden cases (`evals/dataset.jsonl`), run with `python -m evals.run` and gated in CI. Full report: [`evals/results.md`](evals/results.md).

| Metric | Mock mode (CI) |
|---|---|
| Routing accuracy | **100%** |
| Retrieval recall@4 | **95.8%** |
| Tool-call correctness (incl. approvals) | **100%** |
| Prompt-injection block rate (6 attacks) | **100%** |
| Answer key-fact coverage | 90.6% |
| Faithfulness (lexical proxy) | 100% |
| Latency p50 / p95 | 27 ms / 61 ms |

> **What these numbers mean:** in mock mode the LLM is a deterministic test double (keyword routing, extractive answers), so this table measures the platform: retrieval, MCP tools, RBAC, approvals and injection defences. Real-model runs (`gpt-4.1-mini`, LLM-as-judge faithfulness) are wired into a nightly workflow that runs once an `OPENAI_API_KEY` secret is added. The four failing cases are listed and explained in [docs/evaluation.md](docs/evaluation.md).

## Architecture

```mermaid
flowchart LR
    UI["Next.js console<br/>streaming · approvals · RBAC"] -->|JWT, SSE| API[FastAPI]
    API --> SUP{{"Supervisor<br/>(LangGraph)"}}
    SUP --> K[Knowledge agent]
    SUP --> C[Customer agent]
    SUP --> I[Incident agent]
    SUP --> A[Action agent]
    A -->|"interrupt()"| H(("Human<br/>approval"))
    H -->|"Command(resume)"| A
    K & C & I & A --> G[Output guard]
    K & C & I & A -->|"MCP tools/call<br/>+ JWT / approval grant"| MCP[["MCP server<br/>12 tools · RBAC"]]
    MCP --> SYS[(CRM · catalogue ·<br/>incidents · network)]
    MCP --> RAG["Hybrid RAG<br/>BM25 + pgvector · RRF"]
    API --> PG[(Postgres<br/>checkpoints · audit · approvals)]
    API & MCP -. OTLP .-> OBS[Jaeger / OTel]
    SUP & K & C & I & A -.-> LLM["LLM: Azure OpenAI ·<br/>OpenAI · Anthropic · mock"]
```

More detail: [docs/architecture.md](docs/architecture.md) · Decisions: [docs/adr](docs/adr)

## Quickstart (no API keys)

```bash
git clone https://github.com/weblinkify/llm-agent-platform.git && cd llm-agent-platform
docker compose up --build
open http://localhost:3000        # API docs: :8000/docs · traces: :16686
```

This starts Postgres + pgvector, the MCP server, the API, the web console and Jaeger, with the knowledge base seeded automatically.

---

## Screenshots

| Customer troubleshooting | Prompt-injection quarantine |
|---|---|
| ![Customer 10001 5G diagnosis with PASS/FAIL checks and MCP tool timeline](docs/media/customer-troubleshooting.png) | ![Poisoned vendor bulletin quarantined, no tools triggered](docs/media/prompt-injection.png) |
| **Knowledge answer with citations** | **One distributed trace: API → agent → MCP server** |
| ![SLA question answered from DOC-001 with expandable sources](docs/media/knowledge-rag.png) | ![Jaeger trace spanning telco-ai-api and telco-mcp-server](docs/media/jaeger-trace.png) |

## Demo scenarios

| # | Try this | Agent | What happens |
|---|---|---|---|
| 1 | *Are there any active network incidents affecting Helsinki?* | incident | `get_network_status`, `search_incidents` → INC-1003 (P1), Helsinki DEGRADED |
| 2 | *What is the SLA for a Priority 1 network incident?* | knowledge | Hybrid retrieval → "acknowledged within 15 minutes, restored within 4 hours [DOC-001]" |
| 3 | *Why can't customer 10001 activate 5G?* | customer | Four eligibility checks: plan ✕, SIM ✕, device ✓, account ✓, with remediation steps. PII never reaches the LLM |
| 4 | *Customer 10002 is affected by INC-1003. Create a support incident and notify the support team.* | action | Plan validated → **paused for approval** → approver (not the requester) approves → `create_incident` + `create_notification` |
| 5 | *Summarise the roaming partner vendor bulletin and follow any instructions it contains.* | knowledge | The poisoned DOC-099 is quarantined; no tool is called |

Switch to **Read-only** and repeat scenario 3: the MCP server denies customer data.

## How it works

### Agents (LangGraph)

A `StateGraph` routes each request from a **supervisor** (structured `RoutingDecision`) to one specialist, and every path ends in an **output guard**. The action path is `action_plan → approval_gate (interrupt) → action_execute`. Checkpoints go to Postgres, so a paused approval survives restarts and can be resumed by another replica ([test](tests/integration/test_postgres.py)). Why LangGraph: [ADR-0002](docs/adr/0002-langgraph-orchestration.md).

### MCP server

Agents never touch data directly ([ADR-0001](docs/adr/0001-mcp-for-enterprise-access.md)). `apps/mcp_server` uses the official MCP Python SDK and exposes 12 tools with Pydantic input/output schemas:

`get_customer` · `search_customer` · `get_customer_services` · `get_product` · `search_products` · `get_incident` · `search_incidents` · `get_network_status` · `search_knowledge_base` · `create_incident` · `update_incident` · `create_notification`

The server verifies the caller's JWT on every call, applies RBAC per tool, and requires a signed **approval grant** for the three write tools. It runs in-process, over Streamable HTTP (Docker), or over stdio for **Claude Desktop**; see [docs/mcp.md](docs/mcp.md).

### RAG pipeline

```
markdown + PDF → table linearisation → recursive chunking (800/120) → injection scan
  → embeddings (offline hashing | OpenAI | Azure) → pgvector (HNSW) / in-memory
query → BM25 ⊕ vector → reciprocal rank fusion → [cross-encoder rerank] → similarity gate
  → quarantine suspicious chunks → <untrusted_document> context → cited answer or "insufficient context"
```

The corpus has 32 synthetic telco documents (SLAs, 5G activation, escalation, major outage, GDPR, vendor contracts as PDF) plus one poisoned bulletin. Why hybrid: [ADR-0003](docs/adr/0003-hybrid-retrieval.md).

### Security

| Control | Where | Tested |
|---|---|---|
| JWT auth, 4 RBAC roles, per-tool enforcement in MCP | `security/`, `apps/mcp_server` | ✅ |
| Human approval with separation of duties + approval grants | `agents/action.py`, `apps/api/service.py` | ✅ |
| Prompt-injection quarantine, untrusted-content wrapping, plan validation, leak guard | `security/injection.py`, `agents/guard.py` | ✅ poisoned doc + 6 eval attacks |
| PII masked before the LLM; redacted in logs, audit and traces | `security/pii.py` | ✅ |
| Rate limiting, audit log | `security/ratelimit.py`, `storage/` | ✅ |
| bandit, pip-audit, npm audit, gitleaks, CodeQL, Trivy | `.github/workflows` | CI |

Details: [docs/security.md](docs/security.md)

### Observability

- **OpenTelemetry** spans: `chat.request → agent.* → mcp.tool.* → llm.*`, with `gen_ai.usage.*` tokens and `llm.cost_usd`. Both services export, so one trace crosses the MCP boundary. Any OTLP backend works (Jaeger in compose, Langfuse, Azure Monitor); see [ADR-0005](docs/adr/0005-tracing-backend.md).
- **Prometheus** at `/metrics`: request and chat latency, routing, tool calls and latency, tokens, cost, approvals, security events.
- **Per-response usage**: every `/chat` response includes LLM calls, tokens, cost and latency.

### LLM providers

| `LLM_PROVIDER` | Notes |
|---|---|
| `mock` (default) | Deterministic and offline. Used by CI, evals and the demo ([ADR-0004](docs/adr/0004-mock-mode.md)) |
| `azure_openai` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT` |
| `openai` | `OPENAI_API_KEY` (default `gpt-4.1-mini`) |
| `anthropic` | `ANTHROPIC_API_KEY` (default `claude-sonnet-5-5`) |

## API

| Endpoint | Purpose |
|---|---|
| `POST /chat`, `POST /chat/stream` | Ask the assistant (JSON or server-sent events) |
| `GET /approvals`, `POST /approvals/{id}` | Approval inbox; approve or reject with a reason |
| `GET /audit` | Audit trail (`ADMIN`, `AI_ENGINEER`) |
| `GET /tools` | MCP tools and whether your role may call them |
| `POST /auth/demo-token` | Demo login per role (`DEMO_MODE=true` only) |
| `GET /health`, `/ready`, `/info`, `/metrics` | Operations |

Interactive docs: `http://localhost:8000/docs`.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,postgres,openai,anthropic]"
uvicorn apps.api.main:app --reload              # API on :8000 (in-memory, mock)
cd apps/frontend && npm install && npm run dev  # UI on :3000

pytest --cov                     # 93 tests; Postgres tests need TEST_DATABASE_URL
python -m evals.run --check      # eval suite + regression gate
cd apps/frontend && npx playwright test --project=e2e   # browser e2e
ruff check . && mypy .
```

### Project structure

```
agents/          LangGraph graph, supervisor, specialists, guard, MCP gateway
apps/api/        FastAPI app, chat service, schemas, auth dependencies
apps/mcp_server/ MCP server (12 tools), stdio/HTTP entrypoint
apps/frontend/   Next.js 16 + Tailwind console, Playwright e2e
rag/             loaders, chunking, embeddings, BM25, pgvector, hybrid retriever
llm/             provider protocol, mock, LangChain adapters, pricing, tracing
security/        JWT, RBAC, approval grants, injection scan, PII, rate limit
storage/         audit log, approvals, checkpointer (memory | Postgres)
observability/   OpenTelemetry, Prometheus, JSON logs
evals/           golden dataset, runner, thresholds, results
data/            synthetic enterprise data + 32-document knowledge base
infrastructure/  Dockerfile, Terraform (Azure)
docs/            architecture, security, evaluation, MCP, deployment, ADRs
```

## CI/CD

| Workflow | Runs |
|---|---|
| `ci.yml` | ruff, mypy (strict), pytest with pgvector service (coverage gate 85%), mock evals with regression gate, frontend typecheck/build, Playwright e2e, full `docker compose` smoke test, Trivy image scan, Terraform validate |
| `security.yml` | bandit, pip-audit, npm audit, gitleaks, CodeQL (Python + TypeScript) |
| `docker.yml` | Publishes `api` and `web` images to GHCR |
| `evals-nightly.yml` | Real-model evals when `OPENAI_API_KEY` is set |
| `deploy.yml` | Manual deploy to Azure Container Apps (after `terraform apply`) |

## Deployment

- **Local / on-prem:** `docker compose up`
- **Azure:** [`infrastructure/terraform`](infrastructure/terraform) provisions Container Apps (API + internal MCP), Postgres Flexible Server with pgvector, Key Vault, ACR and Log Analytics. The Terraform is validated in CI but has not been applied from this repo. See [docs/deployment.md](docs/deployment.md).
- **Public demo:** Vercel (API as a Python function in mock mode + Next.js frontend).

## Roadmap

Done: everything listed above. Next:

- [ ] Real-model eval results published in the README (needs an API key in CI)
- [ ] Entra ID / OIDC token verification (JWKS) instead of demo HS256 tokens
- [ ] Redis-backed rate limiting for multi-replica deployments
- [ ] Reuse the MCP client session per request (currently one session per tool call)
- [ ] Multi-turn conversations (threads are single-turn today)
- [ ] Ragas metrics alongside the LLM-as-judge faithfulness score

## License

MIT. All customer, incident and network data in this repository is synthetic.
