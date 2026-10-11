from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from core.models import Role

ApprovalStatus = Literal["PENDING", "APPROVED", "REJECTED"]
AuditKind = Literal[
    "request",
    "agent_step",
    "tool_call",
    "approval_requested",
    "approval_decision",
    "security",
    "response",
]


def _now() -> datetime:
    return datetime.now(UTC)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=_now)
    request_id: str
    thread_id: str
    actor: str
    role: Role
    kind: AuditKind
    name: str
    status: str = "ok"
    detail: dict[str, Any] = Field(default_factory=dict)


class Approval(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"APR-{uuid4().hex[:10].upper()}")
    thread_id: str
    requested_by: str
    requester_role: Role
    request_message: str
    actions: list[dict[str, Any]]
    status: ApprovalStatus = "PENDING"
    created_at: datetime = Field(default_factory=_now)
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None
    result: dict[str, Any] | None = None
