import re
from typing import Any

from agents.common import citation, denied_answer, knowledge_hits, summarize
from agents.runtime import Deps, ToolCallError, audit, run_context
from agents.state import AgentState
from security.pii import PII_FIELDS

_CUSTOMER_ID = re.compile(r"\b(1\d{4})\b")
_FIVE_G = re.compile(r"\b5g\b", re.I)

_REMEDIATION = {
    "Account status": "Account is suspended: the customer must contact Billing to settle the "
    "overdue balance before any activation (Account Suspension Policy).",
    "5G-enabled plan": "Offer an upgrade to a 5G plan (MOB-5G-PLUS or MOB-5G-UNLIMITED).",
    "5G-capable device": "The handset does not support 5G; the customer needs a 5G-capable device.",
    "5G-compatible SIM": "Order a free SIM upgrade to USIM-5G or provision an ESIM-5G profile.",
}


def five_g_checks(customer: dict[str, Any], services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plans = [s["product_id"] for s in services if s["five_g_enabled"]]
    return [
        {
            "check": "Account status",
            "passed": customer["account_status"] == "ACTIVE",
            "detail": customer["account_status"],
        },
        {
            "check": "5G-enabled plan",
            "passed": bool(plans),
            "detail": ", ".join(plans)
            or "none (" + ", ".join(s["product_id"] for s in services) + ")",
        },
        {
            "check": "5G-capable device",
            "passed": customer["device"]["five_g_capable"],
            "detail": customer["device"]["model"],
        },
        {
            "check": "5G-compatible SIM",
            "passed": customer["sim"]["five_g_supported"],
            "detail": customer["sim"]["type"],
        },
    ]


async def customer(state: AgentState, deps: Deps) -> dict[str, Any]:
    ctx = run_context.get()
    message = state["message"]
    match = _CUSTOMER_ID.search(message)
    if not match:
        return {
            "answer": "Please include the 5-digit customer ID so I can investigate.",
            "status": "completed",
            "steps": ["customer"],
        }
    customer_id = match.group(1)

    try:
        record = await deps.mcp.call("get_customer", {"customer_id": customer_id}, ctx)
        services = (
            await deps.mcp.call("get_customer_services", {"customer_id": customer_id}, ctx)
        )["services"]
    except ToolCallError as exc:
        if exc.denied:
            return {
                "answer": denied_answer(exc, ctx.principal.role),
                "status": "denied",
                "steps": ["customer"],
            }
        return {
            "answer": f"Customer {customer_id} was not found.",
            "status": "completed",
            "steps": ["customer"],
        }

    service_ids = {s["product_id"] for s in services}
    incidents = [
        i
        for i in (
            await deps.mcp.call(
                "search_incidents",
                {"location": record["city"], "status": "ACTIVE"},
                ctx,
            )
        )["incidents"]
        if service_ids & set(i["affected_services"])
    ]
    # Personal data never reaches the LLM (Customer Data Protection Policy).
    masked = {k: v for k, v in record.items() if k not in PII_FIELDS}

    lines = [
        f"Customer {customer_id} ({record['segment'].lower()}, {record['city']}) "
        f"is {record['account_status']} with services: {', '.join(sorted(service_ids))}."
    ]
    checks: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    if _FIVE_G.search(message):
        checks = five_g_checks(record, services)
        hits = await knowledge_hits(
            deps, ctx, "5G activation prerequisites plan device SIM", top_k=2
        )
        failed = [c for c in checks if not c["passed"]]
        lines.append("5G activation checks (5G Activation Runbook [DOC-002]):")
        lines += [
            f"- {'PASS' if c['passed'] else 'FAIL'} {c['check']}: {c['detail']}" for c in checks
        ]
        if failed:
            lines.append(
                "Why 5G cannot be activated: " + "; ".join(c["check"] for c in failed) + " not met."
            )
            lines.append("Recommended actions:")
            lines += [f"- {_REMEDIATION[c['check']]}" for c in failed]
        else:
            lines.append("All prerequisites are met.")
    for inc in incidents:
        lines.append(
            f"Note: active incident {inc['incident_id']} ({inc['severity']}, {inc['title']}) "
            f"affects this customer's services in {inc['location']}."
        )
    if not checks and not incidents:
        lines.append("No active incidents affect this customer's services.")
    lines.append("No changes were made to the customer's account.")

    answer = await summarize(
        deps,
        facts=str({"customer": masked, "services": services}),
        draft="\n".join(lines),
    )
    await audit(
        deps,
        ctx,
        "agent_step",
        "customer",
        customer_id=customer_id,
        failed_checks=[c["check"] for c in checks if not c["passed"]],
    )
    return {
        "answer": answer,
        "status": "completed",
        "citations": [citation(h) for h in hits],
        "data": {
            "customer": masked,
            "services": services,
            "checks": checks,
            "incidents": incidents,
        },
        "steps": ["customer"],
    }
