"use client";

import { useState } from "react";
import { Check, Clock, X } from "lucide-react";
import type { Approval, Role } from "@/lib/types";
import { Badge, Empty } from "./ui";

const APPROVERS: Role[] = ["ADMIN", "SUPPORT_AGENT"];

export function ApprovalInbox({
  approvals,
  role,
  subject,
  busy,
  onDecide,
}: {
  approvals: Approval[];
  role: Role;
  subject: string;
  busy: string | null;
  onDecide: (approval: Approval, decision: "approve" | "reject", reason: string) => void;
}) {
  const [reasons, setReasons] = useState<Record<string, string>>({});
  if (!approvals.length) return <Empty>No pending approvals.</Empty>;
  return (
    <div className="space-y-3" data-testid="approval-inbox">
      {approvals.map((a) => {
        const own = a.requested_by === subject;
        const canApprove = APPROVERS.includes(role) && !own;
        const hint = !APPROVERS.includes(role)
          ? `${role} cannot approve actions`
          : own
            ? "Separation of duties: switch to another approver role"
            : null;
        return (
          <div
            key={a.approval_id}
            data-testid="approval-card"
            className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-[11px] text-amber-300">{a.approval_id}</span>
              <Badge tone="amber">
                <Clock size={11} /> pending
              </Badge>
            </div>
            <ul className="mb-2 space-y-1">
              {a.actions.map((action, i) => (
                <li key={i} className="text-xs text-slate-200">
                  <span className="mr-1.5 font-mono text-[10px] text-slate-500">{action.tool}</span>
                  {action.summary}
                </li>
              ))}
            </ul>
            <p className="mb-2 text-[11px] text-slate-500">
              Requested by {a.requested_by} ({a.requester_role})
            </p>
            {canApprove ? (
              <div className="space-y-2">
                <input
                  value={reasons[a.approval_id] ?? ""}
                  onChange={(e) => setReasons({ ...reasons, [a.approval_id]: e.target.value })}
                  placeholder="Reason (optional)"
                  className="w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200 outline-none focus:border-indigo-500"
                />
                <div className="flex gap-2">
                  <button
                    data-testid="approve-button"
                    disabled={busy === a.approval_id}
                    onClick={() => onDecide(a, "approve", reasons[a.approval_id] ?? "")}
                    className="flex flex-1 items-center justify-center gap-1 rounded-md bg-emerald-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    <Check size={13} /> Approve
                  </button>
                  <button
                    data-testid="reject-button"
                    disabled={busy === a.approval_id}
                    onClick={() => onDecide(a, "reject", reasons[a.approval_id] ?? "")}
                    className="flex flex-1 items-center justify-center gap-1 rounded-md bg-slate-800 px-2 py-1.5 text-xs font-medium text-slate-200 hover:bg-rose-600 disabled:opacity-50"
                  >
                    <X size={13} /> Reject
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-[11px] italic text-amber-200/70" data-testid="approval-hint">
                {hint}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
