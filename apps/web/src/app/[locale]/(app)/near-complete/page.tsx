"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Download, Upload } from "lucide-react";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

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
  route_missing?: boolean;
  route_warning?: string;
  pulled_start: string;
  pulled_end: string;
};

type LiveMeta = {
  loaded: boolean;
  file_name: string;
  cable_count: number;
  verlegt_count: number;
  uploaded_at?: string | null;
};

function fmtM(n: number | undefined | null) {
  return Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

export default function NearCompletePage() {
  const t = useTranslations("nearComplete");
  const tc = useTranslations("common");
  const [maxRemaining, setMaxRemaining] = useState(DEFAULT_MAX);
  const [excludeLive, setExcludeLive] = useState(false);
  const [liveMeta, setLiveMeta] = useState<LiveMeta | null>(null);
  const [liveFile, setLiveFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [remainingTotal, setRemainingTotal] = useState(0);
  const [fullyPulledM, setFullyPulledM] = useState(0);
  const [fullyPulledGainM, setFullyPulledGainM] = useState(0);
  const [fullyPulledAfterM, setFullyPulledAfterM] = useState(0);
  const [metricBasis, setMetricBasis] = useState<"dataset" | "live">("dataset");
  const [liveMissing, setLiveMissing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [routeById, setRouteById] = useState<Record<string, CableRouteDetail | "loading" | "error">>({});

  useEffect(() => {
    api
      .get<LiveMeta>("/near-complete/live-progressliste")
      .then((m) => setLiveMeta(m))
      .catch(() => setLiveMeta(null));
  }, []);

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
        fully_pulled_m: number;
        fully_pulled_gain_m: number;
        fully_pulled_after_m: number;
        metric_basis?: "dataset" | "live";
        max_remaining_m: number;
        live_progressliste_missing?: boolean;
        live_progressliste?: LiveMeta;
      }>(
        `/near-complete${qs({
          max_remaining_m: maxRemaining,
          exclude_live_verlegt: excludeLive,
        })}`
      )
      .then((data) => {
        if (cancelled) return;
        setRows(data.rows || []);
        setTotal(data.total || 0);
        setRemainingTotal(Number(data.remaining_total_m || 0));
        setFullyPulledM(Number(data.fully_pulled_m || 0));
        setFullyPulledGainM(Number(data.fully_pulled_gain_m || 0));
        setFullyPulledAfterM(Number(data.fully_pulled_after_m || 0));
        setMetricBasis(data.metric_basis === "live" ? "live" : "dataset");
        setLiveMissing(!!data.live_progressliste_missing);
        if (data.live_progressliste) setLiveMeta(data.live_progressliste);
      })
      .catch((e) => {
        if (cancelled) return;
        setRows([]);
        setTotal(0);
        setRemainingTotal(0);
        setFullyPulledM(0);
        setFullyPulledGainM(0);
        setFullyPulledAfterM(0);
        setMetricBasis("dataset");
        setLiveMissing(false);
        setError(e instanceof Error ? e.message : tc("loadFailed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [maxRemaining, excludeLive, refreshKey, tc]);

  async function uploadLive() {
    if (!liveFile) return;
    setUploading(true);
    setUploadMsg("");
    setError("");
    try {
      const form = new FormData();
      form.append("file", liveFile);
      const meta = await api.post<LiveMeta>("/near-complete/live-progressliste", form);
      setLiveMeta(meta);
      setLiveFile(null);
      setUploadMsg(t("uploadOk"));
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("uploadFailed"));
    } finally {
      setUploading(false);
    }
  }

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
      <TopProgress show={loading || uploading} />
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
              `/near-complete/export${qs({
                max_remaining_m: maxRemaining,
                exclude_live_verlegt: excludeLive,
              })}`,
              `near_complete_${maxRemaining}m.xlsx`
            )
          }
        >
          <Download size={16} />
          {tc("excel")}
        </Button>
      </div>

      <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
        <p className="text-xs uppercase tracking-wide text-[#71717A]">{t("liveUpload")}</p>
        <p className="mt-1 text-xs text-[#71717A]">{t("liveUploadHint")}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-[#27272A] bg-[#09090B] px-3 text-sm text-[#A1A1AA]">
            <span className="truncate max-w-[220px]">{liveFile ? liveFile.name : t("liveChoose")}</span>
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="hidden"
              onChange={(e) => setLiveFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <Button type="button" variant="outline" disabled={!liveFile || uploading} onClick={() => void uploadLive()}>
            <Upload size={16} />
            {t("liveUploadBtn")}
          </Button>
        </div>
        <p className="mt-2 text-xs text-[#A1A1AA]">
          {liveMeta?.loaded
            ? t("liveStatus", {
                name: liveMeta.file_name || "—",
                cables: liveMeta.cable_count.toLocaleString(),
                verlegt: liveMeta.verlegt_count.toLocaleString(),
              })
            : t("liveNone")}
        </p>
        {uploadMsg && <p className="mt-1 text-xs text-[#2DD4BF]">{uploadMsg}</p>}
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
        <label
          className={cn(
            "mt-4 inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm",
            excludeLive
              ? "border-[#2DD4BF]/50 bg-[#042F2E]/40 text-[#FAFAFA]"
              : "border-[#27272A] bg-[#09090B] text-[#A1A1AA]"
          )}
        >
          <input
            type="checkbox"
            className="accent-[#2DD4BF]"
            checked={excludeLive}
            onChange={(e) => setExcludeLive(e.target.checked)}
          />
          {t("excludeLive")}
        </label>
        <p className="mt-1 text-xs text-[#71717A]">{t("excludeLiveHelp")}</p>
        {excludeLive && liveMissing && (
          <p className="mt-2 text-xs text-[#F97316]">{t("liveFilterWarn")}</p>
        )}
      </div>

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      <div className="mb-4 space-y-1">
        <p className="text-sm text-[#A1A1AA]">
          {t("count", { count: total.toLocaleString() })}
          {" · "}
          {t("remainingTotal", { meters: fmtM(remainingTotal) })}
        </p>
        <p className="text-sm font-medium text-[#2DD4BF]">
          {t(metricBasis === "live" ? "fullyPulledAfterLive" : "fullyPulledAfter", {
            after: fmtM(fullyPulledAfterM),
            now: fmtM(fullyPulledM),
            gain: fmtM(fullyPulledGainM),
          })}
        </p>
        <p className="text-xs text-[#71717A]">
          {t(metricBasis === "live" ? "fullyPulledGainHintLive" : "fullyPulledGainHint")}
        </p>
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
              {(detail.pulled_start || detail.pulled_end) && !detail.route_missing && (
                <p className="text-xs text-[#71717A]">
                  {tc("pulledSpan")}{" "}
                  <span className="font-mono-data text-[#FAFAFA]">
                    {detail.pulled_start || "—"} → {detail.pulled_end || "—"}
                  </span>
                </p>
              )}
              {detail.route_missing ? (
                <p className="rounded-md border border-[#F97316]/40 bg-[#F97316]/10 p-3 text-sm text-[#FDBA74]">
                  {detail.route_warning || tc("routeMissing")}
                </p>
              ) : (
                <>
                  <div
                    className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
                    dangerouslySetInnerHTML={{ __html: detail.route_html || detail.route || "—" }}
                  />
                  <p className="text-xs text-[#52525B]">{tc("pulledHint")}</p>
                </>
              )}
            </div>
          );
        }}
      />
    </div>
  );
}
