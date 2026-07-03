export type RetrievalMode = "vector" | "graph";

export interface ReasoningStep {
  mode: RetrievalMode;
  query: string;
  detail: string;
}

export interface VectorSourceResult {
  doc_id: string;
  chapter: string | null;
  section: string | null;
  score: number;
  snippet: string;
}

export interface GraphTriple {
  source: string;
  rel: string;
  target: string;
  detail: string | null;
}

export interface ChatResponse {
  answer: string;
  status: string;
  reasoning_steps: ReasoningStep[];
  sources: VectorSourceResult[];
  graph_triples: GraphTriple[];
}

export interface IngestionUploadResponse {
  task_id: string;
  filename: string;
  status: string;
  message: string;
}

export interface IngestionStatusResponse {
  task_id: string;
  status: string;
  message: string;
  error?: string;
}

export type DocumentStatus = "queued" | "ingesting" | "ready" | "failed";

export interface DocumentSummary {
  id: string;
  title: string;
  status: DocumentStatus;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
}

export type MessageRole = "user" | "assistant" | "error";

export interface ChatMessage {
  role: MessageRole;
  content: string;
  reasoningSteps?: ReasoningStep[];
  sources?: VectorSourceResult[];
  graphTriples?: GraphTriple[];
}
