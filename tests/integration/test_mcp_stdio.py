"""Launch the MCP server as a subprocess over stdio, exactly as Claude Desktop does."""

import sys

from mcp import Client, StdioServerParameters


async def test_stdio_server_lists_tools_and_answers() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "apps.mcp_server"],
        env={"MCP_STDIO_ROLE": "READ_ONLY_USER", "LLM_PROVIDER": "mock", "DATABASE_URL": ""},
    )
    async with Client(params) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
        assert len(tools) == 12
        result = await client.call_tool(
            "search_knowledge_base", {"query": "Priority 1 SLA restore"}
        )
        assert not result.is_error
        assert result.structured_content["results"][0]["doc_id"] == "DOC-001"
        denied = await client.call_tool("get_customer", {"customer_id": "10001"})
        assert denied.is_error
