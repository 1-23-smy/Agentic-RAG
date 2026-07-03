import * as React from "react";
import { cn } from "@/lib/utils";

export interface MessageBubbleProps {
  role: "user" | "assistant";
  children: React.ReactNode;
  sources?: React.ReactNode;
  className?: string;
}

export function MessageBubble({ role, children, sources, className }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className={cn("flex justify-end", className)}>
        <div className="max-w-[78%] rounded-[var(--radius-lg)] rounded-br-[var(--radius-xs)] border border-[var(--signal-100)] bg-[var(--accent-soft)] px-3.5 py-2.5 text-[var(--text-md)] font-medium text-[var(--accent-soft-text)]">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex gap-3", className)}>
      <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--ink-950)]" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="2" fill="var(--vector-300)" />
          <circle cx="8" cy="8" r="6" stroke="var(--signal-400)" strokeWidth="1.2" strokeDasharray="2 2.2" />
        </svg>
      </div>
      <div className="min-w-0 flex-1 pt-[3px]">
        <div className="text-[var(--text-md)] leading-[var(--lh-relaxed)] text-[var(--text-body)]">{children}</div>
        {sources && <div className="mt-3">{sources}</div>}
      </div>
    </div>
  );
}
