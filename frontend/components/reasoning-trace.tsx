"use client";

import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentStep } from "@/components/agent-step";
import type { ReasoningStep } from "@/lib/types";

export interface ReasoningTraceProps {
  steps: ReasoningStep[];
  running: boolean;
}

export function ReasoningTrace({ steps, running }: ReasoningTraceProps) {
  const [open, setOpen] = useState(true);

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 border-none bg-transparent px-3.5 py-2.5 text-[12px] font-semibold uppercase tracking-[var(--track-caps)] text-[var(--text-body)] font-[var(--font-mono)]"
      >
        <Sparkles size={14} />
        <span>{running ? "Agent reasoning" : `Reasoning trace · ${steps.length} steps`}</span>
        <span className={cn("ml-auto transition-transform duration-[var(--dur-fast)]", open && "rotate-180")}>
          <ChevronDown size={15} />
        </span>
      </button>
      {open && (
        <div className="px-4 pb-3.5 pt-1">
          {steps.map((s, i) => (
            <AgentStep
              key={i}
              mode={s.mode}
              query={s.query}
              detail={s.detail}
              status={running && i === steps.length - 1 ? "running" : "done"}
              last={i === steps.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
