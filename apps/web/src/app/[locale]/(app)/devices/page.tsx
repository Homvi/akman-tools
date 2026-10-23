"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Search, X } from "lucide-react";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

const COLS = ["Kabelnr", "Category", "Length_m", "Liste", "Geraet_A", "Geraet_E"];
const PAGE_SIZE = 200;
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
type StatusKey = "not_started" | "started" | "fully_pulled";
type CardLang = "en" | "hu" | "de";
type ExportColumn = { key: string; label: string };

type ProgressFilter = "" | "at" | "started" | "not_started";

type PriorityDevice = {
  name: string;
  matched: boolean;
  total: number;
  wired: number;
  wired_a: number;
  wired_e: number;
  pulled: number;
  pulled_a: number;
  pulled_e: number;
  device_at: number;
  device_started: number;
  device_not_started: number;
};

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

export default function DevicesPage() {
  const t = useTranslations("devices");
  const tc = useTranslations("common");
  const progressLabel: Record<Exclude<ProgressFilter, "">, string> = {
    at: t("filterAt"),
    started: t("filterStarted"),
    not_started: t("filterNotStarted"),
  };
  const [devices, setDevices] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("");
  const [progressFilter, setProgressFilter] = useState<ProgressFilter>("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [thickCount, setThickCount] = useState(0);
  const [thinCount, setThinCount] = useState(0);
  const [atDevice, setAtDevice] = useState(0);
  const [started, setStarted] = useState(0);
  const [notStarted, setNotStarted] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [routeById, setRouteById] = useState<Record<string, CableRouteDetail | "loading" | "error">>({});
  const [priority, setPriority] = useState<PriorityDevice[]>([]);
  const [priorityLoading, setPriorityLoading] = useState(false);
  const [exportStatuses, setExportStatuses] = useState<StatusKey[]>([
    "not_started",
    "started",
    "fully_pulled",
  ]);
  const [exportColumns, setExportColumns] = useState<ExportColumn[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>(DEFAULT_EXPORT_KEYS);
  const [showExportCols, setShowExportCols] = useState(false);
  const [showDeviceExportCols, setShowDeviceExportCols] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [cardLang, setCardLang] = useState<CardLang>("en");
  const boxRef = useRef<HTMLDivElement>(null);

  const statusOptions: { key: StatusKey; label: string }[] = [
    { key: "not_started", label: t("statusNotStarted") },
    { key: "started", label: t("statusStarted") },
    { key: "fully_pulled", label: t("statusFully") },
  ];

  useEffect(() => {
    api
      .get<{ devices?: string[] }>("/filters/options")
      .then((o) => setDevices(o.devices || []))
      .catch(() => setDevices([]));
    api
      .get<{ columns: ExportColumn[]; defaults: string[] }>("/devices/priority/export-columns")
      .then((data) => {
        setExportColumns(data.columns || []);
        if (data.defaults?.length) setSelectedColumns(data.defaults);
      })
      .catch(() => {
        setExportColumns(DEFAULT_EXPORT_KEYS.map((key) => ({ key, label: key })));
      });
  }, []);

  useEffect(() => {
    setPriorityLoading(true);
    api
      .get<{ devices: PriorityDevice[] }>("/devices/priority")
      .then((d) => setPriority(d.devices || []))
      .catch(() => setPriority([]))
      .finally(() => setPriorityLoading(false));
  }, []);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const filteredDevices = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return devices.slice(0, 80);
    return devices.filter((d) => d.toLowerCase().includes(q)).slice(0, 80);
  }, [devices, query]);

  async function loadPreview(device: string, p = 1, progress: ProgressFilter = progressFilter) {
    if (!device) {
      setRows([]);
      setTotal(0);
      setThickCount(0);
      setThinCount(0);
      setAtDevice(0);
      setStarted(0);
      setNotStarted(0);
      setPages(1);
      setPage(1);
      return;
    }
    setLoading(true);
    setError("");
    setExpandedId(null);
    try {
      const data = await api.get<{
        rows: Record<string, unknown>[];
        total: number;
        pages: number;
        page: number;
        metrics?: {
          thick_count?: number;
          thin_count?: number;
          device_at?: number;
          device_started?: number;
          device_not_started?: number;
        };
      }>(
        `/cables${qs({
          devices: device,
          page: p,
          page_size: PAGE_SIZE,
          device_progress: progress || undefined,
        })}`
      );
      setRows(data.rows);
      setTotal(data.total);
      setThickCount(Number(data.metrics?.thick_count ?? 0));
      setThinCount(Number(data.metrics?.thin_count ?? 0));
      setAtDevice(Number(data.metrics?.device_at ?? 0));
      setStarted(Number(data.metrics?.device_started ?? 0));
      setNotStarted(Number(data.metrics?.device_not_started ?? 0));
      setPages(data.pages);
      setPage(data.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : tc("loadFailed"));
      setRows([]);
      setTotal(0);
      setThickCount(0);
      setThinCount(0);
      setAtDevice(0);
      setStarted(0);
      setNotStarted(0);
    } finally {
      setLoading(false);
    }
  }

  function pickDevice(name: string) {
    setSelected(name);
    setQuery(name);
    setOpen(false);
    setProgressFilter("");
    void loadPreview(name, 1, "");
  }

  function toggleExportStatus(key: StatusKey) {
    setExportStatuses((prev) => {
      if (prev.includes(key)) {
        if (prev.length === 1) return prev;
        return prev.filter((k) => k !== key);
      }
      return [...prev, key];
    });
  }

  function toggleColumn(key: string) {
    setSelectedColumns((prev) => {
      if (prev.includes(key)) {
        if (prev.length === 1) return prev;
        return prev.filter((k) => k !== key);
      }
      return [...prev, key];
    });
  }

  async function exportPriority() {
    setExporting(true);
    setError("");
    try {
      await api.downloadPost(
        "/devices/priority/export",
        {
          devices: priority.map((p) => p.name),
          statuses: exportStatuses,
          columns: selectedColumns,
        },
        "priority_devices.xlsx"
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  async function exportPriorityPullCards() {
    setExporting(true);
    setError("");
    try {
      await api.downloadPost(
        "/devices/priority/pull-cards",
        {
          devices: priority.map((p) => p.name),
          statuses: exportStatuses,
          lang: cardLang,
          filter_note: `Priority · ${exportStatuses.join("+")}`,
        },
        "priority_pull_cards.pdf"
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  async function exportSelectedDevice() {
    if (!selected) return;
    setExporting(true);
    setError("");
    try {
      await api.downloadPost(
        "/devices/export",
        {
          device: selected,
          device_progress: progressFilter || null,
          columns: selectedColumns,
        },
        `device_${slug}.xlsx`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  async function exportSelectedPullCards() {
    if (!selected) return;
    setExporting(true);
    setError("");
    try {
      await api.downloadPost(
        "/devices/pull-cards",
        {
          device: selected,
          device_progress: progressFilter || null,
          lang: cardLang,
          filter_note: selected,
        },
        `device_${slug}_pull_cards.pdf`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : t("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  function clearSelection() {
    setSelected("");
    setQuery("");
    setOpen(false);
    setProgressFilter("");
    void loadPreview("", 1, "");
  }

  function toggleProgress(kind: Exclude<ProgressFilter, "">) {
    if (!selected) return;
    const next: ProgressFilter = progressFilter === kind ? "" : kind;
    setProgressFilter(next);
    void loadPreview(selected, 1, next);
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

  const slug = selected.replace(/[^a-zA-Z0-9-_]+/g, "_").slice(0, 80) || "device";

  const prioritySorted = [...priority].sort((a, b) => {
    if (b.total !== a.total) return b.total - a.total;
    return a.name.localeCompare(b.name);
  });

  return (
    <div>
      <TopProgress show={loading || priorityLoading || exporting} />
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
        <p className="mt-1 text-sm text-[#A1A1AA]">
          {t("subtitle", { count: devices.length.toLocaleString() })}
        </p>
        <p className="mt-1 text-sm text-[#71717A]">
          {t("help")}
        </p>
      </div>

      <section className="mb-8 rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-[#71717A]">{t("priorityTitle")}</h2>
        <p className="mt-1 mb-3 text-sm text-[#A1A1AA]">{t("priorityHelp")}</p>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          {statusOptions.map((opt) => {
            const checked = exportStatuses.includes(opt.key);
            return (
              <label
                key={opt.key}
                className={cn(
                  "inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border px-3 text-sm",
                  checked
                    ? "border-[#2DD4BF]/50 bg-[#042F2E]/40 text-[#FAFAFA]"
                    : "border-[#27272A] bg-[#09090B] text-[#A1A1AA]"
                )}
              >
                <input
                  type="checkbox"
                  className="accent-[#2DD4BF]"
                  checked={checked}
                  onChange={() => toggleExportStatus(opt.key)}
                />
                {opt.label}
              </label>
            );
          })}
          <label className="inline-flex items-center gap-2 text-sm text-[#A1A1AA]">
            {t("pullCardsLang")}
            <select
              className="h-9 rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]"
              value={cardLang}
              onChange={(e) => setCardLang(e.target.value as CardLang)}
            >
              <option value="en">EN</option>
              <option value="hu">HU</option>
              <option value="de">DE</option>
            </select>
          </label>
          <Button
            type="button"
            variant="outline"
            disabled={exporting || !priority.length || selectedColumns.length === 0}
            onClick={() => void exportPriority()}
          >
            <Download size={16} />
            {t("priorityExport")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={exporting || !priority.length}
            onClick={() => void exportPriorityPullCards()}
          >
            <Download size={16} />
            {t("priorityPullCards")}
          </Button>
          <Button type="button" variant="ghost" onClick={() => setShowExportCols((v) => !v)}>
            {showExportCols ? t("hideCols") : t("exportCols")}
          </Button>
        </div>

        {showExportCols && (
          <div className="mb-3 rounded-md border border-[#27272A] bg-[#09090B] p-3">
            <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{t("exportColsHelp")}</p>
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

        <p className="mb-2 flex flex-wrap items-center gap-3 text-xs text-[#71717A]">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-sm bg-[#F97316]/45" />
            {t("priorityPulled")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-sm bg-[#2DD4BF]/40" />
            {t("priorityWired")}
          </span>
          <span>{t("prioritySortHint")}</span>
        </p>

        <div className="overflow-hidden rounded-md border border-[#27272A]">
          {prioritySorted.map((row) => {
            const denom = Math.max(row.total, 1);
            const pulledPct = Math.min(100, (row.pulled / denom) * 100);
            const wiredPct = Math.min(100, (row.wired / denom) * 100);
            return (
              <button
                key={row.name}
                type="button"
                disabled={!row.matched}
                onClick={() => {
                  if (row.matched) pickDevice(row.name);
                }}
                className={cn(
                  "relative block w-full overflow-hidden border-b border-[#27272A] text-left last:border-0",
                  row.matched ? "hover:brightness-110" : "cursor-not-allowed opacity-60"
                )}
              >
                {/* layer 1: odahúzva (pulled) */}
                <span
                  className="pointer-events-none absolute inset-y-0 left-0 bg-[#F97316]/35"
                  style={{ width: `${pulledPct}%` }}
                  aria-hidden
                />
                {/* layer 2: bekötve (wired) */}
                <span
                  className="pointer-events-none absolute inset-y-0 left-0 bg-[#2DD4BF]/30"
                  style={{ width: `${wiredPct}%` }}
                  aria-hidden
                />
                <span className="relative z-10 grid grid-cols-[minmax(0,1.4fr)_auto_minmax(0,1fr)_minmax(0,1fr)] items-center gap-2 px-3 py-2.5 text-sm">
                  <span className="min-w-0 truncate text-[#FAFAFA]">
                    {row.name}
                    {!row.matched && (
                      <span className="ml-2 text-xs text-[#F97316]">{t("priorityMissing")}</span>
                    )}
                  </span>
                  <span className="font-mono-data tabular-nums text-[#E4E4E7]">{row.total}</span>
                  <span className="font-mono-data text-[#E4E4E7]">
                    {row.wired}/{row.total}
                    <span className="ml-1.5 text-xs text-[#A1A1AA]">
                      {t("prioritySideA")} {row.wired_a} · {t("prioritySideE")} {row.wired_e}
                    </span>
                  </span>
                  <span className="font-mono-data text-[#E4E4E7]">
                    {row.pulled}/{row.total}
                    <span className="ml-1.5 text-xs text-[#A1A1AA]">
                      {t("prioritySideA")} {row.pulled_a} · {t("prioritySideE")} {row.pulled_e}
                    </span>
                  </span>
                </span>
              </button>
            );
          })}
          {!priority.length && !priorityLoading && (
            <p className="px-3 py-4 text-sm text-[#71717A]">{tc("noRows")}</p>
          )}
        </div>
      </section>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div ref={boxRef} className="relative min-w-[280px] flex-1">
          <label className="block text-xs text-[#71717A]">
            {t("device")}
            <div className="relative mt-1">
              <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[#52525B]" />
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setOpen(true);
                  if (selected && e.target.value !== selected) setSelected("");
                }}
                onFocus={() => setOpen(true)}
                placeholder={t("typePlaceholder")}
                className="pl-8 pr-9"
                autoComplete="off"
              />
              {(query || selected) && (
                <button
                  type="button"
                  aria-label={tc("clear")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-[#FAFAFA]"
                  onClick={clearSelection}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </label>
          {open && (
            <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-[#27272A] bg-[#0C0C0E] py-1 shadow-lg">
              {filteredDevices.length === 0 ? (
                <li className="px-3 py-2 text-sm text-[#71717A]">{tc("noRows")}</li>
              ) : (
                filteredDevices.map((d) => (
                  <li key={d}>
                    <button
                      type="button"
                      className={cn(
                        "w-full px-3 py-2 text-left text-sm hover:bg-[#18181B]",
                        d === selected ? "bg-[#18181B] text-[#2DD4BF]" : "text-[#E4E4E7]"
                      )}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pickDevice(d)}
                    >
                      {d}
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
        <Button
          variant="outline"
          disabled={!selected || !total || exporting || selectedColumns.length === 0}
          onClick={() => void exportSelectedDevice()}
        >
          <Download size={16} />
          {tc("excel")}
        </Button>
        <Button
          variant="outline"
          disabled={!selected || !total || exporting}
          onClick={() => void exportSelectedPullCards()}
        >
          <Download size={16} />
          {t("pullCards")}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setShowDeviceExportCols((v) => !v)}>
          {showDeviceExportCols ? t("hideCols") : t("deviceExportCols")}
        </Button>
      </div>

      {showDeviceExportCols && (
        <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{t("exportColsHelp")}</p>
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

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {selected && (
        <div className="mb-3 space-y-1 text-sm text-[#A1A1AA]">
          <p>
            <span className="text-[#FAFAFA]">{selected}</span>
            {!progressFilter && (
              <>
                {" "}
                · {t("cablesShown", { count: total.toLocaleString() })} ·{" "}
                <span className="text-[#FAFAFA]">{thickCount}</span> {t("thick")} ·{" "}
                <span className="text-[#FAFAFA]">{thinCount}</span> {t("thin")}
              </>
            )}
          </p>
          <p className="leading-relaxed">
            <button
              type="button"
              className={cn(
                "underline-offset-2 hover:underline",
                progressFilter === "at" ? "font-medium text-[#2DD4BF] underline" : "text-[#2DD4BF]"
              )}
              onClick={() => toggleProgress("at")}
            >
              {t("atDevice", { count: atDevice.toLocaleString() })}
            </button>
            {", "}
            <button
              type="button"
              className={cn(
                "underline-offset-2 hover:underline",
                progressFilter === "started" ? "font-medium text-[#F97316] underline" : "text-[#F97316]"
              )}
              onClick={() => toggleProgress("started")}
            >
              {t("started", { count: started.toLocaleString() })}
            </button>
            {", "}
            <button
              type="button"
              className={cn(
                "underline-offset-2 hover:underline",
                progressFilter === "not_started" ? "font-medium text-[#E4E4E7] underline" : "text-[#A1A1AA]"
              )}
              onClick={() => toggleProgress("not_started")}
            >
              {t("notStarted", { count: notStarted.toLocaleString() })}
            </button>
          </p>
          {progressFilter && (
            <p className="text-xs text-[#71717A]">
              {progressLabel[progressFilter]} · {t("cablesShown", { count: total.toLocaleString() })}.{" "}
              <button
                type="button"
                className="text-[#2DD4BF] underline-offset-2 hover:underline"
                onClick={() => {
                  setProgressFilter("");
                  void loadPreview(selected, 1, "");
                }}
              >
                {t("showAll")}
              </button>
            </p>
          )}
        </div>
      )}

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

      {selected && pages > 1 && (
        <div className="mt-3 flex gap-2">
          <Button
            variant="outline"
            disabled={page <= 1 || loading}
            onClick={() => loadPreview(selected, page - 1, progressFilter)}
          >
            {tc("previous")}
          </Button>
          <Button
            variant="outline"
            disabled={page >= pages || loading}
            onClick={() => loadPreview(selected, page + 1, progressFilter)}
          >
            {tc("next")}
          </Button>
        </div>
      )}
    </div>
  );
}
