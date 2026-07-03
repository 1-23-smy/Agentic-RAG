"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listDocuments } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

const POLL_INTERVAL_MS = 4000;

export function useDocumentList() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const { documents: docs } = await listDocuments();
      if (!cancelledRef.current) setDocuments(docs);
    } catch {
      // Sidebar polling failures are silent — the chat/upload flows
      // already surface connection errors via toasts.
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;

    const tick = async () => {
      await refresh();
      if (cancelledRef.current) return;
      timeoutRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    };

    tick();

    return () => {
      cancelledRef.current = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [refresh]);

  return { documents, refresh };
}
