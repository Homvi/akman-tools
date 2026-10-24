"use client";

import { DragEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
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

function stripPersonFromTasks(tasks: Task[], personId: string): Task[] {
  return tasks.map((task) => ({
    ...task,
    lead_id: task.lead_id === personId ? null : task.lead_id,
    worker_ids: task.worker_ids.filter((id) => id !== personId),
  }));
}

/** Workers only — the group lead is not part of the task headcount. */
export function taskHeadcount(task: Pick<Task, "worker_ids">) {
  return task.worker_ids.length;
}

export function useTaskBoard(options?: {
  locale?: string;
  fallbackError?: string;
  autoLoad?: boolean;
}) {
  const fallbackError = options?.fallbackError || "Failed to load";
  const locale = options?.locale || "hu";
  const autoLoad = options?.autoLoad !== false;

  const [people, setPeople] = useState<Person[]>([]);
  const [positions, setPositions] = useState<string[]>([]);
  const [board, setBoard] = useState<Board>({ tasks: [] });
  const [notes, setNotes] = useState<Record<string, TaskNote[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [needUpload, setNeedUpload] = useState(false);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setNeedUpload(false);
    try {
      const [peopleRes, boardRes, notesRes] = await Promise.all([
        api.get<{ people: Person[]; positions: string[] }>("/workforce/people"),
        api.get<Board>("/workforce/board"),
        api.get<Record<string, TaskNote[]>>("/workforce/board/notes").catch(() => ({})),
      ]);
      setNotes(notesRes || {});
      setPeople(peopleRes.people || []);
      setPositions(peopleRes.positions || []);
      setBoard({
        tasks: (boardRes.tasks || []).map((task) => {
          const normalized = normalizeTask({ ...task, requirements: {} });
          // Keep worker target (`size`); drop category requirements.
          return {
            ...normalized,
            requirements: {},
            size: typeof task.size === "number" && task.size > 0 ? task.size : normalized.size,
          };
        }),
        updated_at: boardRes.updated_at,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : fallbackError;
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
  }, [fallbackError]);

  useEffect(() => {
    if (autoLoad) void load();
  }, [autoLoad, load]);

  useEffect(() => {
    if (!autoLoad || typeof window === "undefined") return;
    const onChanged = () => {
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
      const saved = await api.put<Board>("/workforce/board", payload);
      setBoard({
        tasks: (saved.tasks || []).map((task) => {
          const normalized = normalizeTask({ ...task, requirements: {} });
          return {
            ...normalized,
            requirements: {},
            size: typeof task.size === "number" && task.size > 0 ? task.size : normalized.size,
          };
        }),
        updated_at: saved.updated_at,
      });
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackError);
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
      // Leads may supervise several tasks; only clear worker slot on *this* task.
      commitBoard(
        board.tasks.map((task) => {
          if (task.id !== taskId) return task;
          return {
            ...task,
            lead_id: leadId,
            worker_ids: leadId ? task.worker_ids.filter((id) => id !== leadId) : task.worker_ids,
          };
        })
      );
    },
    [board.tasks, commitBoard]
  );

  const assignToTask = useCallback(
    (personId: string, taskId: string, role: "lead" | "worker" | "auto") => {
      let resolved: "lead" | "worker" = role === "lead" || role === "worker" ? role : "worker";
      if (role === "auto") {
        resolved = peopleById.get(personId)?.is_lead ? "lead" : "worker";
      }
      if (resolved === "lead") {
        setTaskLead(taskId, personId);
        return;
      }
      // Workers (and leads dropped onto a worker slot) may sit on multiple tasks.
      commitBoard(
        board.tasks.map((task) => {
          if (task.id !== taskId) return task;
          if (task.lead_id === personId || task.worker_ids.includes(personId)) {
            return task;
          }
          return {
            ...task,
            worker_ids: [...task.worker_ids, personId],
          };
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
      setSaving(true);
      setError("");
      try {
        const res = await api.put<Pick<Person, "category" | "category_source">>("/workforce/people/category", {
          name: person.name,
          category,
        });
        setPeople((prev) =>
          prev.map((p) =>
            p.id === person.id
              ? { ...p, ...res, is_lead: res.category ? LEAD_CATEGORIES.has(res.category) : p.is_lead }
              : p
          )
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackError);
      } finally {
        setSaving(false);
      }
    },
    [fallbackError]
  );

  const setRoster = useCallback(
    async (person: Person, patch: { afternoon: boolean; project: Project | null }) => {
      setSaving(true);
      setError("");
      try {
        const res = await api.put<{ afternoon: boolean; project: string | null }>("/workforce/people/roster", {
          name: person.name,
          afternoon: patch.afternoon,
          project: patch.project,
        });
        setPeople((prev) =>
          prev.map((p) =>
            p.id === person.id
              ? {
                  ...p,
                  afternoon: Boolean(res.afternoon),
                  project: (res.project as Project | null) || null,
                }
              : p
          )
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackError);
      } finally {
        setSaving(false);
      }
    },
    [fallbackError]
  );

  const addNote = useCallback(
    async (taskId: string, text: string) => {
      try {
        const note = await api.post<TaskNote>(`/workforce/tasks/${encodeURIComponent(taskId)}/notes`, {
          text,
        });
        setNotes((prev) => ({ ...prev, [taskId]: [note, ...(prev[taskId] || [])] }));
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
