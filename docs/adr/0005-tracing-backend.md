# ADR-0005: OpenTelemetry with Jaeger locally instead of self-hosted Langfuse

**Status:** accepted

## Context

The goal was one trace per request across API → supervisor → agent → MCP tool → LLM, with tokens and cost. Self-hosting Langfuse v3 needs Postgres, ClickHouse, Redis and MinIO (six containers), which would double the size of the local stack.

## Decision

Instrument with **vendor-neutral OpenTelemetry**, using GenAI semantic-convention attributes (`gen_ai.usage.input_tokens`, `gen_ai.request.model`, plus `llm.cost_usd`). Export over OTLP/HTTP. Compose ships **Jaeger** (one container). Both the API and the MCP server export, so traces cross the service boundary.

## Consequences

* Pointing `OTEL_EXPORTER_OTLP_ENDPOINT` at Langfuse (which accepts OTLP), Grafana Tempo, or an OTel Collector feeding Azure Monitor works with no code changes.
* Prometheus metrics at `/metrics` cover the aggregate view (latency histograms, tokens, cost, tool errors, security events).
