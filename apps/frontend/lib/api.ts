import type { Approval, ChatResponse, Info, Role, StreamEvent } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
const tokens = new Map<Role, string>();

async function token(role: Role): Promise<string> {
  const cached = tokens.get(role);
  if (cached) return cached;
  const res = await fetch(`${BASE}/auth/demo-token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) throw new Error(`Login failed (${res.status})`);
  const body = (await res.json()) as { access_token: string };
  tokens.set(role, body.access_token);
  return body.access_token;
}

async function call<T>(role: Role, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${await token(role)}`,
      ...init.headers,
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

export const getInfo = async (): Promise<Info> => (await fetch(`${BASE}/info`)).json();

export const listApprovals = (role: Role) => call<Approval[]>(role, "/approvals?status=PENDING");

export const decideApproval = (role: Role, id: string, decision: "approve" | "reject", reason: string) =>
  call<ChatResponse>(role, `/approvals/${id}`, {
    method: "POST",
    body: JSON.stringify({ decision, reason }),
  });

/** POST /chat/stream and yield parsed server-sent events. */
export async function* streamChat(role: Role, message: string): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${await token(role)}` },
    body: JSON.stringify({ message }),
  });
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `Request failed (${res.status})`);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data) as StreamEvent;
    }
  }
}
