import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, hint, rows = 3, id, className, ...rest }, ref) => {
    const fieldId = id ?? (label ? `ta-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="font-[var(--fw-semibold)] text-[var(--text-xs)] text-[var(--text-body)]">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={fieldId}
          rows={rows}
          className={cn(
            "w-full resize-y rounded-[var(--radius-control)] border border-[var(--border-default)] bg-[var(--surface-card)] py-2.5 px-3 text-[var(--text-sm)] text-[var(--text-strong)] outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:border-[var(--border-strong)] focus:border-[var(--border-focus)] focus:shadow-[var(--ring)]",
            className
          )}
          {...rest}
        />
        {hint && <span className="text-[var(--text-xs)] text-[var(--text-muted)]">{hint}</span>}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";
