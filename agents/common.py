import re
from typing import Any

from agents.runtime import Deps, RunContext, ToolCallError, emit
from prompts.agents import SUMMARY_SYSTEM

INSUFFICIENT_ANSWER = (
    "I couldn't find enough evidence in the knowledge base to answer this reliably, "
    "so I won't guess. Try rephrasing the question or ask a specialist team."
)


async def token_emitter(text: str) -> None:
    emit({"type": "token", "text": text})


def citation(hit: dict[str, Any], cited_ids: set[str] | None = None) -> dict[str, Any]:
    return {
        "doc_id": hit["doc_id"],
        "chunk_id": hit["chunk_id"],
        "title": hit["title"],
        "section": hit["section"],
        "snippet": hit["text"][:400],
        "similarity": hit["similarity"],
        "cited": cited_ids is None or hit["doc_id"] in cited_ids,
    }


def cited_ids(text: str) -> set[str]:
    return set(re.findall(r"\[(DOC-\d+)\]", text))


async def knowledge_hits(
    deps: Deps, ctx: RunContext, query: str, top_k: int = 2
) -> list[dict[str, Any]]:
    """Supporting documentation for non-knowledge agents. Best effort: an empty
    list when retrieval is insufficient or denied."""
    try:
        kb = await deps.mcp.call("search_knowledge_base", {"query": query, "top_k": top_k}, ctx)
    except ToolCallError:
        return []
    if not kb["sufficient"]:
        return []
    first_per_doc: dict[str, dict[str, Any]] = {}
    for hit in kb["results"]:
        first_per_doc.setdefault(hit["doc_id"], hit)
    return list(first_per_doc.values())


async def summarize(deps: Deps, facts: str, draft: str) -> str:
    """The draft is built deterministically from tool results; the LLM only
    rewrites it for readability (the mock returns it unchanged)."""
    result = await deps.llm.generate(
        task="summarize",
        system=SUMMARY_SYSTEM,
        prompt=f"Facts:\n{facts}\n\nDraft:\n{draft}",
        on_token=token_emitter,
    )
    return result.text


def denied_answer(error: ToolCallError, role: str) -> str:
    return (
        f"Access denied: your role ({role}) is not permitted to use `{error.tool}`. "
        "Ask a SUPPORT_AGENT or ADMIN to run this request."
    )
