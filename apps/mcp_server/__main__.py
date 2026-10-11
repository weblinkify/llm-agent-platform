"""Run the MCP server standalone.

    telco-mcp                                   # stdio (Claude Desktop, MCP Inspector)
    telco-mcp --transport streamable-http --port 8001

Uses pgvector when DATABASE_URL is set, otherwise an in-memory index.
"""

import argparse
import asyncio
import logging
import os

from apps.mcp_server.bootstrap import build_retriever, load_enterprise
from apps.mcp_server.server import build_mcp_server
from core.models import Principal, Role
from core.settings import get_settings
from observability.tracing import setup_tracing
from storage.factory import open_backends


async def serve(transport: str, host: str, port: int) -> None:
    settings = get_settings()
    setup_tracing(settings)
    async with open_backends(settings) as backends:
        retriever = await build_retriever(backends.vector_store, backends.embedder, settings)
        role = Role(os.getenv("MCP_STDIO_ROLE", Role.READ_ONLY_USER.value))
        default = Principal(subject="mcp-stdio-client", role=role) if transport == "stdio" else None
        server = build_mcp_server(load_enterprise(settings), retriever, settings, default)
        if transport == "stdio":
            await server.run_stdio_async()
        else:
            await server.run_streamable_http_async(host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Telco enterprise MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    # stdout belongs to the MCP protocol on stdio; log to stderr only.
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(serve(args.transport, args.host, args.port))


if __name__ == "__main__":
    main()
