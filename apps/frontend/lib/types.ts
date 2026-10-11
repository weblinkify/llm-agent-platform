export type Role = "SUPPORT_AGENT" | "ADMIN" | "AI_ENGINEER" | "READ_ONLY_USER";

export type AgentName = "supervisor" | "knowledge" | "customer" | "incident" | "action" | "guard";

export interface Citation {
  doc_id: string;
  chunk_id: string;
  title: string;
  section: string;
  snippet: string;
  similarity: number;
  cited: boolean;
}

export interface ToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  status: "ok" | "error";
  latency_ms: number;
  error?: string;
}

export interface PlannedAction {
  tool: string;
  arguments: Record<string, unknown>;
  summary: string;
}

export interface Approval {
  approval_id: string;
  thread_id: string;
  requested_by: string;
  requester_role: Role;
  request_message: string;
  actions: PlannedAction[];
  status: "PENDING" | "APPROVED" | "REJECTED";
  created_at: string;
  decided_by: string | null;
  reason: string | null;
}

export interface ChatResponse {
  request_id: string;
  thread_id: string;
  agent: Exclude<AgentName, "supervisor" | "guard"> | null;
  route_reason: string | null;
  status: string;
  answer: string;
  citations: Citation[];
  quarantined_sources: { chunk_id: string; doc_id: string; title: string; rules: string[] }[];
  tool_calls: ToolCall[];
  approval: Approval | null;
  data: Record<string, unknown>;
  security_flags: string[];
  steps: string[];
  usage: {
    provider: string;
    model: string;
    llm_calls: number;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  };
  latency_ms: number;
}

export type StreamEvent =
  | { type: "agent"; agent: AgentName }
  | { type: "route"; agent: string; reason: string }
  | { type: "tool_call"; tool: string; arguments: Record<string, unknown> }
  | ({ type: "tool_result" } & ToolCall)
  | { type: "token"; text: string }
  | { type: "approval_required"; actions: PlannedAction[] }
  | { type: "approval_pending"; approval: Approval }
  | { type: "final"; response: ChatResponse };

export interface Info {
  version: string;
  llm_provider: string;
  llm_model: string;
  embeddings: string;
  backends: string;
  demo_mode: boolean;
}
