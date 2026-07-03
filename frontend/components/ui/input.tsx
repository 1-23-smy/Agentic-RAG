import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  iconLeft?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, iconLeft, id, className, ...rest }, ref) => {
    const fieldId = id ?? (label ? `in-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="font-[var(--fw-semibold)] text-[var(--text-xs)] text-[var(--text-body)]">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {iconLeft && (
            <span aria-hidden="true" className="pointer-events-none absolute left-[0.6875rem] inline-flex text-[var(--text-faint)]">
              {iconLeft}
            </span>
          )}
          <input
            ref={ref}
            id={fieldId}
            className={cn(
              "w-full rounded-[var(--radius-control)] border bg-[var(--surface-card)] py-2 px-3 text-[var(--text-sm)] text-[var(--text-strong)] outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:border-[var(--border-strong)] focus:border-[var(--border-focus)] focus:shadow-[var(--ring)]",
              error ? "border-[var(--danger-500)]" : "border-[var(--border-default)]",
              iconLeft && "pl-9",
              className
            )}
            {...rest}
          />
        </div>
        {(hint || error) && (
          <span className={cn("text-[var(--text-xs)]", error ? "text-[var(--danger-600)]" : "text-[var(--text-muted)]")}>
            {error || hint}
          </span>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
