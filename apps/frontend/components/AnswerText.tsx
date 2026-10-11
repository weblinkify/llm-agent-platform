import { Fragment } from "react";

function withCitations(text: string) {
  return text.split(/(\[DOC-\d+\])/g).map((part, i) =>
    /^\[DOC-\d+\]$/.test(part) ? (
      <span
        key={i}
        className="mx-0.5 rounded bg-indigo-500/20 px-1.5 py-px font-mono text-[10px] text-indigo-300"
      >
        {part.slice(1, -1)}
      </span>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
}

export function AnswerText({ text }: { text: string }) {
  const lines = text.split("\n").filter((l) => l.trim());
  return (
    <div className="space-y-1.5 text-sm leading-relaxed text-slate-200">
      {lines.map((line, i) => {
        const bullet = /^\s*-\s+/.test(line);
        const body = line.replace(/^\s*-\s+/, "");
        const pass = body.startsWith("PASS ");
        const fail = body.startsWith("FAIL ");
        return bullet ? (
          <div key={i} className="flex gap-2 pl-1">
            <span className={pass ? "text-emerald-400" : fail ? "text-rose-400" : "text-slate-500"}>
              {pass ? "✓" : fail ? "✕" : "•"}
            </span>
            <span>{withCitations(pass || fail ? body.slice(5) : body)}</span>
          </div>
        ) : (
          <p key={i}>{withCitations(line)}</p>
        );
      })}
    </div>
  );
}
