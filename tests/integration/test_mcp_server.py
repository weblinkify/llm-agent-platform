from typing import Any

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer

from apps.mcp_server.bootstrap import build_retriever, load_enterprise
from apps.mcp_server.server import AUTH_META_KEY, GRANT_META_KEY, build_mcp_server
from core.models import Principal, Role
from core.settings import Settings
from rag.embeddings import HashingEmbedder
from rag.store import InMemoryVectorStore
from security.auth import issue_approval_grant, issue_token

README_TOOLS = {
    "get_customer",
    "search_customer",
    "get_customer_services",
    "get_product",
    "search_products",
    "get_incident",
    "search_incidents",
    "create_incident",
    "update_incident",
    "search_knowledge_base",
    "get_network_status",
    "create_notification",
}


@pytest.fixture(scope="module")
async def server(settings: Settings) -> MCPServer:
    retriever = await build_retriever(InMemoryVectorStore(), HashingEmbedder(), settings)
    return build_mcp_server(load_enterprise(settings), retriever, settings)


def meta(settings: Settings, role: Role, grant_tools: list[str] | None = None) -> Any:
    principal = Principal(subject=f"mcp-{role.value.lower()}", role=role)
    data = {AUTH_META_KEY: issue_token(principal, settings)}
    if grant_tools:
        approver = Principal(subject="approver", role=Role.ADMIN)
        data[GRANT_META_KEY] = issue_approval_grant("APR-T", grant_tools, approver, settings)
    return data


async def test_all_readme_tools_exposed_with_schemas(server: MCPServer) -> None:
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == README_TOOLS
    for tool in tools.values():
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None
    assert tools["create_incident"].annotations.read_only_hint is False
    assert tools["get_customer"].annotations.read_only_hint is True


async def test_read_tool_returns_structured_content(server: MCPServer, settings: Settings) -> None:
    async with Client(server) as client:
        result = await client.call_tool(
            "get_customer", {"customer_id": "10001"}, meta=meta(settings, Role.SUPPORT_AGENT)
        )
    assert not result.is_error
    assert result.structured_content["services"] == ["FIB-100", "MOB-4G-BASIC"]


async def test_missing_token_is_denied(server: MCPServer) -> None:
    async with Client(server) as client:
        result = await client.call_tool("get_network_status", {})
    assert result.is_error and "DENIED" in result.content[0].text


async def test_rbac_enforced_per_tool(server: MCPServer, settings: Settings) -> None:
    async with Client(server) as client:
        denied = await client.call_tool(
            "get_customer", {"customer_id": "10001"}, meta=meta(settings, Role.READ_ONLY_USER)
        )
        allowed = await client.call_tool(
            "get_network_status", {"location": "Helsinki"}, meta=meta(settings, Role.READ_ONLY_USER)
        )
    assert denied.is_error and "not permitted" in denied.content[0].text
    assert not allowed.is_error
    assert allowed.structured_content["regions"][0]["status"] == "DEGRADED"


async def test_input_validation_and_not_found(server: MCPServer, settings: Settings) -> None:
    async with Client(server) as client:
        invalid = await client.call_tool(
            "get_customer", {"customer_id": "abc"}, meta=meta(settings, Role.ADMIN)
        )
        missing = await client.call_tool(
            "get_incident", {"incident_id": "INC-9999"}, meta=meta(settings, Role.ADMIN)
        )
    assert invalid.is_error
    assert missing.is_error and "NOT_FOUND" in missing.content[0].text


async def test_write_tools_require_approval_grant(server: MCPServer, settings: Settings) -> None:
    args = {"title": "Test incident", "description": "Created by test", "severity": "P3"}
    async with Client(server) as client:
        no_grant = await client.call_tool("create_incident", args, meta=meta(settings, Role.ADMIN))
        wrong_scope = await client.call_tool(
            "create_incident", args, meta=meta(settings, Role.ADMIN, ["create_notification"])
        )
        granted = await client.call_tool(
            "create_incident", args, meta=meta(settings, Role.ADMIN, ["create_incident"])
        )
    assert no_grant.is_error and "approval grant" in no_grant.content[0].text
    assert wrong_scope.is_error
    assert not granted.is_error and granted.structured_content["status"] == "OPEN"


async def test_knowledge_search_quarantines_poisoned_chunk(
    server: MCPServer, settings: Settings
) -> None:
    async with Client(server) as client:
        result = await client.call_tool(
            "search_knowledge_base",
            {"query": "roaming partner network codes Estonia"},
            meta=meta(settings, Role.READ_ONLY_USER),
        )
    data = result.structured_content
    assert data["sufficient"]
    assert all(hit["doc_id"] != "DOC-099" for hit in data["results"])
    assert data["quarantined"][0]["doc_id"] == "DOC-099"
