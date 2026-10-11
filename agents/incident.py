import re
from typing import Any

from agents.common import citation, denied_answer, knowledge_hits, summarize
from agents.runtime import Deps, ToolCallError, audit, run_context
from agents.state import AgentState

_INCIDENT_ID = re.compile(r"\bINC-\d{4}\b", re.I)


def _incident_line(inc: dict[str, Any]) -> str:
    return (
        f"- {inc['incident_id']} ({inc['severity']}, {inc['status']}, {inc['location']}): "
        f"{inc['title']}. {inc['description']} Affected services: "
        f"{', '.join(inc['affected_services']) or 'n/a'}."
    )


async def incident(state: AgentState, deps: Deps) -> dict[str, Any]:
    ctx = run_context.get()
    message = state["message"]
    try:
        if match := _INCIDENT_ID.search(message):
            incident_id = match.group(0).upper()
            try:
                inc = await deps.mcp.call("get_incident", {"incident_id": incident_id}, ctx)
            except ToolCallError as exc:
                if exc.denied:
                    raise
                return {
                    "answer": f"Incident {incident_id} was not found.",
                    "status": "completed",
                    "steps": ["incident"],
                }
            network = (
                await deps.mcp.call("get_network_status", {"location": inc["location"]}, ctx)
            )["regions"]
            incidents = [inc]
            lines = [
                f"Incident {incident_id}: {inc['title']}.",
                _incident_line(inc),
                f"Network status in {inc['location']}: {network[0]['status']}.",
            ]
        else:
            regions = (await deps.mcp.call("get_network_status", {}, ctx))["regions"]
            named = [r for r in regions if r["location"].lower() in message.lower()]
            incidents = []
            if named:
                for region in named:
                    incidents += (
                        await deps.mcp.call(
                            "search_incidents",
                            {"location": region["location"], "status": "ACTIVE"},
                            ctx,
                        )
                    )["incidents"]
                network = named
            else:
                incidents = (await deps.mcp.call("search_incidents", {"status": "ACTIVE"}, ctx))[
                    "incidents"
                ]
                network = regions
            scope = ", ".join(r["location"] for r in named) or "all regions"
            count = f"{len(incidents)} active incident" + ("" if len(incidents) == 1 else "s")
            verb = "is" if len(incidents) == 1 else "are"
            lines = [
                f"There {verb} {count} affecting {scope}."
                if incidents
                else f"There are no active incidents affecting {scope}."
            ]
            lines += [_incident_line(i) for i in incidents]
            lines.append(
                "Network status: "
                + ", ".join(f"{r['location']} {r['status']}" for r in network)
                + "."
            )
    except ToolCallError as exc:
        return {
            "answer": denied_answer(exc, ctx.principal.role),
            "status": "denied",
            "steps": ["incident"],
        }

    hits: list[dict[str, Any]] = []
    if incidents:
        top = min(incidents, key=lambda i: i["severity"])
        hits = await knowledge_hits(
            deps, ctx, f"Priority {top['severity'][1]} incident SLA restore", top_k=3
        )
        if hits:
            lines.append(
                "Relevant procedures: "
                + "; ".join(f"{h['title']} [{h['doc_id']}]" for h in hits)
                + "."
            )
    lines.append("This was a read-only investigation; no approval was required.")

    answer = await summarize(
        deps,
        facts=str({"incidents": incidents, "network": network}),
        draft="\n".join(lines),
    )
    await audit(
        deps,
        ctx,
        "agent_step",
        "incident",
        incidents=[i["incident_id"] for i in incidents],
    )
    return {
        "answer": answer,
        "status": "completed",
        "citations": [citation(h) for h in hits],
        "data": {"incidents": incidents, "network": network},
        "steps": ["incident"],
    }
