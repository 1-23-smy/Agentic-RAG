"use client";

import { PanelLeftClose } from "lucide-react";
import { RetrievalBadge } from "@/components/retrieval-badge";
import { Citation } from "@/components/citation";
import { Card } from "@/components/ui/card";
import type { VectorSourceResult, GraphTriple } from "@/lib/types";

export interface SourcesPanelProps {
  open: boolean;
  onClose: () => void;
  sources: VectorSourceResult[];
  graphTriples: GraphTriple[];
}

export function SourcesPanel({ open, onClose, sources, graphTriples }: SourcesPanelProps) {
  if (!open) return null;

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-[18px] py-4">
        <span className="text-[var(--text-sm)] font-semibold text-[var(--text-strong)]">Sources</span>
        <button onClick={onClose} aria-label="Close" className="border-none bg-transparent leading-none text-[var(--text-muted)]">
          <PanelLeftClose size={17} />
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-[18px] overflow-y-auto p-4">
        {sources.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <RetrievalBadge mode="vector" count={sources.length} />
            {sources.map((s, i) => (
              <Card key={i} elevation="xs" className="p-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <Citation docId={s.doc_id} chapter={s.chapter} section={s.section} mode="vector" />
                  <span className="text-[11px] font-medium text-[var(--text-faint)] font-[var(--font-mono)]">{s.score}</span>
                </div>
                <p className="text-[12.5px] leading-[1.5] text-[var(--text-body)]">{s.snippet}</p>
              </Card>
            ))}
          </section>
        )}

        {graphTriples.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <RetrievalBadge mode="graph" count={graphTriples.length} />
            <Card elevation="xs" className="flex flex-col gap-2 p-3">
              {graphTriples.map((g, i) => (
                <div key={i} className="flex flex-wrap items-center gap-1.5 text-[12px] text-[var(--text-body)] font-[var(--font-mono)]">
                  <span className="font-semibold text-[var(--graph-700)]">{g.source}</span>
                  <span className="text-[var(--text-faint)]">—({g.rel})→</span>
                  <span className="font-semibold text-[var(--graph-700)]">{g.target}</span>
                </div>
              ))}
            </Card>
          </section>
        )}
      </div>
    </aside>
  );
}
