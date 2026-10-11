# ADR-0001: Agents reach enterprise data only through MCP

**Status:** accepted

## Context

Agents need customer, product, incident and network data. Calling Python functions or databases directly from agent code mixes reasoning with integration, makes authorisation easy to bypass, and makes tools impossible to reuse from other AI clients.

## Decision

All enterprise access goes through an MCP server (`apps/mcp_server`) built on the official SDK. Agents use `McpGateway`, which is either in-process (tests, serverless) or Streamable HTTP (compose, Azure). Authorisation is enforced **in the server**: it verifies the caller's JWT from `_meta`, applies RBAC per tool, and requires a human-approval grant for writes.

## Consequences

* The same tools work from Claude Desktop, MCP Inspector or another agent framework without changes.
* The security boundary lives in one place, and an agent bug cannot skip it.
* Each tool call costs an MCP round trip. The gateway opens one client session per call (about 5 ms over the network in compose); a per-request session pool would be the next optimisation.
