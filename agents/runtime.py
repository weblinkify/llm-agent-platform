import json
import time
from contextlib import suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, cast

from langgraph.config import get_stream_writer
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp_types import RequestParamsMeta

from apps.mcp_server.server import AUTH_META_KEY, GRANT_META_KEY
from core.models import Principal
from core.settings import Settings
from llm.base import LLMProvider
from observability.metrics import TOOL_CALLS, TOOL_LATENCY
from observability.tracing import tracer
from security.pii import redact
from storage.models import AuditEvent, AuditKind
from storage.protocols import AuditLog


class ToolCallError(Exception):
    def __init__(self, tool: str, message: str) -> None:
        super().__init__(message)
        self.tool = tool
        self.denied = "DENIED:" in message
        self.not_found = "NOT_FOUND:" in message


@dataclass
class RunContext:
    """Per-request identity and correlation IDs, visible to every graph node."""

    principal: Principal
    token: str
    request_id: str
    thread_id: str
    approval_grant: str | None = None
    tool_log: list[dict[str, Any]] = field(default_factory=list)


run_context: ContextVar[RunContext] = ContextVar("run_context")


def emit(event: dict[str, Any]) -> None:
    """Send a custom event to /chat/stream clients (no-op outside streaming)."""
    with suppress(RuntimeError):
        get_stream_writer()(event)


class McpGateway:
    """The only path from agents to enterprise data. Calls the MCP server
    in-process (default) or over Streamable HTTP when MCP_SERVER_URL is set."""

    def __init__(self, target: MCPServer | str) -> None:
        self.target = target

    async def call(self, tool: str, arguments: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
        meta: dict[str, Any] = {AUTH_META_KEY: ctx.token}
        if ctx.approval_grant:
            meta[GRANT_META_KEY] = ctx.approval_grant
        started = time.perf_counter()
        emit({"type": "tool_call", "tool": tool, "arguments": redact(arguments)})
        with tracer.start_as_current_span(f"mcp.tool.{tool}") as span:
            span.set_attribute("mcp.tool.name", tool)
            async with Client(self.target) as client:
                result = await client.call_tool(tool, arguments, meta=cast(RequestParamsMeta, meta))
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            status = "error" if result.is_error else "ok"
            span.set_attribute("mcp.tool.status", status)
        TOOL_CALLS.labels(tool, status).inc()
        TOOL_LATENCY.labels(tool).observe(elapsed_ms / 1000)
        record = {
            "tool": tool,
            "arguments": redact(arguments),
            "status": status,
            "latency_ms": elapsed_ms,
        }
        if result.is_error:
            message = " ".join(getattr(c, "text", "") for c in result.content)
            record["error"] = message
            ctx.tool_log.append(record)
            emit({"type": "tool_result", **record})
            raise ToolCallError(tool, message)
        data = result.structured_content or json.loads(getattr(result.content[0], "text", "{}"))
        ctx.tool_log.append(record)
        emit({"type": "tool_result", **record})
        return dict(data)


@dataclass
class Deps:
    llm: LLMProvider
    mcp: McpGateway
    audit: AuditLog
    settings: Settings


async def audit(
    deps: Deps,
    ctx: RunContext,
    kind: AuditKind,
    name: str,
    status: str = "ok",
    **detail: Any,
) -> None:
    await deps.audit.write(
        AuditEvent(
            request_id=ctx.request_id,
            thread_id=ctx.thread_id,
            actor=ctx.principal.subject,
            role=ctx.principal.role,
            kind=kind,
            name=name,
            status=status,
            detail=redact(detail),
        )
    )
