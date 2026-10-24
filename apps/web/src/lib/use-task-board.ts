"use client";

import { DragEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { cachedGet, invalidateApiCache, peekApiCache, setApiCache } from "@/lib/api-cache";
import { useToast } from "@/components/toast";
import type { TaskNote } from "@/components/teams/task-notes";
import {
  LEAD_CATEGORIES,
  normalizeTask,
  supervisedCounts,
  type Board,
  type Category,
  type Person,
  type Project,
  type Task,
} from "@/lib/staffing";

const PEOPLE_PATH = "/workforce/people";
const BOARD_PATH = "/workforce/board";
const NOTES_PATH = "/workforce/board/notes";

type PeoplePayload = { people: Person[]; positions: string[] };

function stripPersonFromTasks(tasks: Task[], personId: string): Task[] {
  return tasks.map((task) => {
    const leadGone = task.lead_id === personId;
    return {
      ...task,
      lead_id: leadGone ? null : task.lead_id,
      lead_counts: leadGone ? false : task.lead_counts,
      worker_ids: task.worker_ids.filter((id) => id !== personId),
    };
  });
}

function normalizeBoard(boardRes: Board): Board {
  return {
    tasks: (boardRes.tasks || []).map((task) => {
      const normalized = normalizeTask({ ...task, requirements: {} });
      return {
        ...normalized,
        requirements: {},
        size: typeof task.size === "number" && task.size > 0 ? task.size : normalized.size,
      };
    }),
    updated_at: boardRes.updated_at,
  };
}

function patchCachedPeople(updater: (people: Person[]) => Person[]): void {
  const hit = peekApiCache<PeoplePayload>(PEOPLE_PATH);
  if (!hit) return;
  setApiCache(PEOPLE_PATH, { ...hit, people: updater(hit.people || []) });
}

/** Headcount: workers, plus lead when ``lead_counts`` (lead may be in worker_ids). */
export function taskHeadcount(task: Pick<Task, "worker_ids" | "lead_id" | "lead_counts">) {
  const n = task.worker_ids.length;
  if (task.lead_counts && task.lead_id && !task.worker_ids.includes(task.lead_id)) {
    return n + 1;
  }
  return n;
}

export function useTaskBoard(options?: {
  locale?: string;
  fallbackError?: string;
  autoLoad?: boolean;
  /** When false, skip GET /workforce/board/notes (Organisation does not need them). */
  loadNotes?: boolean;
  /** Toast message when optimistic category/roster save fails. */
  saveFailedMessage?: string;
}) {
  const fallbackError = options?.fallbackError || "Failed to load";
  const saveFailedMessage = options?.saveFailedMessage || fallbackError;
  const locale = options?.locale || "hu";
  const autoLoad = options?.autoLoad !== false;
  const loadNotes = options?.loadNotes !== false;
  const toast = useToast();

  const [people, setPeople] = useState<Person[]>(() => peekApiCache<PeoplePayload>(PEOPLE_PATH)?.people || []);
  const [positions, setPositions] = useState<string[]>(
    () => peekApiCache<PeoplePayload>(PEOPLE_PATH)?.positions || []
  );
  const [board, setBoard] = useState<Board>(() => {
    const hit = peekApiCache<Board>(BOARD_PATH);
    return hit ? normalizeBoard(hit) : { tasks: [] };
  });
  const [notes, setNotes] = useState<Record<string, TaskNote[]>>({});
  const [loading, setLoading] = useState(() => !peekApiCache(PEOPLE_PATH) && !peekApiCache(BOARD_PATH));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [needUpload, setNeedUpload] = useState(false);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const warm = Boolean(peekApiCache(PEOPLE_PATH) || peekApiCache(BOARD_PATH));
    if (!warm) setLoading(true);
    setError("");
    setNeedUpload(false);
    try {
      const peopleReq = cachedGet(PEOPLE_PATH, () => api.get<PeoplePayload>(PEOPLE_PATH));
      const boardReq = cachedGet(BOARD_PATH, () => api.get<Board>(BOARD_PATH));
      const notesReq = loadNotes
        ? cachedGet(NOTES_PATH, () =>
            api.get<Record<string, TaskNote[]>>(NOTES_PATH).catch(() => ({} as Record<string, TaskNote[]>))
          )
        : Promise.resolve({} as Record<string, TaskNote[]>);
      const [peopleRes, boardRes, notesRes] = await Promise.all([peopleReq, boardReq, notesReq]);
      setNotes(notesRes || {});
      setPeople(peopleRes.people || []);
      setPositions(peopleRes.positions || []);
      setBoard(normalizeBoard(boardRes));
    } catch (err) {
      const msg = err instanceof Error ? err.message : fallbackError;
      if (/workforce|upload|404/i.test(msg) || msg.toLowerCase().includes("no workforce")) {
        setNeedUpload(true);
        setPeople([]);
        setPositions([]);
        invalidateApiCache(PEOPLE_PATH);
        invalidateApiCache(BOARD_PATH);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [fallbackError, loadNotes]);

  useEffect(() => {
    if (autoLoad) void load();
  }, [autoLoad, load]);

  useEffect(() => {
    if (!autoLoad || typeof window === "undefined") return;
    const onChanged = () => {
      invalidateApiCache(PEOPLE_PATH);
      invalidateApiCache(BOARD_PATH);
      invalidateApiCache(NOTES_PATH);
      void load();
    };
    window.addEventListener("dataset-changed", onChanged);
    return () => window.removeEventListener("dataset-changed", onChanged);
  }, [autoLoad, load]);

  const persist = useCallback(
    async (next: Board) => {
      setSaving(true);
      setError("");
      try {
        const payload = {
          tasks: next.tasks.map((task) => ({
            ...task,
            requirements: {},
            size: Math.max(0, Math.floor(Number(task.size) || 0)),
          })),
        };
        const saved = await api.put<Board>(BOARD_PATH, payload);
        const normalized = normalizeBoard(saved);
        setBoard(normalized);
        setApiCache(BOARD_PATH, saved);
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackError);
        invalidateApiCache(BOARD_PATH);
      } finally {
        setSaving(false);
      }
    },
    [fallbackError]
  );

  const peopleById = useMemo(() => {
    const map = new Map<string, Person>();
    for (const p of people) map.set(p.id, p);
    return map;
  }, [people]);

  const assignedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const task of board.tasks) {
      if (task.lead_id) ids.add(task.lead_id);
      for (const wid of task.worker_ids) ids.add(wid);
    }
    return ids;
  }, [board.tasks]);

  const watchByLead = useMemo(() => supervisedCounts(board.tasks), [board.tasks]);

  const leadOptions = useMemo(
    () => people.filter((p) => p.is_lead).sort((a, b) => a.name.localeCompare(b.name, locale)),
    [people, locale]
  );

  const commitBoard = useCallback(
    (tasks: Task[]) => {
      const next = { ...board, tasks };
      setBoard(next);
      setSelectedPersonId(null);
      void persist(next);
    },
    [board, persist]
  );

  const setTaskLead = useCallback(
    (taskId: string, leadId: string | null) => {
      // Leads may supervise several tasks; counting-as-worker resets until re-checked.
      commitBoard(
        board.tasks.map((task) => {
          if (task.id !== taskId) return task;
          const prevLead = task.lead_id;
          return {
            ...task,
            lead_id: leadId,
            lead_counts: false,
            worker_ids: task.worker_ids.filter((id) => id !== leadId && id !== prevLead),
          };
        })
      );
    },
    [board.tasks, commitBoard]
  );

  /** Count lead in this team's headcount and list them among workers (exclusive per lead). */
  const setLeadCounts = useCallback(
    (taskId: string, counts: boolean) => {
      const target = board.tasks.find((t) => t.id === taskId);
      const leadId = target?.lead_id || null;
      if (!leadId) return;
      commitBoard(
        board.tasks.map((task) => {
          if (task.id === taskId) {
            if (!counts) {
              return {
                ...task,
                lead_counts: false,
                worker_ids: task.worker_ids.filter((id) => id !== leadId),
              };
            }
            return {
              ...task,
              lead_counts: true,
              worker_ids: task.worker_ids.includes(leadId)
                ? task.worker_ids
                : [...task.worker_ids, leadId],
            };
          }
          if (counts && task.lead_id === leadId && task.lead_counts) {
            return {
              ...task,
              lead_counts: false,
              worker_ids: task.worker_ids.filter((id) => id !== leadId),
            };
          }
          return task;
        })
      );
    },
    [board.tasks, commitBoard]
  );

  const assignToTask = useCallback(
    (personId: string, taskId: string, role: "lead" | "worker" | "auto") => {
      const person = peopleById.get(personId);
      let resolved: "lead" | "worker" = role === "lead" || role === "worker" ? role : "worker";
      if (role === "auto") {
        resolved = person?.is_lead ? "lead" : "worker";
      }
      if (resolved === "lead") {
        setTaskLead(taskId, personId);
        return;
      }
      // A worker may sit on only one task; leads may still supervise several via lead_id.
      commitBoard(
        board.tasks.map((task) => {
          if (task.id === taskId) {
            if (task.worker_ids.includes(personId)) {
              return task;
            }
            return {
              ...task,
              worker_ids: [...task.worker_ids, personId],
            };
          }
          const nextWorkers = task.worker_ids.filter((id) => id !== personId);
          if (task.lead_id === personId && task.lead_counts) {
            return { ...task, lead_counts: false, worker_ids: nextWorkers };
          }
          return { ...task, worker_ids: nextWorkers };
        })
      );
    },
    [board.tasks, commitBoard, peopleById, setTaskLead]
  );

  const unassignPerson = useCallback(
    (personId: string) => {
      const next = { ...board, tasks: stripPersonFromTasks(board.tasks, personId) };
      setBoard(next);
      setSelectedPersonId(null);
      void persist(next);
    },
    [board, persist]
  );

  const patchTask = useCallback(
    (taskId: string, patch: Partial<Task>) => {
      const next = {
        ...board,
        tasks: board.tasks.map((task) => (task.id === taskId ? { ...task, ...patch } : task)),
      };
      setBoard(next);
      void persist(next);
    },
    [board, persist]
  );

  const removeTask = useCallback(
    (taskId: string) => {
      const next = { ...board, tasks: board.tasks.filter((task) => task.id !== taskId) };
      setBoard(next);
      void persist(next);
    },
    [board, persist]
  );

  const addTask = useCallback(
    (task: Task) => {
      const clean = {
        ...task,
        requirements: {},
        size: Math.max(0, Math.floor(Number(task.size) || 0)),
      };
      const next = { ...board, tasks: [...board.tasks, clean] };
      setBoard(next);
      void persist(next);
    },
    [board, persist]
  );

  const onDropPool = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragOver(null);
      const personId = e.dataTransfer.getData("text/person-id") || draggingId;
      setDraggingId(null);
      if (!personId) return;
      unassignPerson(personId);
    },
    [draggingId, unassignPerson]
  );

  const onDropTask = useCallback(
    (taskId: string, role: "lead" | "worker" | "auto") => {
      return (e: DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragOver(null);
        const personId = e.dataTransfer.getData("text/person-id") || draggingId;
        setDraggingId(null);
        if (!personId) return;
        assignToTask(personId, taskId, role);
      };
    },
    [assignToTask, draggingId]
  );

  const toggleSelectPerson = useCallback((personId: string) => {
    setSelectedPersonId((prev) => (prev === personId ? null : personId));
  }, []);

  const setCategory = useCallback(
    async (person: Person, category: Category | null) => {
      const prev = people.find((p) => p.id === person.id);
      if (!prev) return;
      const optimistic: Person = {
        ...prev,
        category,
        category_source: category ? "manual" : prev.category_source,
        is_lead: category ? LEAD_CATEGORIES.has(category) : prev.is_lead,
      };
      setPeople((list) => list.map((p) => (p.id === person.id ? optimistic : p)));
      patchCachedPeople((list) => list.map((p) => (p.id === person.id ? optimistic : p)));
      try {
        const res = await api.put<Pick<Person, "category" | "category_source">>("/workforce/people/category", {
          name: person.name,
          category,
        });
        setPeople((list) =>
          list.map((p) =>
            p.id === person.id
              ? {
                  ...p,
                  ...res,
                  is_lead: res.category ? LEAD_CATEGORIES.has(res.category) : p.is_lead,
                }
              : p
          )
        );
        patchCachedPeople((list) =>
          list.map((p) =>
            p.id === person.id
              ? {
                  ...p,
                  ...res,
                  is_lead: res.category ? LEAD_CATEGORIES.has(res.category) : p.is_lead,
                }
              : p
          )
        );
      } catch {
        setPeople((list) => list.map((p) => (p.id === person.id ? prev : p)));
        patchCachedPeople((list) => list.map((p) => (p.id === person.id ? prev : p)));
        toast.error(saveFailedMessage);
      }
    },
    [people, saveFailedMessage, toast]
  );

  const setRoster = useCallback(
    async (person: Person, patch: { afternoon: boolean; project: Project | null }) => {
      const prev = people.find((p) => p.id === person.id);
      if (!prev) return;
      const optimistic: Person = {
        ...prev,
        afternoon: patch.afternoon,
        project: patch.project,
      };
      setPeople((list) => list.map((p) => (p.id === person.id ? optimistic : p)));
      patchCachedPeople((list) => list.map((p) => (p.id === person.id ? optimistic : p)));
      try {
        const res = await api.put<{ afternoon: boolean; project: string | null }>("/workforce/people/roster", {
          name: person.name,
          afternoon: patch.afternoon,
          project: patch.project,
        });
        const next: Person = {
          ...optimistic,
          afternoon: Boolean(res.afternoon),
          project: (res.project as Project | null) || null,
        };
        setPeople((list) => list.map((p) => (p.id === person.id ? next : p)));
        patchCachedPeople((list) => list.map((p) => (p.id === person.id ? next : p)));
      } catch {
        setPeople((list) => list.map((p) => (p.id === person.id ? prev : p)));
        patchCachedPeople((list) => list.map((p) => (p.id === person.id ? prev : p)));
        toast.error(saveFailedMessage);
      }
    },
    [people, saveFailedMessage, toast]
  );

  const addNote = useCallback(
    async (taskId: string, text: string) => {
      try {
        const note = await api.post<TaskNote>(`/workforce/tasks/${encodeURIComponent(taskId)}/notes`, {
          text,
        });
        setNotes((prev) => ({ ...prev, [taskId]: [note, ...(prev[taskId] || [])] }));
        invalidateApiCache(NOTES_PATH);
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackError);
        throw err;
      }
    },
    [fallbackError]
  );

  const deleteNote = useCallback(
    async (note: TaskNote) => {
      try {
        await api.del(`/workforce/tasks/notes/${note.id}`);
        setNotes((prev) => ({
          ...prev,
          [note.task_id]: (prev[note.task_id] || []).filter((n) => n.id !== note.id),
        }));
        invalidateApiCache(NOTES_PATH);
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackError);
      }
    },
    [fallbackError]
  );

  const selectedPerson = selectedPersonId ? peopleById.get(selectedPersonId) : undefined;

  return {
    people,
    setPeople,
    positions,
    setPositions,
    board,
    setBoard,
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
    setSelectedPersonId,
    selectedPerson,
    peopleById,
    assignedIds,
    watchByLead,
    leadOptions,
    load,
    persist,
    patchTask,
    removeTask,
    setTaskLead,
    setLeadCounts,
    assignToTask,
    unassignPerson,
    addTask,
    onDropPool,
    onDropTask,
    toggleSelectPerson,
    setCategory,
    setRoster,
    addNote,
    deleteNote,
  };
}
