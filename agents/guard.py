from typing import Any

from agents.runtime import Deps, audit, run_context
from agents.state import AgentState
from observability.metrics import SECURITY_EVENTS
from prompts import agents as prompts
from security.pii import redact_text

_PROMPT_LINES = [
    line.strip()
    for text in (
        prompts.SUPERVISOR_SYSTEM,
        prompts.KNOWLEDGE_SYSTEM,
        prompts.SUMMARY_SYSTEM,
        prompts.ACTION_SYSTEM,
    )
    for line in text.splitlines()
    if len(line.strip()) > 40
]
REFUSAL = "I can't share my internal instructions. How can I help with telecom operations?"


def leaks_system_prompt(answer: str) -> bool:
    return prompts.CANARY in answer or any(line in answer for line in _PROMPT_LINES)


async def output_guard(state: AgentState, deps: Deps) -> dict[str, Any]:
    """Last node on every path: blocks system-prompt leakage and redacts PII."""
    answer = state.get("answer", "")
    if leaks_system_prompt(answer):
        SECURITY_EVENTS.labels("output_blocked").inc()
        await audit(deps, run_context.get(), "security", "output_blocked", "blocked")
        return {
            "answer": REFUSAL,
            "status": "blocked",
            "security_flags": ["system_prompt_leak"],
            "steps": ["guard"],
        }
    return {"answer": redact_text(answer), "steps": ["guard"]}
