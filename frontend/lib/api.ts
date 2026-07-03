import type {
  ChatResponse,
  DocumentListResponse,
  IngestionStatusResponse,
  IngestionUploadResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "Failed to connect to the backend. Is the FastAPI server running on port 8000?"
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export function sendChatMessage(query: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export function uploadPdf(file: File): Promise<IngestionUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<IngestionUploadResponse>("/ingest/upload", {
    method: "POST",
    body: formData,
  });
}

export function getIngestionStatus(taskId: string): Promise<IngestionStatusResponse> {
  return request<IngestionStatusResponse>(`/ingest/status/${taskId}`);
}

export function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents");
}
