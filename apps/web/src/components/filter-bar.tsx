"use client";

import { Button } from "@/components/ui/button";

export type FilterState = {
  devices: string;
  pulled: string;
  thickness: string;
  categories: string;
};

const selectCls =
  "mt-1 block h-9 min-w-[140px] rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]";

export function FilterBar({
  value,
  options,
  onChange,
  onApply,
}: {
  value: FilterState;
  options?: {
    devices?: string[];
    pull_statuses?: string[];
    thickness?: string[];
    categories?: string[];
  };
  onChange: (next: FilterState) => void;
  onApply: () => void;
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 md:flex-row md:flex-wrap md:items-end">
      <label className="text-xs text-[#71717A]">
        Pulled
        <select
          className={selectCls}
          value={value.pulled}
          onChange={(e) => onChange({ ...value, pulled: e.target.value })}
        >
          <option value="">All</option>
          {(options?.pull_statuses || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs text-[#71717A]">
        Thickness
        <select
          className={selectCls}
          value={value.thickness}
          onChange={(e) => onChange({ ...value, thickness: e.target.value })}
        >
          <option value="">All</option>
          {(options?.thickness || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs text-[#71717A]">
        Category
        <select
          className={selectCls}
          value={value.categories}
          onChange={(e) => onChange({ ...value, categories: e.target.value })}
        >
          <option value="">All</option>
          {(options?.categories || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>
      <Button onClick={onApply}>Apply filters</Button>
    </div>
  );
}
