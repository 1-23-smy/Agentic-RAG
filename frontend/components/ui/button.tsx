import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "solid" | "soft" | "outline" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
  loading?: boolean;
  fullWidth?: boolean;
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-[var(--text-xs)] gap-1.5 h-[30px]",
  md: "px-3.5 py-2 text-[var(--text-sm)] gap-2 h-[38px]",
  lg: "px-[1.125rem] py-[0.6875rem] text-[var(--text-md)] gap-2 h-[46px]",
};

const variantClasses: Record<ButtonVariant, string> = {
  solid: "bg-[var(--accent)] text-[var(--text-on-accent)] border border-transparent hover:bg-[var(--accent-hover)]",
  soft: "bg-[var(--accent-soft)] text-[var(--accent-soft-text)] border border-transparent hover:bg-[color-mix(in_oklab,var(--accent-soft)_70%,var(--accent))]",
  outline: "bg-[var(--surface-card)] text-[var(--text-strong)] border border-[var(--border-default)] hover:bg-[var(--surface-sunken)] hover:border-[var(--border-strong)]",
  ghost: "bg-transparent text-[var(--text-body)] border border-transparent hover:bg-[var(--surface-sunken)]",
  danger: "bg-[var(--danger-500)] text-white border border-transparent hover:bg-[var(--danger-600)]",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = "solid",
      size = "md",
      iconLeft,
      iconRight,
      loading = false,
      fullWidth = false,
      disabled,
      className,
      type = "button",
      ...rest
    },
    ref
  ) => {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-[var(--radius-control)] font-semibold tracking-[var(--track-snug)] transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] active:scale-[0.994] active:translate-y-[0.5px]",
          sizeClasses[size],
          variantClasses[variant],
          fullWidth && "w-full",
          isDisabled ? "cursor-not-allowed opacity-55" : "cursor-pointer",
          className
        )}
        {...rest}
      >
        {loading && (
          <span
            aria-hidden="true"
            className="h-[0.85em] w-[0.85em] animate-spin rounded-full border-2 border-current border-t-transparent"
          />
        )}
        {!loading && iconLeft}
        {children && <span>{children}</span>}
        {iconRight}
      </button>
    );
  }
);
Button.displayName = "Button";
