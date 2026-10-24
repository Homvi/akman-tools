"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocale, useTranslations } from "next-intl";
import { DayPicker, type DateRange } from "react-day-picker";
import { de, enGB, hu } from "react-day-picker/locale";
import { CalendarDays, X } from "lucide-react";
import "react-day-picker/style.css";
import { cn } from "@/lib/utils";
import {
  addDays,
  daysBetween,
  parseIsoDate,
  startOfDay,
  toIsoDate,
  type LeaveRange,
} from "@/lib/staffing";

const LOCALES = { hu, de, en: enGB } as const;
const POPOVER_TWO_MONTHS = 600;
const POPOVER_ONE_MONTH = 320;

export function formatRangeLabel(
  locale: string,
  start: string | null,
  end: string | null,
  dayCount: (count: number) => string
): string | null {
  const from = parseIsoDate(start);
  if (!from) return null;
  const to = parseIsoDate(end) || from;
  const fmt = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" });
  const days = daysBetween(from, to) + 1;
  const label = days === 1 ? fmt.format(from) : `${fmt.format(from)} – ${fmt.format(to)}`;
  return `${label} · ${dayCount(days)}`;
}

export function DateRangePicker({
  start,
  end,
  onChange,
  leaveRanges = [],
  className,
  placeholder,
}: {
  start: string | null;
  end: string | null;
  onChange: (start: string | null, end: string | null) => void;
  /** Leave blocks of the task's members; those days get a red dot. */
  leaveRanges?: LeaveRange[];
  className?: string;
  placeholder?: string;
}) {
  const t = useTranslations("datePicker");
  const locale = useLocale();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange | undefined>();
  const [hoverDay, setHoverDay] = useState<Date | null>(null);
  const [month, setMonth] = useState<Date>(() => parseIsoDate(start) || new Date());
  const [pos, setPos] = useState<{ top: number; left: number; months: 1 | 2 }>({
    top: 0,
    left: 0,
    months: 2,
  });

  const label = formatRangeLabel(locale, start, end, (count) => t("days", { count }));

  function openPicker() {
    const from = parseIsoDate(start);
    setDraft(from ? { from, to: parseIsoDate(end) || from } : undefined);
    setMonth(from || new Date());
    setHoverDay(null);
    setOpen(true);
  }

  function place() {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const months: 1 | 2 = window.innerWidth >= 680 ? 2 : 1;
    const width = months === 2 ? POPOVER_TWO_MONTHS : POPOVER_ONE_MONTH;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    const below = rect.bottom + 6;
    const height = popoverRef.current?.offsetHeight || 400;
    const top = below + height > window.innerHeight - 8 ? Math.max(8, rect.top - height - 6) : below;
    setPos({ top, left, months });
  }

  useLayoutEffect(() => {
    if (open) place();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      const target = e.target as Node;
      if (popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  function commit(from: Date, to: Date) {
    onChange(toIsoDate(from), toIsoDate(to));
    setOpen(false);
  }

  function onDayClick(day: Date) {
    const picked = startOfDay(day);
    if (!draft?.from || draft.to) {
      setDraft({ from: picked, to: undefined });
      return;
    }
    if (picked < draft.from) {
      setDraft({ from: picked, to: undefined });
      return;
    }
    commit(draft.from, picked);
  }

  function quick(days: number) {
    const from = draft?.from || parseIsoDate(start) || startOfDay(new Date());
    commit(from, addDays(from, days - 1));
  }

  const shown: DateRange | undefined = useMemo(() => {
    if (draft?.from && !draft.to && hoverDay && hoverDay >= draft.from) {
      return { from: draft.from, to: hoverDay };
    }
    return draft;
  }, [draft, hoverDay]);

  const leaveMatchers = useMemo(
    () =>
      leaveRanges
        .map((r) => {
          const from = parseIsoDate(r.start);
          const to = parseIsoDate(r.end) || from;
          return from && to ? { from, to } : null;
        })
        .filter((r): r is { from: Date; to: Date } => Boolean(r)),
    [leaveRanges]
  );

  const pickingEnd = Boolean(draft?.from && !draft.to);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (open) setOpen(false);
          else openPicker();
        }}
        className={cn(
          "inline-flex h-8 min-w-0 items-center gap-1.5 rounded-md border px-2 text-xs transition-colors",
          label
            ? "border-[#2DD4BF]/40 bg-[#2DD4BF]/10 text-[#5EEAD4] hover:border-[#2DD4BF]"
            : "border-dashed border-[#3F3F46] text-[#71717A] hover:border-[#71717A] hover:text-[#A1A1AA]",
          className
        )}
      >
        <CalendarDays className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label || placeholder || t("setDates")}</span>
      </button>
      {open &&
        createPortal(
          <div
            ref={popoverRef}
            style={{ top: pos.top, left: pos.left }}
            className="fixed z-50 rounded-lg border border-[#3F3F46] bg-[#0C0C0E] p-3 shadow-2xl shadow-black/60"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "rounded px-2 py-1",
                    !pickingEnd ? "bg-[#F59E0B]/20 text-[#FCD34D]" : "text-[#A1A1AA]"
                  )}
                >
                  {t("from")}: {draft?.from ? draft.from.toLocaleDateString(locale) : "—"}
                </span>
                <span
                  className={cn(
                    "rounded px-2 py-1",
                    pickingEnd ? "bg-[#F59E0B]/20 text-[#FCD34D]" : "text-[#A1A1AA]"
                  )}
                >
                  {t("to")}: {draft?.to ? draft.to.toLocaleDateString(locale) : "—"}
                </span>
              </div>
              <button
                type="button"
                className="text-[#71717A] hover:text-[#FAFAFA]"
                onClick={() => setOpen(false)}
                aria-label={t("close")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <DayPicker
              className="rdp-dark"
              mode="range"
              selected={shown}
              onSelect={() => undefined}
              onDayClick={onDayClick}
              onDayMouseEnter={(day) => setHoverDay(startOfDay(day))}
              onDayMouseLeave={() => setHoverDay(null)}
              month={month}
              onMonthChange={setMonth}
              numberOfMonths={pos.months}
              weekStartsOn={1}
              showOutsideDays={false}
              locale={LOCALES[locale as keyof typeof LOCALES] || enGB}
              modifiers={{ leave: leaveMatchers }}
              modifiersClassNames={{ leave: "rdp-leave" }}
            />
            {leaveMatchers.length > 0 && (
              <p className="mt-1 flex items-center gap-1.5 text-[11px] text-[#FCA5A5]">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#EF4444]" />
                {t("leaveLegend")}
              </p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-[#27272A] pt-2">
              {(
                [
                  [7, t("oneWeek")],
                  [14, t("twoWeeks")],
                  [30, t("oneMonth")],
                ] as const
              ).map(([days, text]) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => quick(days)}
                  className="rounded-md border border-[#27272A] px-2 py-1 text-xs text-[#E4E4E7] hover:border-[#2DD4BF] hover:text-[#5EEAD4]"
                >
                  {text}
                </button>
              ))}
              <span className="flex-1" />
              {(start || draft?.from) && (
                <button
                  type="button"
                  onClick={() => {
                    onChange(null, null);
                    setOpen(false);
                  }}
                  className="rounded-md px-2 py-1 text-xs text-[#F87171] hover:bg-[#EF4444]/10"
                >
                  {t("clear")}
                </button>
              )}
            </div>
            <p className="mt-1.5 text-[10px] text-[#52525B]">
              {pickingEnd ? t("hintEnd") : t("hintStart")}
            </p>
          </div>,
          document.body
        )}
    </>
  );
}
