// frontend/components/landing/corpus-card.tsx
import * as React from "react";
import type { CorpusDoc } from "./corpus-data";

export interface CorpusCardProps {
  doc: CorpusDoc;
}

export const CorpusCard = React.forwardRef<HTMLDivElement, CorpusCardProps>(
  ({ doc }, ref) => {
    return (
      <div ref={ref} className="smh-card">
        <div className="smh-flip">
          <div className={`smh-face smh-front smh-front--${doc.mode}`}>
            <span className="smh-tab" />
            <span className="smh-docid">{doc.id}</span>
            <span className="smh-title">{doc.title}</span>
            <span className="smh-lines">
              {[92, 78, 88, 64, 82, 50].map((w, k) => (
                <i key={k} style={{ width: `${w}%` }} />
              ))}
            </span>
          </div>
          <div className={`smh-face smh-back smh-back--${doc.mode}`}>
            {doc.mode === "graph" && doc.fact ? (
              <div className="smh-graph">
                <span className="smh-node">{doc.fact[0]}</span>
                <span className="smh-rel">{doc.fact[1]}</span>
                <span className="smh-node">{doc.fact[2]}</span>
              </div>
            ) : (
              <div className="smh-chunk">
                <span className="smh-score">{doc.score}</span>
                <span className="smh-snip">&ldquo;&hellip;{doc.snippet}&hellip;&rdquo;</span>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
);
CorpusCard.displayName = "CorpusCard";
