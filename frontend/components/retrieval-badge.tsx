import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface RetrievalBadgeProps {
  mode?: RetrievalMode;
  label?: string;
  count?: number;
  size?: "sm" | "md";
  className?: string;
}

export function RetrievalBadge({ mode = "vector", label, count, size = "md", className }: RetrievalBadgeProps) {
  const isGraph = mode === "graph";
  const text = label ?? (isGraph ? "Graph search" : "Vector search");
  const iconSize = size === "sm" ? 11 : 13;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-full)] border font-semibold font-[var(--font-mono)]",
        size === "sm" ? "px-2 py-0.5 text-[var(--text-2xs)]" : "px-2.5 py-1 text-[var(--text-xs)]",
        isGraph
          ? "text-[var(--mode-graph-text)] bg-[var(--mode-graph-soft)] border-[var(--graph-300)]"
          : "text-[var(--mode-vector-text)] bg-[var(--mode-vector-soft)] border-[var(--vector-300)]",
        className
      )}
    >
      {isGraph ? (
        <svg width={iconSize} height={iconSize} viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="3.5" cy="4" r="2" fill="currentColor" />
          <circle cx="12.5" cy="5" r="2" fill="currentColor" />
          <circle cx="7.5" cy="12" r="2" fill="currentColor" />
          <path d="M4.8 5.4 6.2 10.6M9.4 6.2 5.6 11M11 6.6 8.7 10.7" stroke="currentColor" strokeWidth="1.1" />
        </svg>
      ) : (
        <svg width={iconSize} height={iconSize} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <circle cx="3" cy="4" r="1.5" /><circle cx="8.5" cy="2.5" r="1.5" />
          <circle cx="13" cy="6" r="1.5" /><circle cx="5" cy="9.5" r="1.5" />
          <circle cx="11" cy="11.5" r="1.5" /><circle cx="7" cy="13.5" r="1.5" />
        </svg>
      )}
      <span>{text}</span>
      {count != null && <span className="opacity-70">· {count}</span>}
    </span>
  );
}
