"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { CATEGORIES, isCategory, type Category, type Person } from "@/lib/staffing";

export function useCategoryLabel() {
  const t = useTranslations("categories");
  return (cat: Category | null | undefined) => (cat ? t(cat) : t("none"));
}

export function CategorySelect({
  person,
  onChange,
  disabled,
  className,
}: {
  person: Pick<Person, "category" | "category_source">;
  onChange: (category: Category | null) => void;
  disabled?: boolean;
  className?: string;
}) {
  const t = useTranslations("categories");
  const manual = person.category_source === "manual";
  const value = manual && person.category ? person.category : "";
  const autoLabel = person.category_source === "auto" && person.category
    ? t("autoWith", { label: t(person.category) })
    : t("none");

  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(isCategory(e.target.value) ? e.target.value : null)}
      title={manual ? t("manualHint") : t("autoHint")}
      className={cn(
        "h-8 rounded-md border bg-[#18181B] px-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#2DD4BF]",
        person.category ? "border-[#3F3F46] text-[#FAFAFA]" : "border-[#F59E0B]/60 text-[#FCD34D]",
        className
      )}
    >
      <option value="">{autoLabel}</option>
      {CATEGORIES.map((cat) => (
        <option key={cat} value={cat}>
          {t(cat)}
        </option>
      ))}
    </select>
  );
}
