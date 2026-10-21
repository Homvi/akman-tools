"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";

const COLS = [
  "Kabelnr",
  "Remaining_m",
  "Length_m",
  "Total_teilgezogene_meter",
  "Category",
  "Liste",
  "Geraet_A",
  "Geraet_E",
];

const DEFAULT_MAX = 15;
const SLIDER_MIN = 1;
const SLIDER_MAX = 50;

type CableRouteDetail = {
  kabelnr: string;
  status_label: string;
  status_message: string;
  route_html: string;
  route: string;
  pulled_start: string;
  pulled_end: string;
};

function fmtM(n: number | undefined | null) {
  return Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

export default function NearCompletePage() {
  const t = useTranslations("nearComplete");
  const tc = useTranslations("common");
  const [maxRemaining, setMaxRemaining] = useState(DEFAULT_MAX);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [remainingTotal, setRemainingTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [routeById, setRouteById] = useState<Record<string, CableRouteDetail | "loading" | "error">>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setExpandedId(null);
    api
      .get<{
        rows: Record<string, unknown>[];
        total: number;
        remaining_total_m: number;
        max_remaining_m: number;
      }>(`/near-complete${qs({ max_remaining_m: maxRemaining })}`)
      .then((data) => {
        if (cancelled) return;
        setRows(data.rows || []);
        setTotal(data.total || 0);
        setRemainingTotal(Number(data.remaining_total_m || 0));
      })
      .catch((e) => {
        if (cancelled) return;
        setRows([]);
        setTotal(0);
        setRemainingTotal(0);
        setError(e instanceof Error ? e.message : tc("loadFailed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [maxRemaining, tc]);

  async function toggleRow(row: Record<string, unknown>) {
    const id = String(row.Kabelnr ?? "").trim();
    if (!id) return;
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (routeById[id] && routeById[id] !== "error") return;
    setRouteById((prev) => ({ ...prev, [id]: "loading" }));
    try {
      const detail = await api.get<CableRouteDetail>(`/cables/by-id/${encodeURIComponent(id)}`);
      setRouteById((prev) => ({ ...prev, [id]: detail }));
    } catch {
      setRouteById((prev) => ({ ...prev, [id]: "error" }));
    }
  }

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
          <p className="mt-1 text-sm text-[#A1A1AA]">{t("subtitle")}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={!total || loading}
          onClick={() =>
            api.download(
              `/near-complete/export${qs({ max_remaining_m: maxRemaining })}`,
              `near_complete_${maxRemaining}m.xlsx`
            )
          }
        >
          <Download size={16} />
          {tc("excel")}
        </Button>
      </div>

      <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
        <label className="block text-xs uppercase tracking-wide text-[#71717A]">
          {t("slider")}: <span className="font-mono-data text-[#FAFAFA]">{maxRemaining}</span> m
          <input
            type="range"
            className="mt-3 w-full accent-[#2DD4BF]"
            min={SLIDER_MIN}
            max={SLIDER_MAX}
            step={1}
            value={maxRemaining}
            onChange={(e) => setMaxRemaining(Number(e.target.value))}
          />
        </label>
        <div className="mt-1 flex justify-between text-[11px] text-[#52525B]">
          <span>{SLIDER_MIN} m</span>
          <span>{SLIDER_MAX} m</span>
        </div>
      </div>

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      <div className="mb-4 space-y-1">
        <p className="text-sm text-[#A1A1AA]">
          {t("count", { count: total.toLocaleString() })}
          {" · "}
          <span className="font-medium text-[#2DD4BF]">{t("remainingTotal", { meters: fmtM(remainingTotal) })}</span>
        </p>
        <p className="text-xs text-[#71717A]">{t("gainHint")}</p>
        {rows.length > 0 && <p className="text-xs text-[#52525B]">{t("clickHint")}</p>}
      </div>

      <DataTable
        rows={rows}
        columns={COLS}
        rowKey={(row) => String(row.Kabelnr ?? "")}
        expandedKey={expandedId}
        onRowClick={(row) => void toggleRow(row)}
        renderExpanded={(row) => {
          const id = String(row.Kabelnr ?? "").trim();
          const detail = routeById[id];
          if (detail === "loading" || !detail) {
            return <p className="text-sm text-[#71717A]">{tc("loadingRoute")}</p>;
          }
          if (detail === "error") {
            return <p className="text-sm text-[#F87171]">{tc("routeError")}</p>;
          }
          return (
            <div className="space-y-2">
              <p className="text-sm text-[#FAFAFA]">{detail.status_message || detail.status_label}</p>
              {(detail.pulled_start || detail.pulled_end) && (
                <p className="text-xs text-[#71717A]">
                  {tc("pulledSpan")}{" "}
                  <span className="font-mono-data text-[#FAFAFA]">
                    {detail.pulled_start || "—"} → {detail.pulled_end || "—"}
                  </span>
                </p>
              )}
              <div
                className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
                dangerouslySetInnerHTML={{ __html: detail.route_html || detail.route || "—" }}
              />
              <p className="text-xs text-[#52525B]">{tc("pulledHint")}</p>
            </div>
          );
        }}
      />
    </div>
  );
}
