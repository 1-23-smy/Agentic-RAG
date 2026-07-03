import * as React from "react";
import { cn } from "@/lib/utils";

type BadgeTone = "neutral" | "accent" | "vector" | "graph" | "success" | "warning" | "danger";
type BadgeVariant = "soft" | "solid" | "outline";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  dot?: boolean;
}

const toneClasses: Record<BadgeTone, Record<BadgeVariant, string>> = {
  neutral: {
    soft: "bg-[var(--ink-100)] text-[var(--ink-700)]",
    solid: "bg-[var(--ink-800)] text-white",
    outline: "bg-transparent text-[var(--text-body)] border-[var(--border-default)]",
  },
  accent: {
    soft: "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]",
    solid: "bg-[var(--accent)] text-white",
    outline: "bg-transparent text-[var(--accent-soft-text)] border-[var(--signal-300)]",
  },
  vector: {
    soft: "bg-[var(--mode-vector-soft)] text-[var(--mode-vector-text)]",
    solid: "bg-[var(--vector-600)] text-white",
    outline: "bg-transparent text-[var(--mode-vector-text)] border-[var(--vector-300)]",
  },
  graph: {
    soft: "bg-[var(--mode-graph-soft)] text-[var(--mode-graph-text)]",
    solid: "bg-[var(--graph-600)] text-white",
    outline: "bg-transparent text-[var(--mode-graph-text)] border-[var(--graph-300)]",
  },
  success: {
    soft: "bg-[var(--success-50)] text-[var(--success-600)]",
    solid: "bg-[var(--success-500)] text-white",
    outline: "bg-transparent text-[var(--success-600)] border-[var(--success-500)]",
  },
  warning: {
    soft: "bg-[var(--warning-50)] text-[var(--warning-600)]",
    solid: "bg-[var(--warning-500)] text-white",
    outline: "bg-transparent text-[var(--warning-600)] border-[var(--warning-500)]",
  },
  danger: {
    soft: "bg-[var(--danger-50)] text-[var(--danger-600)]",
    solid: "bg-[var(--danger-500)] text-white",
    outline: "bg-transparent text-[var(--danger-600)] border-[var(--danger-500)]",
  },
};

export function Badge({ children, tone = "neutral", variant = "soft", size = "md", dot = false, className, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-full)] border border-transparent font-semibold tracking-[var(--track-snug)]",
        size === "sm" ? "px-[0.4375rem] py-[0.0625rem] text-[var(--text-2xs)]" : "px-2 py-[0.1875rem] text-[var(--text-xs)]",
        toneClasses[tone][variant],
        className
      )}
      {...rest}
    >
      {dot && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />}
      {children}
    </span>
  );
}
