"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, Info } from "lucide-react";
import { Link } from "@/i18n/routing";
import { isStaff, useMe } from "@/components/auth-gate";
import { useCategoryLabel } from "@/components/category-select";
import { cn } from "@/lib/utils";
import {
  formatShortRange,
  isProject,
  leaveOverlapsNextWeek,
  personLeaveRanges,
  type Person,
} from "@/lib/staffing";

function formatLeaveHint(person: Person, leaveLabel: string): string | null {
  const first = personLeaveRanges(person)[0];
  return first ? `${leaveLabel} ${formatShortRange(first)}` : null;
}

export function PersonChip({
  person,
  dragging,
  selected,
  leaveLabel,
  nowLeaveLabel,
  nextWeekLeaveLabel,
  conflictText,
  outsideRequirements,
  watching,
  watchingLabel,
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
  /** The task's requirements don't ask for this person's category. */
  outsideRequirements?: boolean;
  watching?: number;
  watchingLabel?: string;
  onDragStart: (id: string) => void;
  onSelect?: (id: string) => void;
}) {
  const t = useTranslations("teams");
  const categoryLabel = useCategoryLabel();
  const canSeeDetails = isStaff(useMe());
  const leaveHint = formatLeaveHint(person, leaveLabel);
  const onLeaveNow = Boolean(person.on_leave);
  const nextWeek = leaveOverlapsNextWeek(person);
  const afternoon = Boolean(person.afternoon);
  const project = person.project && isProject(person.project) ? person.project : null;

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
        person.category ? categoryLabel(person.category) : null,
        afternoon ? t("shiftAfternoon") : null,
        project ? t("projectLabel", { code: project }) : null,
        leaveHint,
        onLeaveNow ? nowLeaveLabel : null,
        nextWeek ? nextWeekLeaveLabel : null,
        conflictText,
        watching != null && watchingLabel ? watchingLabel : null,
      ]
        .filter(Boolean)
        .join(" · ") || undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 break-words font-medium leading-tight">
          {person.name}
          {watching != null ? <span className="text-[#FCD34D]/80"> · {watching}</span> : null}
        </div>
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
      {person.position || person.category || canSeeDetails ? (
        <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-[#A1A1AA]">
          <span className="min-w-0 truncate">
            {person.category ? categoryLabel(person.category) : person.position}
          </span>
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
      {(afternoon || project) && (
        <div className="mt-1 flex flex-wrap gap-1">
          {afternoon ? (
            <span className="rounded bg-[#7C3AED]/25 px-1.5 py-0.5 text-[10px] font-semibold text-[#C4B5FD]">
              {t("shiftAfternoonShort")}
            </span>
          ) : null}
          {project ? (
            <span className="rounded bg-[#0E7490]/30 px-1.5 py-0.5 text-[10px] font-semibold text-[#67E8F9]">
              {project}
            </span>
          ) : null}
        </div>
      )}
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
      {outsideRequirements ? (
        <div className="mt-1 inline-flex rounded border border-[#F59E0B]/60 px-1.5 py-0.5 text-[10px] font-semibold text-[#FCD34D]">
          {person.category ? t("notRequired") : t("noCategory")}
        </div>
      ) : null}
    </div>
  );
}
