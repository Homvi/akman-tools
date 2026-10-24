"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, ChevronLeft, ChevronRight, MessageSquare } from "lucide-react";
import { Link } from "@/i18n/routing";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";
import {
  addDays,
  daysBetween,
  formatShortRange,
  normalizeTask,
  startOfDay,
  startOfWeek,
  taskLeaveConflict,
  taskMembers,
  taskRange,
  toIsoDate,
  type Board,
  type Person,
  type Task,
} from "@/lib/staffing";

type View = "gantt" | "month";
type Zoom = 28 | 91;
type Scheduled = { task: Task; start: Date; end: Date };

const MONTH_LANES = 3;

function isoWeek(d: Date): number {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil(((date.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
}

function statusOf(task: Task): "done" | "blocked" | "active" {
  if (task.done) return "done";
  if (task.blocker) return "blocked";
  return "active";
}

const BAR_STYLE = {
  active: "bg-[#2DD4BF]/25 border-[#2DD4BF] text-[#99F6E4]",
  blocked: "bg-[#EF4444]/25 border-[#EF4444] text-[#FECACA]",
  done: "bg-[#3F3F46]/60 border-[#52525B] text-[#A1A1AA]",
} as const;

export default function CalendarPage() {
  const t = useTranslations("calendar");
  const tc = useTranslations("common");
  const locale = useLocale();
  const [board, setBoard] = useState<Board>({ tasks: [] });
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("gantt");
  const [zoom, setZoom] = useState<Zoom>(28);
  const [ganttStart, setGanttStart] = useState(() => addDays(startOfWeek(new Date()), -7));
  const [monthCursor, setMonthCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1, 12);
  });
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [latestNote, setLatestNote] = useState<Record<string, { count: number; text: string }>>({});

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [boardRes, peopleRes, notesRes] = await Promise.all([
        api.get<Board>("/workforce/board"),
        api.get<{ people: Person[] }>("/workforce/people").catch(() => ({ people: [] as Person[] })),
        api
          .get<Record<string, { text: string }[]>>("/workforce/board/notes")
          .catch(() => ({}) as Record<string, { text: string }[]>),
      ]);
      setBoard({ tasks: (boardRes.tasks || []).map((task) => normalizeTask(task)) });
      setPeople(peopleRes.people || []);
      setLatestNote(
        Object.fromEntries(
          Object.entries(notesRes || {})
            .filter(([, list]) => list.length)
            .map(([id, list]) => [id, { count: list.length, text: list[0].text }])
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const peopleById = useMemo(() => {
    const map = new Map<string, Person>();
    for (const p of people) map.set(p.id, p);
    return map;
  }, [people]);

  const { scheduled, unscheduled } = useMemo(() => {
    const withRange: Scheduled[] = [];
    const without: Task[] = [];
    for (const task of board.tasks) {
      const range = taskRange(task);
      if (range) withRange.push({ task, ...range });
      else without.push(task);
    }
    withRange.sort((a, b) => a.start.getTime() - b.start.getTime() || a.task.order - b.task.order);
    return { scheduled: withRange, unscheduled: without };
  }, [board.tasks]);

  const today = startOfDay(new Date());
  const dayFmt = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" });
  const longDayFmt = new Intl.DateTimeFormat(locale, { weekday: "long", month: "long", day: "numeric" });
  const monthFmt = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" });

  function describe(item: Scheduled): string {
    const lead = item.task.lead_id ? peopleById.get(item.task.lead_id)?.name || item.task.lead_id : t("noLead");
    const members = taskMembers(item.task, peopleById);
    const conflicts = members
      .map((p) => {
        const c = taskLeaveConflict(p, item.task);
        return c ? `${p.name} (${formatShortRange(c)})` : null;
      })
      .filter(Boolean);
    return [
      item.task.title,
      `${dayFmt.format(item.start)} – ${dayFmt.format(item.end)}`,
      `${t("lead")}: ${lead}`,
      members.length ? members.map((p) => p.name).join(", ") : null,
      conflicts.length ? `⚠ ${conflicts.join(", ")}` : null,
    ]
      .filter(Boolean)
      .join("\n");
  }

  function conflictCount(task: Task): number {
    return taskMembers(task, peopleById).filter((p) => taskLeaveConflict(p, task)).length;
  }

  function shift(direction: -1 | 1) {
    if (view === "gantt") {
      setGanttStart((prev) => addDays(prev, direction * (zoom === 28 ? 7 : 28)));
    } else {
      setMonthCursor((prev) => new Date(prev.getFullYear(), prev.getMonth() + direction, 1, 12));
    }
  }

  function goToday() {
    setGanttStart(addDays(startOfWeek(new Date()), -7));
    const now = new Date();
    setMonthCursor(new Date(now.getFullYear(), now.getMonth(), 1, 12));
  }

  const rangeTitle =
    view === "gantt"
      ? `${dayFmt.format(ganttStart)} – ${dayFmt.format(addDays(ganttStart, zoom - 1))}`
      : monthFmt.format(monthCursor);

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
          <p className="mt-1 text-sm text-[#A1A1AA]">{t("subtitle")}</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          {tc("refresh")}
        </Button>
      </div>
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-md border border-[#27272A] p-0.5">
          {(["gantt", "month"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={cn(
                "rounded px-3 py-1 text-sm",
                view === v ? "bg-[#2DD4BF] font-medium text-[#042F2E]" : "text-[#A1A1AA] hover:text-[#FAFAFA]"
              )}
            >
              {v === "gantt" ? t("viewGantt") : t("viewMonth")}
            </button>
          ))}
        </div>
        {view === "gantt" && (
          <div className="inline-flex rounded-md border border-[#27272A] p-0.5">
            {([28, 91] as const).map((z) => (
              <button
                key={z}
                type="button"
                onClick={() => setZoom(z)}
                className={cn(
                  "rounded px-2.5 py-1 text-xs",
                  zoom === z ? "bg-[#27272A] text-[#FAFAFA]" : "text-[#71717A] hover:text-[#A1A1AA]"
                )}
              >
                {z === 28 ? t("zoom4w") : t("zoom3m")}
              </button>
            ))}
          </div>
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button variant="outline" className="h-8 w-8 p-0" onClick={() => shift(-1)} aria-label={t("prev")}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" className="h-8 px-3 text-xs" onClick={goToday}>
            {t("today")}
          </Button>
          <Button variant="outline" className="h-8 w-8 p-0" onClick={() => shift(1)} aria-label={t("next")}>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="ml-2 min-w-[10rem] text-sm font-medium capitalize text-[#E4E4E7]">{rangeTitle}</span>
        </div>
      </div>

      {!loading && !scheduled.length && (
        <div className="mb-4 rounded-md border border-dashed border-[#3F3F46] bg-[#0C0C0E]/60 p-4 text-sm text-[#A1A1AA]">
          {t("noScheduled")}{" "}
          <Link href="/teams" className="text-[#2DD4BF] underline-offset-2 hover:underline">
            {t("goTeams")}
          </Link>
        </div>
      )}

      {view === "gantt" ? (
        <GanttView
          scheduled={scheduled}
          start={ganttStart}
          days={zoom}
          today={today}
          locale={locale}
          peopleById={peopleById}
          describe={describe}
          conflictCount={conflictCount}
        />
      ) : (
        <MonthView
          scheduled={scheduled}
          monthCursor={monthCursor}
          today={today}
          selectedDay={selectedDay}
          onSelectDay={setSelectedDay}
          describe={describe}
          conflictCount={conflictCount}
        />
      )}

      {view === "month" && selectedDay && (
        <DayPanel
          day={selectedDay}
          title={t("dayTasks", { date: longDayFmt.format(selectedDay) })}
          items={scheduled.filter((s) => s.start <= selectedDay && s.end >= selectedDay)}
          peopleById={peopleById}
          conflictCount={conflictCount}
          latestNote={latestNote}
        />
      )}

      {unscheduled.length > 0 && (
        <div className="mt-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-medium text-[#FAFAFA]">{t("unscheduled", { count: unscheduled.length })}</h2>
            <Link href="/teams" className="text-xs text-[#2DD4BF] hover:underline">
              {t("goTeams")}
            </Link>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {unscheduled.map((task) => (
              <span
                key={task.id}
                className="rounded-md border border-[#27272A] bg-[#18181B] px-2 py-0.5 text-xs text-[#A1A1AA]"
              >
                {task.title}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GanttView({
  scheduled,
  start,
  days,
  today,
  locale,
  peopleById,
  describe,
  conflictCount,
}: {
  scheduled: Scheduled[];
  start: Date;
  days: number;
  today: Date;
  locale: string;
  peopleById: Map<string, Person>;
  describe: (item: Scheduled) => string;
  conflictCount: (task: Task) => number;
}) {
  const t = useTranslations("calendar");
  const end = addDays(start, days - 1);
  const dayList = useMemo(() => Array.from({ length: days }, (_, i) => addDays(start, i)), [start, days]);
  const visible = scheduled.filter((s) => s.start <= end && s.end >= start);
  const cellWidth = days === 28 ? 32 : 12;
  const todayIdx = daysBetween(start, today);
  const monthFmt = new Intl.DateTimeFormat(locale, { month: "long" });

  const monthSpans = useMemo(() => {
    const spans: { label: string; from: number; len: number }[] = [];
    dayList.forEach((d, i) => {
      const label = monthFmt.format(d);
      const last = spans[spans.length - 1];
      if (last && last.label === label) last.len += 1;
      else spans.push({ label, from: i, len: 1 });
    });
    return spans;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dayList, locale]);

  const gridCols = `220px repeat(${days}, minmax(${cellWidth}px, 1fr))`;

  return (
    <div className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E]">
      <div className="min-w-max" style={{ display: "grid", gridTemplateColumns: gridCols }}>
        <div className="sticky left-0 z-20 border-b border-r border-[#27272A] bg-[#0C0C0E]" style={{ gridRow: "1 / 3" }}>
          <div className="flex h-full items-end px-3 pb-1.5 text-[10px] uppercase tracking-wide text-[#71717A]">
            {t("task")}
          </div>
        </div>
        {monthSpans.map((span) => (
          <div
            key={`${span.label}-${span.from}`}
            className="truncate border-b border-l border-[#27272A] px-1.5 py-1 text-xs font-medium capitalize text-[#E4E4E7]"
            style={{ gridRow: 1, gridColumn: `${span.from + 2} / span ${span.len}` }}
          >
            {span.label}
          </div>
        ))}
        {days === 28
          ? dayList.map((d, i) => {
              const weekend = d.getDay() === 0 || d.getDay() === 6;
              return (
                <div
                  key={i}
                  className={cn(
                    "border-b border-[#27272A] py-1 text-center text-[10px]",
                    weekend ? "bg-[#18181B] text-[#52525B]" : "text-[#A1A1AA]",
                    i === todayIdx && "font-bold text-[#F59E0B]"
                  )}
                  style={{ gridRow: 2, gridColumn: i + 2 }}
                >
                  {d.getDate()}
                </div>
              );
            })
          : dayList.map((d, i) =>
              d.getDay() === 1 || i === 0 ? (
                <div
                  key={i}
                  className="truncate border-b border-l border-[#27272A] px-1 py-1 text-[10px] text-[#A1A1AA]"
                  style={{ gridRow: 2, gridColumn: `${i + 2} / span ${Math.min(7, days - i)}` }}
                >
                  {t("week", { week: isoWeek(d) })}
                </div>
              ) : null
            )}

        {visible.map((item, row) => {
          const status = statusOf(item.task);
          const from = Math.max(0, daysBetween(start, item.start));
          const to = Math.min(days - 1, daysBetween(start, item.end));
          const clippedLeft = item.start < start;
          const clippedRight = item.end > end;
          const lead = item.task.lead_id ? peopleById.get(item.task.lead_id)?.name || item.task.lead_id : null;
          const members = taskMembers(item.task, peopleById).length;
          const conflicts = conflictCount(item.task);
          const gridRow = row + 3;
          return (
            <div key={item.task.id} className="contents">
              <div
                className="sticky left-0 z-10 min-w-0 border-b border-r border-[#27272A] bg-[#0C0C0E] px-3 py-1.5"
                style={{ gridRow, gridColumn: 1 }}
              >
                <div className="truncate text-sm font-medium text-[#FAFAFA]" title={item.task.title}>
                  {item.task.title}
                </div>
                <div className="truncate text-[11px] text-[#71717A]">
                  <span className={lead ? "text-[#FCD34D]" : ""}>{lead || t("noLead")}</span>
                  {" · "}
                  {t("members", { count: members })}
                </div>
              </div>
              <div
                className="relative border-b border-[#27272A]"
                style={{
                  gridRow,
                  gridColumn: `2 / span ${days}`,
                  display: "grid",
                  gridTemplateColumns: `repeat(${days}, minmax(0, 1fr))`,
                }}
              >
                {dayList.map((d, i) =>
                  d.getDay() === 0 || d.getDay() === 6 ? (
                    <div key={i} className="bg-[#18181B]/70" style={{ gridColumn: i + 1, gridRow: 1 }} />
                  ) : null
                )}
                {todayIdx >= 0 && todayIdx < days && (
                  <div
                    className="pointer-events-none absolute inset-y-0 z-[1] w-px bg-[#F59E0B]"
                    style={{ left: `${((todayIdx + 0.5) / days) * 100}%` }}
                  />
                )}
                <div
                  className={cn(
                    "z-[2] my-1.5 flex min-w-0 items-center gap-1 overflow-hidden border px-1.5 text-[11px] font-medium",
                    BAR_STYLE[status],
                    clippedLeft ? "rounded-l-none border-l-0" : "rounded-l-md",
                    clippedRight ? "rounded-r-none border-r-0" : "rounded-r-md",
                    conflicts > 0 && "ring-1 ring-[#EF4444]"
                  )}
                  style={{ gridColumn: `${from + 1} / ${to + 2}`, gridRow: 1 }}
                  title={describe(item)}
                >
                  {conflicts > 0 && <AlertTriangle className="h-3 w-3 shrink-0 text-[#F87171]" />}
                  <span className="truncate">{item.task.title}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MonthView({
  scheduled,
  monthCursor,
  today,
  selectedDay,
  onSelectDay,
  describe,
  conflictCount,
}: {
  scheduled: Scheduled[];
  monthCursor: Date;
  today: Date;
  selectedDay: Date | null;
  onSelectDay: (day: Date | null) => void;
  describe: (item: Scheduled) => string;
  conflictCount: (task: Task) => number;
}) {
  const t = useTranslations("calendar");
  const locale = useLocale();
  const weekdayFmt = new Intl.DateTimeFormat(locale, { weekday: "short" });
  const gridStart = startOfWeek(monthCursor);
  const monthEnd = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 0, 12);
  const weekCount = Math.ceil((daysBetween(gridStart, monthEnd) + 1) / 7);
  const selectedIso = selectedDay ? toIsoDate(selectedDay) : null;
  const todayIso = toIsoDate(today);

  const weeks = Array.from({ length: weekCount }, (_, w) => {
    const weekStart = addDays(gridStart, w * 7);
    const weekEnd = addDays(weekStart, 6);
    const segments = scheduled
      .filter((s) => s.start <= weekEnd && s.end >= weekStart)
      .map((s) => ({
        item: s,
        from: Math.max(0, daysBetween(weekStart, s.start)),
        to: Math.min(6, daysBetween(weekStart, s.end)),
      }))
      .sort((a, b) => a.from - b.from || b.to - b.from - (a.to - a.from));
    const laneEnds: number[] = [];
    const placed = segments.map((seg) => {
      let lane = laneEnds.findIndex((endCol) => endCol < seg.from);
      if (lane === -1) {
        lane = laneEnds.length;
        laneEnds.push(seg.to);
      } else {
        laneEnds[lane] = seg.to;
      }
      return { ...seg, lane };
    });
    const hiddenPerDay = Array.from({ length: 7 }, (_, d) =>
      placed.filter((p) => p.lane >= MONTH_LANES && p.from <= d && p.to >= d).length
    );
    return { weekStart, placed, hiddenPerDay };
  });

  return (
    <div className="overflow-hidden rounded-md border border-[#27272A] bg-[#0C0C0E]">
      <div className="grid grid-cols-7 border-b border-[#27272A]">
        {Array.from({ length: 7 }, (_, i) => (
          <div key={i} className="px-2 py-1.5 text-[10px] uppercase tracking-wide text-[#71717A]">
            {weekdayFmt.format(addDays(gridStart, i))}
          </div>
        ))}
      </div>
      {weeks.map(({ weekStart, placed, hiddenPerDay }) => (
        <div
          key={toIsoDate(weekStart)}
          className="grid border-b border-[#27272A] last:border-b-0"
          style={{
            gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
            gridTemplateRows: `26px repeat(${MONTH_LANES}, 22px) 20px`,
          }}
        >
          {Array.from({ length: 7 }, (_, d) => {
            const day = addDays(weekStart, d);
            const iso = toIsoDate(day);
            const weekend = d >= 5;
            return (
              <button
                key={`bg-${iso}`}
                type="button"
                onClick={() => onSelectDay(selectedIso === iso ? null : day)}
                className={cn(
                  "border-l border-[#27272A] text-left first:border-l-0 hover:bg-[#18181B]",
                  weekend && "bg-[#18181B]/50",
                  selectedIso === iso && "bg-[#2DD4BF]/10 ring-1 ring-inset ring-[#2DD4BF]"
                )}
                style={{ gridColumn: d + 1, gridRow: "1 / -1" }}
                aria-label={iso}
              />
            );
          })}
          {Array.from({ length: 7 }, (_, d) => {
            const day = addDays(weekStart, d);
            const iso = toIsoDate(day);
            const inMonth = day.getMonth() === monthCursor.getMonth();
            return (
              <div
                key={`num-${iso}`}
                className="pointer-events-none px-2 pt-1 text-xs"
                style={{ gridColumn: d + 1, gridRow: 1 }}
              >
                <span
                  className={cn(
                    "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1",
                    inMonth ? "text-[#E4E4E7]" : "text-[#3F3F46]",
                    iso === todayIso && "bg-[#F59E0B] font-bold text-black"
                  )}
                >
                  {day.getDate()}
                </span>
              </div>
            );
          })}
          {placed
            .filter((p) => p.lane < MONTH_LANES)
            .map((p) => {
              const status = statusOf(p.item.task);
              const conflicts = conflictCount(p.item.task);
              const startsHere = p.item.start >= weekStart;
              const endsHere = p.item.end <= addDays(weekStart, 6);
              return (
                <button
                  key={`${p.item.task.id}-${toIsoDate(weekStart)}`}
                  type="button"
                  onClick={() => onSelectDay(addDays(weekStart, p.from))}
                  title={describe(p.item)}
                  className={cn(
                    "z-[1] mx-0.5 my-[2px] flex min-w-0 items-center gap-1 overflow-hidden border px-1.5 text-left text-[11px] font-medium",
                    BAR_STYLE[status],
                    startsHere ? "rounded-l" : "-ml-px rounded-l-none border-l-0",
                    endsHere ? "rounded-r" : "-mr-px rounded-r-none border-r-0",
                    conflicts > 0 && "ring-1 ring-[#EF4444]"
                  )}
                  style={{ gridColumn: `${p.from + 1} / ${p.to + 2}`, gridRow: p.lane + 2 }}
                >
                  {conflicts > 0 && <AlertTriangle className="h-3 w-3 shrink-0 text-[#F87171]" />}
                  <span className="truncate">{p.item.task.title}</span>
                </button>
              );
            })}
          {hiddenPerDay.map((count, d) =>
            count > 0 ? (
              <button
                key={`more-${d}`}
                type="button"
                onClick={() => onSelectDay(addDays(weekStart, d))}
                className="z-[1] px-2 text-left text-[10px] font-medium text-[#A1A1AA] hover:text-[#FAFAFA]"
                style={{ gridColumn: d + 1, gridRow: MONTH_LANES + 2 }}
              >
                {t("more", { count })}
              </button>
            ) : null
          )}
        </div>
      ))}
    </div>
  );
}

function DayPanel({
  day,
  title,
  items,
  peopleById,
  conflictCount,
  latestNote,
}: {
  day: Date;
  title: string;
  items: Scheduled[];
  peopleById: Map<string, Person>;
  conflictCount: (task: Task) => number;
  latestNote: Record<string, { count: number; text: string }>;
}) {
  const t = useTranslations("calendar");
  const locale = useLocale();
  const dayFmt = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" });
  return (
    <div className="mt-3 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3" data-day={toIsoDate(day)}>
      <h2 className="mb-2 text-sm font-medium capitalize text-[#FAFAFA]">{title}</h2>
      {items.length ? (
        <ul className="space-y-1.5">
          {items.map((item) => {
            const status = statusOf(item.task);
            const lead = item.task.lead_id ? peopleById.get(item.task.lead_id)?.name || item.task.lead_id : null;
            const members = taskMembers(item.task, peopleById);
            const conflicts = conflictCount(item.task);
            return (
              <li
                key={item.task.id}
                className={cn("rounded-md border px-2.5 py-1.5 text-sm", BAR_STYLE[status])}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{item.task.title}</span>
                  <span className="text-[11px] opacity-80">
                    {dayFmt.format(item.start)} – {dayFmt.format(item.end)} ·{" "}
                    {status === "done"
                      ? t("statusDone")
                      : status === "blocked"
                        ? t("statusBlocked")
                        : t("statusActive")}
                  </span>
                </div>
                <div className="mt-0.5 text-[11px] text-[#A1A1AA]">
                  <span className={lead ? "text-[#FCD34D]" : ""}>{lead || t("noLead")}</span>
                  {members.length ? ` · ${members.map((p) => p.name).join(", ")}` : null}
                </div>
                {item.task.blocker && item.task.blocker_note ? (
                  <div className="mt-0.5 text-[11px] text-[#FCA5A5]">{item.task.blocker_note}</div>
                ) : null}
                {conflicts > 0 && (
                  <div className="mt-0.5 inline-flex items-center gap-1 text-[11px] font-semibold text-[#F87171]">
                    <AlertTriangle className="h-3 w-3" />
                    {t("conflicts", { count: conflicts })}
                  </div>
                )}
                {latestNote[item.task.id] ? (
                  <div className="mt-0.5 flex items-center gap-1 text-[11px] text-[#A1A1AA]">
                    <MessageSquare className="h-3 w-3 shrink-0" />
                    <span className="shrink-0">{t("notesCount", { count: latestNote[item.task.id].count })}</span>
                    <span className="truncate text-[#71717A]">· {latestNote[item.task.id].text}</span>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-[#71717A]">{t("noTasksDay")}</p>
      )}
    </div>
  );
}
