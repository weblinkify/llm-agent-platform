"""Run the MCP server standalone.

telco-mcp                                   # stdio (Claude Desktop, MCP Inspector)
telco-mcp --transport streamable-http --port 8001
"""

import argparse
import asyncio
import logging
import os

from apps.mcp_server.bootstrap import build_retriever, load_enterprise
from apps.mcp_server.server import build_mcp_server
from core.models import Principal, Role
from core.settings import get_settings
from rag.embeddings import create_embedder
from rag.store import InMemoryVectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Telco enterprise MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    # stdout belongs to the MCP protocol on stdio; log to stderr only.
    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()
    embedder = create_embedder(settings)
    retriever = asyncio.run(build_retriever(InMemoryVectorStore(), embedder, settings))
    role = Role(os.getenv("MCP_STDIO_ROLE", Role.READ_ONLY_USER.value))
    default = (
        Principal(subject="mcp-stdio-client", role=role) if args.transport == "stdio" else None
    )
    server = build_mcp_server(load_enterprise(settings), retriever, settings, default)
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
