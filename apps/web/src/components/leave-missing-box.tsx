"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronRight } from "lucide-react";
import { Link } from "@/i18n/routing";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { isStaff, useMe } from "@/components/auth-gate";
import { useCategoryLabel } from "@/components/category-select";
import type { Category } from "@/lib/staffing";

type Missing = { name: string; position: string; category: Category | null };

/** People with no current or future leave day in the uploaded headcount Excel. */
export function LeaveMissingBox() {
  const t = useTranslations("dashboard");
  const categoryLabel = useCategoryLabel();
  const staff = isStaff(useMe());
  const [people, setPeople] = useState<Missing[]>([]);
  const [open, setOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    api
      .get<{ people: Missing[] }>("/workforce/leave-missing")
      .then((res) => {
        if (!cancelled) setPeople(res.people || []);
      })
      .catch(() => {
        if (!cancelled) setPeople([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const groups = useMemo(() => {
    const map = new Map<string, Missing[]>();
    for (const p of people) {
      const key = p.category || "";
      map.set(key, [...(map.get(key) || []), p]);
    }
    return [...map.entries()];
  }, [people]);

  if (!people.length) return null;

  return (
    <div className="space-y-2 rounded-md border border-[#F87171]/40 bg-[#450A0A]/30 p-4">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left font-medium text-[#F87171]"
      >
        <ChevronRight className={cn("h-4 w-4 shrink-0 transition-transform", open && "rotate-90")} />
        {t("leaveMissingTitle", { count: people.length })}
      </button>
      {open && (
        <div className="space-y-1 pl-5">
          <p className="text-xs text-[#FCA5A5]/80">{t("leaveMissingHint")}</p>
          {groups.map(([key, rows]) => (
            <div key={key || "none"}>
              <button
                type="button"
                aria-expanded={Boolean(openGroups[key])}
                onClick={() => setOpenGroups((prev) => ({ ...prev, [key]: !prev[key] }))}
                className="flex w-full items-center gap-1.5 rounded py-1 text-left text-sm font-medium text-[#FCA5A5] hover:text-[#FECACA]"
              >
                <ChevronRight
                  className={cn("h-4 w-4 shrink-0 transition-transform", openGroups[key] && "rotate-90")}
                />
                {categoryLabel((key || null) as Category | null)}{" "}
                <span className="font-normal text-[#F87171]/80">({rows.length})</span>
              </button>
              {openGroups[key] && (
                <ul className="mb-1 grid grid-cols-1 gap-x-4 gap-y-0.5 pl-6 text-sm text-[#FCA5A5] sm:grid-cols-2">
                  {rows.map((p) => (
                    <li key={p.name} className="truncate" title={p.position}>
                      {staff ? (
                        <Link href={`/workers/${encodeURIComponent(p.name)}`} className="hover:underline">
                          {p.name}
                        </Link>
                      ) : (
                        p.name
                      )}
                      {p.position ? <span className="ml-1 text-xs text-[#F87171]/70">· {p.position}</span> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
