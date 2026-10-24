"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { AlertTriangle, ChevronRight, FileDown, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { isStaff, useMe } from "@/components/auth-gate";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { DateRangePicker, formatRangeLabel } from "@/components/date-range-picker";
import { PersonChip } from "@/components/teams/person-chip";
import { SummaryBar } from "@/components/teams/summary-bar";
import { TaskNotes } from "@/components/teams/task-notes";
import { cn } from "@/lib/utils";
import { taskHeadcount, useTaskBoard } from "@/lib/use-task-board";
import {
  PROJECTS,
  formatShortRange,
  leaveOverlapsNextWeek,
  newId,
  normalizeTask,
  personLeaveRanges,
  requirementsSummary,
  taskLeaveConflict,
  taskMembers,
  toIsoDate,
  type LeaveRange,
  type Person,
  type Project,
  type Task,
} from "@/lib/staffing";

const HIDE_KEY = "tasks.hideLeave";

function readHidePrefs(): { now: boolean; nextWeek: boolean } {
  if (typeof window === "undefined") return { now: false, nextWeek: false };
  try {
    const raw = JSON.parse(window.localStorage.getItem(HIDE_KEY) || "{}");
    return { now: Boolean(raw.now), nextWeek: Boolean(raw.nextWeek) };
  } catch {
    return { now: false, nextWeek: false };
  }
}

type StatusFilter = "all" | "available" | "leaveNow" | "leaveNextWeek";
type ShiftFilter = "all" | "day" | "afternoon";

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "statusAll" },
  { key: "available", label: "statusAvailable" },
  { key: "leaveNow", label: "statusLeaveNow" },
  { key: "leaveNextWeek", label: "statusLeaveNextWeek" },
];

const SHIFT_FILTERS: { key: ShiftFilter; label: string }[] = [
  { key: "all", label: "shiftAll" },
  { key: "day", label: "shiftDay" },
  { key: "afternoon", label: "shiftAfternoon" },
];

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export default function TasksPage() {
  const t = useTranslations("teams");
  const tc = useTranslations("common");
  const td = useTranslations("datePicker");
  const locale = useLocale();
  const me = useMe();
  const staff = isStaff(me);
  const isAdmin = Boolean(me?.roles.includes("admin"));
  const {
    people,
    positions,
    board,
    notes,
    loading,
    saving,
    error,
    setError,
    needUpload,
    dragOver,
    setDragOver,
    draggingId,
    setDraggingId,
    selectedPersonId,
    selectedPerson,
    peopleById,
    assignedIds,
    watchByLead,
    leadOptions,
    load,
    patchTask,
    removeTask,
    setTaskLead,
    setLeadCounts,
    assignToTask,
    addTask: pushTask,
    onDropPool,
    onDropTask,
    toggleSelectPerson,
    addNote,
    deleteNote,
  } = useTaskBoard({ locale, fallbackError: tc("loadFailed"), saveFailedMessage: tc("saveFailed") });

  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskSize, setNewTaskSize] = useState(4);
  const [hide, setHide] = useState({ now: false, nextWeek: false });
  const [exporting, setExporting] = useState(false);
  const [newTaskRange, setNewTaskRange] = useState<{ start: string | null; end: string | null }>({
    start: null,
    end: null,
  });
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [personSearch, setPersonSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [shiftFilter, setShiftFilter] = useState<ShiftFilter>("all");
  const [projectFilter, setProjectFilter] = useState<Set<Project | "none">>(new Set());
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [openTaskIds, setOpenTaskIds] = useState<Set<string>>(new Set());

  function toggleProjectFilter(value: Project | "none") {
    setProjectFilter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function toggleTaskOpen(taskId: string) {
    setOpenTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  useEffect(() => {
    setHide(readHidePrefs());
  }, []);

  useEffect(() => {
    if (!positions.length) {
      setSelectedPositions([]);
      return;
    }
    setSelectedPositions((prev) => (prev.length ? prev.filter((p) => positions.includes(p)) : positions));
  }, [positions]);

  const filteredPeople = useMemo(() => {
    if (!selectedPositions.length) return people;
    const wanted = new Set(selectedPositions.map((p) => p.trim().toLowerCase()));
    return people.filter((p) => wanted.has((p.position || "").trim().toLowerCase()));
  }, [people, selectedPositions]);

  function setHidePref(patch: Partial<typeof hide>) {
    const next = { ...hide, ...patch };
    setHide(next);
    try {
      window.localStorage.setItem(HIDE_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  }

  function matchesPoolFilters(person: Person): boolean {
    if (hide.now && person.on_leave) return false;
    if (hide.nextWeek && leaveOverlapsNextWeek(person)) return false;
    if (statusFilter === "available" && person.on_leave) return false;
    if (statusFilter === "leaveNow" && !person.on_leave) return false;
    if (statusFilter === "leaveNextWeek" && !leaveOverlapsNextWeek(person)) return false;
    if (shiftFilter === "afternoon" && !person.afternoon) return false;
    if (shiftFilter === "day" && person.afternoon) return false;
    if (projectFilter.size) {
      if (!person.project) {
        if (!projectFilter.has("none")) return false;
      } else if (!projectFilter.has(person.project)) {
        return false;
      }
    }
    return true;
  }

  const searchNeedle = normalizeSearch(personSearch);
  const pool = filteredPeople.filter(
    (p) =>
      !assignedIds.has(p.id) &&
      matchesPoolFilters(p) &&
      (!searchNeedle ||
        normalizeSearch(p.name).includes(searchNeedle) ||
        normalizeSearch(p.position || "").includes(searchNeedle))
  );
  const poolLeads = pool.filter((p) => p.is_lead);
  const poolWorkers = pool.filter((p) => !p.is_lead);
  const summary = useMemo(() => requirementsSummary(board.tasks, people), [board.tasks, people]);
  const unclassifiedCount = people.filter((p) => !p.category).length;

  function addTask(e: FormEvent) {
    e.preventDefault();
    const title = newTaskTitle.trim();
    if (!title) return;
    pushTask(
      normalizeTask({
        id: newId("task"),
        title,
        requirements: {},
        size: Math.max(0, Math.floor(newTaskSize) || 0),
        lead_id: null,
        worker_ids: [],
        blocker: false,
        done: false,
        start_date: newTaskRange.start,
        end_date: newTaskRange.end,
        order: board.tasks.length,
      })
    );
    setNewTaskTitle("");
    setNewTaskRange({ start: null, end: null });
  }

  function handleRemoveTask(taskId: string) {
    if (editingTaskId === taskId) {
      setEditingTaskId(null);
      setEditingTitle("");
    }
    removeTask(taskId);
  }

  function startEditTitle(task: Task) {
    setEditingTaskId(task.id);
    setEditingTitle(task.title);
  }

  function commitEditTitle(taskId: string) {
    const title = editingTitle.trim();
    setEditingTaskId(null);
    setEditingTitle("");
    if (!title) return;
    const current = board.tasks.find((task) => task.id === taskId);
    if (!current || current.title === title) return;
    patchTask(taskId, { title });
  }

  function commitBlockerNote(task: Task) {
    const draft = noteDrafts[task.id];
    if (draft === undefined) return;
    setNoteDrafts((prev) => {
      const next = { ...prev };
      delete next[task.id];
      return next;
    });
    const note = draft.trim();
    if (note !== task.blocker_note) patchTask(task.id, { blocker_note: note });
  }

  async function exportPdf() {
    setExporting(true);
    setError("");
    try {
      await api.download(
        `/workforce/board/pdf${qs({ lang: locale })}`,
        `csapatok_${toIsoDate(new Date())}.pdf`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  function togglePosition(pos: string) {
    setSelectedPositions((prev) =>
      prev.includes(pos) ? prev.filter((p) => p !== pos) : [...prev, pos]
    );
  }

  function conflictLabel(range: LeaveRange | null): string | null {
    return range ? t("conflictLeave", { range: formatShortRange(range) }) : null;
  }

  return (
    <div>
      <TopProgress show={loading || saving} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
          <p className="mt-1 text-sm text-[#A1A1AA]">{t("subtitle")}</p>
          {!needUpload && !loading && (
            <p className="mt-2 text-xs text-[#A1A1AA]">
              {t("unassignedCount", { count: pool.length })}
              {selectedPersonId ? (
                <>
                  {" · "}
                  <span className="text-[#5EEAD4]">{t("clickTaskHint")}</span>
                </>
              ) : null}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {!needUpload && (
            <Button variant="outline" onClick={() => void exportPdf()} disabled={exporting || !board.tasks.length}>
              <FileDown className="mr-1 h-4 w-4" />
              {t("exportPdf")}
            </Button>
          )}
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            {tc("refresh")}
          </Button>
        </div>
      </div>

      {!needUpload && !loading && (
        <SummaryBar rows={summary} unclassified={unclassifiedCount} />
      )}

      {needUpload && (
        <div className="mb-4 rounded-md border border-[#F97316]/40 bg-[#F97316]/10 p-4 text-sm text-[#FDBA74]">
          {t("needUpload")}{" "}
          <Link href="/workforce" className="underline underline-offset-2">
            {t("goWorkforce")}
          </Link>
        </div>
      )}
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {!needUpload && positions.length > 0 && (
        <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-[#71717A]">{t("filterPosition")}</p>
            <div className="flex gap-2">
              <button
                type="button"
                className="text-xs text-[#2DD4BF] hover:underline"
                onClick={() => setSelectedPositions(positions)}
              >
                {t("selectAll")}
              </button>
              <button
                type="button"
                className="text-xs text-[#A1A1AA] hover:underline"
                onClick={() => setSelectedPositions([])}
              >
                {t("clearFilter")}
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {positions.map((pos) => {
              const on = selectedPositions.includes(pos);
              const leadish = /lead|csoportvezet|vorarbeiter|leiter/i.test(pos);
              return (
                <button
                  key={pos}
                  type="button"
                  onClick={() => togglePosition(pos)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-xs",
                    on
                      ? leadish
                        ? "border-[#F59E0B]/60 bg-[#F59E0B]/20 text-[#FCD34D]"
                        : "border-[#2DD4BF]/50 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                      : "border-[#27272A] text-[#71717A]"
                  )}
                >
                  {pos}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-[#52525B]">{t("leadHint")}</p>
        </div>
      )}

      {!needUpload && (
        <form onSubmit={addTask} className="mb-4 flex flex-wrap items-center gap-2">
          <Input
            value={newTaskTitle}
            onChange={(e) => setNewTaskTitle(e.target.value)}
            placeholder={t("taskNamePlaceholder")}
            className="max-w-xs"
            autoFocus={!board.tasks.length}
          />
          <label className="inline-flex items-center gap-1.5 text-xs text-[#A1A1AA]">
            <span>{t("teamSizeLabel")}</span>
            <Input
              type="number"
              min={0}
              max={99}
              value={newTaskSize}
              onChange={(e) => setNewTaskSize(Math.max(0, Math.min(99, Number(e.target.value) || 0)))}
              className="h-9 w-16"
              placeholder={t("teamSizePlaceholder")}
            />
          </label>
          <DateRangePicker
            start={newTaskRange.start}
            end={newTaskRange.end}
            onChange={(start, end) => setNewTaskRange({ start, end })}
            className="h-9"
          />
          <Button type="submit" disabled={!newTaskTitle.trim() || saving}>
            <Plus className="mr-1 h-4 w-4" />
            {t("addTask")}
          </Button>
          {!board.tasks.length && (
            <p className="w-full text-sm text-[#A1A1AA]">{t("howToStart")}</p>
          )}
        </form>
      )}

      {!needUpload && (
        <div className="flex flex-col gap-3 pb-4 md:flex-row md:items-start">
          <div
            className={cn(
              "w-full shrink-0 rounded-md border bg-[#0C0C0E] p-3 md:sticky md:top-4 md:w-72",
              dragOver === "pool" ? "border-[#2DD4BF]" : "border-[#27272A]"
            )}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver("pool");
            }}
            onDragLeave={() => setDragOver(null)}
            onDrop={onDropPool}
          >
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <h2 className="text-sm font-medium text-[#FAFAFA]">{t("pool")}</h2>
              <span className="text-xs text-[#71717A]">{pool.length}</span>
            </div>
            <p className="mb-2 text-[11px] text-[#71717A]">{t("poolHint")}</p>
            <div className="relative mb-2">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#71717A]" />
              <Input
                type="search"
                value={personSearch}
                onChange={(e) => setPersonSearch(e.target.value)}
                placeholder={t("searchPeople")}
                className="h-8 pl-7 text-sm"
              />
            </div>
            <div className="mb-3 flex flex-wrap gap-1" role="radiogroup" aria-label={t("filterStatus")}>
              {STATUS_FILTERS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  role="radio"
                  aria-checked={statusFilter === item.key}
                  onClick={() => setStatusFilter(item.key)}
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[11px]",
                    statusFilter === item.key
                      ? item.key === "leaveNextWeek"
                        ? "border-[#F97316] bg-[#F97316]/20 text-[#FDBA74]"
                        : item.key === "leaveNow"
                          ? "border-[#71717A] bg-[#3F3F46] text-[#E4E4E7]"
                          : "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                      : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                  )}
                >
                  {t(item.label)}
                </button>
              ))}
            </div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{t("filterShift")}</p>
            <div className="mb-3 flex flex-wrap gap-1" role="radiogroup" aria-label={t("filterShift")}>
              {SHIFT_FILTERS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  role="radio"
                  aria-checked={shiftFilter === item.key}
                  onClick={() => setShiftFilter(item.key)}
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[11px]",
                    shiftFilter === item.key
                      ? item.key === "afternoon"
                        ? "border-[#7C3AED]/60 bg-[#7C3AED]/20 text-[#C4B5FD]"
                        : "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                      : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                  )}
                >
                  {t(item.label)}
                </button>
              ))}
            </div>
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{t("filterProject")}</p>
            <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label={t("filterProject")}>
              <button
                type="button"
                aria-pressed={projectFilter.has("none")}
                onClick={() => toggleProjectFilter("none")}
                className={cn(
                  "rounded-md border px-2 py-0.5 text-[11px]",
                  projectFilter.has("none")
                    ? "border-[#71717A] bg-[#3F3F46] text-[#E4E4E7]"
                    : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                )}
              >
                {t("projectNone")}
              </button>
              {PROJECTS.map((code) => (
                <button
                  key={code}
                  type="button"
                  aria-pressed={projectFilter.has(code)}
                  onClick={() => toggleProjectFilter(code)}
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[11px]",
                    projectFilter.has(code)
                      ? "border-[#0E7490] bg-[#0E7490]/25 text-[#67E8F9]"
                      : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                  )}
                >
                  {code}
                </button>
              ))}
            </div>
            <div className="mb-3 flex flex-col gap-1 text-[11px] text-[#A1A1AA]">
              <label className="inline-flex cursor-pointer items-center gap-1.5">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 accent-[#71717A]"
                  checked={hide.now}
                  onChange={(e) => setHidePref({ now: e.target.checked })}
                />
                {t("hideLeaveNow")}
              </label>
              <label className="inline-flex cursor-pointer items-center gap-1.5">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 accent-[#F97316]"
                  checked={hide.nextWeek}
                  onChange={(e) => setHidePref({ nextWeek: e.target.checked })}
                />
                {t("hideLeaveNextWeek")}
              </label>
            </div>
            {(searchNeedle ||
              statusFilter !== "all" ||
              shiftFilter !== "all" ||
              projectFilter.size > 0 ||
              hide.now ||
              hide.nextWeek) &&
              pool.length === 0 && (
                <p className="mb-2 text-xs text-[#71717A]">{t("noSearchResults")}</p>
              )}

            {poolLeads.length > 0 && (
              <>
                <p className="mb-1 text-[10px] uppercase tracking-wide text-[#F59E0B]">{t("leads")}</p>
                <div className="mb-3 flex flex-col gap-2">
                  {poolLeads.map((person) => (
                    <PersonChip
                      key={person.id}
                      person={person}
                      dragging={draggingId === person.id}
                      selected={selectedPersonId === person.id}
                      leaveLabel={t("leaveSoon")}
                      nowLeaveLabel={t("leaveNow")}
                      nextWeekLeaveLabel={t("leaveNextWeek")}
                      onDragStart={setDraggingId}
                      onSelect={toggleSelectPerson}
                    />
                  ))}
                </div>
              </>
            )}

            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{t("workers")}</p>
            <div className="flex max-h-[60vh] flex-col gap-2 overflow-y-auto">
              {poolWorkers.map((person) => (
                <PersonChip
                  key={person.id}
                  person={person}
                  dragging={draggingId === person.id}
                  selected={selectedPersonId === person.id}
                  leaveLabel={t("leaveSoon")}
                  nowLeaveLabel={t("leaveNow")}
                  nextWeekLeaveLabel={t("leaveNextWeek")}
                  onDragStart={setDraggingId}
                  onSelect={toggleSelectPerson}
                />
              ))}
              {!pool.length && !searchNeedle && statusFilter === "all" && !hide.now && !hide.nextWeek && (
                <p className="text-xs text-[#52525B]">{t("poolEmpty")}</p>
              )}
            </div>
          </div>

          <div className="grid min-w-0 flex-1 grid-cols-1 items-start gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {!board.tasks.length && !loading && (
            <div className="flex flex-col justify-center rounded-md border border-dashed border-[#3F3F46] bg-[#0C0C0E]/60 p-4 text-sm text-[#A1A1AA]">
              <p className="font-medium text-[#E4E4E7]">{t("noTasks")}</p>
              <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs text-[#A1A1AA]">
                <li>{t("stepAddTask")}</li>
                <li>{t("stepAssignLead")}</li>
                <li>{t("stepAssignWorkers")}</li>
              </ol>
            </div>
          )}

          {board.tasks
            .slice()
            .sort((a, b) => a.order - b.order)
            .map((task) => {
              const lead = task.lead_id ? peopleById.get(task.lead_id) : undefined;
              const workers = task.worker_ids
                .map((id) => peopleById.get(id))
                .filter((p): p is Person => Boolean(p));
              const members = taskMembers(task, peopleById);
              const conflictCount = members.filter((p) => taskLeaveConflict(p, task)).length;
              const memberLeave = members.flatMap((p) => personLeaveRanges(p));
              const selectedConflict =
                selectedPerson && !task.done ? taskLeaveConflict(selectedPerson, task) : null;
              const filled = taskHeadcount(task);
              const target = task.size > 0 ? task.size : 0;
              const staffed = target > 0 && filled >= target;
              const understaffed = target > 0 && filled < target;
              const blockedOpen = task.blocker && !task.done;
              const noteValue = noteDrafts[task.id] ?? task.blocker_note;
              const noteMissing = task.blocker && !noteValue.trim();
              const open = openTaskIds.has(task.id);
              const dateLabel = formatRangeLabel(locale, task.start_date, task.end_date, (count) =>
                td("days", { count })
              );
              const extraWorkers = Math.max(0, workers.length - 2);
              const taskNotes = notes[task.id] || [];
              return (
                <div
                  key={task.id}
                  className={cn(
                    "min-w-0 rounded-md border p-2.5",
                    staffed
                      ? "border-[#2DD4BF]/55 bg-[#042F2E]"
                      : understaffed
                        ? "border-[#F59E0B]/45 bg-[#1A1207]"
                        : "border-[#27272A] bg-[#0C0C0E]",
                    dragOver === task.id || dragOver?.startsWith(`${task.id}:`)
                      ? "border-[#2DD4BF]"
                      : null,
                    blockedOpen && "border-[#EF4444]/60",
                    task.done && "opacity-70",
                    selectedConflict && "outline-dashed outline-2 outline-offset-2 outline-[#EF4444]"
                  )}
                  title={
                    selectedConflict && selectedPerson
                      ? t("selectedConflict", {
                          name: selectedPerson.name,
                          range: formatShortRange(selectedConflict),
                        })
                      : undefined
                  }
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(task.id);
                  }}
                  onDragLeave={() => setDragOver(null)}
                  onDrop={onDropTask(task.id, "auto")}
                  onClick={() => {
                    if (!selectedPersonId || task.done) return;
                    assignToTask(selectedPersonId, task.id, "auto");
                  }}
                >
                  <div className="mb-1.5 flex items-start gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleTaskOpen(task.id);
                      }}
                      className="mt-0.5 shrink-0 text-[#71717A] hover:text-[#FAFAFA]"
                      aria-expanded={open}
                      title={open ? t("hideDetails") : t("showDetails")}
                    >
                      <ChevronRight className={cn("h-4 w-4 transition-transform", open && "rotate-90")} />
                    </button>
                    {editingTaskId === task.id ? (
                      <Input
                        autoFocus
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onBlur={() => commitEditTitle(task.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            commitEditTitle(task.id);
                          } else if (e.key === "Escape") {
                            setEditingTaskId(null);
                            setEditingTitle("");
                          }
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="h-8 min-w-0 flex-1"
                      />
                    ) : (
                      <div className="flex min-w-0 flex-1 items-start gap-1">
                        <Link
                          href={`/tasks/${encodeURIComponent(task.id)}`}
                          onClick={(e) => e.stopPropagation()}
                          className="min-w-0 flex-1 break-words text-sm font-semibold leading-snug text-[#FAFAFA] hover:text-[#5EEAD4] hover:underline"
                          title={t("openTask")}
                        >
                          {task.title}
                        </Link>
                        <button
                          type="button"
                          className="mt-0.5 shrink-0 text-[#71717A] hover:text-[#E4E4E7]"
                          title={t("renameTask")}
                          onClick={(e) => {
                            e.stopPropagation();
                            startEditTitle(task);
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 w-8 shrink-0 p-0 text-[#F87171]"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveTask(task.id);
                      }}
                      title={t("removeTask")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  <div className="mb-1 flex flex-wrap items-center gap-1.5">
                    {conflictCount > 0 && (
                      <span className="inline-flex items-center gap-1 rounded bg-[#EF4444] px-1.5 py-0.5 text-[10px] font-bold text-white">
                        <AlertTriangle className="h-3 w-3" />
                        {t("conflictsCount", { count: conflictCount })}
                      </span>
                    )}
                    {blockedOpen && (
                      <span className="rounded bg-[#EF4444]/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#FCA5A5]">
                        {t("blocked")}
                      </span>
                    )}
                    {task.done && (
                      <span className="rounded bg-[#3F3F46] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#E4E4E7]">
                        {t("markDone")}
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-[#A1A1AA]">{dateLabel || t("noDates")}</p>
                  <p
                    className={cn(
                      "text-xs",
                      staffed && "font-medium text-[#5EEAD4]",
                      understaffed && "text-[#FBBF24]",
                      !target && "text-[#71717A]"
                    )}
                  >
                    {target
                      ? t("headcountProgress", { current: filled, target })
                      : t("peopleCount", { count: filled })}
                  </p>
                  <p className="truncate text-xs">
                    <span className={lead ? "text-[#FCD34D]" : "text-[#EF4444]"}>
                      {lead
                        ? `${lead.name} · ${watchByLead.get(lead.id) ?? 0}`
                        : t("noLeadShort")}
                    </span>
                    <span className="text-[#71717A]">
                      {" · "}
                      {t("workers")} · {workers.length}
                      {workers.length
                        ? ` · ${workers
                            .slice(0, 2)
                            .map((p) => p.name)
                            .join(", ")}${extraWorkers ? ` ${t("moreWorkers", { count: extraWorkers })}` : ""}`
                        : ""}
                    </span>
                  </p>
                  {taskNotes.length > 0 && (
                    <p className="text-[11px] text-[#71717A]">{t("notesTitle", { count: taskNotes.length })}</p>
                  )}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleTaskOpen(task.id);
                    }}
                    className="mt-1 text-[11px] text-[#2DD4BF] hover:underline"
                  >
                    {open ? t("hideDetails") : t("showDetails")}
                  </button>

                  {open && (
                  <div className="mt-2 border-t border-[#27272A] pt-2">
                  <div className="mb-1.5">
                    <DateRangePicker
                      start={task.start_date}
                      end={task.end_date}
                      onChange={(start_date, end_date) => patchTask(task.id, { start_date, end_date })}
                      leaveRanges={memberLeave}
                      className="max-w-full"
                    />
                  </div>
                  <label
                    className="mb-2 inline-flex items-center gap-1.5 text-xs text-[#A1A1AA]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span>{t("teamSizeLabel")}</span>
                    <Input
                      type="number"
                      min={0}
                      max={99}
                      value={task.size}
                      onChange={(e) =>
                        patchTask(task.id, {
                          size: Math.max(0, Math.min(99, Math.floor(Number(e.target.value) || 0))),
                        })
                      }
                      className="h-8 w-16"
                    />
                  </label>

                  <p className="mb-1 text-[10px] uppercase tracking-wide text-[#F59E0B]">{t("leadSlot")}</p>
                  <div className="mb-2" onClick={(e) => e.stopPropagation()}>
                    <select
                      value={task.lead_id || ""}
                      onChange={(e) => setTaskLead(task.id, e.target.value || null)}
                      className={cn(
                        "w-full rounded-md border bg-[#18181B] px-2 py-1.5 text-sm",
                        task.lead_id ? "border-[#F59E0B]/50 text-[#FCD34D]" : "border-[#EF4444] text-[#A1A1AA]"
                      )}
                      aria-label={t("leadSlot")}
                    >
                      <option value="">{t("noLeadShort")}</option>
                      {leadOptions.map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.name} · {watchByLead.get(person.id) ?? 0}
                        </option>
                      ))}
                    </select>
                    {lead ? (
                      <div className="mt-1">
                        <PersonChip
                          person={lead}
                          dragging={draggingId === lead.id}
                          selected={selectedPersonId === lead.id}
                          leaveLabel={t("leaveSoon")}
                          nowLeaveLabel={t("leaveNow")}
                          nextWeekLeaveLabel={t("leaveNextWeek")}
                          conflictText={conflictLabel(taskLeaveConflict(lead, task))}
                          watching={watchByLead.get(lead.id) ?? 0}
                          watchingLabel={t("watching", { count: watchByLead.get(lead.id) ?? 0 })}
                          onDragStart={setDraggingId}
                          onSelect={toggleSelectPerson}
                        />
                        <label
                          className="mt-1.5 flex cursor-pointer items-start gap-1.5 text-[11px] text-[#A1A1AA]"
                          title={t("leadCountsHelp")}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5 h-3.5 w-3.5 accent-[#F59E0B]"
                            checked={Boolean(task.lead_counts)}
                            onChange={(e) => setLeadCounts(task.id, e.target.checked)}
                          />
                          <span>{t("leadCounts")}</span>
                        </label>
                      </div>
                    ) : null}
                  </div>

                  <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">
                    {t("workers")} · {workers.length}
                  </p>
                  <div
                    className={cn(
                      "flex max-h-72 min-h-[2.25rem] flex-col gap-1.5 overflow-y-auto rounded-md border border-dashed p-1",
                      dragOver === `${task.id}:worker` ? "border-[#2DD4BF]" : "border-[#3F3F46]"
                    )}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setDragOver(`${task.id}:worker`);
                    }}
                    onDrop={onDropTask(task.id, "worker")}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!selectedPersonId) return;
                      assignToTask(selectedPersonId, task.id, "worker");
                    }}
                  >
                    {workers.map((person) => (
                      <PersonChip
                        key={person.id}
                        person={person}
                        dragging={draggingId === person.id}
                        selected={selectedPersonId === person.id}
                        leaveLabel={t("leaveSoon")}
                        nowLeaveLabel={t("leaveNow")}
                        nextWeekLeaveLabel={t("leaveNextWeek")}
                        conflictText={conflictLabel(taskLeaveConflict(person, task))}
                        watching={watchByLead.has(person.id) ? watchByLead.get(person.id) : undefined}
                        watchingLabel={
                          watchByLead.has(person.id)
                            ? t("watching", { count: watchByLead.get(person.id) ?? 0 })
                            : undefined
                        }
                        onDragStart={setDraggingId}
                        onSelect={toggleSelectPerson}
                      />
                    ))}
                    {!workers.length && (
                      <p className="px-1 py-1 text-xs text-[#52525B]">{t("dropWorkers")}</p>
                    )}
                  </div>

                  <TaskNotes
                    notes={notes[task.id] || []}
                    canWrite={staff}
                    canDelete={(n) => isAdmin || n.author_email === me?.email}
                    onAdd={(text) => addNote(task.id, text)}
                    onDelete={(n) => void deleteNote(n)}
                  />

                  <div
                    className="mt-2 border-t border-[#27272A] pt-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="flex items-center gap-4 text-xs text-[#A1A1AA]">
                      <label className="inline-flex cursor-pointer items-center gap-1.5">
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 accent-[#2DD4BF]"
                          checked={task.done}
                          onChange={(e) => patchTask(task.id, { done: e.target.checked })}
                        />
                        {t("markDone")}
                      </label>
                      <label
                        className={cn(
                          "inline-flex cursor-pointer items-center gap-1.5",
                          task.blocker && "text-[#FCA5A5]"
                        )}
                      >
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 accent-[#EF4444]"
                          checked={task.blocker}
                          onChange={(e) => patchTask(task.id, { blocker: e.target.checked })}
                        />
                        {t("blocker")}
                      </label>
                    </div>
                    {task.blocker && (
                      <div className="mt-2">
                        <label
                          className="mb-1 block text-[10px] uppercase tracking-wide text-[#FCA5A5]"
                          htmlFor={`blocker-${task.id}`}
                        >
                          {t("blockerNoteLabel")} *
                        </label>
                        <textarea
                          id={`blocker-${task.id}`}
                          required
                          rows={2}
                          value={noteValue}
                          autoFocus={!task.blocker_note}
                          onChange={(e) =>
                            setNoteDrafts((prev) => ({ ...prev, [task.id]: e.target.value }))
                          }
                          onBlur={() => commitBlockerNote(task)}
                          placeholder={t("blockerNotePlaceholder")}
                          maxLength={500}
                          className={cn(
                            "w-full resize-y rounded-md border bg-[#18181B] px-2 py-1.5 text-sm text-[#FAFAFA] placeholder:text-[#52525B] focus:outline-none focus:ring-1",
                            noteMissing
                              ? "border-[#EF4444] focus:ring-[#EF4444]"
                              : "border-[#3F3F46] focus:ring-[#2DD4BF]"
                          )}
                        />
                        {noteMissing && (
                          <p className="mt-0.5 text-[11px] text-[#F87171]">{t("blockerRequired")}</p>
                        )}
                      </div>
                    )}
                  </div>
                  </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
