"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { FileText, Layers } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Sidebar } from "@/components/sidebar";
import { SourcesPanel } from "@/components/sources-panel";
import { ReasoningTrace } from "@/components/reasoning-trace";
import { MessageBubble } from "@/components/message-bubble";
import { Citation } from "@/components/citation";
import { EmptyState } from "@/components/empty-state";
import { Composer } from "@/components/composer";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { sendChatMessage, uploadPdf, getIngestionStatus, ApiError } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

const STATUS_POLL_INTERVAL_MS = 3000;

export function ChatApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [showSources, setShowSources] = useState(true);
  const [activeIngestionFilename, setActiveIngestionFilename] = useState<string | null>(null);
  // Presentation-only: highlights the selected chip; /chat has no per-document filter yet.
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const hasChat = messages.length > 0 || isSending;
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  const pollIngestionStatus = useCallback((taskId: string, filename: string) => {
    const poll = async () => {
      try {
        const status = await getIngestionStatus(taskId);
        if (status.status === "SUCCESS") {
          toast.success("Ingestion complete. You can now ask questions about this document.");
          setActiveIngestionFilename(null);
          return;
        }
        if (status.status === "FAILURE") {
          toast.error(status.error ?? "Ingestion failed. Please check the worker logs and try again.");
          setActiveIngestionFilename(null);
          return;
        }
        setTimeout(poll, STATUS_POLL_INTERVAL_MS);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to check ingestion status.");
        setActiveIngestionFilename(null);
      }
    };
    setActiveIngestionFilename(filename);
    setTimeout(poll, STATUS_POLL_INTERVAL_MS);
  }, []);

  const handleFileSelected = useCallback(
    async (file: File) => {
      if (activeIngestionFilename) return;
      try {
        const { task_id, filename } = await uploadPdf(file);
        pollIngestionStatus(task_id, filename);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to upload PDF.");
      }
    },
    [activeIngestionFilename, pollIngestionStatus]
  );

  const ask = useCallback(async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || isSending) return;

    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");
    setIsSending(true);

    try {
      const response = await sendChatMessage(trimmed);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: response.answer,
          reasoningSteps: response.reasoning_steps,
          sources: response.sources,
          graphTriples: response.graph_triples,
        },
      ]);
      setShowSources(true);
    } catch (err) {
      if (err instanceof ApiError && err.status == null) {
        toast.error(err.message);
      }
      setMessages((m) => [
        ...m,
        { role: "error", content: err instanceof ApiError ? err.message : "Something went wrong." },
      ]);
    } finally {
      setIsSending(false);
    }
  }, [isSending]);

  const resetChat = () => setMessages([]);

  return (
    <div className="flex h-full bg-[var(--surface-page)]">
      <Sidebar
        activeDocId={activeDocId}
        onSelectDoc={setActiveDocId}
        onNew={resetChat}
        onUploadClick={() => fileInputRef.current?.click()}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelected(file);
          e.target.value = "";
        }}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--surface-card)] px-5">
          <div className="flex min-w-0 items-center gap-2">
            <FileText size={16} />
            <span className="overflow-hidden text-ellipsis whitespace-nowrap text-[14px] font-semibold text-[var(--text-strong)]">
              {activeIngestionFilename ? `Ingesting ${activeIngestionFilename}…` : "Agentic RAG"}
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <ThemeToggle />
            <Button variant="outline" size="sm" iconLeft={<Layers size={15} />} onClick={() => setShowSources((s) => !s)}>
              {showSources ? "Hide sources" : "Show sources"}
            </Button>
          </div>
        </header>

        {!hasChat ? (
          <EmptyState hasDocs={false} onUploadClick={() => fileInputRef.current?.click()} onSuggestionClick={ask} />
        ) : (
          <div className="flex-1 overflow-y-auto px-6 pb-2 pt-[26px]">
            <div className="mx-auto flex max-w-[760px] flex-col gap-[22px]">
              {messages.map((m, i) =>
                m.role === "user" ? (
                  <MessageBubble key={i} role="user">{m.content}</MessageBubble>
                ) : m.role === "error" ? (
                  <MessageBubble key={i} role="assistant">
                    <span className="text-[var(--danger-600)]">{m.content}</span>
                  </MessageBubble>
                ) : (
                  <div key={i} className="flex flex-col gap-3.5">
                    {m.reasoningSteps && m.reasoningSteps.length > 0 && (
                      <ReasoningTrace steps={m.reasoningSteps} running={false} />
                    )}
                    <MessageBubble
                      role="assistant"
                      sources={
                        m.sources && m.sources.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {m.sources.map((s, si) => (
                              <Citation key={si} docId={s.doc_id} chapter={s.chapter} section={s.section} mode="vector" />
                            ))}
                          </div>
                        ) : undefined
                      }
                    >
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    </MessageBubble>
                  </div>
                )
              )}
              {isSending && (
                <div className="flex flex-col gap-3.5">
                  <div className="pl-[42px]"><Spinner label="Synthesizing answer…" /></div>
                </div>
              )}
            </div>
          </div>
        )}

        <Composer
          value={input}
          onChange={setInput}
          onSend={() => ask(input)}
          onAttachClick={() => fileInputRef.current?.click()}
          disabled={isSending}
        />
      </main>

      <SourcesPanel
        open={showSources && hasChat && !!lastAssistant}
        onClose={() => setShowSources(false)}
        sources={lastAssistant?.sources ?? []}
        graphTriples={lastAssistant?.graphTriples ?? []}
      />
    </div>
  );
}
