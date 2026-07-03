"use client";

import { useEffect, useRef } from "react";
import { Paperclip, Send } from "lucide-react";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

export interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onAttachClick: () => void;
  disabled?: boolean;
}

export function Composer({ value, onChange, onSend, onAttachClick, disabled = false }: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 160)}px`;
    }
  }, [value]);

  const submit = () => {
    if (value.trim() && !disabled) onSend();
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="flex justify-center px-6 pb-5 pt-3">
      <div className="flex w-full max-w-[760px] items-end gap-2 rounded-[var(--radius-xl)] border border-[var(--border-default)] bg-[var(--surface-card)] py-2 pl-3.5 pr-2 shadow-[var(--shadow-sm)]">
        <IconButton label="Attach PDF" onClick={onAttachClick}><Paperclip size={18} /></IconButton>
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask a complex question about your documents…"
          className="max-h-40 flex-1 resize-none border-none bg-transparent py-1.5 text-[15px] text-[var(--text-strong)] outline-none"
        />
        <button
          onClick={submit}
          disabled={!canSend}
          aria-label="Send"
          className={cn(
            "flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[var(--radius-lg)] border-none text-white transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
            canSend ? "cursor-pointer bg-[var(--accent)]" : "cursor-default bg-[var(--ink-200)]"
          )}
        >
          <Send size={17} />
        </button>
      </div>
    </div>
  );
}
