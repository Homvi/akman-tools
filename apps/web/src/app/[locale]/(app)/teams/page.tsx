"use client";

import { DragEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { AlertTriangle, Info, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { isStaff, useMe } from "@/components/auth-gate";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { DateRangePicker } from "@/components/date-range-picker";
import { cn } from "@/lib/utils";
import {
  formatShortRange,
  leaveOverlapsNextWeek,
  newId,
  normalizeTask,
  personLeaveRanges,
  taskLeaveConflict,
  taskMembers,
  type Board,
  type LeaveRange,
  type Person,
  type Task,
} from "@/lib/staffing";

type StatusFilter = "all" | "available" | "leaveNow" | "leaveNextWeek";

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "statusAll" },
  { key: "available", label: "statusAvailable" },
  { key: "leaveNow", label: "statusLeaveNow" },
  { key: "leaveNextWeek", label: "statusLeaveNextWeek" },
];

function parseSize(raw: string): number {
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.min(n, 999);
}

function formatLeaveHint(person: Person, leaveLabel: string): string | null {
  const first = personLeaveRanges(person)[0];
  return first ? `${leaveLabel} ${formatShortRange(first)}` : null;
}

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function PersonChip({
  person,
  dragging,
  selected,
  leaveLabel,
  nowLeaveLabel,
  nextWeekLeaveLabel,
  conflictText,
  onDragStart,
  onSelect,
}: {
  person: Person;
  dragging?: boolean;
  selected?: boolean;
  leaveLabel: string;
  nowLeaveLabel: string;
  nextWeekLeaveLabel: string;
  /** Set when this person's leave overlaps the task they sit on. */
  conflictText?: string | null;
  onDragStart: (id: string) => void;
  onSelect?: (id: string) => void;
}) {
  const t = useTranslations("teams");
  const canSeeDetails = isStaff(useMe());
  const leaveHint = formatLeaveHint(person, leaveLabel);
  const onLeaveNow = Boolean(person.on_leave);
  const nextWeek = leaveOverlapsNextWeek(person);
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/person-id", person.id);
        e.dataTransfer.effectAllowed = "move";
        onDragStart(person.id);
      }}
      onClick={() => onSelect?.(person.id)}
      className={cn(
        "cursor-grab rounded-md border px-2.5 py-1.5 text-sm active:cursor-grabbing",
        person.is_lead
          ? "border-[#F59E0B]/50 bg-[#F59E0B]/15 text-[#FCD34D]"
          : "border-[#27272A] bg-[#18181B] text-[#E4E4E7]",
        nextWeek && !onLeaveNow && "border-[#F97316] bg-[#F97316]/15 ring-1 ring-[#F97316]/70",
        onLeaveNow && "border-[#3F3F46] bg-[#18181B] text-[#A1A1AA] grayscale",
        onLeaveNow && !conflictText && "opacity-50",
        conflictText && "border-[#EF4444] ring-2 ring-[#EF4444]",
        selected && "ring-2 ring-[#2DD4BF]",
        dragging && "opacity-50"
      )}
      title={[
        person.position,
        leaveHint,
        onLeaveNow ? nowLeaveLabel : null,
        nextWeek ? nextWeekLeaveLabel : null,
        conflictText,
      ]
        .filter(Boolean)
        .join(" · ") || undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 break-words font-medium leading-tight">{person.name}</div>
        {onLeaveNow || nextWeek ? (
          <div className="flex shrink-0 flex-col items-end gap-0.5">
            {onLeaveNow ? (
              <span className="rounded bg-[#52525B] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#E4E4E7]">
                {nowLeaveLabel}
              </span>
            ) : null}
            {nextWeek ? (
              <span className="rounded bg-[#F97316] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-black">
                {nextWeekLeaveLabel}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      {person.position || canSeeDetails ? (
        <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-[#A1A1AA]">
          <span className="min-w-0 truncate">{person.position}</span>
          {canSeeDetails ? (
            <Link
              href={`/workers/${encodeURIComponent(person.id)}`}
              draggable={false}
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              className="inline-flex shrink-0 items-center gap-0.5 rounded px-1 text-[#71717A] hover:bg-[#27272A] hover:text-[#5EEAD4]"
            >
              <Info className="h-3 w-3" />
              {t("details")}
            </Link>
          ) : null}
        </div>
      ) : null}
      {conflictText ? (
        <div className="mt-1 inline-flex items-center gap-1 rounded bg-[#EF4444] px-1.5 py-0.5 text-[10px] font-bold text-white">
          <AlertTriangle className="h-3 w-3" />
          {conflictText}
        </div>
      ) : leaveHint ? (
        <div
          className={cn(
            "mt-0.5 text-[10px]",
            onLeaveNow ? "text-[#A1A1AA]" : nextWeek ? "font-semibold text-[#FDBA74]" : "text-[#FBBF24]"
          )}
        >
          {leaveHint}
        </div>
      ) : null}
    </div>
  );
}

export default function TeamsPage() {
  const t = useTranslations("teams");
  const tc = useTranslations("common");
  const [people, setPeople] = useState<Person[]>([]);
  const [positions, setPositions] = useState<string[]>([]);
  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [board, setBoard] = useState<Board>({ tasks: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [needUpload, setNeedUpload] = useState(false);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskSize, setNewTaskSize] = useState("4");
  const [newTaskRange, setNewTaskRange] = useState<{ start: string | null; end: string | null }>({
    start: null,
    end: null,
  });
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [personSearch, setPersonSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    setError("");
    setNeedUpload(false);
    try {
      const [peopleRes, boardRes] = await Promise.all([
        api.get<{ people: Person[]; positions: string[] }>("/workforce/people"),
        api.get<Board>("/workforce/board"),
      ]);
      setPeople(peopleRes.people || []);
      const pos = peopleRes.positions || [];
      setPositions(pos);
      setSelectedPositions((prev) => (prev.length ? prev.filter((p) => pos.includes(p)) : pos));
      setBoard({
        tasks: (boardRes.tasks || []).map((task) => normalizeTask(task)),
        updated_at: boardRes.updated_at,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : tc("loadFailed");
      if (/workforce|upload|404/i.test(msg) || msg.toLowerCase().includes("no workforce")) {
        setNeedUpload(true);
        setPeople([]);
        setPositions([]);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function persist(next: Board) {
    setSaving(true);
    setError("");
    try {
      const saved = await api.put<Board>("/workforce/board", { tasks: next.tasks });
      setBoard({
        tasks: (saved.tasks || []).map((task) => normalizeTask(task)),
        updated_at: saved.updated_at,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("exportFailed"));
    } finally {
      setSaving(false);
    }
  }

  const peopleById = useMemo(() => {
    const map = new Map<string, Person>();
    for (const p of people) map.set(p.id, p);
    return map;
  }, [people]);

  const filteredPeople = useMemo(() => {
    if (!selectedPositions.length) return people;
    const wanted = new Set(selectedPositions.map((p) => p.trim().toLowerCase()));
    return people.filter((p) => wanted.has((p.position || "").trim().toLowerCase()));
  }, [people, selectedPositions]);

  const assignedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const task of board.tasks) {
      if (task.lead_id) ids.add(task.lead_id);
      for (const wid of task.worker_ids) ids.add(wid);
    }
    return ids;
  }, [board.tasks]);

  function matchesStatus(person: Person): boolean {
    if (statusFilter === "available") return !person.on_leave;
    if (statusFilter === "leaveNow") return Boolean(person.on_leave);
    if (statusFilter === "leaveNextWeek") return leaveOverlapsNextWeek(person);
    return true;
  }

  const searchNeedle = normalizeSearch(personSearch);
  const pool = filteredPeople.filter(
    (p) =>
      !assignedIds.has(p.id) &&
      matchesStatus(p) &&
      (!searchNeedle ||
        normalizeSearch(p.name).includes(searchNeedle) ||
        normalizeSearch(p.position || "").includes(searchNeedle))
  );
  const poolLeads = pool.filter((p) => p.is_lead);
  const poolWorkers = pool.filter((p) => !p.is_lead);
  const selectedPerson = selectedPersonId ? peopleById.get(selectedPersonId) : undefined;

  function taskHeadcount(task: Task) {
    return (task.lead_id ? 1 : 0) + task.worker_ids.length;
  }

  function stripPersonFromTasks(tasks: Task[], personId: string): Task[] {
    return tasks.map((task) => ({
      ...task,
      lead_id: task.lead_id === personId ? null : task.lead_id,
      worker_ids: task.worker_ids.filter((id) => id !== personId),
    }));
  }

  function assignToTask(personId: string, taskId: string, role: "lead" | "worker" | "auto") {
    const person = peopleById.get(personId);
    const resolved: "lead" | "worker" =
      role === "auto" ? (person?.is_lead ? "lead" : "worker") : role;

    let tasks = stripPersonFromTasks(board.tasks, personId);
    tasks = tasks.map((task) => {
      if (task.id !== taskId) return task;
      if (resolved === "lead") {
        const previousLead = task.lead_id;
        const workers = task.worker_ids.filter((id) => id !== personId);
        if (previousLead && previousLead !== personId) {
          workers.unshift(previousLead);
        }
        return { ...task, lead_id: personId, worker_ids: workers };
      }
      const workers = task.worker_ids.filter((id) => id !== personId);
      if (!workers.includes(personId) && task.lead_id !== personId) {
        workers.push(personId);
      }
      return {
        ...task,
        lead_id: task.lead_id === personId ? null : task.lead_id,
        worker_ids: workers,
      };
    });
    const next = { ...board, tasks };
    setBoard(next);
    setSelectedPersonId(null);
    void persist(next);
  }

  function unassignPerson(personId: string) {
    const next = { ...board, tasks: stripPersonFromTasks(board.tasks, personId) };
    setBoard(next);
    setSelectedPersonId(null);
    void persist(next);
  }

  function onDropPool(e: DragEvent) {
    e.preventDefault();
    setDragOver(null);
    const personId = e.dataTransfer.getData("text/person-id") || draggingId;
    setDraggingId(null);
    if (!personId) return;
    unassignPerson(personId);
  }

  function onDropTask(taskId: string, role: "lead" | "worker" | "auto") {
    return (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(null);
      const personId = e.dataTransfer.getData("text/person-id") || draggingId;
      setDraggingId(null);
      if (!personId) return;
      assignToTask(personId, taskId, role);
    };
  }

  function addTask(e: FormEvent) {
    e.preventDefault();
    const title = newTaskTitle.trim();
    if (!title) return;
    const task = normalizeTask({
      id: newId("task"),
      title,
      size: parseSize(newTaskSize),
      lead_id: null,
      worker_ids: [],
      blocker: false,
      done: false,
      start_date: newTaskRange.start,
      end_date: newTaskRange.end,
      order: board.tasks.length,
    });
    const next = { ...board, tasks: [...board.tasks, task] };
    setNewTaskTitle("");
    setNewTaskRange({ start: null, end: null });
    setBoard(next);
    void persist(next);
  }

  function patchTask(taskId: string, patch: Partial<Task>) {
    const next = {
      ...board,
      tasks: board.tasks.map((task) => (task.id === taskId ? { ...task, ...patch } : task)),
    };
    setBoard(next);
    void persist(next);
  }

  function removeTask(taskId: string) {
    const next = { ...board, tasks: board.tasks.filter((task) => task.id !== taskId) };
    setBoard(next);
    if (editingTaskId === taskId) {
      setEditingTaskId(null);
      setEditingTitle("");
    }
    void persist(next);
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

  function togglePosition(pos: string) {
    setSelectedPositions((prev) =>
      prev.includes(pos) ? prev.filter((p) => p !== pos) : [...prev, pos]
    );
  }

  function toggleSelectPerson(personId: string) {
    setSelectedPersonId((prev) => (prev === personId ? null : personId));
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
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          {tc("refresh")}
        </Button>
      </div>

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
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-[#A1A1AA]" htmlFor="new-task-size">
              {t("teamSizeLabel")}
            </label>
            <Input
              id="new-task-size"
              type="number"
              min={0}
              max={999}
              value={newTaskSize}
              onChange={(e) => setNewTaskSize(e.target.value)}
              className="h-9 w-20"
            />
          </div>
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
            {(searchNeedle || statusFilter !== "all") && pool.length === 0 && (
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
              {!pool.length && !searchNeedle && statusFilter === "all" && (
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
              const sizeOver = target > 0 && filled > target;
              const sizeUnder = target > 0 && filled < target;
              const sizeOk = target > 0 && filled === target;
              const blockedOpen = task.blocker && !task.done;
              const noteValue = noteDrafts[task.id] ?? task.blocker_note;
              const noteMissing = task.blocker && !noteValue.trim();
              return (
                <div
                  key={task.id}
                  className={cn(
                    "min-w-0 rounded-md border bg-[#0C0C0E] p-2.5",
                    dragOver === task.id || dragOver?.startsWith(`${task.id}:`)
                      ? "border-[#2DD4BF]"
                      : "border-[#27272A]",
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
                        <h3 className="min-w-0 flex-1 break-words text-sm font-semibold leading-snug text-[#FAFAFA]">
                          {task.title}
                        </h3>
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
                    <Input
                      type="number"
                      min={0}
                      max={999}
                      value={task.size || ""}
                      onChange={(e) => {
                        const size = parseSize(e.target.value);
                        setBoard({
                          ...board,
                          tasks: board.tasks.map((item) =>
                            item.id === task.id ? { ...item, size } : item
                          ),
                        });
                      }}
                      onBlur={() => void persist(board)}
                      onClick={(e) => e.stopPropagation()}
                      title={t("teamSizeLabel")}
                      className="h-8 w-14 shrink-0 px-1 text-center"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 w-8 shrink-0 p-0 text-[#F87171]"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeTask(task.id);
                      }}
                      title={t("removeTask")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>

                  <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                    <DateRangePicker
                      start={task.start_date}
                      end={task.end_date}
                      onChange={(start_date, end_date) => patchTask(task.id, { start_date, end_date })}
                      leaveRanges={memberLeave}
                      className="max-w-full"
                    />
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

                  <p
                    className={cn(
                      "mb-1.5 text-xs",
                      sizeOver && "text-[#F87171]",
                      sizeUnder && "text-[#FBBF24]",
                      sizeOk && "text-[#5EEAD4]",
                      !target && "text-[#71717A]"
                    )}
                  >
                    {target
                      ? t("headcountProgress", { current: filled, target })
                      : t("peopleCount", { count: filled })}
                  </p>

                  <p className="mb-1 text-[10px] uppercase tracking-wide text-[#F59E0B]">{t("leadSlot")}</p>
                  <div
                    className={cn(
                      "mb-2 min-h-[2.25rem] rounded-md border border-dashed p-1",
                      dragOver === `${task.id}:lead` ? "border-[#F59E0B]" : "border-[#3F3F46]"
                    )}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setDragOver(`${task.id}:lead`);
                    }}
                    onDrop={onDropTask(task.id, "lead")}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!selectedPersonId) return;
                      assignToTask(selectedPersonId, task.id, "lead");
                    }}
                  >
                    {lead ? (
                      <PersonChip
                        person={lead}
                        dragging={draggingId === lead.id}
                        selected={selectedPersonId === lead.id}
                        leaveLabel={t("leaveSoon")}
                        nowLeaveLabel={t("leaveNow")}
                        nextWeekLeaveLabel={t("leaveNextWeek")}
                        conflictText={conflictLabel(taskLeaveConflict(lead, task))}
                        onDragStart={setDraggingId}
                        onSelect={toggleSelectPerson}
                      />
                    ) : (
                      <p className="px-1 py-1 text-xs text-[#52525B]">{t("dropLead")}</p>
                    )}
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
                        onDragStart={setDraggingId}
                        onSelect={toggleSelectPerson}
                      />
                    ))}
                    {!workers.length && (
                      <p className="px-1 py-1 text-xs text-[#52525B]">{t("dropWorkers")}</p>
                    )}
                  </div>

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
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
