"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Info, Search } from "lucide-react";
import { Link } from "@/i18n/routing";
import { isStaff, useMe } from "@/components/auth-gate";
import { CategorySelect, useCategoryLabel } from "@/components/category-select";
import { ClassificationPanel } from "@/components/teams/classification-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";
import { useTaskBoard } from "@/lib/use-task-board";
import {
  CATEGORIES,
  PROJECTS,
  formatShortRange,
  isProject,
  leaveOverlapsNextWeek,
  personLeaveRanges,
  type Category,
  type Person,
  type Project,
  type Task,
} from "@/lib/staffing";

type PersonAssignment = { taskId: string; title: string; role: "lead" | "worker" };

type StatusFilter = "all" | "available" | "leaveNow" | "leaveNextWeek";
type ShiftFilter = "all" | "afternoon" | "day";
type AssignmentFilter = "all" | "free" | "assigned";

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

const ASSIGNMENT_FILTERS: { key: AssignmentFilter; label: string }[] = [
  { key: "all", label: "assignAll" },
  { key: "free", label: "assignFree" },
  { key: "assigned", label: "assignBusy" },
];

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function PersonCard({
  person,
  assignments,
  tasks,
  canEdit,
  busy = false,
  onCategory,
  onRoster,
  onAssign,
  onUnassign,
}: {
  person: Person;
  assignments: PersonAssignment[];
  tasks: Task[];
  canEdit: boolean;
  busy?: boolean;
  onCategory: (person: Person, category: Category | null) => void;
  onRoster: (person: Person, patch: { afternoon: boolean; project: Project | null }) => void;
  onAssign: (person: Person, taskId: string, role: "lead" | "worker") => void;
  onUnassign: (person: Person) => void;
}) {
  const t = useTranslations("organisation");
  const tt = useTranslations("teams");
  const categoryLabel = useCategoryLabel();
  const afternoon = Boolean(person.afternoon);
  const project = person.project && isProject(person.project) ? person.project : null;
  const onLeaveNow = Boolean(person.on_leave);
  const nextWeek = leaveOverlapsNextWeek(person);
  const leave = personLeaveRanges(person)[0];
  const assigned = assignments.length > 0;
  const primaryTaskId = assignments[0]?.taskId || "";
  const openTasks = tasks.filter((task) => !task.done);

  function handleAssignChange(value: string) {
    if (!value) {
      onUnassign(person);
      return;
    }
    const role: "lead" | "worker" = person.is_lead ? "lead" : "worker";
    onAssign(person, value, role);
  }

  const statusChips = (
    <div className="flex flex-wrap items-center gap-1">
      {assigned ? (
        assignments.map((a) => (
          <Link
            key={`${a.taskId}-${a.role}`}
            href={`/tasks/${encodeURIComponent(a.taskId)}`}
            className="max-w-[10rem] truncate rounded bg-[#2DD4BF]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[#5EEAD4] hover:bg-[#2DD4BF]/25"
            title={a.title}
          >
            {a.title}
            {a.role === "lead" ? ` · ${t("asLead")}` : ""}
          </Link>
        ))
      ) : (
        <span className="rounded bg-[#27272A] px-1.5 py-0.5 text-[10px] font-semibold text-[#A1A1AA]">
          {t("free")}
        </span>
      )}
      {onLeaveNow ? (
        <span className="rounded bg-[#52525B] px-1.5 py-0.5 text-[10px] font-bold uppercase text-[#E4E4E7]">
          {tt("leaveNow")}
        </span>
      ) : null}
      {nextWeek && !onLeaveNow ? (
        <span className="rounded bg-[#F97316] px-1.5 py-0.5 text-[10px] font-bold uppercase text-black">
          {tt("leaveNextWeek")}
        </span>
      ) : null}
      {afternoon ? (
        <span className="rounded bg-[#7C3AED]/25 px-1.5 py-0.5 text-[10px] font-semibold text-[#C4B5FD] md:hidden">
          {tt("shiftAfternoonShort")}
        </span>
      ) : null}
      {project ? (
        <span className="rounded bg-[#0E7490]/30 px-1.5 py-0.5 text-[10px] font-semibold text-[#67E8F9] md:hidden">
          {project}
        </span>
      ) : null}
    </div>
  );

  const assignControl = canEdit ? (
    <div className="min-w-0 md:w-44 md:shrink-0 lg:w-52">
      <label className="sr-only" htmlFor={`assign-${person.id}`}>
        {t("assignToTask")}
      </label>
      <select
        id={`assign-${person.id}`}
        value={primaryTaskId}
        disabled={busy || openTasks.length === 0}
        onChange={(e) => handleAssignChange(e.target.value)}
        className="h-8 w-full rounded-md border border-[#3F3F46] bg-[#0C0C0E] px-2 text-xs text-[#E4E4E7] disabled:opacity-50"
      >
        <option value="">{assigned ? t("unassign") : t("assignToTask")}</option>
        {openTasks.map((task) => (
          <option key={task.id} value={task.id}>
            {task.title}
            {task.lead_id === person.id
              ? ` · ${t("asLead")}`
              : task.worker_ids.includes(person.id)
                ? ` · ${t("asWorker")}`
                : person.is_lead
                  ? ` · ${t("asLead")}`
                  : ""}
          </option>
        ))}
      </select>
      {assignments.length > 1 ? (
        <p className="mt-0.5 truncate text-[10px] text-[#A1A1AA] md:hidden">
          {t("alsoOn", {
            titles: assignments
              .slice(1)
              .map((a) => a.title)
              .join(", "),
          })}
        </p>
      ) : null}
    </div>
  ) : null;

  const rosterControls = canEdit ? (
    <div className="flex flex-wrap items-center gap-2 md:flex-nowrap md:shrink-0">
      <CategorySelect
        person={person}
        disabled={busy}
        onChange={(category) => onCategory(person, category)}
        className="w-full md:w-40 lg:w-48"
      />
      <label className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-[#A1A1AA]">
        <input
          type="checkbox"
          className="h-3.5 w-3.5 accent-[#7C3AED]"
          checked={afternoon}
          disabled={busy}
          onChange={(e) => onRoster(person, { afternoon: e.target.checked, project })}
        />
        <span className="md:hidden">{tt("shiftAfternoon")}</span>
        <span className="hidden md:inline">{tt("shiftAfternoonShort")}</span>
      </label>
      <select
        value={project || ""}
        disabled={busy}
        onChange={(e) =>
          onRoster(person, {
            afternoon,
            project: isProject(e.target.value) ? e.target.value : null,
          })
        }
        className="h-8 w-full rounded-md border border-[#3F3F46] bg-[#0C0C0E] px-2 text-xs text-[#E4E4E7] md:w-28"
        aria-label={tt("filterProject")}
      >
        <option value="">{tt("projectNone")}</option>
        {PROJECTS.map((code) => (
          <option key={code} value={code}>
            {code}
          </option>
        ))}
      </select>
    </div>
  ) : null;

  const detailsLink = (
    <Link
      href={`/workers/${encodeURIComponent(person.id)}`}
      className="inline-flex shrink-0 items-center gap-0.5 rounded px-1.5 py-0.5 text-[11px] text-[#71717A] hover:bg-[#27272A] hover:text-[#5EEAD4]"
    >
      <Info className="h-3 w-3" />
      <span className="md:sr-only lg:not-sr-only">{tt("details")}</span>
    </Link>
  );

  return (
    <article
      className={cn(
        "rounded-md border border-[#27272A] bg-[#18181B]",
        // Mobile: stacked card. Desktop (md+): one compact horizontal strip.
        "flex flex-col gap-2 p-3 md:flex-row md:items-center md:gap-3 md:px-3 md:py-2",
        onLeaveNow && "opacity-60",
        person.is_lead && "border-[#F59E0B]/40"
      )}
    >
      <div className="flex min-w-0 items-start justify-between gap-2 md:w-48 md:shrink-0 lg:w-56">
        <div className="min-w-0">
          <h3 className="truncate font-medium text-[#FAFAFA] md:text-sm">{person.name}</h3>
          <p className="truncate text-xs text-[#A1A1AA]">
            {person.category ? categoryLabel(person.category) : person.position || "—"}
          </p>
          {leave ? (
            <p className="mt-0.5 truncate text-[10px] text-[#A1A1AA]">
              {tt("leaveSoon")} {formatShortRange(leave)}
            </p>
          ) : null}
        </div>
        <div className="md:hidden">{detailsLink}</div>
      </div>

      <div className="min-w-0 md:flex-1">{statusChips}</div>

      {assignControl}
      {rosterControls}
      <div className="hidden md:block">{detailsLink}</div>
    </article>
  );
}

export default function OrganisationPage() {
  const t = useTranslations("organisation");
  const tt = useTranslations("teams");
  const tc = useTranslations("common");
  const categoryLabel = useCategoryLabel();
  const locale = useLocale();
  const me = useMe();
  const staff = isStaff(me);

  const {
    people,
    board,
    loading,
    error,
    needUpload,
    assignedIds,
    load,
    setCategory,
    setRoster,
    assignToTask,
    unassignPerson,
  } = useTaskBoard({
    locale,
    fallbackError: tc("loadFailed"),
    loadNotes: false,
    saveFailedMessage: tc("saveFailed"),
  });

  const assignmentsByPerson = useMemo(() => {
    const map = new Map<string, PersonAssignment[]>();
    for (const task of board.tasks) {
      if (task.done) continue;
      if (task.lead_id) {
        const list = map.get(task.lead_id) || [];
        list.push({ taskId: task.id, title: task.title, role: "lead" });
        map.set(task.lead_id, list);
      }
      for (const wid of task.worker_ids) {
        const list = map.get(wid) || [];
        list.push({ taskId: task.id, title: task.title, role: "worker" });
        map.set(wid, list);
      }
    }
    return map;
  }, [board.tasks]);

  const [personSearch, setPersonSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [shiftFilter, setShiftFilter] = useState<ShiftFilter>("all");
  const [projectFilter, setProjectFilter] = useState<Set<Project | "none">>(new Set());
  const [categoryFilter, setCategoryFilter] = useState<Set<Category | "none">>(new Set());
  const [assignmentFilter, setAssignmentFilter] = useState<AssignmentFilter>("all");

  function toggleProjectFilter(value: Project | "none") {
    setProjectFilter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function toggleCategoryFilter(value: Category | "none") {
    setCategoryFilter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  const filtered = useMemo(() => {
    const needle = normalizeSearch(personSearch);
    return people.filter((p) => {
      if (statusFilter === "available" && p.on_leave) return false;
      if (statusFilter === "leaveNow" && !p.on_leave) return false;
      if (statusFilter === "leaveNextWeek" && !leaveOverlapsNextWeek(p)) return false;
      if (shiftFilter === "afternoon" && !p.afternoon) return false;
      if (shiftFilter === "day" && p.afternoon) return false;
      if (projectFilter.size) {
        if (!p.project) {
          if (!projectFilter.has("none")) return false;
        } else if (!projectFilter.has(p.project)) {
          return false;
        }
      }
      if (categoryFilter.size) {
        if (!p.category) {
          if (!categoryFilter.has("none")) return false;
        } else if (!categoryFilter.has(p.category)) {
          return false;
        }
      }
      if (assignmentFilter === "free" && assignedIds.has(p.id)) return false;
      if (assignmentFilter === "assigned" && !assignedIds.has(p.id)) return false;
      if (
        needle &&
        !normalizeSearch(p.name).includes(needle) &&
        !normalizeSearch(p.position || "").includes(needle)
      ) {
        return false;
      }
      return true;
    });
  }, [
    people,
    personSearch,
    statusFilter,
    shiftFilter,
    projectFilter,
    categoryFilter,
    assignmentFilter,
    assignedIds,
  ]);

  const groups = useMemo(() => {
    const byCat = new Map<Category | "none", Person[]>();
    for (const cat of CATEGORIES) byCat.set(cat, []);
    byCat.set("none", []);
    for (const person of filtered) {
      const key =
        person.category && (CATEGORIES as readonly string[]).includes(person.category)
          ? person.category
          : "none";
      byCat.get(key)!.push(person);
    }
    for (const list of byCat.values()) {
      list.sort((a, b) => a.name.localeCompare(b.name, locale));
    }
    return [
      ...CATEGORIES.map((cat) => ({ key: cat as Category | "none", people: byCat.get(cat)! })),
      { key: "none" as const, people: byCat.get("none")! },
    ].filter((g) => g.people.length > 0);
  }, [filtered, locale]);

  const unclassifiedCount = people.filter((p) => !p.category).length;

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-[#71717A]">{t("subtitle")}</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          {tc("refresh")}
        </Button>
      </div>

      {needUpload && (
        <div className="mb-4 rounded-md border border-[#F97316]/40 bg-[#F97316]/10 p-4 text-sm text-[#FDBA74]">
          {tt("needUpload")}{" "}
          <Link href="/workforce" className="underline underline-offset-2">
            {tt("goWorkforce")}
          </Link>
        </div>
      )}
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {!needUpload && staff && people.length > 0 && unclassifiedCount > 0 && (
        <ClassificationPanel people={people} onSet={(p, c) => void setCategory(p, c)} />
      )}

      {!needUpload && (
        <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <div className="relative mb-3 max-w-md">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#71717A]" />
            <Input
              type="search"
              value={personSearch}
              onChange={(e) => setPersonSearch(e.target.value)}
              placeholder={tt("searchPeople")}
              className="h-8 pl-7 text-sm"
            />
          </div>

          <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{tt("filterStatus")}</p>
          <div className="mb-3 flex flex-wrap gap-1" role="radiogroup" aria-label={tt("filterStatus")}>
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
                    ? "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                    : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                )}
              >
                {tt(item.label)}
              </button>
            ))}
          </div>

          <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{tt("filterShift")}</p>
          <div className="mb-3 flex flex-wrap gap-1" role="radiogroup" aria-label={tt("filterShift")}>
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
                {tt(item.label)}
              </button>
            ))}
          </div>

          <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{tt("filterProject")}</p>
          <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label={tt("filterProject")}>
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
              {tt("projectNone")}
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

          <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{t("filterCategory")}</p>
          <div className="mb-3 flex flex-wrap gap-1" role="group" aria-label={t("filterCategory")}>
            <button
              type="button"
              aria-pressed={categoryFilter.has("none")}
              onClick={() => toggleCategoryFilter("none")}
              className={cn(
                "rounded-md border px-2 py-0.5 text-[11px]",
                categoryFilter.has("none")
                  ? "border-[#F59E0B]/60 bg-[#F59E0B]/15 text-[#FCD34D]"
                  : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
              )}
            >
              {t("uncategorized")}
            </button>
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                aria-pressed={categoryFilter.has(cat)}
                onClick={() => toggleCategoryFilter(cat)}
                className={cn(
                  "rounded-md border px-2 py-0.5 text-[11px]",
                  categoryFilter.has(cat)
                    ? "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                    : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                )}
              >
                {categoryLabel(cat)}
              </button>
            ))}
          </div>

          <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{t("filterAssignment")}</p>
          <div className="flex flex-wrap gap-1" role="radiogroup" aria-label={t("filterAssignment")}>
            {ASSIGNMENT_FILTERS.map((item) => (
              <button
                key={item.key}
                type="button"
                role="radio"
                aria-checked={assignmentFilter === item.key}
                onClick={() => setAssignmentFilter(item.key)}
                className={cn(
                  "rounded-md border px-2 py-0.5 text-[11px]",
                  assignmentFilter === item.key
                    ? "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                    : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                )}
              >
                {t(item.label)}
              </button>
            ))}
          </div>
        </div>
      )}

      {!needUpload && (
        <p className="mb-3 text-xs text-[#71717A]">
          {t("showing", { shown: filtered.length, total: people.length })}
        </p>
      )}

      {!needUpload &&
        groups.map((group) => (
          <section key={group.key} className="mb-6">
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <h2 className="text-sm font-medium text-[#FAFAFA]">
                {group.key === "none" ? t("uncategorized") : categoryLabel(group.key)}
              </h2>
              <span className="text-xs text-[#71717A]">{group.people.length}</span>
            </div>
            <div className="flex flex-col gap-1.5 md:gap-1">
              {group.people.map((person) => (
                <PersonCard
                  key={person.id}
                  person={person}
                  assignments={assignmentsByPerson.get(person.id) || []}
                  tasks={board.tasks}
                  canEdit={staff}
                  onCategory={(p, c) => void setCategory(p, c)}
                  onRoster={(p, patch) => void setRoster(p, patch)}
                  onAssign={(p, taskId, role) => assignToTask(p.id, taskId, role)}
                  onUnassign={(p) => unassignPerson(p.id)}
                />
              ))}
            </div>
          </section>
        ))}

      {!needUpload && !loading && filtered.length === 0 && (
        <p className="text-sm text-[#71717A]">{t("empty")}</p>
      )}
    </div>
  );
}
