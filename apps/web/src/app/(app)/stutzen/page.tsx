"use client";

import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

type StatusKey = "not_started" | "started" | "fully_pulled";

type StatusCounts = Record<StatusKey, number>;

type ThicknessCounts = { thick: number; thin: number; unknown: number };

type ExportColumn = { key: string; label: string };

type AreaOption = {
  key: string;
  name: string;
  deck: string;
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
  pulled_start: string;
  pulled_end: string;
};

const STATUS_OPTIONS: { key: StatusKey; label: string }[] = [
  { key: "not_started", label: "El nem indított" },
  { key: "started", label: "Elindított" },
  { key: "fully_pulled", label: "Teljesen behúzott" },
];

const PREVIEW_COLS = ["Kabelnr", "Category", "Thickness", "Length_m", "Liste"];

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

export default function StutzenPage() {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("AND");
  const [statuses, setStatuses] = useState<StatusKey[]>([
    "not_started",
    "started",
    "fully_pulled",
  ]);
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
  const [areas, setAreas] = useState<AreaOption[]>([]);
  const [areasSource, setAreasSource] = useState<"upload" | "default" | "empty" | "">("");
  const [areaKey, setAreaKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [routeById, setRouteById] = useState<Record<string, CableRouteDetail | "loading" | "error">>({});

  useEffect(() => {
    api
      .get<{ columns: ExportColumn[]; defaults: string[] }>("/stutzen/export-columns")
      .then((data) => {
        setExportColumns(data.columns || []);
        if (data.defaults?.length) setSelectedColumns(data.defaults);
      })
      .catch(() => {
        setExportColumns(
          DEFAULT_EXPORT_KEYS.map((key) => ({
            key,
            label: key,
          }))
        );
      });
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

  const selectedArea = useMemo(
    () => areas.find((a) => a.key === areaKey) || null,
    [areas, areaKey]
  );

  const selectedSet = useMemo(() => new Set(statuses), [statuses]);

  function toggleColumn(key: string) {
    setSelectedColumns((prev) => {
      if (prev.includes(key)) {
        if (prev.length === 1) return prev;
        return prev.filter((c) => c !== key);
      }
      return [...prev, key];
    });
  }

  async function run(nextStatuses: StatusKey[] = statuses, keepPreview = false) {
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
      }>("/stutzen/filter", {
        nodes_text: text,
        unique_only: true,
        mode,
        statuses: nextStatuses,
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
      setError(e instanceof Error ? e.message : "Szűrés sikertelen");
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
      let next: StatusKey[];
      if (prev.includes(key)) {
        if (prev.length === 1) return prev;
        next = prev.filter((s) => s !== key);
      } else {
        next = [...prev, key];
      }
      if (nodes.length) void run(next, true);
      return next;
    });
  }

  async function exportExcel() {
    setExporting(true);
    setError("");
    try {
      await api.downloadPost(
        "/stutzen/export",
        {
          nodes_text: text,
          unique_only: true,
          mode,
          statuses,
          columns: selectedColumns,
        },
        `stutzen_${nodes.join("_") || "szures"}.xlsx`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export sikertelen");
    } finally {
      setExporting(false);
    }
  }

  function insertFromArea(kind: AreaInsertKind) {
    if (!selectedArea) {
      setError("Válassz helyiséget a beszúráshoz.");
      return;
    }
    const picked =
      kind === "bahn" ? selectedArea.bahn : kind === "stuetzen" ? selectedArea.stuetzen : selectedArea.all;
    if (!picked.length) {
      setError(
        kind === "bahn"
          ? "Ehhez a helyiséghez nincs Bahn."
          : kind === "stuetzen"
            ? "Ehhez a helyiséghez nincs Stütze."
            : "Ehhez a helyiséghez nincs Bahn / Stütze adat."
      );
      return;
    }
    setError("");
    setText(picked.join("; "));
    // Room insert usually means “any of these nodes” — switch to OR.
    setMode("OR");
  }

  return (
    <div>
      <TopProgress show={loading || exporting} />
      <h1 className="mb-1 text-2xl font-semibold tracking-tight text-[#FAFAFA]">Stützen / Bahn szűrő</h1>
      <div className="mb-4 space-y-2 text-sm leading-relaxed text-[#A1A1AA]">
        <p>A Stützenszámokat és Bahn számokat pontosvesszővel elválasztva kell megadni.</p>
        <p>
          A kapcsolót <span className="text-[#FAFAFA]">AND (mind)</span> értékre állítva azokat a kábeleket
          kapod, amelyek nyomvonalán <span className="text-[#FAFAFA]">mindegyik</span> megadott érték
          szerepel. <span className="text-[#FAFAFA]">OR (bármelyik)</span> esetén elég, ha a nyomvonalon{" "}
          <span className="text-[#FAFAFA]">bármelyik</span> megadott érték megjelenik.
        </p>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          className="h-9 min-w-[220px] flex-1 rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]"
          value={areaKey}
          onChange={(e) => setAreaKey(e.target.value)}
          disabled={!areas.length}
        >
          <option value="">
            {areas.length
              ? "Helyiség választása…"
              : areasSource === "empty"
                ? "Nincs helyiségadat"
                : "Helyiséglista betöltése…"}
          </option>
          {areas.map((a) => (
            <option key={a.key} value={a.key}>
              {a.label || a.name}
              {a.all_count ? ` (${a.all_count})` : ""}
            </option>
          ))}
        </select>
        <Button
          type="button"
          variant="outline"
          disabled={!selectedArea || !selectedArea.bahn_count}
          onClick={() => insertFromArea("bahn")}
        >
          Bahn ({selectedArea?.bahn_count ?? 0})
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!selectedArea || !selectedArea.stuetzen_count}
          onClick={() => insertFromArea("stuetzen")}
        >
          Stützen ({selectedArea?.stuetzen_count ?? 0})
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!selectedArea || !selectedArea.all_count}
          onClick={() => insertFromArea("both")}
        >
          Mindkettő ({selectedArea?.all_count ?? 0})
        </Button>
      </div>
      <p className="mb-3 text-xs text-[#71717A]">
        {areasSource === "default"
          ? "Beépített Helység adatok (amíg nincs frissebb feltöltés)."
          : areasSource === "upload"
            ? "Feltöltött Helység Excel."
            : null}
        {selectedArea
          ? ` ${selectedArea.label}: ${selectedArea.bahn_count} Bahn · ${selectedArea.stuetzen_count} Stütze — beszúrás után a mód OR-re vált.`
          : null}
      </p>

      <textarea
        className="mb-3 h-28 w-full rounded-md border border-[#27272A] bg-[#09090B] p-3 font-mono-data text-sm text-[#FAFAFA] placeholder:text-[#52525B]"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="1EDV606; 1E2104"
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          className="h-9 rounded-md border border-[#27272A] bg-[#09090B] px-2 text-sm text-[#FAFAFA]"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          <option value="AND">AND — mind</option>
          <option value="OR">OR — bármelyik</option>
        </select>
        {STATUS_OPTIONS.map((opt) => {
          const checked = selectedSet.has(opt.key);
          const count = statusCounts[opt.key];
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
              <span className="font-mono-data text-xs text-[#71717A]">({count})</span>
            </label>
          );
        })}
        <Button onClick={() => void run()} disabled={loading}>
          Szűrés
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!nodes.length || exporting || selectedColumns.length === 0}
          onClick={exportExcel}
        >
          <Download size={16} />
          Excel
        </Button>
        <Button type="button" variant="ghost" onClick={() => setShowExportCols((v) => !v)}>
          {showExportCols ? "Oszlopok elrejtése" : "Export oszlopok"}
        </Button>
      </div>

      {showExportCols && (
        <div className="mb-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">
            Mely adatok kerüljenek az Excelbe?
          </p>
          <div className="flex flex-wrap gap-2">
            {(exportColumns.length ? exportColumns : DEFAULT_EXPORT_KEYS.map((key) => ({ key, label: key }))).map(
              (col) => {
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
              }
            )}
          </div>
        </div>
      )}

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {hasResult && (
        <div className="mb-4 space-y-3">
          <p className="text-xs text-[#71717A]">
            Keresett: {nodes.join("; ") || "—"}
            {matchedTotal > 0 ? ` · ${matchedTotal.toLocaleString()} kábel` : ""}
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
              <p className="mb-3 text-xs uppercase tracking-wide text-[#71717A]">Vastagság</p>
              <div className="flex flex-wrap gap-6">
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#FAFAFA]">
                    {thicknessCounts.thick.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">vastag</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#FAFAFA]">
                    {thicknessCounts.thin.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">vékony</p>
                </div>
                {thicknessCounts.unknown > 0 && (
                  <div>
                    <p className="text-2xl font-semibold tabular-nums text-[#FAFAFA]">
                      {thicknessCounts.unknown.toLocaleString()}
                    </p>
                    <p className="text-sm text-[#A1A1AA]">ismeretlen</p>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-4">
              <p className="mb-3 text-xs uppercase tracking-wide text-[#71717A]">Behúzás státusz</p>
              <div className="flex flex-wrap gap-6">
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#A1A1AA]">
                    {statusCounts.not_started.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">nincs elindítva</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#F97316]">
                    {statusCounts.started.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">elindítva</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-[#2DD4BF]">
                    {statusCounts.fully_pulled.toLocaleString()}
                  </p>
                  <p className="text-sm text-[#A1A1AA]">teljesen behúzva</p>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" onClick={() => setShowPreview((v) => !v)}>
              {showPreview ? "Előnézet elrejtése" : "Kábel előnézet"}
            </Button>
            {showPreview && (
              <p className="text-xs text-[#71717A]">
                {total.toLocaleString()} megjelenítve
                {rows.length > 0 ? " · Kattints egy kábelre a nyomvonalhoz." : ""}
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
              return <p className="text-sm text-[#71717A]">Nyomvonal betöltése…</p>;
            }
            if (detail === "error") {
              return <p className="text-sm text-[#F87171]">Nem sikerült betölteni a nyomvonalat.</p>;
            }
            return (
              <div className="space-y-2">
                <p className="text-sm text-[#FAFAFA]">{detail.status_message || detail.status_label}</p>
                {(detail.pulled_start || detail.pulled_end) && (
                  <p className="text-xs text-[#71717A]">
                    Behúzott szakasz:{" "}
                    <span className="font-mono-data text-[#FAFAFA]">
                      {detail.pulled_start || "—"} → {detail.pulled_end || "—"}
                    </span>
                  </p>
                )}
                <div
                  className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
                  dangerouslySetInnerHTML={{ __html: detail.route_html || detail.route || "—" }}
                />
                <p className="text-xs text-[#52525B]">Narancs = behúzott szakasz a nyomvonalon.</p>
              </div>
            );
          }}
        />
      )}
    </div>
  );
}
