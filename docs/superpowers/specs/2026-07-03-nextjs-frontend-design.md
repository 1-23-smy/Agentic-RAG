# Next.js Frontend (Replacing Streamlit UI) — Design

## Context

The project currently ships a Streamlit UI (`ui/app.py`) as its frontend, talking to a FastAPI backend (`main.py`) on `http://127.0.0.1:8000`. The backend exposes three endpoints:

- `POST /chat` — `{query: string}` → `{answer: string, status: string}`
- `POST /ingest/upload` — multipart PDF upload → `{task_id, filename, status, message}`
- `GET /ingest/status/{task_id}` — → `{task_id, status, message, error?}`

The Streamlit app has two features: a chat interface (message history, kept in `st.session_state`, reset on reload) and a single-PDF uploader that kicks off async ingestion (Celery task) and polls status every 3 seconds until `SUCCESS`/`FAILURE`.

Goal: replace the Streamlit UI with a Next.js 16 + Tailwind v4 frontend, running on Node 24, with true feature parity — no new backend capabilities in this pass.

## Stack

- **Next.js 16** (App Router), **TypeScript**, **Node 24**
- **Tailwind CSS v4**
- **shadcn/ui** (Radix-based, Tailwind-styled components — button, input, textarea, toast/sonner, card)
- **pnpm** as package manager
- **next-themes** for dark mode
- **react-markdown** for rendering assistant answers (may contain formatting/citations)

## Location

New top-level `frontend/` directory, sibling to `ingestion/`, `retrieval/`, `storage/`, etc. The existing `ui/` (Streamlit) directory is deleted as part of this work.

## Architecture

Single-page client app. One route (`app/page.tsx`) renders a `"use client"` component tree — no meaningful server-rendering need since the whole UI is stateful/interactive (chat history, polling, file upload), matching the original Streamlit app's single-page nature.

The frontend talks **directly** to FastAPI via `fetch`, using `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`) as the base URL. No Next.js API-route proxying. This requires adding `CORSMiddleware` to `main.py` (currently absent) to allow the Next.js dev origin (`http://localhost:3000`, and configurable for prod).

## Components

- **`app/page.tsx`** — thin shell, renders `<ChatApp />`.
- **`components/chat-app.tsx`** — top-level client component. Owns state:
  - `messages: Message[]` (`{role: "user" | "assistant" | "error", content: string}`)
  - `activeIngestion: {taskId: string, filename: string} | null`
  - `isSending: boolean`
- **`components/pdf-uploader.tsx`** — file picker + "Upload PDF" button (disabled while a file isn't selected or an ingestion is already active, mirroring Streamlit's `upload_disabled` logic). On success, lifts `{task_id, filename}` to `ChatApp`, which begins polling.
- **`components/ingestion-status-banner.tsx`** — visible while `activeIngestion` is set. Polls `GET /ingest/status/{task_id}` every 3s via `useEffect` + `setInterval`/timeout loop. On `SUCCESS` → toast "Ingestion complete..." and clear `activeIngestion`. On `FAILURE` → toast/inline error with `error` detail and clear `activeIngestion`. Otherwise shows current `message` + filename.
- **`components/message-list.tsx`** + **`components/message-bubble.tsx`** — renders chat history; assistant content rendered via `react-markdown`; error-role messages styled distinctly (red/destructive variant).
- **`components/chat-input.tsx`** — textarea + send button, disabled while `isSending`, submits on Enter (Shift+Enter for newline) matching `st.chat_input` UX.
- **`lib/api.ts`** — typed fetch wrappers:
  - `sendChatMessage(query: string): Promise<{answer: string}>`
  - `uploadPdf(file: File): Promise<{task_id: string, filename: string}>`
  - `getIngestionStatus(taskId: string): Promise<IngestionStatusResponse>`

  All read `process.env.NEXT_PUBLIC_API_URL`, throw typed errors distinguishing network failure (`fetch` rejects) from HTTP error responses (non-2xx).

## Data Flow

1. **Upload:** user selects PDF → clicks Upload → `POST /ingest/upload` → on success, `activeIngestion` is set → `IngestionStatusBanner` starts polling `GET /ingest/status/{task_id}` every 3s → terminal state clears `activeIngestion` and shows a toast.
2. **Chat:** user types a question → Enter/Send → user message optimistically appended to `messages` → `isSending = true`, loading indicator shown → `POST /chat` → on success, assistant message appended; on HTTP error, an error-role message appended with the API error text; on network failure, a toast ("Failed to connect to the backend...") plus an error-role message, matching Streamlit's `ConnectionError` handling.

## Error Handling

- **Network/connection errors** (backend not running): caught at the `fetch` layer in `lib/api.ts`, surfaced as a toast: "Failed to connect to the backend. Is the FastAPI server running on port 8000?"
- **HTTP errors (4xx/5xx):** for `/chat`, rendered as an error-styled chat bubble with the response body's error text; for `/ingest/upload` and `/ingest/status`, rendered as a toast.
- No retry/backoff logic beyond the existing 3s polling loop (parity with Streamlit — no additional resilience features).

## Config

- `.env.local` (gitignored): `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`
- `.env.example` (committed) documenting the same variable.

## Backend Change Required

Add `CORSMiddleware` to `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Styling

Tailwind v4 + shadcn/ui. Clean neutral base palette with a single accent color, full dark-mode support via `next-themes` (toggle in the header). Layout: centered chat column (parity with Streamlit's `layout="centered"`), similar visual density to Claude/ChatGPT-style chat UIs.

## Testing / Verification

No automated frontend test suite in this pass (no existing frontend tests to mirror; YAGNI). Verification is manual: run `pnpm dev` against the real FastAPI + Celery backend, exercise PDF upload (including a failure case) and chat (including a backend-down case) end to end.

## Out of Scope (this pass)

- Streaming chat responses
- Multi-file upload
- Persistent/multiple chat sessions or localStorage persistence
- Citation-specific UI beyond markdown rendering
- Automated frontend tests
