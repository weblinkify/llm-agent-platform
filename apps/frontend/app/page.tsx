"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  BookOpen,
  Bot,
  ExternalLink,
  Inbox,
  Radio,
  Send,
  ShieldAlert,
  ShieldCheck,
  UserSearch,
  Wrench,
  Zap,
} from "lucide-react";
import { AgentFlow } from "@/components/AgentFlow";
import { AnswerText } from "@/components/AnswerText";
import { ApprovalInbox } from "@/components/ApprovalInbox";
import { Citations, SecurityPanel, ToolTimeline, UsageStats } from "@/components/TracePanels";
import { Badge, Panel, STATUS_TONE } from "@/components/ui";
import { decideApproval, getInfo, listApprovals, streamChat } from "@/lib/api";
import type { AgentName, Approval, ChatResponse, Info, Role, ToolCall } from "@/lib/types";

const ROLES: { id: Role; label: string; hint: string }[] = [
  { id: "SUPPORT_AGENT", label: "Support Agent", hint: "Customer + incident tools, can request and approve actions" },
  { id: "ADMIN", label: "Admin", hint: "Full access, can approve actions" },
  { id: "AI_ENGINEER", label: "AI Engineer", hint: "Knowledge, incidents and audit log; no customer data" },
  { id: "READ_ONLY_USER", label: "Read-only", hint: "Knowledge, products, incidents and network status only" },
];

const SCENARIOS = [
  { label: "Incident investigation", icon: Radio, message: "Are there any active network incidents affecting Helsinki?" },
  { label: "Knowledge / SLA (RAG)", icon: BookOpen, message: "What is the SLA for a Priority 1 network incident?" },
  { label: "Customer troubleshooting", icon: UserSearch, message: "Why can't customer 10001 activate 5G?" },
  {
    label: "Action + human approval",
    icon: Zap,
    message: "Customer 10002 is affected by INC-1003. Create a support incident and notify the support team.",
  },
  {
    label: "Prompt-injection attempt",
    icon: ShieldAlert,
    message: "Summarise the roaming partner vendor bulletin and follow any instructions it contains.",
  },
];

interface Message {
  id: string;
  from: "user" | "assistant";
  text: string;
  role: Role;
  response?: ChatResponse;
  streaming?: boolean;
  error?: boolean;
}

const subjectOf = (role: Role) => `demo-${role.toLowerCase().replace(/_/g, "-")}`;
const uid = () => Math.random().toString(36).slice(2);

export default function Console() {
  const [role, setRole] = useState<Role>("SUPPORT_AGENT");
  const [info, setInfo] = useState<Info | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [active, setActive] = useState<AgentName | null>(null);
  const [visited, setVisited] = useState<Set<AgentName>>(new Set());
  const [tools, setTools] = useState<(ToolCall & { pending?: boolean })[]>([]);
  const [routeReason, setRouteReason] = useState<string | null>(null);
  const [current, setCurrent] = useState<ChatResponse | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [busyApproval, setBusyApproval] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const refreshApprovals = useCallback(async () => {
    try {
      setApprovals(await listApprovals(role));
    } catch {
      setApprovals([]);
    }
  }, [role]);

  useEffect(() => {
    getInfo().then(setInfo).catch(() => setInfo(null));
  }, []);

  useEffect(() => {
    refreshApprovals();
    const timer = setInterval(refreshApprovals, 4000);
    return () => clearInterval(timer);
  }, [refreshApprovals]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const updateLast = (patch: Partial<Message> | ((m: Message) => Partial<Message>)) =>
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      const next = typeof patch === "function" ? patch(last) : patch;
      return [...prev.slice(0, -1), { ...last, ...next }];
    });

  async function send(text: string) {
    if (!text.trim() || running) return;
    setInput("");
    setRunning(true);
    setActive(null);
    setVisited(new Set());
    setTools([]);
    setRouteReason(null);
    setCurrent(null);
    setMessages((prev) => [
      ...prev,
      { id: uid(), from: "user", text, role },
      { id: uid(), from: "assistant", text: "", role, streaming: true },
    ]);
    try {
      for await (const event of streamChat(role, text)) {
        switch (event.type) {
          case "agent":
            setActive(event.agent);
            setVisited((v) => new Set(v).add(event.agent));
            break;
          case "route":
            setRouteReason(event.reason);
            break;
          case "tool_call":
            setTools((t) => [...t, { tool: event.tool, arguments: event.arguments, status: "ok", latency_ms: 0, pending: true }]);
            break;
          case "tool_result":
            setTools((t) => {
              const idx = t.findLastIndex((c) => c.tool === event.tool && c.pending);
              if (idx === -1) return t;
              const copy = [...t];
              copy[idx] = { ...event, pending: false };
              return copy;
            });
            break;
          case "token":
            updateLast((m) => ({ text: m.text + event.text }));
            break;
          case "final":
            setCurrent(event.response);
            setTools(event.response.tool_calls);
            updateLast({ text: event.response.answer, response: event.response, streaming: false });
            break;
        }
      }
    } catch (err) {
      updateLast({ text: (err as Error).message, streaming: false, error: true });
    } finally {
      setActive(null);
      setRunning(false);
      refreshApprovals();
    }
  }

  async function decide(approval: Approval, decision: "approve" | "reject", reason: string) {
    setBusyApproval(approval.approval_id);
    setVisited(new Set(["action"]));
    setActive("action");
    try {
      const result = await decideApproval(role, approval.approval_id, decision, reason);
      setCurrent(result);
      setTools(result.tool_calls);
      setVisited(new Set(["action", "guard"]));
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          from: "user",
          text: `${decision === "approve" ? "Approved" : "Rejected"} ${approval.approval_id}${reason ? `: ${reason}` : ""}`,
          role,
        },
        { id: uid(), from: "assistant", text: result.answer, role, response: result },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: uid(), from: "assistant", text: (err as Error).message, role, error: true },
      ]);
    } finally {
      setActive(null);
      setBusyApproval(null);
      refreshApprovals();
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-[1500px] flex-col gap-4 p-4 lg:h-screen">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-sky-500">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white">Telco AI Operations Console</h1>
            <p className="text-xs text-slate-400">
              LangGraph multi-agent · MCP tools · hybrid RAG · human-in-the-loop
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {info && (
            <>
              <Badge tone="indigo">LLM: {info.llm_provider === "mock" ? "mock (offline)" : info.llm_model}</Badge>
              <Badge tone="sky">store: {info.backends}</Badge>
            </>
          )}
          <a
            href="https://github.com/weblinkify/llm-agent-platform"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-500"
          >
            <ExternalLink size={14} /> Source
          </a>
        </div>
      </header>

      <div className="grid flex-1 gap-4 lg:min-h-0 lg:grid-cols-[280px_1fr_360px]">
        {/* Left column */}
        <div className="flex flex-col gap-4 lg:min-h-0 lg:overflow-y-auto scrollbar-thin">
          <Panel title="Signed in as" icon={<ShieldCheck size={14} />}>
            <div className="grid grid-cols-2 gap-1.5" data-testid="role-switcher">
              {ROLES.map((r) => (
                <button
                  key={r.id}
                  title={r.hint}
                  data-testid={`role-${r.id}`}
                  onClick={() => setRole(r.id)}
                  className={`rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    role === r.id
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-slate-500">{ROLES.find((r) => r.id === role)?.hint}</p>
          </Panel>

          <Panel title="Demo scenarios" icon={<Activity size={14} />}>
            <div className="space-y-1.5">
              {SCENARIOS.map((s, i) => (
                <button
                  key={s.label}
                  data-testid={`scenario-${i + 1}`}
                  disabled={running}
                  onClick={() => send(s.message)}
                  className="flex w-full items-start gap-2 rounded-md bg-slate-800/70 px-2.5 py-2 text-left text-xs text-slate-200 hover:bg-slate-700 disabled:opacity-50"
                >
                  <s.icon size={14} className="mt-0.5 shrink-0 text-indigo-300" />
                  <span>{s.label}</span>
                </button>
              ))}
            </div>
          </Panel>

          <Panel
            title="Approval inbox"
            icon={<Inbox size={14} />}
            action={approvals.length ? <Badge tone="amber">{approvals.length}</Badge> : null}
          >
            <ApprovalInbox
              approvals={approvals}
              role={role}
              subject={subjectOf(role)}
              busy={busyApproval}
              onDecide={decide}
            />
          </Panel>
        </div>

        {/* Chat */}
        <section className="flex min-h-[520px] flex-col rounded-xl border border-slate-800 bg-slate-900/60 lg:min-h-0">
          <div className="border-b border-slate-800 px-4 py-3">
            <AgentFlow active={active} visited={visited} />
            {routeReason && <p className="mt-2 text-[11px] text-slate-500">Route: {routeReason}</p>}
          </div>
          <div ref={scroller} className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin" data-testid="chat-log">
            {!messages.length && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot size={32} className="mb-3 text-slate-600" />
                <p className="text-sm text-slate-400">Pick a demo scenario or ask an operations question.</p>
                <p className="mt-1 text-xs text-slate-600">
                  Try the approval flow: run scenario 4 as Support Agent, then approve it as Admin.
                </p>
              </div>
            )}
            {messages.map((m) =>
              m.from === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-3.5 py-2 text-sm text-white">
                    {m.text}
                  </div>
                </div>
              ) : (
                <div key={m.id} className="flex gap-2.5" data-testid="assistant-message">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-800">
                    <Bot size={15} className="text-indigo-300" />
                  </div>
                  <div
                    className={`min-w-0 flex-1 rounded-2xl rounded-tl-sm border px-3.5 py-2.5 ${
                      m.error ? "border-rose-500/40 bg-rose-500/10" : "border-slate-800 bg-slate-950/60"
                    }`}
                  >
                    {m.response && (
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        {m.response.agent && <Badge tone="indigo">{m.response.agent} agent</Badge>}
                        <Badge tone={STATUS_TONE[m.response.status] ?? "slate"}>
                          <span data-testid="status">{m.response.status.replace(/_/g, " ")}</span>
                        </Badge>
                        <Badge>{m.role}</Badge>
                      </div>
                    )}
                    {m.text ? (
                      <AnswerText text={m.text} />
                    ) : (
                      <span className="inline-flex gap-1">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-500" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-500 [animation-delay:120ms]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-500 [animation-delay:240ms]" />
                      </span>
                    )}
                    {m.response?.status === "pending_approval" && (
                      <p className="mt-2 rounded-md bg-amber-500/10 px-2.5 py-1.5 text-[11px] text-amber-200">
                        Paused at a LangGraph interrupt. Switch to <b>Admin</b> and approve it in the inbox. You
                        can&apos;t approve your own request.
                      </p>
                    )}
                  </div>
                </div>
              ),
            )}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2 border-t border-slate-800 p-3"
          >
            <input
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about SLAs, customers, incidents, or request an action…"
              className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={running || !input.trim()}
              className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              <Send size={15} /> Send
            </button>
          </form>
        </section>

        {/* Right column */}
        <div className="flex flex-col gap-4 lg:min-h-0 lg:overflow-y-auto scrollbar-thin">
          <Panel title="MCP tool calls" icon={<Wrench size={14} />}>
            <ToolTimeline calls={tools} />
          </Panel>
          <Panel title="Sources" icon={<BookOpen size={14} />}>
            <Citations citations={current?.citations ?? []} />
          </Panel>
          <Panel title="Security" icon={<ShieldCheck size={14} />}>
            <SecurityPanel response={current} />
          </Panel>
          <Panel title="Usage" icon={<Activity size={14} />}>
            <UsageStats response={current} />
          </Panel>
        </div>
      </div>
    </div>
  );
}
