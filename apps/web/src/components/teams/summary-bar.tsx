"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CategorySummary } from "@/lib/staffing";

export function SummaryBar({ rows, unclassified }: { rows: CategorySummary[]; unclassified: number }) {
  const t = useTranslations("teams");
  const tc = useTranslations("categories");
  const visible = rows.filter((r) => r.needed > 0 || r.roster > 0);
  if (!visible.length) return null;
  const shortCount = visible.filter((r) => r.short).length;

  return (
    <section className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-[#71717A]">{t("summaryTitle")}</h2>
        <span className={cn("text-xs", shortCount ? "font-semibold text-[#F87171]" : "text-[#71717A]")}>
          {shortCount ? t("summaryShort", { count: shortCount }) : t("summaryHint")}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
        {visible.map((row) => (
          <div
            key={row.category}
            className={cn(
              "rounded-md border px-2.5 py-2",
              row.short ? "border-[#EF4444]/70 bg-[#450A0A]/40" : "border-[#27272A] bg-[#18181B]"
            )}
          >
            <p className={cn("truncate text-xs", row.short ? "text-[#FCA5A5]" : "text-[#A1A1AA]")} title={tc(row.category)}>
              {tc(row.category)}
            </p>
            <p
              className={cn(
                "mt-0.5 flex items-center gap-1 text-xl font-semibold tabular-nums",
                row.short ? "text-[#F87171]" : "text-[#FAFAFA]"
              )}
              title={t("summaryTileTitle")}
            >
              {row.short ? <AlertTriangle className="h-4 w-4" /> : null}
              {row.needed}/{row.roster}
            </p>
            <p className="mt-0.5 text-[10px] text-[#71717A]">
              {t("summaryAssigned", { count: row.assigned })}
            </p>
            {row.onLeaveNow || row.leaveNextWeek ? (
              <p className="text-[10px] text-[#A1A1AA]">
                {t("summaryLeave", { now: row.onLeaveNow, next: row.leaveNextWeek })}
              </p>
            ) : null}
          </div>
        ))}
      </div>
      {unclassified > 0 ? (
        <p className="mt-2 text-[11px] text-[#FCD34D]">{t("summaryUnclassified", { count: unclassified })}</p>
      ) : null}
    </section>
  );
}
