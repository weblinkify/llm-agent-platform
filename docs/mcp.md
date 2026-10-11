# Using the MCP server

`apps/mcp_server` is a standard MCP server built on the official Python SDK. Any MCP client can use it.

## Claude Desktop

Add this to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "telco-enterprise": {
      "command": "/absolute/path/to/llm-agent-platform/.venv/bin/telco-mcp",
      "env": { "MCP_STDIO_ROLE": "SUPPORT_AGENT" }
    }
  }
}
```

Restart Claude Desktop and ask *"Why can't customer 10001 activate 5G?"*. Claude calls `get_customer`, `get_customer_services` and `search_knowledge_base`.

* Over stdio there is no bearer token, so `MCP_STDIO_ROLE` sets the role (default `READ_ONLY_USER`).
* Write tools (`create_incident`, `update_incident`, `create_notification`) always require an approval grant issued by the platform API, so they are unavailable over stdio by design.

## MCP Inspector

```bash
npx @modelcontextprotocol/inspector .venv/bin/telco-mcp
```

## Over HTTP

```bash
telco-mcp --transport streamable-http --host 0.0.0.0 --port 8001
```

Clients pass a platform JWT in the request `_meta` as `authorization`. Docker Compose runs it this way, with the API pointing at it through `MCP_SERVER_URL`.

## Tools

| Tool | Access | Description |
|---|---|---|
| `get_customer` | ADMIN, SUPPORT_AGENT | Customer record |
| `search_customer` | ADMIN, SUPPORT_AGENT | Search by name, city or ID |
| `get_customer_services` | ADMIN, SUPPORT_AGENT | Subscribed products |
| `get_product` | all | Catalogue item |
| `search_products` | all | Catalogue search, optional 5G filter |
| `get_incident` | all | Incident by ID |
| `search_incidents` | all | By location, status, severity |
| `get_network_status` | all | One region or all regions |
| `search_knowledge_base` | all | Hybrid RAG with quarantine info |
| `create_incident` | ADMIN, SUPPORT_AGENT + approval grant | Create incident |
| `update_incident` | ADMIN, SUPPORT_AGENT + approval grant | Status, severity, notes |
| `create_notification` | ADMIN, SUPPORT_AGENT + approval grant | Notify a team channel |
