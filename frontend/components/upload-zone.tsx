import * as React from "react";
import { cn } from "@/lib/utils";

export interface UploadZoneProps {
  title?: string;
  hint?: string;
  dragging?: boolean;
  onSelect?: () => void;
  className?: string;
}

export function UploadZone({
  title = "Drop a PDF to ingest",
  hint = "or click to browse · one PDF at a time",
  dragging = false,
  onSelect,
  className,
}: UploadZoneProps) {
  return (
    <div
      role="button"
      onClick={onSelect}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[var(--radius-lg)] border-[1.5px] border-dashed p-9 text-center transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] cursor-pointer",
        dragging ? "border-[var(--signal-400)] bg-[var(--accent-soft)]" : "border-[var(--border-default)] bg-[var(--surface-sunken)]",
        className
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-card)] text-[var(--accent)] shadow-[var(--shadow-xs)]" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 16V4M12 4 7 9M12 4l5 5" />
          <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
        </svg>
      </span>
      <div>
        <div className="text-[var(--text-md)] font-semibold text-[var(--text-strong)]">{title}</div>
        <div className="mt-0.5 text-[var(--text-xs)] text-[var(--text-muted)] font-[var(--font-mono)]">{hint}</div>
      </div>
    </div>
  );
}
