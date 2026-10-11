import re
from typing import Any

from langgraph.types import interrupt

from agents.common import denied_answer
from agents.runtime import Deps, ToolCallError, audit, emit, run_context
from agents.schemas import ActionPlan, PlannedAction
from agents.state import AgentState
from observability.metrics import APPROVALS, SECURITY_EVENTS
from prompts.agents import ACTION_SYSTEM
from security.rbac import can_use_tool

_ID_ARGS = ("customer_ids", "incident_id", "related_incident_id")


def ungrounded_ids(action: PlannedAction, message: str) -> list[str]:
    """IDs in a planned action must appear verbatim in the user's own message, so
    that IDs smuggled in through retrieved content or model error are rejected."""
    ids: list[str] = []
    for key in _ID_ARGS:
        value = action.arguments.get(key)
        ids += value if isinstance(value, list) else [value] if value else []
    return [i for i in ids if not re.search(rf"\b{re.escape(str(i))}\b", message, re.I)]


def describe(action: dict[str, Any]) -> str:
    args = action["arguments"]
    if action["tool"] == "create_incident":
        who = (
            f" for customer(s) {', '.join(args['customer_ids'])}"
            if args.get("customer_ids")
            else ""
        )
        rel = (
            f", linked to {args['related_incident_id']}" if args.get("related_incident_id") else ""
        )
        return f"Create {args.get('severity', 'P2')} incident{who}{rel}"
    if action["tool"] == "update_incident":
        changes = ", ".join(f"{k}={args[k]}" for k in ("status", "severity") if args.get(k))
        return f"Update {args.get('incident_id', '?')}" + (f" ({changes})" if changes else "")
    return f"Notify #{args.get('channel', 'support-team')}" + (
        f" about {args['incident_id']}" if args.get("incident_id") else ""
    )


async def action_plan(state: AgentState, deps: Deps) -> dict[str, Any]:
    ctx = run_context.get()
    message = state["message"]
    plan, _ = await deps.llm.structured(
        task="plan_actions", system=ACTION_SYSTEM, prompt=message, schema=ActionPlan
    )
    flags: list[str] = []
    actions: list[PlannedAction] = []
    for action in plan.actions:
        if bad := ungrounded_ids(action, message):
            flags.append(f"ungrounded_ids:{action.tool}:{','.join(bad)}")
            SECURITY_EVENTS.labels("plan_rejected").inc()
            continue
        actions.append(action)
    base: dict[str, Any] = {"security_flags": flags, "steps": ["action_plan"]}
    if not actions:
        return {
            **base,
            "status": "completed",
            "answer": "I could not identify a supported enterprise action in this request. "
            "I can create or update incidents and notify operational teams.",
        }

    role = ctx.principal.role
    forbidden = sorted({a.tool for a in actions if not can_use_tool(role, a.tool)})
    if forbidden:
        await audit(deps, ctx, "security", "action_denied_rbac", "denied", tools=forbidden)
        return {
            **base,
            "status": "denied",
            "answer": f"Access denied: your role ({role}) cannot request {', '.join(forbidden)}. "
            "Nothing was executed.",
        }

    try:
        for cid in sorted({c for a in actions for c in a.arguments.get("customer_ids") or []}):
            await deps.mcp.call("get_customer", {"customer_id": cid}, ctx)
        related: dict[str, Any] = {}
        for iid in sorted(
            {
                a.arguments[k]
                for a in actions
                for k in ("incident_id", "related_incident_id")
                if a.arguments.get(k)
            }
        ):
            related = await deps.mcp.call("get_incident", {"incident_id": iid}, ctx)
    except ToolCallError as exc:
        if exc.denied:
            return {**base, "status": "denied", "answer": denied_answer(exc, role)}
        return {
            **base,
            "status": "completed",
            "answer": f"Validation failed, nothing was executed: {exc}",
        }

    planned: list[dict[str, Any]] = []
    for action in actions:
        args = {k: v for k, v in action.arguments.items() if v is not None}
        if action.tool == "create_incident" and related:
            args.setdefault("location", related.get("location", "Unknown"))
        planned.append({"tool": action.tool, "arguments": args})
    for item in planned:
        item["summary"] = describe(item)

    APPROVALS.labels("requested").inc()
    emit({"type": "approval_required", "actions": planned})
    await audit(deps, ctx, "approval_requested", "action_plan", "pending", actions=planned)
    return {
        **base,
        "plan": planned,
        "status": "pending_approval",
        "answer": "Approval required before executing:\n"
        + "\n".join(f"- {p['summary']}" for p in planned),
    }


def approval_gate(state: AgentState) -> dict[str, Any]:
    """Pauses the graph. The checkpoint is persisted and the run resumes when
    POST /approvals/{id} supplies the human decision via Command(resume=...)."""
    decision = interrupt({"actions": state["plan"], "message": state["message"]})
    return {"approval": decision, "steps": ["approval_gate"]}


async def action_execute(state: AgentState, deps: Deps) -> dict[str, Any]:
    ctx = run_context.get()
    decision = state["approval"]
    reviewer = decision.get("reviewer", "unknown")
    if not decision.get("approved"):
        return {
            "status": "rejected",
            "steps": ["action_execute"],
            "answer": f"Rejected by {reviewer}: {decision.get('reason') or 'no reason given'}. "
            "Nothing was executed.",
        }

    results: list[dict[str, Any]] = []
    lines = [f"Approved by {reviewer}. Executed:"]
    created_id: str | None = None
    for action in state["plan"]:
        args = dict(action["arguments"])
        if action["tool"] == "create_notification" and created_id:
            args["message"] = f"{created_id} opened: {args.get('message', '')}"
        try:
            result = await deps.mcp.call(action["tool"], args, ctx)
        except ToolCallError as exc:
            lines.append(f"- FAILED {action['summary']}: {exc}")
            results.append({"tool": action["tool"], "error": str(exc)})
            break
        results.append({"tool": action["tool"], "result": result})
        if action["tool"] == "create_incident":
            created_id = result["incident_id"]
            lines.append(
                f"- Created incident {created_id} ({result['severity']}, {result['status']})"
            )
        elif action["tool"] == "update_incident":
            lines.append(f"- Updated {result['incident_id']} (status {result['status']})")
        else:
            lines.append(f"- Notification {result['notification_id']} sent to #{result['channel']}")
    await audit(deps, ctx, "tool_call", "action_execute", results=[r["tool"] for r in results])
    return {
        "status": "completed",
        "answer": "\n".join(lines),
        "data": {"results": results},
        "steps": ["action_execute"],
    }
