import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface SpinnerProps {
  size?: number;
  label?: string;
  mode?: RetrievalMode | "signal";
  className?: string;
}

const colorVar: Record<string, string> = {
  vector: "var(--vector-500)",
  graph: "var(--graph-500)",
  signal: "var(--accent)",
};

export function Spinner({ size = 18, label, mode = "signal", className }: SpinnerProps) {
  const color = colorVar[mode] ?? colorVar.signal;
  const borderWidth = Math.max(2, Math.round(size / 9));
  const ring = (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        borderWidth,
        borderColor: `color-mix(in oklab, ${color} 24%, transparent)`,
        borderTopColor: color,
      }}
      className="inline-block shrink-0 animate-spin rounded-full border-solid"
    />
  );

  if (!label) return <span className={className}>{ring}</span>;

  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      {ring}
      <span className="text-[var(--text-sm)] font-medium text-[var(--text-muted)]">{label}</span>
    </span>
  );
}
