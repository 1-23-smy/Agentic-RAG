import * as React from "react";
import { cn } from "@/lib/utils";

type AlertTone = "info" | "success" | "warning" | "danger";

export interface AlertProps {
  tone?: AlertTone;
  title?: string;
  children?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

const toneConf: Record<AlertTone, { bg: string; bd: string; fg: string; path: string }> = {
  info: { bg: "bg-[var(--accent-soft)]", bd: "border-[var(--signal-200)]", fg: "text-[var(--accent-soft-text)]", path: "M12 8h.01M11 12h1v4h1" },
  success: { bg: "bg-[var(--success-50)]", bd: "border-[color-mix(in_oklab,var(--success-500)_35%,transparent)]", fg: "text-[var(--success-600)]", path: "M20 6 9 17l-5-5" },
  warning: { bg: "bg-[var(--warning-50)]", bd: "border-[color-mix(in_oklab,var(--warning-500)_35%,transparent)]", fg: "text-[var(--warning-600)]", path: "M12 9v4M12 17h.01" },
  danger: { bg: "bg-[var(--danger-50)]", bd: "border-[color-mix(in_oklab,var(--danger-500)_35%,transparent)]", fg: "text-[var(--danger-600)]", path: "M15 9l-6 6M9 9l6 6" },
};

export function Alert({ tone = "info", title, children, onDismiss, className }: AlertProps) {
  const conf = toneConf[tone];
  return (
    <div role="status" className={cn("flex items-start gap-2.5 rounded-[var(--radius-md)] border p-3.5", conf.bg, conf.bd, className)}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={cn("mt-px shrink-0", conf.fg)} stroke="currentColor" aria-hidden="true">
        <circle cx="12" cy="12" r="9" opacity={tone === "success" || tone === "danger" ? 0 : 0.4} />
        <path d={conf.path} />
      </svg>
      <div className="min-w-0 flex-1">
        {title && <div className={cn("text-[var(--text-sm)] font-semibold", conf.fg)}>{title}</div>}
        {children && <div className={cn("text-[var(--text-sm)] text-[var(--text-body)]", title && "mt-0.5")}>{children}</div>}
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss" className={cn("shrink-0 rounded-[var(--radius-xs)] p-0.5", conf.fg)}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      )}
    </div>
  );
}
