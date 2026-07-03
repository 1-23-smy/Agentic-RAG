import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface AgentStepProps {
  mode?: RetrievalMode;
  query?: string;
  detail?: string;
  status?: "done" | "running";
  last?: boolean;
}

export function AgentStep({ mode = "vector", query, detail, status = "done", last = false }: AgentStepProps) {
  const isGraph = mode === "graph";
  const accent = isGraph ? "text-[var(--mode-graph-text)]" : "text-[var(--mode-vector-text)]";
  const dotBorder = isGraph ? "border-[var(--mode-graph-text)]" : "border-[var(--mode-vector-text)]";
  const rail = isGraph ? "bg-[var(--graph-300)]" : "bg-[var(--vector-300)]";
  const running = status === "running";

  return (
    <div className="flex gap-3">
      <div className="flex shrink-0 flex-col items-center">
        <span
          className={cn(
            "mt-[3px] h-3 w-3 rounded-full border-2",
            dotBorder,
            running ? "bg-transparent animate-pulse" : isGraph ? "bg-[var(--mode-graph-text)]" : "bg-[var(--mode-vector-text)]"
          )}
        />
        {!last && <span className={cn("mt-1 min-h-[14px] w-0.5 flex-1 opacity-50", rail)} />}
      </div>
      <div className={cn("min-w-0", !last && "pb-3")}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("text-[var(--text-2xs)] font-semibold uppercase tracking-[var(--track-caps)] font-[var(--font-mono)]", accent)}>
            {isGraph ? "graph_search" : "vector_search"}
          </span>
          {query && (
            <code className="rounded-[var(--radius-xs)] bg-[var(--surface-sunken)] px-1.5 py-0.5 text-[var(--text-xs)] text-[var(--text-body)] font-[var(--font-mono)]">
              {query}
            </code>
          )}
        </div>
        {detail && <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">{detail}</p>}
      </div>
    </div>
  );
}
