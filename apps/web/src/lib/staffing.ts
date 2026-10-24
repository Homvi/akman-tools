export type LeaveRange = { start: string; end: string };

export type Person = {
  id: string;
  name: string;
  position: string;
  is_lead: boolean;
  available?: boolean;
  on_leave?: boolean;
  leave_start?: string | null;
  leave_end?: string | null;
  leave_ranges?: LeaveRange[];
  last_present?: string | null;
};

export type Task = {
  id: string;
  title: string;
  size: number;
  lead_id: string | null;
  worker_ids: string[];
  blocker: boolean;
  blocker_note: string;
  done: boolean;
  start_date: string | null;
  end_date: string | null;
  order: number;
};

export type Board = {
  tasks: Task[];
  updated_at?: string | null;
};

export function newId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function normalizeTask(task: Partial<Task> & { title: string }): Task {
  return {
    id: task.id || newId("task"),
    title: task.title,
    size: typeof task.size === "number" && task.size > 0 ? task.size : Number(task.size) || 0,
    lead_id: task.lead_id || null,
    worker_ids: Array.isArray(task.worker_ids) ? task.worker_ids.filter(Boolean) : [],
    blocker: Boolean(task.blocker),
    blocker_note: typeof task.blocker_note === "string" ? task.blocker_note : "",
    done: Boolean(task.done),
    start_date: task.start_date || null,
    end_date: task.end_date || task.start_date || null,
    order: typeof task.order === "number" ? task.order : 0,
  };
}

/** Noon local time avoids DST shifting the calendar day. */
export function parseIsoDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(`${value.slice(0, 10)}T12:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(d: Date, days: number): Date {
  const next = new Date(d);
  next.setDate(next.getDate() + days);
  return next;
}

export function startOfDay(d: Date): Date {
  const next = new Date(d);
  next.setHours(12, 0, 0, 0);
  return next;
}

export function daysBetween(a: Date, b: Date): number {
  return Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / 86_400_000);
}

export function startOfWeek(d: Date): Date {
  const base = startOfDay(d);
  const dow = (base.getDay() + 6) % 7; // Monday = 0
  return addDays(base, -dow);
}

/** Next calendar week Mon–Sun relative to `today`. */
export function nextWeekRange(today = new Date()): { start: Date; end: Date } {
  const start = addDays(startOfWeek(today), 7);
  return { start, end: addDays(start, 6) };
}

export function personLeaveRanges(person: Person): LeaveRange[] {
  if (person.leave_ranges?.length) return person.leave_ranges;
  if (person.leave_start) {
    return [{ start: person.leave_start, end: person.leave_end || person.leave_start }];
  }
  return [];
}

/** First leave block of `person` overlapping [start, end], if any. */
export function leaveInRange(person: Person, start: Date, end: Date): LeaveRange | null {
  for (const range of personLeaveRanges(person)) {
    const from = parseIsoDate(range.start);
    const to = parseIsoDate(range.end) || from;
    if (from && to && from <= end && to >= start) return range;
  }
  return null;
}

export function taskRange(task: Pick<Task, "start_date" | "end_date">): { start: Date; end: Date } | null {
  const start = parseIsoDate(task.start_date);
  if (!start) return null;
  const end = parseIsoDate(task.end_date) || start;
  return { start, end };
}

export function taskLeaveConflict(person: Person, task: Task): LeaveRange | null {
  const range = taskRange(task);
  return range ? leaveInRange(person, range.start, range.end) : null;
}

export function leaveOverlapsNextWeek(person: Person, today = new Date()): boolean {
  const { start, end } = nextWeekRange(today);
  return leaveInRange(person, start, end) !== null;
}

export function formatShortRange(range: LeaveRange): string {
  const start = range.start.slice(5).replace("-", ".");
  if (!range.end || range.end === range.start) return start;
  return `${start}–${range.end.slice(5).replace("-", ".")}`;
}

export function taskMembers(task: Task, peopleById: Map<string, Person>): Person[] {
  const ids = [task.lead_id, ...task.worker_ids].filter((id): id is string => Boolean(id));
  return ids.map((id) => peopleById.get(id)).filter((p): p is Person => Boolean(p));
}
