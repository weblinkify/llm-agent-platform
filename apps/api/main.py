import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from mcp.server.mcpserver import MCPServer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette import EventSourceResponse

from agents.graph import build_graph
from agents.runtime import Deps, McpGateway
from apps.api.dependencies import Caller, get_caller, get_service, rate_limited
from apps.api.schemas import (
    ApprovalDecision,
    ChatRequest,
    ChatResponse,
    DemoTokenRequest,
    TokenResponse,
)
from apps.api.service import ApprovalError, ChatService
from apps.mcp_server.bootstrap import build_retriever, load_enterprise
from apps.mcp_server.server import build_mcp_server
from core.models import Principal
from core.settings import Settings, get_settings
from llm.factory import create_llm
from llm.traced import TracedLLM
from observability.logging import setup_logging
from observability.metrics import HTTP_REQUESTS, REGISTRY
from observability.tracing import setup_tracing
from security.auth import issue_token
from security.ratelimit import SlidingWindowRateLimiter
from security.rbac import APPROVER_ROLES, AUDIT_READER_ROLES, TOOL_PERMISSIONS
from storage.factory import open_backends
from storage.models import Approval, ApprovalStatus, AuditEvent

VERSION = "1.0.0"
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    setup_logging(settings.log_level)
    setup_tracing(settings)
    async with open_backends(settings) as backends:
        retriever = await build_retriever(backends.vector_store, backends.embedder, settings)
        mcp_server = build_mcp_server(load_enterprise(settings), retriever, settings)
        target: MCPServer | str = settings.mcp_server_url or mcp_server
        deps = Deps(
            TracedLLM(create_llm(settings)),
            McpGateway(target),
            backends.audit_log,
            settings,
        )
        graph = build_graph(deps, backends.checkpointer)
        app.state.backends = backends
        app.state.mcp_server = mcp_server
        app.state.service = ChatService(graph, deps, backends.approvals)
        app.state.rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)
        log.info(
            "startup complete",
            extra={"backends": backends.kind, "llm": settings.llm_provider},
        )
        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Telco AI Operations Assistant",
        version=VERSION,
        description="Multi-agent AI operations assistant: LangGraph supervisor, MCP tools, "
        "hybrid RAG, human-in-the-loop approvals, RBAC and audit logging.",
        lifespan=lifespan,
    )
    app.state.settings = settings or get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        route = request.scope.get("route")
        path = route.path if isinstance(route, APIRoute) else "unmatched"
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        return response

    register_routes(app)
    return app


def register_routes(app: FastAPI) -> None:
    CallerDep = Annotated[Caller, Depends(get_caller)]
    LimitedCaller = Annotated[Caller, Depends(rate_limited)]
    ServiceDep = Annotated[ChatService, Depends(get_service)]

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "Telco AI Operations Assistant",
            "version": VERSION,
        }

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/ready", tags=["meta"])
    async def ready(request: Request) -> dict[str, Any]:
        backends = request.app.state.backends
        chunks = await backends.vector_store.count()
        if chunks == 0:
            raise HTTPException(503, "Knowledge base not loaded")
        return {"status": "ready", "backends": backends.kind, "chunks": chunks}

    @app.get("/info", tags=["meta"])
    async def info(request: Request) -> dict[str, Any]:
        settings: Settings = request.app.state.settings
        llm = request.app.state.service.deps.llm
        return {
            "version": VERSION,
            "llm_provider": llm.provider,
            "llm_model": llm.model,
            "embeddings": request.app.state.backends.embedder.name,
            "backends": request.app.state.backends.kind,
            "demo_mode": settings.demo_mode,
        }

    @app.get("/metrics", tags=["meta"], include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    @app.post("/auth/demo-token", tags=["auth"])
    async def demo_token(body: DemoTokenRequest, request: Request) -> TokenResponse:
        """Issue a token for a demo user of the given role (only when DEMO_MODE=true).
        In production, tokens come from your identity provider (e.g. Entra ID)."""
        settings: Settings = request.app.state.settings
        if not settings.demo_mode:
            raise HTTPException(404, "Not found")
        principal = Principal(
            subject=f"demo-{body.role.value.lower().replace('_', '-')}", role=body.role
        )
        return TokenResponse(
            access_token=issue_token(principal, settings),
            subject=principal.subject,
            role=principal.role,
        )

    @app.get("/auth/me", tags=["auth"])
    async def me(caller: CallerDep) -> dict[str, Any]:
        role = caller.principal.role
        return {
            "subject": caller.principal.subject,
            "role": role,
            "tools": sorted(TOOL_PERMISSIONS[role]),
            "can_approve": role in APPROVER_ROLES,
            "can_read_audit": role in AUDIT_READER_ROLES,
        }

    @app.post("/chat", tags=["chat"])
    async def chat(body: ChatRequest, caller: LimitedCaller, service: ServiceDep) -> ChatResponse:
        return await service.chat(caller.principal, caller.token, body.message)

    @app.post("/chat/stream", tags=["chat"])
    async def chat_stream(
        body: ChatRequest, caller: LimitedCaller, service: ServiceDep
    ) -> EventSourceResponse:
        """Server-sent events: agent, route, tool_call, tool_result, token,
        approval_required, approval_pending, final."""

        async def events() -> AsyncIterator[dict[str, str]]:
            async for event in service.stream(caller.principal, caller.token, body.message):
                yield {"event": event["type"], "data": json.dumps(event, default=str)}

        return EventSourceResponse(events(), ping=15)

    @app.get("/approvals", tags=["approvals"])
    async def list_approvals(
        caller: CallerDep,
        service: ServiceDep,
        status: Annotated[ApprovalStatus | None, Query()] = "PENDING",
    ) -> list[Approval]:
        items = await service.approvals.list(status)
        if caller.principal.role in APPROVER_ROLES:
            return items
        return [a for a in items if a.requested_by == caller.principal.subject]

    @app.get("/approvals/{approval_id}", tags=["approvals"])
    async def get_approval(approval_id: str, caller: CallerDep, service: ServiceDep) -> Approval:
        approval = await service.approvals.get(approval_id)
        if approval is None or (
            caller.principal.role not in APPROVER_ROLES
            and approval.requested_by != caller.principal.subject
        ):
            raise HTTPException(404, "Approval not found")
        return approval

    @app.post("/approvals/{approval_id}", tags=["approvals"])
    async def decide(
        approval_id: str, body: ApprovalDecision, caller: CallerDep, service: ServiceDep
    ) -> ChatResponse:
        try:
            return await service.decide(
                approval_id, caller.principal, body.decision == "approve", body.reason
            )
        except ApprovalError as exc:
            raise HTTPException(exc.status_code, exc.detail) from exc

    @app.get("/audit", tags=["audit"])
    async def audit_log(
        request: Request,
        caller: CallerDep,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        request_id: str | None = None,
    ) -> list[AuditEvent]:
        if caller.principal.role not in AUDIT_READER_ROLES:
            raise HTTPException(403, "Audit log requires ADMIN or AI_ENGINEER")
        events: list[AuditEvent] = await request.app.state.backends.audit_log.list(
            limit, request_id
        )
        return events

    @app.get("/tools", tags=["mcp"])
    async def tools(request: Request, caller: CallerDep) -> list[dict[str, Any]]:
        listed = await request.app.state.mcp_server.list_tools()
        allowed = TOOL_PERMISSIONS[caller.principal.role]
        return [
            {
                "name": t.name,
                "description": t.description,
                "allowed": t.name in allowed,
                "read_only": bool(t.annotations and t.annotations.read_only_hint),
            }
            for t in listed
        ]


app = create_app()
