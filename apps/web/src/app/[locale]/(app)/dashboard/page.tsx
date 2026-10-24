"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ChevronRight, Download, Search } from "lucide-react";
import { api, qs } from "@/lib/api";
import { displayText, isBlankDisplay, isRouteMissing } from "@/lib/display";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";
import { LeaveMissingBox } from "@/components/leave-missing-box";
import { cn } from "@/lib/utils";

type AnschlussOpen = { kabelnr: string; sides: string[]; started?: boolean };

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

const ANSCHLUSS_COLS = ["Kabelnr"];

type Summary = {
  loaded: boolean;
  progress_as_of?: string | null;
  total_length_m?: number;
  fully_pulled_m?: number;
  partially_pulled_m?: number;
  not_started_m?: number;
  pulled_total_m?: number;
  wired_not_verlegt?: string[];
  anschluss_without_verlegt?: AnschlussOpen[];
};

function sideKey(sides: string[]) {
  const hasA = sides.includes("A");
  const hasE = sides.includes("E");
  if (hasA && hasE) return "both";
  if (hasA) return "start";
  if (hasE) return "end";
  return "other";
}

type CableDetail = {
  kabelnr: string;
  status: string;
  status_label: string;
  status_message: string;
  verlegt_date?: string | null;
  stop_date?: string | null;
  route: string;
  route_html: string;
  route_missing?: boolean;
  route_warning?: string;
  pulled_start: string;
  pulled_end: string;
  length_m: number | null;
  category: string;
  liste: string;
  cable_type: string;
  adern: string;
  geraet_a: string;
  geraet_e: string;
  ort_a: string;
  ort_e: string;
  aln_a: string;
  aln_e: string;
};

function fmtM(n: number | undefined | null) {
  return Number(n || 0).toLocaleString("hu-HU", { maximumFractionDigits: 1 });
}

function CableCard({ cable }: { cable: CableDetail }) {
  const t = useTranslations("dashboard");
  const tc = useTranslations("common");
  return (
    <div className="space-y-4 rounded-md border border-[#27272A] bg-[#0C0C0E] p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <div className="font-mono-data text-xl text-[#FAFAFA]">{cable.kabelnr}</div>
          <div className="mt-1 text-sm text-[#A1A1AA]">
            {[cable.cable_type || null, cable.adern ? tc("cores", { count: cable.adern }) : null, cable.category || null]
              .filter(Boolean)
              .join(" · ") || "—"}
            {cable.liste ? ` · Liste ${cable.liste}` : ""}
            {cable.length_m != null ? ` · ${fmtM(cable.length_m)} m` : ""}
          </div>
        </div>
        <span
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium",
            cable.status === "complete" && "bg-[#2DD4BF]/15 text-[#2DD4BF]",
            cable.status === "partial" && "bg-[#F97316]/15 text-[#F97316]",
            cable.status === "none" && "bg-[#27272A] text-[#A1A1AA]"
          )}
        >
          {cable.status_label}
        </span>
      </div>

      <p className="text-sm text-[#FAFAFA]">{cable.status_message}</p>

      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-md border border-[#27272A] bg-[#09090B] p-3">
          <div className="text-xs uppercase tracking-wide text-[#71717A]">{t("sourceA")}</div>
          <div className="mt-1 font-medium text-[#FAFAFA]">{displayText(cable.geraet_a)}</div>
          <div className="mt-1 text-[#A1A1AA]">{displayText(cable.ort_a)}</div>
          <div className="mt-2 text-xs text-[#71717A]">
            {t("alnRequested")}{" "}
            <span className="font-mono-data text-[#FAFAFA]">{displayText(cable.aln_a)}</span>
          </div>
        </div>
        <div className="rounded-md border border-[#27272A] bg-[#09090B] p-3">
          <div className="text-xs uppercase tracking-wide text-[#71717A]">{t("sourceE")}</div>
          <div className="mt-1 font-medium text-[#FAFAFA]">{displayText(cable.geraet_e)}</div>
          <div className="mt-1 text-[#A1A1AA]">{displayText(cable.ort_e)}</div>
          <div className="mt-2 text-xs text-[#71717A]">
            {t("alnRequested")}{" "}
            <span className="font-mono-data text-[#FAFAFA]">{displayText(cable.aln_e)}</span>
          </div>
        </div>
      </div>

      {(!isBlankDisplay(cable.pulled_start) || !isBlankDisplay(cable.pulled_end)) &&
        cable.status !== "none" &&
        !isRouteMissing(cable) && (
        <p className="text-sm text-[#71717A]">
          {tc("pulledSpan")}{" "}
          <span className="font-mono-data text-[#FAFAFA]">
            {displayText(cable.pulled_start)} → {displayText(cable.pulled_end)}
          </span>
        </p>
      )}

      <div>
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-[#71717A]">{tc("route")}</div>
        {isRouteMissing(cable) ? (
          <p className="rounded-md border border-[#F97316]/40 bg-[#F97316]/10 p-3 text-sm text-[#FDBA74]">
            {cable.route_warning || tc("routeMissing")}
          </p>
        ) : (
          <>
            <div
              className="overflow-x-auto rounded-md border border-[#27272A] bg-[#09090B] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
              dangerouslySetInnerHTML={{ __html: cable.route_html || displayText(cable.route) }}
            />
            <p className="mt-2 text-xs text-[#52525B]">{tc("pulledHint")}</p>
          </>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const tc = useTranslations("common");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [cables, setCables] = useState<CableDetail[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [lastIds, setLastIds] = useState("");
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const [routeById, setRouteById] = useState<Record<string, CableRouteDetail | "loading" | "error">>({});

  const anschlussGroups = useMemo(() => {
    const notStarted: Record<string, unknown>[] = [];
    const start: Record<string, unknown>[] = [];
    const end: Record<string, unknown>[] = [];
    const both: Record<string, unknown>[] = [];
    for (const row of summary?.anschluss_without_verlegt || []) {
      const item = { Kabelnr: row.kabelnr };
      if (row.started === false) {
        notStarted.push(item);
        continue;
      }
      const key = sideKey(row.sides);
      if (key === "start") start.push(item);
      else if (key === "end") end.push(item);
      else if (key === "both") both.push(item);
    }
    return { notStarted, start, end, both };
  }, [summary?.anschluss_without_verlegt]);

  const anschlussTotal =
    anschlussGroups.notStarted.length +
    anschlussGroups.start.length +
    anschlussGroups.end.length +
    anschlussGroups.both.length;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await api.get<Summary>("/dataset/summary");
        if (!cancelled) setSummary(data);
      } catch {
        if (!cancelled) setSummary({ loaded: false });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggleAnschlussRow(row: Record<string, unknown>) {
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

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    const raw = query.trim();
    if (!raw) {
      setSearchError(t("searchRequired"));
      setCables([]);
      setMissing([]);
      return;
    }
    setSearching(true);
    setSearchError("");
    setCables([]);
    setMissing([]);
    try {
      const data = await api.get<{ cables: CableDetail[]; missing: string[] }>(
        `/cables/lookup${qs({ ids: raw })}`
      );
      setCables(data.cables);
      setMissing(data.missing);
      setLastIds(raw);
      if (!data.cables.length) {
        setSearchError(
          data.missing.length ? t("missing", { ids: data.missing.join("; ") }) : t("notFound")
        );
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : t("searchFailed"));
    } finally {
      setSearching(false);
    }
  }

  const dateLabel = summary?.progress_as_of || "—";

  return (
    <div className="mx-auto max-w-4xl">
      <TopProgress show={loading || searching} />
      <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>

      <section className="mt-6 space-y-3 text-[15px] leading-relaxed text-[#A1A1AA]">
        {summary?.loaded ? (
          <>
            <p>
              {t("dbUntil", { date: dateLabel })}
            </p>
            <p>
              {t("summary", {
                total: fmtM(summary.total_length_m),
                fully: fmtM(summary.fully_pulled_m),
                partial: fmtM(summary.partially_pulled_m),
                pulled: fmtM(summary.pulled_total_m),
                notStarted: fmtM(summary.not_started_m),
              })}
            </p>
            {anschlussTotal > 0 && (
              <div className="space-y-2 rounded-md border border-[#F87171]/40 bg-[#450A0A]/30 p-4">
                <p className="font-medium text-[#F87171]">
                  {t("anschlussTitle", { count: anschlussTotal })}
                </p>
                {(
                  [
                    {
                      key: "notStarted",
                      title: t("anschlussNotStarted"),
                      rows: anschlussGroups.notStarted,
                    },
                    {
                      key: "start",
                      title: t("anschlussStart"),
                      rows: anschlussGroups.start,
                    },
                    {
                      key: "end",
                      title: t("anschlussEnd"),
                      rows: anschlussGroups.end,
                    },
                    {
                      key: "both",
                      title: t("anschlussBoth"),
                      rows: anschlussGroups.both,
                    },
                  ] as const
                ).map((group) =>
                  group.rows.length === 0 ? null : (
                    <div key={group.key}>
                      <button
                        type="button"
                        aria-expanded={Boolean(openGroups[group.key])}
                        onClick={() =>
                          setOpenGroups((prev) => ({ ...prev, [group.key]: !prev[group.key] }))
                        }
                        className="flex w-full items-center gap-1.5 rounded py-1 text-left text-sm font-medium text-[#FCA5A5] hover:text-[#FECACA]"
                      >
                        <ChevronRight
                          className={cn(
                            "h-4 w-4 shrink-0 transition-transform",
                            openGroups[group.key] && "rotate-90"
                          )}
                        />
                        {group.title}{" "}
                        <span className="font-normal text-[#F87171]/80">({group.rows.length})</span>
                      </button>
                      {openGroups[group.key] && (
                      <div className="mt-2 [&_td]:text-[#FCA5A5] [&_th]:text-[#F87171]">
                        <DataTable
                          rows={group.rows}
                          columns={ANSCHLUSS_COLS}
                          rowKey={(row) => String(row.Kabelnr ?? "")}
                          expandedKey={expandedId}
                          onRowClick={(row) => void toggleAnschlussRow(row)}
                          renderExpanded={(row) => {
                            const id = String(row.Kabelnr ?? "").trim();
                            const detail = routeById[id];
                            if (detail === "loading" || !detail) {
                              return <p className="text-sm text-[#A1A1AA]">{tc("loadingRoute")}</p>;
                            }
                            if (detail === "error") {
                              return (
                                <p className="text-sm text-[#F87171]">
                                  {tc("routeError")}
                                </p>
                              );
                            }
                            return (
                              <div className="space-y-2 text-[#E4E4E7]">
                                <p className="text-sm text-[#FAFAFA]">
                                  {detail.status_message || detail.status_label}
                                </p>
                                {(!isBlankDisplay(detail.pulled_start) || !isBlankDisplay(detail.pulled_end)) &&
                                  !isRouteMissing(detail) && (
                                  <p className="text-xs text-[#A1A1AA]">
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
                                      className="overflow-x-auto rounded-md border border-[#27272A] bg-[#0C0C0E] p-3 font-mono-data text-sm leading-7"
                                      dangerouslySetInnerHTML={{
                                        __html: detail.route_html || displayText(detail.route),
                                      }}
                                    />
                                    <p className="text-xs text-[#71717A]">
                                      {tc("pulledHint")}
                                    </p>
                                  </>
                                )}
                              </div>
                            );
                          }}
                        />
                      </div>
                      )}
                    </div>
                  )
                )}
              </div>
            )}
          </>
        ) : (
          <p>
            {t("empty")}{" "}
            <Link href="/upload" className="text-[#2DD4BF] underline-offset-2 hover:underline">
              {t("emptyUploadLink")}
            </Link>
          </p>
        )}
        <LeaveMissingBox />
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium uppercase tracking-wide text-[#71717A]">{t("searchTitle")}</h2>
        <form onSubmit={onSearch} className="mt-3 flex flex-wrap gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="min-w-[220px] flex-1 font-mono-data"
            disabled={!summary?.loaded}
          />
          <Button type="submit" disabled={!summary?.loaded || searching}>
            <Search size={16} />
            {tc("search")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!cables.length}
            onClick={() =>
              api.download(`/export/lookup${qs({ ids: lastIds || query })}`, "kabel_lookup.xlsx")
            }
          >
            <Download size={16} />
            {tc("excel")}
          </Button>
        </form>
        <p className="mt-2 text-xs text-[#52525B]">
          {t("searchHint")}
        </p>
        {searchError && <p className="mt-3 text-sm text-[#F87171]">{searchError}</p>}
        {missing.length > 0 && cables.length > 0 && (
          <p className="mt-3 text-sm text-[#F97316]">{t("missing", { ids: missing.join("; ") })}</p>
        )}

        <div className="mt-6 space-y-4">
          {cables.map((c) => (
            <CableCard key={c.kabelnr} cable={c} />
          ))}
        </div>
      </section>
    </div>
  );
}
