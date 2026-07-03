"use client";

import { Plus, Settings } from "lucide-react";
import { Wordmark } from "@/components/wordmark";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { DocumentChip } from "@/components/document-chip";
import { useDocumentList } from "@/hooks/use-document-list";

export interface SidebarProps {
  activeDocId: string | null;
  onSelectDoc: (id: string) => void;
  onNew: () => void;
  onUploadClick: () => void;
}

export function Sidebar({ activeDocId, onSelectDoc, onNew, onUploadClick }: SidebarProps) {
  const { documents } = useDocumentList();
  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <aside className="flex h-full w-[288px] shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <div className="flex items-center justify-between px-4 pb-3 pt-4">
        <Wordmark />
        <IconButton label="Settings"><Settings size={17} /></IconButton>
      </div>

      <div className="px-4 pb-3.5">
        <Button variant="solid" fullWidth iconLeft={<Plus size={16} />} onClick={onNew}>
          New conversation
        </Button>
      </div>

      <div className="flex items-center justify-between px-4 pb-2">
        <span className="ar-eyebrow">Documents · {readyCount} ready</span>
        <IconButton label="Upload PDF" onClick={onUploadClick}><Plus size={16} /></IconButton>
      </div>

      <div className="flex flex-1 flex-col gap-1.5 overflow-y-auto px-3 pb-3">
        {documents.map((d) => (
          <DocumentChip
            key={d.id}
            title={d.title}
            status={d.status}
            active={d.id === activeDocId}
            onClick={() => onSelectDoc(d.id)}
          />
        ))}
      </div>
    </aside>
  );
}
