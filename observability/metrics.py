from prometheus_client import CollectorRegistry, Counter, Histogram

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "telco_http_requests_total",
    "HTTP requests",
    ["method", "route", "status"],
    registry=REGISTRY,
)
CHAT_LATENCY = Histogram(
    "telco_chat_latency_seconds",
    "End-to-end /chat latency",
    ["agent"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32),
    registry=REGISTRY,
)
AGENT_ROUTES = Counter(
    "telco_agent_routes_total",
    "Supervisor routing decisions",
    ["agent"],
    registry=REGISTRY,
)
TOOL_CALLS = Counter(
    "telco_tool_calls_total", "MCP tool calls", ["tool", "status"], registry=REGISTRY
)
TOOL_LATENCY = Histogram(
    "telco_tool_latency_seconds",
    "MCP tool latency",
    ["tool"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 2),
    registry=REGISTRY,
)
LLM_TOKENS = Counter(
    "telco_llm_tokens_total",
    "LLM tokens",
    ["provider", "model", "direction"],
    registry=REGISTRY,
)
LLM_COST = Counter(
    "telco_llm_cost_usd_total",
    "Estimated LLM cost (USD)",
    ["provider", "model"],
    registry=REGISTRY,
)
LLM_LATENCY = Histogram(
    "telco_llm_latency_seconds",
    "LLM call latency",
    ["provider", "task"],
    buckets=(0.01, 0.1, 0.5, 1, 2, 4, 8, 16),
    registry=REGISTRY,
)
RETRIEVAL_LATENCY = Histogram(
    "telco_retrieval_latency_seconds",
    "Hybrid retrieval latency",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1),
    registry=REGISTRY,
)
APPROVALS = Counter(
    "telco_approvals_total", "Approval lifecycle events", ["event"], registry=REGISTRY
)
SECURITY_EVENTS = Counter(
    "telco_security_events_total",
    "Security controls triggered",
    ["control"],
    registry=REGISTRY,
)
