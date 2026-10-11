import operator
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

from agents.schemas import AgentName

Status = Literal[
    "completed",
    "pending_approval",
    "rejected",
    "denied",
    "insufficient_context",
    "blocked",
]


class AgentState(TypedDict, total=False):
    message: str
    agent: AgentName
    route_reason: str
    answer: str
    status: Status
    citations: list[dict[str, Any]]
    quarantined: list[dict[str, Any]]
    data: dict[str, Any]
    plan: list[dict[str, Any]]
    approval: dict[str, Any]
    security_flags: Annotated[list[str], operator.add]
    steps: Annotated[list[str], operator.add]
