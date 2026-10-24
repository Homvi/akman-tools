"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { Download, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { displayText, isBlankDisplay, isRouteMissing } from "@/lib/display";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

type StatusKey = "not_started" | "started" | "fully_pulled";
type CardLang = "en" | "hu" | "de";
type ExportColumn = { key: string; label: string };
type StatusCounts = Record<StatusKey, number>;
type ThicknessCounts = { thick: number; thin: number; unknown: number };

type AreaOption = {
  key: string;
  name: string;
  label: string;
  bahn: string[];
  stuetzen: string[];
  all: string[];
  bahn_count: number;
  stuetzen_count: number;
  all_count: number;
};

type AreaInsertKind = "bahn" | "stuetzen" | "both";

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

type FilterOptions = {
  devices: string[];
  thickness: string[];
  categories: string[];
  stop_stuetzen: string[];
};

const PREVIEW_COLS = ["Kabelnr", "Category", "Thickness", "Length_m", "Liste", "Geraet_A", "Geraet_E"];

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

function toggleInList(list: string[], value: string, minOne = false): string[] {
  if (list.includes(value)) {
    if (minOne && list.length === 1) return list;
    return list.filter((v) => v !== value);
  }
  return [...list, value];
}

export default function FilterPage() {
  const t = useTranslations("filterPage");
  const ts = useTranslations("stutzen");
  const tc = useTranslations("common");

  const statusOptions: { key: StatusKey; label: string }[] = [
    { key: "not_started", label: ts("statusNotStarted") },
    { key: "started", label: ts("statusStarted") },
    { key: "fully_pulled", label: ts("statusFully") },
  ];

  const [text, setText] = useState("");
  const [mode, setMode] = useState("AND");
  const [statuses, setStatuses] = useState<StatusKey[]>(["not_started", "started", "fully_pulled"]);
  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [deviceQuery, setDeviceQuery] = useState("");
  const [deviceOpen, setDeviceOpen] = useState(false);
  const [selectedThickness, setSelectedThickness] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedStops, setSelectedStops] = useState<string[]>([]);
  const [stopQuery, setStopQuery] = useState("");

  const [options, setOptions] = useState<FilterOptions>({
    devices: [],
    thickness: [],
    categories: [],
    stop_stuetzen: [],
  });
  const [areas, setAreas] = useState<AreaOption[]>([]);
  const [areasSource, setAreasSource] = useState<"upload" | "default" | "empty" | "">("");
  const [areaKey, setAreaKey] = useState("");

  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [nodes, setNodes] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [matchedTotal, setMatchedTotal] = useState(0);
  const [statusCounts, setStatusCounts] = useState<StatusCounts>({
    not_started: 0,
    started: 0,
    fully_pulled: 0,
  });
  const [thicknessCounts, setThicknessCounts] = useState<ThicknessCounts>({
    thick: 0,
    thin: 0,
    unknown: 0,
  });
  const [hasResult, setHasResult] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [exportColumns, setExportColumns] = useState<ExportColumn[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>(DEFAULT_EXPORT_KEYS);
  const [showExportCols, setShowExportCols] = useState(false);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [pdfExporting, setPdfExporting] = useState(false);
  const [cardLang, setCardLang] = useState<CardLang>("en");
  const [filterNote, setFilterNote] = useState("");
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [routeById, setRouteById] = useState<Record<string, CableRouteDetail | "loading" | "error">>({});

  useEffect(() => {
    api
      .get<{ columns: ExportColumn[]; defaults: string[] }>("/filter/export-columns")
      .then((data) => {
        setExportColumns(data.columns || []);
        if (data.defaults?.length) setSelectedColumns(data.defaults);
      })
      .catch(() => {
        setExportColumns(DEFAULT_EXPORT_KEYS.map((key) => ({ key, label: key })));
      });
    api
      .get<FilterOptions>("/filters/options")
      .then((data) =>
        setOptions({
          devices: data.devices || [],
          thickness: data.thickness || [],
          categories: data.categories || [],
          stop_stuetzen: data.stop_stuetzen || [],
        })
      )
      .catch(() => undefined);
    api
      .get<{ areas: AreaOption[]; source?: "upload" | "default" | "empty" }>("/areas/list")
      .then((data) => {
        setAreas(data.areas || []);
        setAreasSource(data.source || (data.areas?.length ? "upload" : "empty"));
      })
      .catch(() => {
        setAreas([]);
        setAreasSource("empty");
      });
  }, []);

  const selectedArea = useMemo(() => areas.find((a) => a.key === areaKey) || null, [areas, areaKey]);
  const selectedSet = useMemo(() => new Set(statuses), [statuses]);

  const deviceSuggestions = useMemo(() => {
    const needle = deviceQuery.trim().toLowerCase();
    const pool = options.devices.filter((d) => !selectedDevices.includes(d));
    if (!needle) return pool.slice(0, 40);
    return pool.filter((d) => d.toLowerCase().includes(needle)).slice(0, 40);
  }, [options.devices, deviceQuery, selectedDevices]);

  const stopSuggestions = useMemo(() => {
    const needle = stopQuery.trim().toLowerCase();
    const pool = options.stop_stuetzen.filter((s) => !selectedStops.includes(s));
    if (!needle) return pool.slice(0, 40);
    return pool.filter((s) => s.toLowerCase().includes(needle)).slice(0, 40);
  }, [options.stop_stuetzen, stopQuery, selectedStops]);

  function filterBody(extra: Record<string, unknown> = {}) {
    return {
      nodes_text: text,
      unique_only: true,
      mode,
      statuses,
      devices: selectedDevices,
      thickness: selectedThickness,
      categories: selectedCategories,
      stop_stuetzen: selectedStops,
      ...extra,
    };
  }

  function canRun(): boolean {
    if (text.trim() || selectedDevices.length || selectedThickness.length || selectedCategories.length || selectedStops.length) {
      return true;
    }
    const all = new Set(["not_started", "started", "fully_pulled"]);
    return statuses.length > 0 && !(statuses.length === 3 && statuses.every((s) => all.has(s)));
  }

  async function run(nextStatuses: StatusKey[] = statuses, keepPreview = false) {
    if (
      !text.trim() &&
      !selectedDevices.length &&
      !selectedThickness.length &&
      !selectedCategories.length &&
      !selectedStops.length &&
      nextStatuses.length === 3
    ) {
      setError(t("needFilter"));
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api.post<{
        rows: Record<string, unknown>[];
        nodes: string[];
        total: number;
        matched_total?: number;
        status_counts?: StatusCounts;
        thickness_counts?: ThicknessCounts;
      }>("/filter/query", {
        ...filterBody({ statuses: nextStatuses }),
        page: 1,
        page_size: 200,
      });
      setRows(data.rows);
      setNodes(data.nodes || []);
      setTotal(data.total ?? data.rows.length);
      setMatchedTotal(data.matched_total ?? data.total ?? data.rows.length);
      setStatusCounts({
        not_started: data.status_counts?.not_started ?? 0,
        started: data.status_counts?.started ?? 0,
        fully_pulled: data.status_counts?.fully_pulled ?? 0,
      });
      setThicknessCounts({
        thick: data.thickness_counts?.thick ?? 0,
        thin: data.thickness_counts?.thin ?? 0,
        unknown: data.thickness_counts?.unknown ?? 0,
      });
      setHasResult(true);
      if (!keepPreview) setShowPreview(false);
      setExpandedId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("filterFailed"));
      setHasResult(false);
      setShowPreview(false);
    } finally {
      setLoading(false);
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

  function onToggleStatus(key: StatusKey) {
    setStatuses((prev) => {
      const next = toggleInList(prev, key, true) as StatusKey[];
      if (hasResult) void run(next, true);
      return next;
    });
  }

  function toggleColumn(key: string) {
    setSelectedColumns((prev) => toggleInList(prev, key, true));
  }

  function defaultFilterNote() {
    const statusLabels = statuses
      .map((key) => statusOptions.find((o) => o.key === key)?.label || key)
      .join(" + ");
    const parts = [
      nodes.length ? nodes.join("; ") : text.trim() || null,
      selectedDevices.length ? selectedDevices.slice(0, 5).join(", ") : null,
      mode,
      statusLabels,
    ].filter(Boolean);
    return parts.join(" · ");
  }

  async function exportKurzliste() {
    setExporting(true);
    setError("");
    try {
      await api.downloadPost("/filter/export", filterBody({ columns: selectedColumns }), "kurzliste.xlsx");
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  async function exportPullCards() {
    setPdfExporting(true);
    setError("");
    try {
      await api.downloadPost(
        "/filter/pull-cards",
        filterBody({
          filter_note: filterNote.trim() || defaultFilterNote(),
          lang: cardLang,
        }),
        "filter_pull_cards.pdf"
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : tc("exportFailed"));
    } finally {
      setPdfExporting(false);
    }
  }

  function insertFromArea(kind: AreaInsertKind) {
    if (!selectedArea) {
      setError(ts("needArea"));
      return;
    }
    const picked =
      kind === "bahn" ? selectedArea.bahn : kind === "stuetzen" ? selectedArea.stuetzen : selectedArea.all;
    if (!picked.length) {
      setError(kind === "bahn" ? ts("noBahn") : kind === "stuetzen" ? ts("noStuetze") : ts("noBahnStuetze"));
      return;
    }
    setError("");
    setText(picked.join("; "));
    setMode("OR");
  }

  const exportReady = hasResult && matchedTotal > 0;

  return (
    <div>
      <TopProgress show={loading || exporting || pdfExporting} />
      <h1 className="mb-1 text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
      <p className="mb-4 text-sm text-[#A1A1AA]">{t("subtitle")}</p>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          className="h-9 min-w-[220px] flex-1 rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]"
          value={areaKey}
          onChange={(e) => setAreaKey(e.target.value)}
          disabled={!areas.length}
        >
          <option value="">
            {areas.length ? ts("pickArea") : areasSource === "empty" ? ts("noAreas") : ts("loadingAreas")}
          </option>
          {areas.map((a) => (
            <option key={a.key} value={a.key}>
              {a.label || a.name}
              {a.all_count ? ` (${a.all_count})` : ""}
            </option>
          ))}
        </select>
        <Button type="button" variant="outline" disabled={!selectedArea?.bahn_count} onClick={() => insertFromArea("bahn")}>
          {ts("bahn", { count: selectedArea?.bahn_count ?? 0 })}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!selectedArea?.stuetzen_count}
          onClick={() => insertFromArea("stuetzen")}
        >
          {ts("stuetzen", { count: selectedArea?.stuetzen_count ?? 0 })}
        </Button>
        <Button type="button" variant="outline" disabled={!selectedArea?.all_count} onClick={() => insertFromArea("both")}>
          {ts("both", { count: selectedArea?.all_count ?? 0 })}
        </Button>
      </div>

      <textarea
        className="mb-3 h-24 w-full rounded-md border border-[#27272A] bg-[#09090B] p-3 font-mono-data text-sm text-[#FAFAFA] placeholder:text-[#52525B]"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t("nodesPlaceholder")}
      />

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <select
          className="h-9 rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="AND">{ts("modeAnd")}</option>
          <option value="OR">{ts("modeOr")}</option>
        </select>
        {statusOptions.map((opt) => {
          const checked = selectedSet.has(opt.key);
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
                onChange={() => onToggleStatus(opt.key)}
              />
              <span>{opt.label}</span>
              <span className="font-mono-data text-xs text-[#71717A]">({statusCounts[opt.key]})</span>
            </label>
          );
        })}
      </div>

      <div className="mb-3 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{t("devices")}</p>
        <div className="relative mb-2 max-w-md">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#71717A]" />
          <Input
            value={deviceQuery}
            onChange={(e) => {
              setDeviceQuery(e.target.value);
              setDeviceOpen(true);
            }}
            onFocus={() => setDeviceOpen(true)}
            placeholder={t("deviceSearch")}
            className="h-8 pl-7 text-sm"
          />
          {deviceOpen && deviceSuggestions.length > 0 && (
            <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-[#27272A] bg-[#09090B] py-1 shadow-lg">
              {deviceSuggestions.map((name) => (
                <li key={name}>
                  <button
                    type="button"
                    className="w-full px-3 py-1.5 text-left text-sm text-[#E4E4E7] hover:bg-[#18181B]"
                    onClick={() => {
                      setSelectedDevices((prev) => [...prev, name]);
                      setDeviceQuery("");
                      setDeviceOpen(false);
                    }}
                  >
                    {name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {selectedDevices.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setSelectedDevices((prev) => prev.filter((d) => d !== name))}
              className="inline-flex items-center gap-1 rounded border border-[#2DD4BF]/40 bg-[#042F2E]/40 px-2 py-0.5 text-xs text-[#5EEAD4]"
            >
              {name}
              <X className="h-3 w-3" />
            </button>
          ))}
        </div>
      </div>

      <div className="mb-3 grid gap-3 lg:grid-cols-3">
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{t("thickness")}</p>
          <div className="flex flex-wrap gap-1">
            {options.thickness.map((val) => {
              const checked = selectedThickness.includes(val);
              return (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSelectedThickness((prev) => toggleInList(prev, val))}
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[11px]",
                    checked
                      ? "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                      : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                  )}
                >
                  {val}
                </button>
              );
            })}
            {!options.thickness.length && <span className="text-xs text-[#52525B]">—</span>}
          </div>
        </div>
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{t("category")}</p>
          <div className="flex max-h-28 flex-wrap gap-1 overflow-y-auto">
            {options.categories.map((val) => {
              const checked = selectedCategories.includes(val);
              return (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSelectedCategories((prev) => toggleInList(prev, val))}
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[11px]",
                    checked
                      ? "border-[#2DD4BF]/60 bg-[#2DD4BF]/15 text-[#5EEAD4]"
                      : "border-[#27272A] text-[#71717A] hover:text-[#A1A1AA]"
                  )}
                >
                  {val}
                </button>
              );
            })}
            {!options.categories.length && <span className="text-xs text-[#52525B]">—</span>}
          </div>
        </div>
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{t("stopStuetze")}</p>
          <Input
            value={stopQuery}
            onChange={(e) => setStopQuery(e.target.value)}
            placeholder={t("stopSearch")}
            className="mb-2 h-8 text-sm"
          />
          <div className="mb-2 max-h-24 overflow-y-auto">
            {stopSuggestions.slice(0, 20).map((name) => (
              <button
                key={name}
                type="button"
                className="mr-1 mb-1 rounded border border-[#27272A] px-1.5 py-0.5 text-[10px] text-[#A1A1AA] hover:border-[#52525B]"
                onClick={() => {
                  setSelectedStops((prev) => [...prev, name]);
                  setStopQuery("");
                }}
              >
                + {name}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1">
            {selectedStops.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setSelectedStops((prev) => prev.filter((s) => s !== name))}
                className="inline-flex items-center gap-1 rounded border border-[#F97316]/40 bg-[#F97316]/10 px-2 py-0.5 text-xs text-[#FDBA74]"
              >
                {name}
                <X className="h-3 w-3" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button onClick={() => void run()} disabled={loading || !canRun()}>
          {ts("filter")}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!exportReady || exporting || selectedColumns.length === 0}
          onClick={() => void exportKurzliste()}
        >
          <Download size={16} />
          {t("kurzliste")}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setShowExportCols((v) => !v)}>
          {showExportCols ? ts("hideCols") : ts("exportCols")}
        </Button>
      </div>

      <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-[#A1A1AA]">
            {ts("pullCardsLang")}
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
            disabled={!exportReady || pdfExporting}
            onClick={() => void exportPullCards()}
          >
            <Download size={16} />
            {ts("pullCards")}
          </Button>
        </div>
        <label className="block text-xs uppercase tracking-wide text-[#71717A]">
          {ts("filterNote")}
          <textarea
            className="mt-1 h-16 w-full rounded-md border border-[#27272A] bg-[#09090B] p-2 font-mono-data text-sm text-[#FAFAFA] placeholder:text-[#52525B]"
            value={filterNote}
            onChange={(e) => setFilterNote(e.target.value)}
            placeholder={ts("filterNotePlaceholder")}
          />
        </label>
        <p className="mt-1 text-xs text-[#71717A]">{ts("filterNoteHelp")}</p>
      </div>

      {showExportCols && (
        <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">{ts("exportColsHelp")}</p>
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

      {hasResult && (
        <div className="mb-4 space-y-3">
          <p className="text-xs text-[#71717A]">
            {t("resultSummary", {
              nodes: nodes.join("; ") || "—",
              devices: selectedDevices.length ? selectedDevices.join(", ") : "—",
              count: matchedTotal.toLocaleString(),
            })}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
              <p className="mb-3 text-xs uppercase tracking-wide text-[#71717A]">{ts("thickness")}</p>
              <div className="flex flex-wrap gap-6">
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#FAFAFA]">
                    {thicknessCounts.thick.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">{ts("thick")}</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#FAFAFA]">
                    {thicknessCounts.thin.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">{ts("thin")}</p>
                </div>
              </div>
            </div>
            <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
              <p className="mb-3 text-xs uppercase tracking-wide text-[#71717A]">{ts("pullStatus")}</p>
              <div className="flex flex-wrap gap-6">
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#A1A1AA]">
                    {statusCounts.not_started.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">{ts("notStarted")}</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#F97316]">
                    {statusCounts.started.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">{ts("started")}</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#2DD4BF]">
                    {statusCounts.fully_pulled.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">{ts("fullyPulled")}</p>
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" onClick={() => setShowPreview((v) => !v)}>
              {showPreview ? ts("hidePreview") : ts("showPreview")}
            </Button>
            {showPreview && (
              <p className="text-xs text-[#71717A]">
                {ts("shown", { count: total.toLocaleString() })}
                {rows.length > 0 ? ts("clickHint") : ""}
              </p>
            )}
          </div>
        </div>
      )}

      {hasResult && showPreview && (
        <DataTable
          rows={rows}
          columns={PREVIEW_COLS}
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
                {(!isBlankDisplay(detail.pulled_start) || !isBlankDisplay(detail.pulled_end)) &&
                  !isRouteMissing(detail) && (
                    <p className="text-xs text-[#71717A]">
                      {tc("pulledSpan")}{" "}
                      <span className="font-mono-data text-[#FAFAFA]">
                        {displayText(detail.pulled_start)} → {displayText(detail.pulled_end)}
                      </span>
                    </p>
                  )}
                {isRouteMissing(detail) ? (
                  <p className="rounded-md border border-[#F97316]/40 bg-[#F97316]/10 p-3 text-sm text-[#FDBA74]">
                    {detail.route_warning || tc("routeMissing")}
                  </p>
                ) : (
                  <>
                    <div
                      className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
                      dangerouslySetInnerHTML={{ __html: detail.route_html || displayText(detail.route) }}
                    />
                    <p className="text-xs text-[#52525B]">{tc("pulledHint")}</p>
                  </>
                )}
              </div>
            );
          }}
        />
      )}
    </div>
  );
}
