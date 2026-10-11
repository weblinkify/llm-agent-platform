import { BookOpen, Bot, Radio, ShieldCheck, UserSearch, Zap } from "lucide-react";
import type { AgentName } from "@/lib/types";

const SPECIALISTS: { id: AgentName; label: string; icon: typeof Bot }[] = [
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "customer", label: "Customer", icon: UserSearch },
  { id: "incident", label: "Incident", icon: Radio },
  { id: "action", label: "Action", icon: Zap },
];

function Node({
  label,
  icon: Icon,
  state,
  id,
}: {
  label: string;
  icon: typeof Bot;
  state: "idle" | "active" | "done";
  id: string;
}) {
  const style =
    state === "active"
      ? "agent-active border-indigo-400 bg-indigo-500/20 text-indigo-200"
      : state === "done"
        ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
        : "border-slate-800 bg-slate-900 text-slate-500";
  return (
    <div
      data-testid={`agent-${id}`}
      data-state={state}
      className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${style}`}
    >
      <Icon size={14} />
      {label}
    </div>
  );
}

export function AgentFlow({ active, visited }: { active: AgentName | null; visited: Set<AgentName> }) {
  const state = (id: AgentName) => (active === id ? "active" : visited.has(id) ? "done" : "idle");
  return (
    <div className="flex items-center gap-3">
      <Node id="supervisor" label="Supervisor" icon={Bot} state={state("supervisor")} />
      <span className="text-slate-600">→</span>
      <div className="grid grid-cols-2 gap-1.5">
        {SPECIALISTS.map((s) => (
          <Node key={s.id} id={s.id} label={s.label} icon={s.icon} state={state(s.id)} />
        ))}
      </div>
      <span className="text-slate-600">→</span>
      <Node id="guard" label="Guard" icon={ShieldCheck} state={state("guard")} />
    </div>
  );
}
