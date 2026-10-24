"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, ArrowLeft, Pencil, Search, Trash2 } from "lucide-react";
import { Link, useRouter } from "@/i18n/routing";
import { isStaff, useMe } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { DateRangePicker, formatRangeLabel } from "@/components/date-range-picker";
import { PersonChip } from "@/components/teams/person-chip";
import { TaskNotes } from "@/components/teams/task-notes";
import { cn } from "@/lib/utils";
import { taskHeadcount, useTaskBoard } from "@/lib/use-task-board";
import {
  PROJECTS,
  formatShortRange,
  personLeaveRanges,
  taskLeaveConflict,
  taskMembers,
  type LeaveRange,
  type Person,
  type Project,
} from "@/lib/staffing";

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = decodeURIComponent(String(params.taskId || ""));
  const t = useTranslations("teams");
  const tc = useTranslations("common");
  const td = useTranslations("datePicker");
  const locale = useLocale();
  const router = useRouter();
  const me = useMe();
  const staff = isStaff(me);
  const isAdmin = Boolean(me?.roles.includes("admin"));

  const {
    people,
    board,
    notes,
    loading,
    saving,
    error,
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
    patchTask,
    removeTask,
    setTaskLead,
    assignToTask,
    onDropPool,
    onDropTask,
    toggleSelectPerson,
    addNote,
    deleteNote,
  } = useTaskBoard({ locale, fallbackError: tc("loadFailed"), saveFailedMessage: tc("saveFailed") });

  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [personSearch, setPersonSearch] = useState("");
  const [noteDraft, setNoteDraft] = useState<string | undefined>(undefined);
  const [hideNow, setHideNow] = useState(false);
  const [projectFilter, setProjectFilter] = useState<Set<Project | "none">>(new Set());

  const task = useMemo(() => board.tasks.find((item) => item.id === taskId), [board.tasks, taskId]);

  useEffect(() => {
    if (!editingTitle && task) setTitleDraft(task.title);
  }, [task, editingTitle]);

  function toggleProjectFilter(value: Project | "none") {
    setProjectFilter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  const pool = useMemo(() => {
    const needle = normalizeSearch(personSearch);
    return people.filter((p) => {
      if (assignedIds.has(p.id)) return false;
      if (hideNow && p.on_leave) return false;
      if (projectFilter.size) {
        if (!p.project) {
          if (!projectFilter.has("none")) return false;
        } else if (!projectFilter.has(p.project)) {
          return false;
        }
      }
      if (
        needle &&
        !normalizeSearch(p.name).includes(needle) &&
        !normalizeSearch(p.position || "").includes(needle)
      ) {
        return false;
      }
      return true;
    });
  }, [people, assignedIds, personSearch, hideNow, projectFilter]);

  const poolLeads = pool.filter((p) => p.is_lead);
  const poolWorkers = pool.filter((p) => !p.is_lead);

  const backLink = (
    <Link href="/tasks" className="mb-4 inline-flex items-center gap-1 text-sm text-[#A1A1AA] hover:text-[#FAFAFA]">
      <ArrowLeft className="h-4 w-4" />
      {t("backToTasks")}
    </Link>
  );

  function conflictLabel(range: LeaveRange | null): string | null {
    return range ? t("conflictLeave", { range: formatShortRange(range) }) : null;
  }

  function commitTitle() {
    const title = titleDraft.trim();
    setEditingTitle(false);
    if (!task || !title || title === task.title) {
      if (task) setTitleDraft(task.title);
      return;
    }
    patchTask(task.id, { title });
  }

  function handleRemove() {
    if (!task) return;
    removeTask(task.id);
    router.push("/tasks");
  }

  if (needUpload) {
    return (
      <div>
        {backLink}
        <div className="rounded-md border border-[#F97316]/40 bg-[#F97316]/10 p-4 text-sm text-[#FDBA74]">
          {t("needUpload")}{" "}
          <Link href="/workforce" className="underline underline-offset-2">
            {t("goWorkforce")}
          </Link>
        </div>
      </div>
    );
  }

  if (!loading && !task) {
    return (
      <div>
        {backLink}
        <p className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4 text-sm text-[#A1A1AA]">{t("taskNotFound")}</p>
      </div>
    );
  }

  const lead = task?.lead_id ? peopleById.get(task.lead_id) : undefined;
  const workers = (task?.worker_ids || [])
    .map((id) => peopleById.get(id))
    .filter((p): p is Person => Boolean(p));
  const members = task ? taskMembers(task, peopleById) : [];
  const conflictCount = members.filter((p) => task && taskLeaveConflict(p, task)).length;
  const memberLeave = members.flatMap((p) => personLeaveRanges(p));
  const filled = task ? taskHeadcount(task) : 0;
  const target = task && task.size > 0 ? task.size : 0;
  const staffed = Boolean(target > 0 && filled >= target);
  const understaffed = Boolean(target > 0 && filled < target);
  const blockedOpen = Boolean(task?.blocker && !task.done);
  const dateLabel = task
    ? formatRangeLabel(locale, task.start_date, task.end_date, (count) => td("days", { count }))
    : "";
  const noteValue = noteDraft ?? task?.blocker_note ?? "";
  const noteMissing = Boolean(task?.blocker && !noteValue.trim());
  const selectedConflict =
    selectedPerson && task && !task.done ? taskLeaveConflict(selectedPerson, task) : null;

  return (
    <div>
      <TopProgress show={loading || saving} />
      {backLink}
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {task && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
          <aside
            className={cn(
              "rounded-md border bg-[#0C0C0E] p-3",
              dragOver === "pool" ? "border-[#2DD4BF]" : "border-[#27272A]"
            )}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver("pool");
            }}
            onDragLeave={() => setDragOver(null)}
            onDrop={onDropPool}
          >
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">{t("pool")}</p>
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
            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">{t("filterProject")}</p>
            <div className="mb-2 flex flex-wrap gap-1" role="group" aria-label={t("filterProject")}>
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
            <label className="mb-2 inline-flex cursor-pointer items-center gap-1.5 text-xs text-[#A1A1AA]">
              <input
                type="checkbox"
                className="h-3.5 w-3.5 accent-[#71717A]"
                checked={hideNow}
                onChange={(e) => setHideNow(e.target.checked)}
              />
              {t("hideLeaveNow")}
            </label>
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
            <div className="flex max-h-[55vh] flex-col gap-2 overflow-y-auto">
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
          </aside>

          <section
            className={cn(
              "rounded-md border p-4",
              staffed
                ? "border-[#2DD4BF]/55 bg-[#042F2E]"
                : understaffed
                  ? "border-[#F59E0B]/45 bg-[#1A1207]"
                  : "border-[#27272A] bg-[#0C0C0E]",
              dragOver === task.id || dragOver?.startsWith(`${task.id}:`) ? "border-[#2DD4BF]" : null,
              blockedOpen && "border-[#EF4444]/60",
              task.done && "opacity-90",
              selectedConflict && "outline-dashed outline-2 outline-offset-2 outline-[#EF4444]"
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
            <div className="mb-3 flex flex-wrap items-start gap-2">
              {editingTitle ? (
                <Input
                  autoFocus
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onBlur={commitTitle}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      commitTitle();
                    } else if (e.key === "Escape") {
                      setEditingTitle(false);
                      setTitleDraft(task.title);
                    }
                  }}
                  onClick={(e) => e.stopPropagation()}
                  className="h-10 min-w-0 flex-1 text-lg"
                />
              ) : (
                <div className="flex min-w-0 flex-1 items-start gap-2">
                  <h1 className="min-w-0 flex-1 break-words text-2xl font-semibold tracking-tight text-[#FAFAFA]">
                    {task.title}
                  </h1>
                  <button
                    type="button"
                    className="mt-1 shrink-0 text-[#71717A] hover:text-[#E4E4E7]"
                    title={t("renameTask")}
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingTitle(true);
                      setTitleDraft(task.title);
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                </div>
              )}
              <Button
                type="button"
                variant="outline"
                className="h-9 shrink-0 text-[#F87171]"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemove();
                }}
                title={t("removeTask")}
              >
                <Trash2 className="mr-1 h-3.5 w-3.5" />
                {t("removeTask")}
              </Button>
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-1.5">
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

            <p className="mb-1 text-sm text-[#A1A1AA]">{dateLabel || t("noDates")}</p>
            <p
              className={cn(
                "mb-4 text-sm",
                staffed && "font-medium text-[#5EEAD4]",
                understaffed && "text-[#FBBF24]",
                !target && "text-[#71717A]"
              )}
            >
              {target
                ? t("headcountProgress", { current: filled, target })
                : t("peopleCount", { count: filled })}
            </p>

            <div className="mb-3" onClick={(e) => e.stopPropagation()}>
              <DateRangePicker
                start={task.start_date}
                end={task.end_date}
                onChange={(start_date, end_date) => patchTask(task.id, { start_date, end_date })}
                leaveRanges={memberLeave}
                className="max-w-full"
              />
            </div>
            <label
              className="mb-3 inline-flex items-center gap-1.5 text-xs text-[#A1A1AA]"
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
            <div className="mb-3" onClick={(e) => e.stopPropagation()}>
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
                </div>
              ) : null}
            </div>

            <p className="mb-1 text-[10px] uppercase tracking-wide text-[#71717A]">
              {t("workers")} · {workers.length}
            </p>
            <div
              className={cn(
                "mb-3 flex min-h-[4rem] flex-col gap-1.5 rounded-md border border-dashed p-2",
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
              {!workers.length && <p className="px-1 py-1 text-xs text-[#52525B]">{t("dropWorkers")}</p>}
            </div>

            <div onClick={(e) => e.stopPropagation()}>
              <TaskNotes
                notes={notes[task.id] || []}
                canWrite={staff}
                canDelete={(n) => isAdmin || n.author_email === me?.email}
                onAdd={(text) => addNote(task.id, text)}
                onDelete={(n) => void deleteNote(n)}
              />
            </div>

            <div className="mt-3 border-t border-[#27272A] pt-3" onClick={(e) => e.stopPropagation()}>
              <div className="flex flex-wrap items-center gap-4 text-xs text-[#A1A1AA]">
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
                  className={cn("inline-flex cursor-pointer items-center gap-1.5", task.blocker && "text-[#FCA5A5]")}
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
              {task.blocker ? (
                <div className="mt-2">
                  <label className="mb-1 block text-[10px] uppercase tracking-wide text-[#FCA5A5]">
                    {t("blockerNoteLabel")}
                    {noteMissing ? <span className="ml-1 text-[#F87171]">· {t("blockerRequired")}</span> : null}
                  </label>
                  <textarea
                    value={noteValue}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    onBlur={() => {
                      if (noteDraft === undefined) return;
                      const note = noteDraft.trim();
                      setNoteDraft(undefined);
                      if (note !== task.blocker_note) patchTask(task.id, { blocker_note: note });
                    }}
                    placeholder={t("blockerNotePlaceholder")}
                    rows={3}
                    className={cn(
                      "w-full rounded-md border bg-[#18181B] px-2 py-1.5 text-sm text-[#E4E4E7]",
                      noteMissing ? "border-[#EF4444]" : "border-[#3F3F46]"
                    )}
                  />
                </div>
              ) : null}
            </div>
          </section>
        </div>
      )}

      {!task && loading ? <p className="text-sm text-[#A1A1AA]">{tc("loading")}</p> : null}
    </div>
  );
}
