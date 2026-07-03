import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface CitationProps {
  docId?: string;
  chapter?: string | null;
  section?: string | null;
  marker?: number;
  mode?: RetrievalMode;
  onClick?: () => void;
  className?: string;
}

export function Citation({ docId, chapter, section, marker, mode = "vector", onClick, className }: CitationProps) {
  const isGraph = mode === "graph";
  const parts = [docId, chapter, section].filter(Boolean) as string[];

  return (
    <span
      role={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap align-baseline font-medium text-[var(--text-2xs)] font-[var(--font-mono)] transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
        marker != null
          ? "h-[1.15rem] min-w-[1.15rem] justify-center rounded-[var(--radius-full)] px-1.5"
          : "rounded-[var(--radius-sm)] py-0.5 pl-1.5 pr-[0.4375rem]",
        isGraph
          ? "text-[var(--mode-graph-text)] bg-[var(--mode-graph-soft)] border border-[var(--graph-300)]"
          : "text-[var(--mode-vector-text)] bg-[var(--mode-vector-soft)] border border-[var(--vector-300)]",
        onClick ? "cursor-pointer hover:border-[var(--border-strong)] hover:bg-[var(--surface-sunken)]" : "cursor-default",
        className
      )}
    >
      {marker != null ? (
        <span>{marker}</span>
      ) : (
        <>
          <span aria-hidden="true" className="h-[5px] w-[5px] shrink-0 rounded-full bg-current opacity-85" />
          {parts.map((p, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="opacity-40">·</span>}
              <span>{p}</span>
            </React.Fragment>
          ))}
        </>
      )}
    </span>
  );
}
