export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
        <circle cx="16" cy="16" r="14" stroke="var(--signal-500)" strokeWidth="1.5" strokeDasharray="3 3" />
        <circle cx="16" cy="16" r="3.4" fill="var(--vector-500)" />
        <circle cx="7" cy="10" r="2.2" fill="var(--graph-500)" />
        <circle cx="25" cy="12" r="2.2" fill="var(--graph-500)" />
        <path d="M9 11l5 4M23 12l-4 3" stroke="var(--graph-300)" strokeWidth="1.1" />
      </svg>
      <span className="text-[17px] font-[var(--fw-extra)] tracking-[-0.03em] text-[var(--text-strong)] font-[var(--font-display)]">
        Agentic<span className="text-[var(--accent)]">RAG</span>
      </span>
    </div>
  );
}
