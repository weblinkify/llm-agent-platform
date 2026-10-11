from typing import Any

from agents.common import (
    INSUFFICIENT_ANSWER,
    citation,
    cited_ids,
    denied_answer,
    token_emitter,
)
from agents.runtime import Deps, ToolCallError, audit, run_context
from agents.state import AgentState
from llm.mock import INSUFFICIENT
from observability.metrics import SECURITY_EVENTS
from prompts.agents import KNOWLEDGE_SYSTEM
from security.injection import wrap_untrusted


async def knowledge(state: AgentState, deps: Deps) -> dict[str, Any]:
    ctx = run_context.get()
    question = state["message"]
    try:
        kb = await deps.mcp.call(
            "search_knowledge_base",
            {"query": question, "top_k": deps.settings.retrieval_top_k},
            ctx,
        )
    except ToolCallError as exc:
        return {
            "answer": denied_answer(exc, ctx.principal.role),
            "status": "denied",
            "steps": ["knowledge"],
        }

    quarantined = kb["quarantined"]
    if quarantined:
        SECURITY_EVENTS.labels("chunk_quarantined").inc(len(quarantined))
        await audit(
            deps,
            ctx,
            "security",
            "retrieval_quarantine",
            "blocked",
            chunks=[q["chunk_id"] for q in quarantined],
        )

    base: dict[str, Any] = {"quarantined": quarantined, "steps": ["knowledge"]}
    if not kb["sufficient"]:
        await audit(
            deps,
            ctx,
            "agent_step",
            "knowledge",
            "insufficient_context",
            best_similarity=kb["best_similarity"],
        )
        return {
            **base,
            "answer": INSUFFICIENT_ANSWER,
            "status": "insufficient_context",
            "citations": [],
        }

    context = "\n\n".join(wrap_untrusted(h["doc_id"], h["title"], h["text"]) for h in kb["results"])
    result = await deps.llm.generate(
        task="answer",
        system=KNOWLEDGE_SYSTEM,
        prompt=f"{context}\n\nQuestion: {question}",
        on_token=token_emitter,
    )
    if INSUFFICIENT in result.text:
        return {
            **base,
            "answer": INSUFFICIENT_ANSWER,
            "status": "insufficient_context",
            "citations": [],
        }

    used = cited_ids(result.text)
    await audit(deps, ctx, "agent_step", "knowledge", sources=sorted(used))
    return {
        **base,
        "answer": result.text,
        "status": "completed",
        "citations": [citation(h, used) for h in kb["results"]],
    }
