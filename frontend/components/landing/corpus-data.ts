export type CorpusMode = "vector" | "graph";

export interface CorpusDoc {
  id: string;
  title: string;
  mode: CorpusMode;
  score: string;
  fact: [string, string, string] | null;
  snippet: string | null;
}

const TITLES = [
  "Clinical Trial",
  "Safety Review",
  "Pharmacovigilance",
  "Dosing Guide",
  "Mechanism",
  "Case Series",
  "Meta-Analysis",
  "Label Extract",
  "Protocol",
  "Registry",
];

const GRAPH_FACTS: [string, string, string][] = [
  ["Warfarin", "INTERACTS_WITH", "Amiodarone"],
  ["Rifampin", "INDUCES", "CYP2C9"],
  ["NSAID", "INCREASES", "Bleed risk"],
  ["Aspirin", "INHIBITS", "COX-1"],
];

const VECTOR_SNIPPETS = [
  "reduce dose 30–50%",
  "monitor INR closely",
  "potentiates effect",
  "displaces from plasma",
];

export const TOTAL_CORPUS_DOCS = 20;

export function buildCorpusDocs(): CorpusDoc[] {
  return Array.from({ length: TOTAL_CORPUS_DOCS }, (_, i) => {
    const mode: CorpusMode = i % 3 === 0 ? "graph" : "vector";
    return {
      id: "DOC-" + String(i + 1).padStart(2, "0"),
      title: TITLES[i % TITLES.length],
      mode,
      score: (0.72 + ((i * 7) % 27) / 100).toFixed(2),
      fact: mode === "graph" ? GRAPH_FACTS[i % GRAPH_FACTS.length] : null,
      snippet: mode === "vector" ? VECTOR_SNIPPETS[i % VECTOR_SNIPPETS.length] : null,
    };
  });
}
