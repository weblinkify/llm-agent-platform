import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agents.runtime import Deps, RunContext, run_context
from apps.api.schemas import ChatResponse, UsageReport
from core.models import Principal
from observability.context import RequestUsage, current_usage
from observability.metrics import APPROVALS, CHAT_LATENCY
from observability.tracing import current_trace_id, tracer
from security.auth import issue_approval_grant, issue_token
from security.pii import redact
from security.rbac import APPROVER_ROLES
from storage.models import Approval, AuditEvent, AuditKind
from storage.protocols import ApprovalStore


class ApprovalError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ChatService:
    """Runs the agent graph for API requests, the SSE stream and the eval runner."""

    def __init__(
        self, graph: CompiledStateGraph[Any], deps: Deps, approvals: ApprovalStore
    ) -> None:
        self.graph = graph
        self.deps = deps
        self.approvals = approvals

    async def chat(self, principal: Principal, token: str, message: str) -> ChatResponse:
        final: ChatResponse | None = None
        async for event in self.stream(principal, token, message, stream=False):
            if event["type"] == "final":
                final = ChatResponse.model_validate(event["response"])
        assert final is not None
        return final

    async def stream(
        self, principal: Principal, token: str, message: str, *, stream: bool = True
    ) -> AsyncIterator[dict[str, Any]]:
        ctx = RunContext(principal, token, uuid.uuid4().hex, f"thr-{uuid.uuid4().hex}")
        await self._audit(ctx, principal, "request", "chat", message=message)
        payload = {"message": message, "security_flags": [], "steps": []}
        async for event in self._run(payload, ctx, stream, message):
            yield event

    async def decide(
        self, approval_id: str, reviewer: Principal, approve: bool, reason: str
    ) -> ChatResponse:
        approval = await self.approvals.get(approval_id)
        if approval is None:
            raise ApprovalError(404, f"Approval {approval_id} not found")
        if approval.status != "PENDING":
            raise ApprovalError(409, f"Approval {approval_id} is already {approval.status}")
        if reviewer.role not in APPROVER_ROLES:
            raise ApprovalError(403, f"Role {reviewer.role} cannot approve actions")
        if reviewer.subject == approval.requested_by:
            raise ApprovalError(403, "Separation of duties: you cannot approve your own request")
        config: RunnableConfig = {"configurable": {"thread_id": approval.thread_id}}
        snapshot = await self.graph.aget_state(config)
        if not snapshot.next:
            raise ApprovalError(
                410, "The paused workflow is no longer available (expired checkpoint)"
            )

        settings = self.deps.settings
        requester = Principal(subject=approval.requested_by, role=approval.requester_role)
        grant = (
            issue_approval_grant(
                approval_id, [a["tool"] for a in approval.actions], reviewer, settings
            )
            if approve
            else None
        )
        ctx = RunContext(
            requester,
            issue_token(requester, settings, 5),
            uuid.uuid4().hex,
            approval.thread_id,
            approval_grant=grant,
        )
        await self._audit(
            ctx,
            reviewer,
            "approval_decision",
            approval_id,
            status="approved" if approve else "rejected",
            reason=reason,
        )
        APPROVALS.labels("approved" if approve else "rejected").inc()

        approval.status = "APPROVED" if approve else "REJECTED"
        approval.decided_by = reviewer.subject
        approval.decided_at = datetime.now(UTC)
        approval.reason = reason or None
        await self.approvals.save(approval)

        resume: Command[Any] = Command(
            resume={"approved": approve, "reviewer": reviewer.subject, "reason": reason}
        )
        final: ChatResponse | None = None
        async for event in self._run(resume, ctx, False, approval.request_message):
            if event["type"] == "final":
                final = ChatResponse.model_validate(event["response"])
        assert final is not None
        approval.result = {
            "answer": final.answer,
            "status": final.status,
            "data": final.data,
        }
        await self.approvals.save(approval)
        final.approval = approval
        return final

    async def _run(
        self,
        payload: dict[str, Any] | Command[Any],
        ctx: RunContext,
        stream: bool,
        message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        usage = RequestUsage()
        current_usage.set(usage)
        run_context.set(ctx)
        config: RunnableConfig = {"configurable": {"thread_id": ctx.thread_id}}
        started = time.perf_counter()
        with tracer.start_as_current_span("chat.request") as span:
            span.set_attribute("telco.request_id", ctx.request_id)
            span.set_attribute("telco.role", ctx.principal.role.value)
            if stream:
                async for mode, chunk in self.graph.astream(
                    payload, config, stream_mode=["custom", "updates"]
                ):
                    if mode == "custom":
                        yield cast(dict[str, Any], chunk)
            else:
                await self.graph.ainvoke(payload, config)
            snapshot = await self.graph.aget_state(config)
            values: dict[str, Any] = dict(snapshot.values)
            trace_id = current_trace_id()
            span.set_attribute("telco.agent", values.get("agent", ""))
            span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
            span.set_attribute("llm.cost_usd", usage.cost_usd)

        approval: Approval | None = None
        if snapshot.next:
            approval = await self.approvals.create(
                Approval(
                    thread_id=ctx.thread_id,
                    requested_by=ctx.principal.subject,
                    requester_role=ctx.principal.role,
                    request_message=message,
                    actions=values.get("plan", []),
                )
            )
            yield {
                "type": "approval_pending",
                "approval": approval.model_dump(mode="json"),
            }

        latency = time.perf_counter() - started
        CHAT_LATENCY.labels(values.get("agent", "unknown")).observe(latency)
        llm = self.deps.llm
        response = ChatResponse(
            request_id=ctx.request_id,
            thread_id=ctx.thread_id,
            agent=values.get("agent"),
            route_reason=values.get("route_reason"),
            status="pending_approval" if approval else values.get("status", "completed"),
            answer=values.get("answer", ""),
            citations=values.get("citations", []),
            quarantined_sources=values.get("quarantined", []),
            tool_calls=ctx.tool_log,
            approval=approval,
            data=values.get("data", {}),
            security_flags=values.get("security_flags", []),
            steps=values.get("steps", []),
            usage=UsageReport(
                provider=llm.provider,
                model=llm.model,
                llm_calls=len(usage.calls),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=round(usage.cost_usd, 6),
            ),
            latency_ms=round(latency * 1000, 1),
            trace_id=trace_id,
        )
        await self._audit(
            ctx,
            ctx.principal,
            "response",
            response.agent or "unknown",
            status=response.status,
            latency_ms=response.latency_ms,
            tokens=usage.input_tokens + usage.output_tokens,
            cost_usd=usage.cost_usd,
        )
        yield {"type": "final", "response": response.model_dump(mode="json")}

    async def _audit(
        self,
        ctx: RunContext,
        actor: Principal,
        kind: AuditKind,
        name: str,
        status: str = "ok",
        **detail: Any,
    ) -> None:
        await self.deps.audit.write(
            AuditEvent(
                request_id=ctx.request_id,
                thread_id=ctx.thread_id,
                actor=actor.subject,
                role=actor.role,
                kind=kind,
                name=name,
                status=status,
                detail=redact(detail),
            )
        )
