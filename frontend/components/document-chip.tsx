import * as React from "react";
import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/lib/types";

export interface DocumentChipProps {
  title: string;
  status?: DocumentStatus;
  active?: boolean;
  onClick?: () => void;
  className?: string;
}

const statusConf: Record<DocumentStatus, { label: string; color: string; dot: string; pulse: boolean }> = {
  queued: { label: "Queued", color: "text-[var(--text-muted)]", dot: "bg-[var(--ink-400)]", pulse: false },
  ingesting: { label: "Ingesting", color: "text-[var(--warning-600)]", dot: "bg-[var(--warning-500)]", pulse: true },
  ready: { label: "Ready", color: "text-[var(--success-600)]", dot: "bg-[var(--success-500)]", pulse: false },
  failed: { label: "Failed", color: "text-[var(--danger-600)]", dot: "bg-[var(--danger-500)]", pulse: false },
};

export function DocumentChip({ title, status = "ready", active = false, onClick, className }: DocumentChipProps) {
  const conf = statusConf[status];
  return (
    <div
      role={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-[var(--radius-md)] border p-2.5 transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
        active ? "bg-[var(--accent-soft)] border-[var(--signal-300)]" : "bg-[var(--surface-card)] border-[var(--border-subtle)]",
        onClick && "cursor-pointer hover:border-[var(--border-strong)] hover:shadow-[var(--shadow-sm)]",
        className
      )}
    >
      <span className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-[color-mix(in_oklab,var(--danger-500)_20%,transparent)] bg-[var(--danger-50)] font-bold text-[8px] tracking-[0.04em] text-[var(--danger-600)] font-[var(--font-mono)]">
        PDF
      </span>
      <div className="min-w-0 flex-1">
        <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[var(--text-sm)] font-semibold text-[var(--text-strong)]">
          {title}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <span className={cn("inline-flex items-center gap-1 text-[var(--text-2xs)] font-medium font-[var(--font-mono)]", conf.color)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", conf.dot, conf.pulse && "animate-pulse")} />
            {conf.label}
          </span>
        </div>
      </div>
    </div>
  );
}
