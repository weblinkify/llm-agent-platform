from typing import Any, Literal

from typing_extensions import TypedDict

AgentName = Literal[
    "knowledge",
    "customer",
    "incident",
    "action",
    "end",
]


class AgentState(TypedDict, total=False):
    user_input: str

    next_agent: AgentName

    messages: list[dict[str, Any]]

    customer_id: str | None
    incident_id: str | None

    customer_data: dict[str, Any] | None
    incident_data: dict[str, Any] | None

    retrieved_documents: list[dict[str, Any]]

    tool_results: list[dict[str, Any]]

    final_answer: str | None

    requires_approval: bool
    approval_granted: bool

    audit_events: list[dict[str, Any]]
