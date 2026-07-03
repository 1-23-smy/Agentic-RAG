import { UploadZone } from "@/components/upload-zone";

export interface EmptyStateProps {
  hasDocs: boolean;
  onUploadClick: () => void;
  onSuggestionClick: (text: string) => void;
}

const SUGGESTIONS = [
  "What is this document about?",
  "Summarize the key findings.",
  "Which entities are connected to the primary outcome?",
];

export function EmptyState({ hasDocs, onUploadClick, onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-[22px] p-8 text-center">
      <div className="max-w-[520px]">
        <div className="ar-eyebrow mb-3 block text-center">Universal Agentic RAG</div>
        <h1 className="text-[42px] tracking-[-0.03em] text-[var(--text-strong)] font-[var(--font-display)] font-[var(--fw-extra)]">
          Ask across every page.
        </h1>
        <p className="mt-3 text-[var(--text-md)] text-[var(--text-muted)]">
          Upload a PDF and interrogate it. The agent routes between vector and graph search to return cited, zero-hallucination answers.
        </p>
      </div>
      {!hasDocs ? (
        <div className="w-full max-w-[460px]"><UploadZone onSelect={onUploadClick} /></div>
      ) : (
        <div className="flex max-w-[560px] flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => onSuggestionClick(s)}
              className="ar-chip-interactive rounded-[var(--radius-full)] border border-[var(--border-default)] bg-[var(--surface-card)] px-3.5 py-2 text-[13px] font-medium text-[var(--text-body)] transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
