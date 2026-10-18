"use client";

import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function DataTable({
  rows,
  columns,
  rowKey,
  expandedKey,
  onRowClick,
  renderExpanded,
}: {
  rows: Record<string, unknown>[];
  columns?: string[];
  rowKey?: (row: Record<string, unknown>, index: number) => string;
  expandedKey?: string | null;
  onRowClick?: (row: Record<string, unknown>, index: number) => void;
  renderExpanded?: (row: Record<string, unknown>, index: number) => ReactNode;
}) {
  if (!rows.length) {
    return <p className="text-sm text-[#71717A]">No rows.</p>;
  }
  const cols = columns || Object.keys(rows[0]).slice(0, 12);
  return (
    <div className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E]">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-[#27272A] bg-[#18181B] text-xs uppercase tracking-wide text-[#71717A]">
          <tr>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const key = rowKey ? rowKey(row, i) : String(i);
            const expanded = expandedKey != null && expandedKey === key;
            return (
              <Fragment key={key}>
                <tr
                  className={cn(
                    "border-b border-[#27272A] last:border-0 hover:bg-[#18181B]/60",
                    onRowClick && "cursor-pointer",
                    expanded && "bg-[#18181B]/80"
                  )}
                  onClick={onRowClick ? () => onRowClick(row, i) : undefined}
                >
                  {cols.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-2 font-mono-data text-[13px] text-[#E4E4E7]">
                      {row[c] == null ? "—" : String(row[c])}
                    </td>
                  ))}
                </tr>
                {expanded && renderExpanded && (
                  <tr className="border-b border-[#27272A] bg-[#09090B]">
                    <td colSpan={cols.length} className="px-3 py-3">
                      {renderExpanded(row, i)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
