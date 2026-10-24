"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ChevronRight, MessageSquare, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type TaskNote = {
  id: number;
  task_id: string;
  text: string;
  author_email: string;
  created_at: string | null;
};

export function TaskNotes({
  notes,
  canWrite,
  canDelete,
  onAdd,
  onDelete,
}: {
  notes: TaskNote[];
  canWrite: boolean;
  canDelete: (note: TaskNote) => boolean;
  onAdd: (text: string) => Promise<void>;
  onDelete: (note: TaskNote) => void;
}) {
  const t = useTranslations("teams");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const fmt = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  async function submit() {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      await onAdd(text);
      setDraft("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mt-2 border-t border-[#27272A] pt-1.5" onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1 text-left text-xs text-[#A1A1AA] hover:text-[#E4E4E7]"
        aria-expanded={open}
      >
        <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")} />
        <MessageSquare className="h-3.5 w-3.5" />
        {t("notesTitle", { count: notes.length })}
        {!open && notes[0] ? (
          <span className="ml-1 min-w-0 flex-1 truncate text-[11px] text-[#71717A]">{notes[0].text}</span>
        ) : null}
      </button>
      {open && (
        <div className="mt-1.5 space-y-2">
          {canWrite && (
            <div>
              <textarea
                value={draft}
                rows={2}
                maxLength={5000}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    void submit();
                  }
                }}
                placeholder={t("notePlaceholder")}
                className="w-full resize-y rounded-md border border-[#3F3F46] bg-[#18181B] px-2 py-1.5 text-sm text-[#FAFAFA] placeholder:text-[#52525B] focus:outline-none focus:ring-1 focus:ring-[#2DD4BF]"
              />
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[#52525B]">{t("noteShortcut")}</span>
                <button
                  type="button"
                  disabled={!draft.trim() || sending}
                  onClick={() => void submit()}
                  className="rounded-md bg-[#2DD4BF] px-2 py-0.5 text-xs font-medium text-black disabled:opacity-40"
                >
                  {t("noteAdd")}
                </button>
              </div>
            </div>
          )}
          {notes.length ? (
            <ul className="max-h-60 space-y-1.5 overflow-y-auto">
              {notes.map((n) => (
                <li key={n.id} className="rounded-md bg-[#18181B] px-2 py-1">
                  <div className="flex items-center justify-between gap-2 text-[10px] text-[#71717A]">
                    <span className="truncate">
                      {n.created_at ? fmt.format(new Date(n.created_at)) : ""} · {n.author_email}
                    </span>
                    {canDelete(n) ? (
                      <button
                        type="button"
                        onClick={() => onDelete(n)}
                        className="shrink-0 hover:text-[#F87171]"
                        title={t("noteDelete")}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    ) : null}
                  </div>
                  <p className="whitespace-pre-wrap break-words text-xs text-[#E4E4E7]">{n.text}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-[#52525B]">{t("notesEmpty")}</p>
          )}
        </div>
      )}
    </div>
  );
}
