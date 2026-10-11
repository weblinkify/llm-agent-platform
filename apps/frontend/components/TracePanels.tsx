"use client";

import { useState } from "react";
import { CheckCircle2, ChevronDown, FileText, ShieldAlert, XCircle } from "lucide-react";
import type { ChatResponse, Citation, ToolCall } from "@/lib/types";
import { Badge, Empty } from "./ui";

export function ToolTimeline({ calls }: { calls: (ToolCall & { pending?: boolean })[] }) {
  if (!calls.length) return <Empty>No MCP tool calls yet.</Empty>;
  return (
    <ol className="relative space-y-2 border-l border-slate-800 pl-4" data-testid="tool-timeline">
      {calls.map((call, i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border border-slate-900 bg-slate-700" />
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 font-mono text-xs text-slate-200">
              {call.pending ? (
                <span className="h-3 w-3 animate-spin rounded-full border border-indigo-400 border-t-transparent" />
              ) : call.status === "ok" ? (
                <CheckCircle2 size={13} className="text-emerald-400" />
              ) : (
                <XCircle size={13} className="text-rose-400" />
              )}
              {call.tool}
            </span>
            {!call.pending && <span className="font-mono text-[10px] text-slate-500">{call.latency_ms} ms</span>}
          </div>
          <p className="mt-0.5 truncate font-mono text-[10px] text-slate-500">
            {JSON.stringify(call.arguments)}
          </p>
          {call.error && <p className="mt-0.5 text-[11px] text-rose-300">{call.error}</p>}
        </li>
      ))}
    </ol>
  );
}

function CitationCard({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50" data-testid="citation">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <span className="flex min-w-0 items-center gap-2">
          <FileText size={14} className="shrink-0 text-indigo-300" />
          <span className="font-mono text-[11px] text-indigo-300">{citation.doc_id}</span>
          <span className="truncate text-xs text-slate-300">{citation.title}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span className="h-1 w-12 overflow-hidden rounded bg-slate-800">
            <span
              className="block h-full bg-indigo-400"
              style={{ width: `${Math.min(100, Math.round(citation.similarity * 200))}%` }}
            />
          </span>
          <ChevronDown size={14} className={`text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-800 px-3 py-2">
          <p className="mb-1 text-[11px] text-slate-500">
            {citation.section} · similarity {citation.similarity.toFixed(3)}
          </p>
          <p className="max-h-48 overflow-y-auto whitespace-pre-line text-xs leading-relaxed text-slate-300 scrollbar-thin">
            {citation.snippet.replace(/\*\*|^#+\s*/gm, "").replace(/\n{2,}/g, "\n")}
          </p>
        </div>
      )}
    </div>
  );
}

export function Citations({ citations }: { citations: Citation[] }) {
  if (!citations.length) return <Empty>No sources for this answer.</Empty>;
  return (
    <div className="space-y-2">
      {citations.map((c) => (
        <CitationCard key={c.chunk_id} citation={c} />
      ))}
    </div>
  );
}

export function SecurityPanel({ response }: { response: ChatResponse | null }) {
  const quarantined = response?.quarantined_sources ?? [];
  const flags = response?.security_flags ?? [];
  if (!quarantined.length && !flags.length)
    return <Empty>No security controls triggered.</Empty>;
  return (
    <div className="space-y-2" data-testid="security-panel">
      {quarantined.map((q) => (
        <div key={q.chunk_id} className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5">
          <p className="flex items-center gap-1.5 text-xs font-medium text-rose-200">
            <ShieldAlert size={14} /> Quarantined {q.doc_id}: {q.title}
          </p>
          <p className="mt-1 text-[11px] text-rose-300/80">
            Withheld from the model (prompt injection: {q.rules.join(", ")})
          </p>
        </div>
      ))}
      {flags.map((f) => (
        <Badge key={f} tone="amber">
          {f}
        </Badge>
      ))}
    </div>
  );
}

export function UsageStats({ response }: { response: ChatResponse | null }) {
  if (!response) return <Empty>Run a request to see tokens, cost and latency.</Empty>;
  const u = response.usage;
  const stats = [
    ["Latency", `${response.latency_ms.toFixed(0)} ms`],
    ["LLM calls", String(u.llm_calls)],
    ["Tokens", `${u.input_tokens} in / ${u.output_tokens} out`],
    ["Cost", `$${u.cost_usd.toFixed(5)}`],
  ];
  return (
    <dl className="grid grid-cols-2 gap-2">
      {stats.map(([k, v]) => (
        <div key={k} className="rounded-lg bg-slate-950/50 px-3 py-2">
          <dt className="text-[10px] uppercase tracking-wider text-slate-500">{k}</dt>
          <dd className="font-mono text-sm text-slate-200">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
