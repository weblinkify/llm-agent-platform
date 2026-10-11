from typing import Any

from agents.runtime import Deps, audit, emit, run_context
from agents.schemas import RoutingDecision
from agents.state import AgentState
from observability.metrics import AGENT_ROUTES, SECURITY_EVENTS
from prompts.agents import SUPERVISOR_SYSTEM
from security.injection import scan


async def supervisor(state: AgentState, deps: Deps) -> dict[str, Any]:
    ctx = run_context.get()
    message = state["message"]
    flags: list[str] = []
    verdict = scan(message)
    if verdict.suspicious:
        flags.append("user_input_injection:" + ",".join(verdict.rules))
        SECURITY_EVENTS.labels("user_input_flagged").inc()
        await audit(deps, ctx, "security", "user_input_flagged", "flagged", rules=verdict.rules)

    decision, _ = await deps.llm.structured(
        task="route", system=SUPERVISOR_SYSTEM, prompt=message, schema=RoutingDecision
    )
    AGENT_ROUTES.labels(decision.next_agent).inc()
    emit({"type": "route", "agent": decision.next_agent, "reason": decision.reason})
    await audit(
        deps,
        ctx,
        "agent_step",
        "supervisor",
        route=decision.next_agent,
        reason=decision.reason,
    )
    return {
        "agent": decision.next_agent,
        "route_reason": decision.reason,
        "security_flags": flags,
        "steps": ["supervisor"],
    }
