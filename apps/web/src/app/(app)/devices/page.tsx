"use client";

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

type ProgressFilter = "" | "at" | "started" | "not_started";

type CableRouteDetail = {
  kabelnr: string;
  status_label: string;
  status_message: string;
  route_html: string;
  route: string;
  pulled_start: string;
  pulled_end: string;
};

const PROGRESS_LABEL: Record<Exclude<ProgressFilter, "">, string> = {
  at: "már a készüléknél",
  started: "elindítva, de még nincs a készüléknél",
  not_started: "még nincs elindítva",
};

export default function DevicesPage() {
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
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get<{ devices?: string[] }>("/filters/options")
      .then((o) => setDevices(o.devices || []))
      .catch(() => setDevices([]));
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
      setError(err instanceof Error ? err.message : "Failed to load");
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

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">Device list</h1>
        <p className="mt-1 text-sm text-[#A1A1AA]">
          Összesen <span className="font-medium text-[#FAFAFA]">{devices.length.toLocaleString()}</span> készülék
        </p>
        <p className="mt-1 text-sm text-[#71717A]">
          Gépelj a készülék / szekrény nevére — a lista élőben szűr. A kábel bekerül, ha bármelyik vége (A
          vagy E) ide megy. A státuszszámokra kattintva szűrhető a lista. Egy kábelre kattintva
          lenyílik a nyomvonal, a behúzott szakasz kiemelésével.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div ref={boxRef} className="relative min-w-[280px] flex-1">
          <label className="block text-xs text-[#71717A]">
            Készülék
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
                placeholder="Kezdj el gépelni…"
                className="pl-8 pr-9"
                autoComplete="off"
              />
              {(query || selected) && (
                <button
                  type="button"
                  aria-label="Törlés"
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
                <li className="px-3 py-2 text-sm text-[#71717A]">Nincs találat</li>
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
          disabled={!selected || !total}
          onClick={() => api.download(`/export/device${qs({ device: selected })}`, `device_${slug}.xlsx`)}
        >
          <Download size={16} />
          Excel
        </Button>
      </div>

      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      {selected && (
        <div className="mb-3 space-y-1 text-sm text-[#A1A1AA]">
          <p>
            <span className="text-[#FAFAFA]">{selected}</span>
            {!progressFilter && (
              <>
                {" "}
                · {total.toLocaleString()} kábel · <span className="text-[#FAFAFA]">{thickCount}</span> vastag ·{" "}
                <span className="text-[#FAFAFA]">{thinCount}</span> vékony
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
              {atDevice.toLocaleString()} kábel már a készüléknél
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
              {started.toLocaleString()} kábel elindítva de még nincs a készüléknél
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
              {notStarted.toLocaleString()} kábel még nincs elindítva
            </button>
          </p>
          {progressFilter && (
            <p className="text-xs text-[#71717A]">
              Szűrve: {PROGRESS_LABEL[progressFilter]} · {total.toLocaleString()} kábel az előnézetben.{" "}
              <button
                type="button"
                className="text-[#2DD4BF] underline-offset-2 hover:underline"
                onClick={() => {
                  setProgressFilter("");
                  void loadPreview(selected, 1, "");
                }}
              >
                Összes mutatása
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

      {selected && pages > 1 && (
        <div className="mt-3 flex gap-2">
          <Button
            variant="outline"
            disabled={page <= 1 || loading}
            onClick={() => loadPreview(selected, page - 1, progressFilter)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={page >= pages || loading}
            onClick={() => loadPreview(selected, page + 1, progressFilter)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
