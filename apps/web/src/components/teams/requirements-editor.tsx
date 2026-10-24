"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { CATEGORIES, LEAD_CATEGORIES, type Category, type Requirements } from "@/lib/staffing";

/**
 * -/+ chips per category. With `counts` it shows "assigned/required" coloured
 * amber (missing), teal (exact) or red (over).
 */
export function RequirementsEditor({
  requirements,
  counts,
  onChange,
  disabled,
}: {
  requirements: Requirements;
  counts?: Requirements;
  onChange: (next: Requirements) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("categories");
  const tt = useTranslations("teams");
  const [adding, setAdding] = useState(false);
  const active = CATEGORIES.filter((cat) => (requirements[cat] || 0) > 0);
  const extraCounted = counts ? CATEGORIES.filter((cat) => !requirements[cat] && (counts[cat] || 0) > 0) : [];
  const addable = CATEGORIES.filter((cat) => !requirements[cat]);

  function set(cat: Category, value: number) {
    const next: Requirements = { ...requirements };
    const n = Math.max(0, Math.min(99, value));
    if (n) next[cat] = n;
    else delete next[cat];
    onChange(next);
  }

  return (
    <div className="flex flex-wrap items-center gap-1" onClick={(e) => e.stopPropagation()}>
      {active.map((cat) => {
        const need = requirements[cat] || 0;
        const have = counts?.[cat] || 0;
        const tone = !counts
          ? LEAD_CATEGORIES.has(cat)
            ? "border-[#F59E0B]/50 text-[#FCD34D]"
            : "border-[#3F3F46] text-[#E4E4E7]"
          : have > need
            ? "border-[#EF4444]/70 bg-[#EF4444]/15 text-[#FCA5A5]"
            : have === need
              ? "border-[#2DD4BF]/60 bg-[#2DD4BF]/10 text-[#5EEAD4]"
              : "border-[#F59E0B]/60 bg-[#F59E0B]/10 text-[#FCD34D]";
        return (
          <span
            key={cat}
            className={cn("inline-flex items-center gap-0.5 rounded-md border py-0.5 pl-1.5 pr-0.5 text-[11px]", tone)}
          >
            <span className="max-w-[11rem] truncate" title={t(cat)}>
              {t(cat)}
            </span>
            <span className="ml-1 font-semibold tabular-nums">{counts ? `${have}/${need}` : need}</span>
            <button
              type="button"
              disabled={disabled}
              onClick={() => set(cat, need - 1)}
              className="ml-0.5 rounded p-0.5 hover:bg-white/10 disabled:opacity-40"
              aria-label={tt("reqDecrease")}
            >
              <Minus className="h-3 w-3" />
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => set(cat, need + 1)}
              className="rounded p-0.5 hover:bg-white/10 disabled:opacity-40"
              aria-label={tt("reqIncrease")}
            >
              <Plus className="h-3 w-3" />
            </button>
          </span>
        );
      })}
      {extraCounted.map((cat) => (
        <span
          key={cat}
          className="inline-flex items-center rounded-md border border-dashed border-[#EF4444]/60 px-1.5 py-0.5 text-[11px] text-[#FCA5A5]"
          title={tt("notRequired")}
        >
          {t(cat)} <span className="ml-1 font-semibold tabular-nums">{counts?.[cat]}/0</span>
        </span>
      ))}
      {addable.length > 0 &&
        (adding ? (
          <select
            autoFocus
            defaultValue=""
            disabled={disabled}
            onBlur={() => setAdding(false)}
            onChange={(e) => {
              setAdding(false);
              const cat = e.target.value as Category;
              if (cat) set(cat, 1);
            }}
            className="h-6 rounded-md border border-[#3F3F46] bg-[#18181B] px-1 text-[11px] text-[#FAFAFA] focus:outline-none"
          >
            <option value="" disabled>
              {tt("reqPick")}
            </option>
            {addable.map((cat) => (
              <option key={cat} value={cat}>
                {t(cat)}
              </option>
            ))}
          </select>
        ) : (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-0.5 rounded-md border border-dashed border-[#3F3F46] px-1.5 py-0.5 text-[11px] text-[#71717A] hover:border-[#2DD4BF]/60 hover:text-[#5EEAD4]"
          >
            <Plus className="h-3 w-3" />
            {active.length ? tt("reqAdd") : tt("reqSet")}
          </button>
        ))}
    </div>
  );
}
