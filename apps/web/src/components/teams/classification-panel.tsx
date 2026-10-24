"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronRight } from "lucide-react";
import { CategorySelect } from "@/components/category-select";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Category, Person } from "@/lib/staffing";

function fold(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

export function ClassificationPanel({
  people,
  onSet,
  busy,
}: {
  people: Person[];
  onSet: (person: Person, category: Category | null) => void;
  busy?: boolean;
}) {
  const t = useTranslations("teams");
  const [open, setOpen] = useState(false);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [search, setSearch] = useState("");
  const unclassified = people.filter((p) => !p.category).length;

  const rows = useMemo(() => {
    const needle = fold(search);
    return people
      .filter((p) => (!onlyMissing || !p.category) && (!needle || fold(`${p.name} ${p.position}`).includes(needle)))
      .sort((a, b) => Number(Boolean(a.category)) - Number(Boolean(b.category)) || a.name.localeCompare(b.name));
  }, [people, onlyMissing, search]);

  if (unclassified === 0) return null;

  return (
    <section className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        aria-expanded={open}
      >
        <ChevronRight className={cn("h-4 w-4 text-[#71717A] transition-transform", open && "rotate-90")} />
        <span className="text-xs font-medium uppercase tracking-wide text-[#A1A1AA]">{t("classifyTitle")}</span>
        {unclassified > 0 ? (
          <span className="rounded bg-[#F59E0B]/20 px-1.5 py-0.5 text-[10px] font-bold text-[#FCD34D]">
            {t("classifyMissing", { count: unclassified })}
          </span>
        ) : (
          <span className="text-[11px] text-[#5EEAD4]">{t("classifyAllDone")}</span>
        )}
      </button>
      {open && (
        <div className="border-t border-[#27272A] p-3">
          <p className="mb-2 text-[11px] text-[#71717A]">{t("classifyHint")}</p>
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <Input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchPeople")}
              className="h-8 max-w-xs text-sm"
            />
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-[#A1A1AA]">
              <input
                type="checkbox"
                className="h-3.5 w-3.5 accent-[#F59E0B]"
                checked={onlyMissing}
                onChange={(e) => setOnlyMissing(e.target.checked)}
              />
              {t("classifyOnlyMissing")}
            </label>
          </div>
          <ul className="grid max-h-80 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
            {rows.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between gap-2 rounded-md border border-[#27272A] bg-[#18181B] px-2 py-1"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm text-[#FAFAFA]">{p.name}</span>
                  <span className="block truncate text-[10px] text-[#71717A]">{p.position || "—"}</span>
                </span>
                <CategorySelect
                  person={p}
                  disabled={busy}
                  onChange={(c) => onSet(p, c)}
                  className="h-7 max-w-[11rem] shrink-0 text-xs"
                />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
