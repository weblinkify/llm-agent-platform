from typing import Any, Literal

from pydantic import BaseModel, Field

from core.models import Role
from storage.models import Approval


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class UsageReport(BaseModel):
    provider: str
    model: str
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class ChatResponse(BaseModel):
    request_id: str
    thread_id: str
    agent: str | None
    route_reason: str | None = None
    status: str
    answer: str
    citations: list[dict[str, Any]] = []
    quarantined_sources: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    approval: Approval | None = None
    data: dict[str, Any] = {}
    security_flags: list[str] = []
    steps: list[str] = []
    usage: UsageReport
    latency_ms: float
    trace_id: str | None = None


class DemoTokenRequest(BaseModel):
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    subject: str
    role: Role


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=500)
