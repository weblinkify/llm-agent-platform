# ADR-0002: LangGraph for orchestration and human-in-the-loop

**Status:** accepted

## Context

The workflow is a supervisor that routes to specialists, plus an action path that must **pause for a human**, potentially for hours and on another server, and then resume exactly where it stopped.

## Decision

Use a LangGraph `StateGraph` with a Postgres checkpointer. The action path ends in a node that calls `interrupt()`. The API stores an approval record keyed to the thread ID and resumes with `Command(resume={...})` when a human decides.

## Alternatives considered

* **A hand-written state machine:** pause and resume, persistence and streaming would all have to be rebuilt.
* **Fully autonomous tool-calling agents (ReAct):** less predictable routing and harder to guarantee that writes happen only after approval. Graph edges make the approval step structural, not a prompt instruction.

## Consequences

* Approvals survive restarts and work across replicas (`tests/integration/test_postgres.py`).
* `stream_mode="custom"` lets nodes and tools emit UI events (agent, tool, token) without coupling them to HTTP.
