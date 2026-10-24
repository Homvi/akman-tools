export type LeaveRange = { start: string; end: string };

export const CATEGORIES = [
  "cable_puller",
  "electrician",
  "long_distance_lead",
  "local_cabling_lead",
  "electrician_lead",
] as const;
export type Category = (typeof CATEGORIES)[number];
export const LEAD_CATEGORIES: ReadonlySet<Category> = new Set([
  "long_distance_lead",
  "local_cabling_lead",
  "electrician_lead",
]);
export type Requirements = Partial<Record<Category, number>>;
export const DEFAULT_REQUIREMENTS: Requirements = { long_distance_lead: 1, cable_puller: 2 };

export function isCategory(value: unknown): value is Category {
  return typeof value === "string" && (CATEGORIES as readonly string[]).includes(value);
}

export type Person = {
  id: string;
  name: string;
  position: string;
  is_lead: boolean;
  category?: Category | null;
  category_source?: "manual" | "auto" | null;
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
  requirements: Requirements;
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

export function normalizeRequirements(raw: unknown): Requirements {
  const out: Requirements = {};
  if (!raw || typeof raw !== "object") return out;
  for (const cat of CATEGORIES) {
    const n = Math.max(0, Math.min(99, Math.floor(Number((raw as Record<string, unknown>)[cat]) || 0)));
    if (n) out[cat] = n;
  }
  return out;
}

export function requirementsTotal(req: Requirements): number {
  return CATEGORIES.reduce((sum, cat) => sum + (req[cat] || 0), 0);
}

export function normalizeTask(task: Partial<Task> & { title: string }): Task {
  const requirements = normalizeRequirements(task.requirements);
  const total = requirementsTotal(requirements);
  return {
    id: task.id || newId("task"),
    title: task.title,
    size: total || (typeof task.size === "number" && task.size > 0 ? task.size : Number(task.size) || 0),
    requirements,
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

/** Assigned members per category on one task. */
export function taskCategoryCounts(task: Task, peopleById: Map<string, Person>): Requirements {
  const out: Requirements = {};
  for (const p of taskMembers(task, peopleById)) {
    if (p.category) out[p.category] = (out[p.category] || 0) + 1;
  }
  return out;
}

/** Members whose category is not requested by the task (or have no category at all). */
export function membersOutsideRequirements(task: Task, peopleById: Map<string, Person>): Set<string> {
  const out = new Set<string>();
  if (!requirementsTotal(task.requirements)) return out;
  for (const p of taskMembers(task, peopleById)) {
    if (!p.category || !task.requirements[p.category]) out.add(p.id);
  }
  return out;
}

export type CategorySummary = {
  category: Category;
  needed: number;
  assigned: number;
  roster: number;
  onLeaveNow: number;
  leaveNextWeek: number;
  short: boolean;
};

/** Mirrors `requirements_summary` in src/staffing_categories.py. */
export function requirementsSummary(tasks: Task[], people: Person[], today = new Date()): CategorySummary[] {
  const byId = new Map(people.map((p) => [p.id, p]));
  const open = tasks.filter((t) => !t.done);
  return CATEGORIES.map((category) => {
    const roster = people.filter((p) => p.category === category);
    const needed = open.reduce((sum, t) => sum + (t.requirements[category] || 0), 0);
    const assigned = open.reduce((sum, t) => sum + (taskCategoryCounts(t, byId)[category] || 0), 0);
    return {
      category,
      needed,
      assigned,
      roster: roster.length,
      onLeaveNow: roster.filter((p) => p.on_leave).length,
      leaveNextWeek: roster.filter((p) => leaveOverlapsNextWeek(p, today)).length,
      short: needed > roster.length,
    };
  });
}
