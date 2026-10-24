"use client";

import { DragEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

type Person = {
  id: string;
  name: string;
  position: string;
  is_lead: boolean;
  available?: boolean;
  on_leave?: boolean;
  leave_start?: string | null;
  leave_end?: string | null;
  last_present?: string | null;
};

type Task = {
  id: string;
  title: string;
  size: number;
  lead_id: string | null;
  worker_ids: string[];
  blocker: boolean;
  done: boolean;
  order: number;
};

type Board = {
  tasks: Task[];
  updated_at?: string | null;
};

function newId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeTask(task: Partial<Task> & { title: string }): Task {
  return {
    id: task.id || newId("task"),
    title: task.title,
    size: typeof task.size === "number" && task.size > 0 ? task.size : Number(task.size) || 0,
    lead_id: task.lead_id || null,
    worker_ids: Array.isArray(task.worker_ids) ? task.worker_ids.filter(Boolean) : [],
    blocker: Boolean(task.blocker),
    done: Boolean(task.done),
    order: typeof task.order === "number" ? task.order : 0,
  };
}

function parseSize(raw: string): number {
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.min(n, 999);
}

function parseIsoDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(`${value}T12:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Next calendar week Mon–Sun relative to `today`. */
function nextWeekRange(today = new Date()): { start: Date; end: Date } {
  const base = new Date(today);
  base.setHours(12, 0, 0, 0);
  const dow = base.getDay(); // 0=Sun … 6=Sat
  const daysUntilNextMon = dow === 0 ? 1 : 8 - dow;
  const start = new Date(base);
  start.setDate(base.getDate() + daysUntilNextMon);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return { start, end };
}

function leaveOverlapsNextWeek(person: Person, today = new Date()): boolean {
  const leaveStart = parseIsoDate(person.leave_start);
  if (!leaveStart) return false;
  const leaveEnd = parseIsoDate(person.leave_end) || leaveStart;
  const { start, end } = nextWeekRange(today);
  return leaveStart <= end && leaveEnd >= start;
}

function formatLeaveHint(person: Person, leaveLabel: string): string | null {
  if (!person.leave_start) return null;
  const start = person.leave_start.slice(5).replace("-", ".");
  if (person.leave_end && person.leave_end !== person.leave_start) {
    const end = person.leave_end.slice(5).replace("-", ".");
    return `${leaveLabel} ${start}–${end}`;
  }
  return `${leaveLabel} ${start}`;
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
  onDragStart,
  onSelect,
}: {
  person: Person;
  dragging?: boolean;
  selected?: boolean;
  leaveLabel: string;
  nowLeaveLabel: string;
  nextWeekLeaveLabel: string;
  onDragStart: (id: string) => void;
  onSelect?: (id: string) => void;
}) {
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
        onLeaveNow && "border-[#EF4444] bg-[#EF4444]/15 ring-1 ring-[#EF4444]/70",
        selected && "ring-2 ring-[#2DD4BF]",
        dragging && "opacity-50"
      )}
      title={[
        person.position,
        leaveHint,
        onLeaveNow ? nowLeaveLabel : null,
        nextWeek ? nextWeekLeaveLabel : null,
      ]
        .filter(Boolean)
        .join(" · ") || undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 break-words font-medium leading-tight">{person.name}</div>
        {onLeaveNow || nextWeek ? (
          <div className="flex shrink-0 flex-col items-end gap-0.5">
            {onLeaveNow ? (
              <span className="rounded bg-[#EF4444] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
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
      {person.position ? (
        <div className="mt-0.5 text-[11px] text-[#A1A1AA]">{person.position}</div>
      ) : null}
      {leaveHint ? (
        <div
          className={cn(
            "mt-0.5 text-[10px]",
            onLeaveNow
              ? "font-semibold text-[#FCA5A5]"
              : nextWeek
                ? "font-semibold text-[#FDBA74]"
                : "text-[#FBBF24]"
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
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [personSearch, setPersonSearch] = useState("");

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

  const searchNeedle = normalizeSearch(personSearch);
  const pool = filteredPeople.filter(
    (p) =>
      !assignedIds.has(p.id) &&
      (!searchNeedle ||
        normalizeSearch(p.name).includes(searchNeedle) ||
        normalizeSearch(p.position || "").includes(searchNeedle))
  );
  const poolLeads = pool.filter((p) => p.is_lead);
  const poolWorkers = pool.filter((p) => !p.is_lead);

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
      order: board.tasks.length,
    });
    const next = { ...board, tasks: [...board.tasks, task] };
    setNewTaskTitle("");
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

  function togglePosition(pos: string) {
    setSelectedPositions((prev) =>
      prev.includes(pos) ? prev.filter((p) => p !== pos) : [...prev, pos]
    );
  }

  function toggleSelectPerson(personId: string) {
    setSelectedPersonId((prev) => (prev === personId ? null : personId));
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
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#71717A]" />
              <Input
                type="search"
                value={personSearch}
                onChange={(e) => setPersonSearch(e.target.value)}
                placeholder={t("searchPeople")}
                className="h-8 pl-7 text-sm"
              />
            </div>
            {searchNeedle && pool.length === 0 && (
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
              {!pool.length && <p className="text-xs text-[#52525B]">{t("poolEmpty")}</p>}
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
              const filled = taskHeadcount(task);
              const target = task.size > 0 ? task.size : 0;
              const sizeOver = target > 0 && filled > target;
              const sizeUnder = target > 0 && filled < target;
              const sizeOk = target > 0 && filled === target;
              return (
                <div
                  key={task.id}
                  className={cn(
                    "min-w-0 rounded-md border bg-[#0C0C0E] p-2.5",
                    dragOver === task.id || dragOver?.startsWith(`${task.id}:`)
                      ? "border-[#2DD4BF]"
                      : "border-[#27272A]",
                    task.blocker && !task.done && "border-[#EF4444]/50"
                  )}
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

                  <div className="mb-2 flex items-center gap-3 text-[10px] text-[#A1A1AA]">
                    <label className="inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={task.done}
                        onChange={(e) => patchTask(task.id, { done: e.target.checked })}
                      />
                      {t("markDone")}
                    </label>
                    <label className="inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={task.blocker}
                        onChange={(e) => patchTask(task.id, { blocker: e.target.checked })}
                      />
                      {t("blocker")}
                    </label>
                  </div>

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
                        onDragStart={setDraggingId}
                        onSelect={toggleSelectPerson}
                      />
                    ))}
                    {!workers.length && (
                      <p className="px-1 py-1 text-xs text-[#52525B]">{t("dropWorkers")}</p>
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
