"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Download, GripVertical, X } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

type Plan = {
  thin_pace: number;
  thick_pace: number;
  h_per_stuetze: number;
  pullers: number;
  max_per_room: number;
  hours_per_week: number;
  priority: Record<string, number>;
  installed?: Record<string, string[]>;
  blocks?: string[];
};

type AreaRow = {
  key: string;
  name: string;
  deck: string;
  area_ids?: string;
  cables: number;
  pulled?: number;
  remaining_cables?: number;
  thick?: number;
  thin?: number;
  through?: number;
  terminate?: number;
  stop?: number;
  pulled_pct: number;
  remaining_m: number;
  person_hours: number;
  crew: number;
  queue_rank?: number;
  start_date?: string | null;
  end_date?: string | null;
  kw?: string | null;
  workdays?: number;
  priority?: number | null;
  thick_through?: number;
  thin_through?: number;
  thick_terminate?: number;
  thin_terminate?: number;
  zero_person_hours?: number;
  zero_weeks?: number;
};

type Totals = {
  person_hours?: number;
  remaining_m?: number;
  cables?: number;
  pulled_pct?: number;
  schedule?: { kw?: string; workdays?: number; end_date?: string | null };
};

type ExportColumn = { key: string; label: string };

type ChartSlice = { name: string; value: number };

type AreaDetail = {
  summary: AreaRow;
  area: {
    key: string;
    name: string;
    deck: string;
    area_ids: string;
    trays: string[];
    penetrations: string[];
  };
  stuetzen: { stuetze: string; cables: number; done: number; pct: number; complete: boolean }[];
  preview: Record<string, unknown>[];
  cable_count: number;
  remaining_cable_count: number;
  charts: {
    pulled_vs_remaining: ChartSlice[];
    thick_thin: ChartSlice[];
    roles: ChartSlice[];
    remaining_m: ChartSlice[];
  };
};

const ZERO_COLS = [
  "name",
  "deck",
  "thick_through",
  "thin_through",
  "thick_terminate",
  "thin_terminate",
  "zero_person_hours",
  "zero_weeks",
];

const DEFAULT_PLAN: Plan = {
  thin_pace: 20,
  thick_pace: 3,
  h_per_stuetze: 5,
  pullers: 25,
  max_per_room: 5,
  hours_per_week: 56,
  priority: {},
};

const DEFAULT_EXPORT_KEYS = [
  "kabelnr",
  "liste",
  "category",
  "length_m",
  "pull_status",
  "stop_locations",
  "geraet_a",
  "geraet_e",
  "ort_a",
  "ort_e",
  "verlegt",
];

const PIE_COLORS = ["#2DD4BF", "#F97316", "#A1A1AA", "#60A5FA"];

export default function AreasPage() {
  const t = useTranslations("areas");
  const tc = useTranslations("common");
  const [summaries, setSummaries] = useState<AreaRow[]>([]);
  const [totals, setTotals] = useState<Totals>({});
  const [plan, setPlan] = useState<Plan>(DEFAULT_PLAN);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<AreaDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exportColumns, setExportColumns] = useState<ExportColumn[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>(DEFAULT_EXPORT_KEYS);
  const [showExportCols, setShowExportCols] = useState(false);
  const [remainingOnly, setRemainingOnly] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api
      .get<{ columns: ExportColumn[]; defaults: string[] }>("/areas/export-columns")
      .then((data) => {
        setExportColumns(data.columns || []);
        if (data.defaults?.length) setSelectedColumns(data.defaults);
      })
      .catch(() => {
        setExportColumns(DEFAULT_EXPORT_KEYS.map((key) => ({ key, label: key })));
      });
  }, []);

  function planQs(p: Plan = plan) {
    return qs({
      thin_pace: p.thin_pace,
      thick_pace: p.thick_pace,
      h_per_stuetze: p.h_per_stuetze,
      pullers: p.pullers,
      max_per_room: p.max_per_room,
      hours_per_week: p.hours_per_week,
    });
  }

  async function load(nextPlan?: Plan) {
    const p = nextPlan || plan;
    setLoading(true);
    setError("");
    try {
      const data = await api.get<{
        summaries: AreaRow[];
        totals: Totals;
        plan?: Plan;
      }>(`/areas/summaries${planQs(p)}`);
      setSummaries(data.summaries || []);
      setTotals(data.totals || {});
      if (data.plan) {
        setPlan({
          thin_pace: Number(data.plan.thin_pace ?? p.thin_pace),
          thick_pace: Number(data.plan.thick_pace ?? p.thick_pace),
          h_per_stuetze: Number(data.plan.h_per_stuetze ?? p.h_per_stuetze),
          pullers: Number(data.plan.pullers ?? p.pullers),
          max_per_room: Number(data.plan.max_per_room ?? p.max_per_room),
          hours_per_week: Number(data.plan.hours_per_week ?? p.hours_per_week),
          priority: data.plan.priority || {},
          installed: data.plan.installed || {},
          blocks: data.plan.blocks || [],
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
      setSummaries([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadDetail(key: string) {
    setSelectedKey(key);
    setDetailLoading(true);
    setError("");
    try {
      const data = await api.get<AreaDetail>(`/areas/detail${qs({ key })}`);
      setDetail(data);
    } catch (e) {
      setDetail(null);
      setError(e instanceof Error ? e.message : "Detail failed");
    } finally {
      setDetailLoading(false);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setLoading(true);
    try {
      await api.post("/areas/upload", form);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setLoading(false);
    } finally {
      e.target.value = "";
    }
  }

  async function savePlan(next: Plan, reload = true) {
    setLoading(true);
    setError("");
    try {
      await api.put("/areas/settings", next);
      setPlan(next);
      if (reload) await load(next);
      else setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setLoading(false);
    }
  }

  function setNum(key: keyof Plan, raw: string) {
    const n = Number(raw);
    if (!Number.isFinite(n)) return;
    setPlan((prev) => ({ ...prev, [key]: n }));
  }

  async function onDropReorder(targetKey: string) {
    if (!dragKey || dragKey === targetKey) {
      setDragKey(null);
      return;
    }
    const keys = summaries.map((s) => s.key);
    const from = keys.indexOf(dragKey);
    const to = keys.indexOf(targetKey);
    setDragKey(null);
    if (from < 0 || to < 0) return;
    const nextKeys = [...keys];
    const [moved] = nextKeys.splice(from, 1);
    nextKeys.splice(to, 0, moved);
    const priority: Record<string, number> = {};
    nextKeys.forEach((k, i) => {
      priority[k] = i + 1;
    });
    const nextPlan = { ...plan, priority };
    setSummaries((prev) => {
      const byKey = new Map(prev.map((s) => [s.key, s]));
      return nextKeys.map((k) => byKey.get(k)!).filter(Boolean);
    });
    await savePlan(nextPlan, true);
    if (selectedKey) void loadDetail(selectedKey);
  }

  function toggleColumn(key: string) {
    setSelectedColumns((prev) => {
      if (prev.includes(key)) {
        if (prev.length === 1) return prev;
        return prev.filter((c) => c !== key);
      }
      return [...prev, key];
    });
  }

  async function exportCables() {
    if (!selectedKey) return;
    setExporting(true);
    setError("");
    try {
      const name = detail?.area.name || selectedKey;
      await api.downloadPost(
        "/areas/export-cables",
        {
          key: selectedKey,
          columns: selectedColumns,
          remaining_only: remainingOnly,
        },
        `area_${name}${remainingOnly ? "_remaining" : ""}.xlsx`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  const zeroRows = useMemo(
    () => summaries.map((s) => ({ ...s }) as Record<string, unknown>),
    [summaries]
  );

  const maxPersonHours = useMemo(
    () => Math.max(0, ...summaries.map((s) => Number(s.person_hours) || 0)),
    [summaries]
  );
  const totalPersonHours = useMemo(
    () => summaries.reduce((acc, s) => acc + (Number(s.person_hours) || 0), 0),
    [summaries]
  );

  return (
    <div>
      <TopProgress show={loading || detailLoading || exporting} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
          <p className="mt-1 text-sm text-[#71717A]">
            {t("subtitle", { max: plan.max_per_room })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-[#27272A] bg-transparent px-3 text-sm text-[#FAFAFA] hover:bg-[#18181B]">
            {t("upload")}
            <input type="file" accept=".xlsx" className="hidden" onChange={onUpload} />
          </label>
          <Button
            type="button"
            variant="outline"
            disabled={!summaries.length}
            onClick={() => api.download(`/areas/export${planQs()}`, "areas_export.xlsx")}
          >
            <Download size={16} />
            {tc("excel")}
          </Button>
        </div>
      </div>

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      <section className="mb-6 rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-[#71717A]">Planning</h2>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {(
            [
              ["thin_pace", "Thin m/h"],
              ["thick_pace", "Thick m/h"],
              ["h_per_stuetze", "Hours / Stütze"],
              ["pullers", "Cable pullers"],
              ["max_per_room", "Max / room"],
              ["hours_per_week", "Hours / week"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="text-xs text-[#71717A]">
              {label}
              <Input
                className="mt-1 font-mono-data"
                type="number"
                step={key === "pullers" || key === "max_per_room" ? 1 : 0.5}
                value={plan[key]}
                onChange={(e) => setNum(key, e.target.value)}
              />
            </label>
          ))}
        </div>
        <div className="mt-3">
          <Button type="button" onClick={() => void savePlan(plan, true)} disabled={loading}>
            {t("calcSave")}
          </Button>
        </div>
      </section>

      <div className="mb-4 flex flex-wrap gap-2">
        <Badge>Person-hours: {Number(totals.person_hours || 0).toFixed(1)}</Badge>
        <Badge>Remaining m: {Number(totals.remaining_m || 0).toFixed(1)}</Badge>
        <Badge>Cables: {Number(totals.cables || 0)}</Badge>
        <Badge>Pulled: {Number(totals.pulled_pct || 0).toFixed(1)}%</Badge>
        {totals.schedule?.kw && <Badge>KW: {totals.schedule.kw}</Badge>}
        {totals.schedule?.end_date && <Badge>Ready: {totals.schedule.end_date}</Badge>}
      </div>

      <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-[#71717A]">
        {t("overview")}
      </h2>
      <p className="mb-3 text-xs text-[#52525B]">
        {t("overviewHint")}
      </p>
      <div className="mb-6 space-y-2">
        {summaries.map((row) => {
          const pulledPct = Math.max(0, Math.min(100, Number(row.pulled_pct) || 0));
          const hours = Number(row.person_hours) || 0;
          const workWeightPct =
            maxPersonHours > 0 ? Math.max(0, Math.min(100, (hours / maxPersonHours) * 100)) : 0;
          const sharePct = totalPersonHours > 0 ? (hours / totalPersonHours) * 100 : 0;
          const selected = selectedKey === row.key;
          return (
            <div
              key={row.key}
              draggable
              onDragStart={() => setDragKey(row.key)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => void onDropReorder(row.key)}
              onClick={() => void loadDetail(row.key)}
              className={cn(
                "relative overflow-hidden rounded-md border border-[#27272A] cursor-pointer transition-colors",
                selected ? "border-[#2DD4BF]/60 bg-[#042F2E]/20" : "bg-[#0C0C0E] hover:border-[#3F3F46]",
                dragKey === row.key && "opacity-60"
              )}
            >
              {/* Relative remaining workload vs heaviest room */}
              <div
                className="pointer-events-none absolute inset-y-0 left-0 bg-[#F97316]/20"
                style={{ width: `${workWeightPct}%` }}
                title={t("hoursLeftTitle", { hours: hours.toFixed(1), pct: sharePct.toFixed(0) })}
              />
              <div className="relative flex flex-wrap items-center gap-3 px-3 py-3">
                <span
                  className="inline-flex cursor-grab text-[#71717A] active:cursor-grabbing"
                  onClick={(e) => e.stopPropagation()}
                  title={t("dragTitle")}
                >
                  <GripVertical size={18} />
                </span>
                <span className="font-mono-data text-xs text-[#71717A] w-6">
                  #{row.queue_rank ?? "—"}
                </span>
                <div className="min-w-[180px] flex-1">
                  <p className="text-sm font-medium text-[#FAFAFA]">
                    {row.name}
                    {row.deck ? <span className="text-[#71717A]"> · {row.deck}</span> : null}
                  </p>
                  <p className="text-xs text-[#A1A1AA]">
                    {t("hoursLeft", { hours: hours.toFixed(1) })}
                    {sharePct > 0 ? t("workShare", { pct: sharePct.toFixed(0) }) : ""}
                    {" · "}
                    {t("metersCables", {
                      meters: Number(row.remaining_m).toFixed(1),
                      cables: row.cables,
                    })}
                  </p>
                  {/* In-area pull progress (not comparable across rooms) */}
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="h-1.5 flex-1 max-w-[220px] overflow-hidden rounded-full bg-[#27272A]">
                      <div
                        className="h-full rounded-full bg-[#2DD4BF]"
                        style={{ width: `${pulledPct}%` }}
                      />
                    </div>
                    <span className="font-mono-data text-[11px] text-[#71717A] tabular-nums">
                      {t("pulledPct", { pct: pulledPct.toFixed(0) })}
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 text-xs">
                  <Badge>Crew {row.crew}</Badge>
                  <Badge>
                    {row.start_date || "—"} → {row.end_date || "—"}
                  </Badge>
                  {row.kw ? <Badge>KW {row.kw}</Badge> : null}
                </div>
              </div>
            </div>
          );
        })}
        {!summaries.length && !loading && (
          <p className="text-sm text-[#71717A]">{t("noRooms")}</p>
        )}
      </div>

      {selectedKey && (
        <section className="mb-8 rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold text-[#FAFAFA]">
                {detail?.area.name || t("room")}
                {detail?.area.deck ? (
                  <span className="text-[#71717A]"> · {detail.area.deck}</span>
                ) : null}
              </h2>
              <p className="mt-1 text-xs text-[#71717A]">
                Crew {detail?.summary.crew ?? "—"} · queue #{detail?.summary.queue_rank ?? "—"} ·{" "}
                {detail?.summary.start_date || "—"} → {detail?.summary.end_date || "—"} ·{" "}
                {t("personHoursLeft", {
                  hours: Number(detail?.summary.person_hours || 0).toFixed(1),
                  meters: Number(detail?.summary.remaining_m || 0).toFixed(1),
                })}
              </p>
            </div>
            <Button type="button" variant="ghost" size="sm" onClick={() => { setSelectedKey(null); setDetail(null); }}>
              <X size={16} />
              {tc("close")}
            </Button>
          </div>

          {detail && (
            <>
              <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <ChartCard title={t("chartPulledVsLeft")}>
                  <MiniPie data={detail.charts.pulled_vs_remaining} />
                </ChartCard>
                <ChartCard title="Thick / Thin">
                  <MiniPie data={detail.charts.thick_thin} />
                </ChartCard>
                <ChartCard title="Through / Terminate / Stop">
                  <MiniBars data={detail.charts.roles} />
                </ChartCard>
                <ChartCard title={t("chartMetersLeft")}>
                  <MiniBars data={detail.charts.remaining_m} />
                </ChartCard>
              </div>

              {detail.stuetzen.length > 0 && (
                <div className="mb-6">
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">
                    {t("stutzenProgress")}
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {detail.stuetzen.map((st) => (
                      <div
                        key={st.stuetze}
                        className="relative overflow-hidden rounded-md border border-[#27272A] bg-[#09090B] px-3 py-2"
                      >
                        <div
                          className="pointer-events-none absolute inset-y-0 left-0 bg-[#2DD4BF]/20"
                          style={{ width: `${Math.max(0, Math.min(100, st.pct))}%` }}
                        />
                        <div className="relative flex justify-between gap-2 text-sm">
                          <span className="font-mono-data text-[#FAFAFA]">{st.stuetze}</span>
                          <span className="text-xs text-[#A1A1AA]">
                            {st.done}/{st.cables} · {st.pct.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={exporting || selectedColumns.length === 0}
                  onClick={() => void exportCables()}
                >
                  <Download size={16} />
                  {remainingOnly
                    ? t("excelRemaining", { count: detail.remaining_cable_count })
                    : t("excelAll", { count: detail.cable_count })}
                </Button>
                <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-[#27272A] px-3 text-sm text-[#A1A1AA]">
                  <input
                    type="checkbox"
                    className="accent-[#2DD4BF]"
                    checked={remainingOnly}
                    onChange={(e) => setRemainingOnly(e.target.checked)}
                  />
                  Csak remaining
                </label>
                <Button type="button" variant="ghost" onClick={() => setShowExportCols((v) => !v)}>
                  {showExportCols ? tc("hideCols") : tc("exportCols")}
                </Button>
              </div>

              {showExportCols && (
                <div className="mb-4 rounded-md border border-[#27272A] bg-[#09090B] p-3">
                  <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">
                    {tc("exportColsHelp")}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(exportColumns.length
                      ? exportColumns
                      : DEFAULT_EXPORT_KEYS.map((key) => ({ key, label: key }))
                    ).map((col) => {
                      const checked = selectedColumns.includes(col.key);
                      return (
                        <label
                          key={col.key}
                          className={cn(
                            "inline-flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs",
                            checked
                              ? "border-[#2DD4BF]/40 bg-[#042F2E]/30 text-[#FAFAFA]"
                              : "border-[#27272A] text-[#A1A1AA]"
                          )}
                        >
                          <input
                            type="checkbox"
                            className="accent-[#2DD4BF]"
                            checked={checked}
                            onChange={() => toggleColumn(col.key)}
                          />
                          {col.label}
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">
                {t("cablePreview", {
                  count:
                    detail.cable_count > detail.preview.length
                      ? `${detail.preview.length} / ${detail.cable_count}`
                      : detail.preview.length,
                })}
              </h3>
              <DataTable
                rows={detail.preview}
                columns={["Kabelnr", "Liste", "Category", "Length_m", "Pull_status", "Geraet_A", "Geraet_E"]}
              />
            </>
          )}
        </section>
      )}

      <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-[#71717A]">From zero</h2>
      <DataTable rows={zeroRows} columns={ZERO_COLS} />
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-[#27272A] bg-[#09090B] p-3">
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">{title}</h3>
      <div className="h-40">{children}</div>
    </div>
  );
}

function MiniPie({ data }: { data: ChartSlice[] }) {
  const t = useTranslations("areas");
  const filtered = data.filter((d) => Number(d.value) > 0);
  if (!filtered.length) {
    return <p className="flex h-full items-center justify-center text-xs text-[#52525B]">{t("noChartData")}</p>;
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={filtered} dataKey="value" nameKey="name" innerRadius={36} outerRadius={58} paddingAngle={2}>
          {filtered.map((_, i) => (
            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 8 }}
          labelStyle={{ color: "#FAFAFA" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

function MiniBars({ data }: { data: ChartSlice[] }) {
  const t = useTranslations("areas");
  if (!data.some((d) => Number(d.value) > 0)) {
    return <p className="flex h-full items-center justify-center text-xs text-[#52525B]">{t("noChartData")}</p>;
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid stroke="#27272A" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: "#71717A", fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: "#71717A", fontSize: 11 }} axisLine={false} tickLine={false} width={32} />
        <Tooltip
          contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 8 }}
          labelStyle={{ color: "#FAFAFA" }}
        />
        <Bar dataKey="value" fill="#2DD4BF" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
