"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Bell } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type NotificationItem = {
  id: string;
  title: string;
  body?: string | null;
  created_at?: string | null;
  read?: boolean;
};

type NotificationsResponse = { items: NotificationItem[]; unread: number };

const POLL_MS = 60_000;

export function NotificationBell({
  className,
  align = "left",
}: {
  className?: string;
  align?: "left" | "right";
}) {
  const t = useTranslations("notifications");
  const [data, setData] = useState<NotificationsResponse>({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await api.get<NotificationsResponse>("/notifications");
        if (!cancelled) setData({ items: res.items || [], unread: res.unread || 0 });
      } catch {
        /* bell stays quiet when the API is unreachable */
      }
    }
    void poll();
    const timer = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [open]);

  const unread = data.unread;

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("open")}
        aria-expanded={open}
        className="relative flex h-8 w-8 items-center justify-center rounded-md text-[#A1A1AA] hover:bg-[#18181B] hover:text-[#FAFAFA]"
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#EF4444] px-1 text-[10px] font-bold leading-none text-white ring-2 ring-[#0C0C0E]">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className={cn(
            "absolute top-full z-50 mt-1 w-72 rounded-md border border-[#27272A] bg-[#0C0C0E] shadow-xl shadow-black/50",
            align === "left" ? "left-0" : "right-0"
          )}
        >
          <div className="border-b border-[#27272A] px-3 py-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">
            {t("title")}
          </div>
          {data.items.length ? (
            <ul className="max-h-80 overflow-y-auto">
              {data.items.map((item) => (
                <li
                  key={item.id}
                  className={cn(
                    "border-b border-[#18181B] px-3 py-2 text-sm last:border-b-0",
                    item.read ? "text-[#A1A1AA]" : "text-[#FAFAFA]"
                  )}
                >
                  <div className="font-medium">{item.title}</div>
                  {item.body ? <div className="mt-0.5 text-xs text-[#A1A1AA]">{item.body}</div> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-4 text-center text-sm text-[#71717A]">{t("empty")}</p>
          )}
        </div>
      )}
    </div>
  );
}
