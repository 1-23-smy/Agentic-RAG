import * as React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevation?: "none" | "xs" | "sm" | "md" | "lg";
  padded?: boolean;
  interactive?: boolean;
}

const shadowClasses: Record<NonNullable<CardProps["elevation"]>, string> = {
  none: "shadow-none",
  xs: "shadow-[var(--shadow-xs)]",
  sm: "shadow-[var(--shadow-sm)]",
  md: "shadow-[var(--shadow-md)]",
  lg: "shadow-[var(--shadow-lg)]",
};

export function Card({ children, elevation = "sm", padded = true, interactive = false, className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-card)] border border-[var(--border-subtle)] bg-[var(--surface-card)]",
        shadowClasses[elevation],
        padded && "p-[var(--pad-card)]",
        interactive && "cursor-pointer transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
