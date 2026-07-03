import * as React from "react";
import { cn } from "@/lib/utils";

type IconButtonSize = "sm" | "md" | "lg";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: IconButtonSize;
  label: string;
  active?: boolean;
}

const dims: Record<IconButtonSize, string> = {
  sm: "w-[30px] h-[30px]",
  md: "w-9 h-9",
  lg: "w-[42px] h-[42px]",
};

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ children, size = "md", label, active = false, disabled, className, ...rest }, ref) => (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--radius-md)] border border-transparent p-0 transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] active:scale-[0.94]",
        dims[size],
        active
          ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
          : "bg-transparent text-[var(--text-muted)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text-strong)]",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        className
      )}
      {...rest}
    >
      {children}
    </button>
  )
);
IconButton.displayName = "IconButton";
