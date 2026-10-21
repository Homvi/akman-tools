"use client";

import { useTranslations } from "next-intl";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowDownToLine, Check, Copy, Search, X } from "lucide-react";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TopProgress } from "@/components/progress-bar";
import { cn } from "@/lib/utils";

type CableFill = {
  kabelnr: string;
  status: string;
  status_label: string;
  status_message: string;
  route: string;
  route_html: string;
  pulled_start: string;
  pulled_end: string;
  already_pulled_m: number;
  nodes: string[];
  node_a: string;
  node_e: string;
  allowance_a: number;
  allowance_e: number;
  length_m: number | null;
};

type CalcResult = {
  ok: boolean;
  meters: number;
  error: string;
  route_m?: number;
  allowance_a?: number;
  allowance_e?: number;
};

type Overlap = {
  has_overlap: boolean;
  suggest_start: string;
  suggest_end: string;
  message: string;
};

function fmtM(n: number | null | undefined) {
  return `${Number(n || 0).toFixed(1).replace(".", ",")} m`;
}

export default function CalculatorPage() {
  const t = useTranslations("calculator");
  const tc = useTranslations("common");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [cable, setCable] = useState<CableFill | null>(null);
  const [previewHtml, setPreviewHtml] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [pickMode, setPickMode] = useState<"start" | "end">("start");
  const [overlap, setOverlap] = useState<Overlap | null>(null);
  const [result, setResult] = useState<CalcResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const calcTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    const q = query.trim();
    if (!q || (cable && q === cable.kabelnr)) {
      setSuggestions([]);
      return;
    }
    searchTimer.current = setTimeout(() => {
      api
        .get<{ ids: string[] }>(`/cables/search${qs({ q, limit: 40 })}`)
        .then((d) => {
          setSuggestions(d.ids || []);
          setOpen(true);
        })
        .catch(() => setSuggestions([]));
    }, 160);
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, [query, cable]);

  useEffect(() => {
    if (!cable?.route) {
      setPreviewHtml("");
      setOverlap(null);
      return;
    }
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => {
      api
        .post<{ route_html: string; overlap: Overlap }>("/calc/preview", {
          route: cable.route,
          pulled_start: cable.pulled_start,
          pulled_end: cable.pulled_end,
          start,
          end,
        })
        .then((d) => {
          setPreviewHtml(d.route_html || cable.route_html || "");
          setOverlap(d.overlap || null);
        })
        .catch(() => setPreviewHtml(cable.route_html || ""));
    }, 150);
    return () => {
      if (previewTimer.current) clearTimeout(previewTimer.current);
    };
  }, [cable, start, end]);

  useEffect(() => {
    if (!cable?.route || !start.trim() || !end.trim()) {
      setResult(null);
      return;
    }
    if (calcTimer.current) clearTimeout(calcTimer.current);
    calcTimer.current = setTimeout(() => {
      api
        .post<{ result: CalcResult }>("/calc/length", {
          route: cable.route,
          start,
          end,
          node_a: cable.node_a,
          node_e: cable.node_e,
          allowance_a: cable.allowance_a,
          allowance_e: cable.allowance_e,
        })
        .then((d) => setResult(d.result))
        .catch(() => setResult(null));
    }, 200);
    return () => {
      if (calcTimer.current) clearTimeout(calcTimer.current);
    };
  }, [cable, start, end]);

  async function loadCable(id: string) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.get<CableFill>(`/cables/by-id/${encodeURIComponent(id)}`);
      setCable(data);
      setQuery(data.kabelnr);
      setOpen(false);
      setSuggestions([]);
      setPreviewHtml(data.route_html || "");
      // Continue from last stop when partial; otherwise empty for user to pick.
      if (data.status === "partial" && data.pulled_end) {
        setStart(data.pulled_end);
        setPickMode("end");
      } else {
        setStart("");
        setPickMode("start");
      }
      setEnd("");
    } catch (err) {
      setCable(null);
      setError(err instanceof Error ? err.message : t("notFound"));
    } finally {
      setLoading(false);
    }
  }

  function onSearchSubmit(e: FormEvent) {
    e.preventDefault();
    const id = query.trim();
    if (!id) return;
    if (suggestions.length === 1) void loadCable(suggestions[0]);
    else void loadCable(id);
  }

  function resetAll() {
    setQuery("");
    setCable(null);
    setSuggestions([]);
    setPreviewHtml("");
    setStart("");
    setEnd("");
    setPickMode("start");
    setOverlap(null);
    setResult(null);
    setError("");
  }

  function pickNode(node: string) {
    if (pickMode === "start") {
      setStart(node);
      setPickMode("end");
    } else {
      setEnd(node);
    }
  }

  const nodes = cable?.nodes || [];

  return (
    <div className="mx-auto max-w-3xl">
      <TopProgress show={loading} />
      <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">{t("title")}</h1>
      <p className="mt-1 text-sm text-[#71717A]">{t("subtitle")}</p>

      <div ref={boxRef} className="relative mt-6">
        <form onSubmit={onSearchSubmit}>
          <label className="block text-xs text-[#71717A]">
            {t("cableId")}
            <div className="relative mt-1">
              <Search
                size={14}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[#52525B]"
              />
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setOpen(true);
                  if (cable && e.target.value !== cable.kabelnr) setCable(null);
                }}
                onFocus={() => setOpen(true)}
                placeholder={t("typePlaceholder")}
                className="pl-8 pr-9 font-mono-data"
                autoComplete="off"
              />
              {(query || cable) && (
                <button
                  type="button"
                  aria-label={tc("clear")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-[#FAFAFA]"
                  onClick={resetAll}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </label>
        </form>
        {open && suggestions.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-[#27272A] bg-[#0C0C0E] py-1 shadow-lg">
            {suggestions.map((id) => (
              <li key={id}>
                <button
                  type="button"
                  className={cn(
                    "w-full px-3 py-2 text-left font-mono-data text-sm hover:bg-[#18181B]",
                    cable?.kabelnr === id ? "bg-[#18181B] text-[#2DD4BF]" : "text-[#E4E4E7]"
                  )}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => void loadCable(id)}
                >
                  {id}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-[#F87171]">{error}</p>}

      {cable && (
        <>
          <div
            className={cn(
              "mt-5 rounded-md border px-4 py-3 text-sm",
              cable.status === "complete" && "border-[#2DD4BF]/40 bg-[#042F2E]/50 text-[#2DD4BF]",
              cable.status === "partial" && "border-[#F97316]/40 bg-[#431407]/50 text-[#FDBA74]",
              cable.status === "none" && "border-[#27272A] bg-[#18181B] text-[#A1A1AA]"
            )}
          >
            <p className="font-medium text-[#FAFAFA]">
              {cable.kabelnr} · {cable.status_label}
            </p>
            <p className="mt-1">{cable.status_message}</p>
            {(cable.pulled_start || cable.pulled_end) && cable.status !== "none" && (
              <p className="mt-2 font-mono-data text-xs text-[#FAFAFA]">
                {t("alreadyPulled", {
                  start: cable.pulled_start || "—",
                  end: cable.pulled_end || "—",
                })}
                {cable.already_pulled_m > 0 ? ` · ${fmtM(cable.already_pulled_m)}` : ""}
              </p>
            )}
            {cable.length_m != null && (
              <p className="mt-1 text-xs opacity-80">
                {t("catalogLength", { length: fmtM(cable.length_m) })}
              </p>
            )}
          </div>

          <div className="mt-5">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-wide">
              <span className="rounded bg-[#fb923c] px-2 py-0.5 text-[#0f172a]">{t("legendPulled")}</span>
              <span className="rounded bg-[#38bdf8] px-2 py-0.5 text-[#0f172a]">{t("legendNow")}</span>
              <span className="rounded bg-[#f43f5e] px-2 py-0.5 text-[#0f172a]">{t("legendOverlap")}</span>
            </div>
            <div
              className="min-h-[88px] overflow-x-auto rounded-md border border-[#27272A] bg-[#020617] p-3 font-mono-data text-sm leading-7 text-[#E4E4E7]"
              dangerouslySetInnerHTML={{ __html: previewHtml || cable.route_html || "—" }}
            />
          </div>

          {nodes.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs text-[#71717A]">
                {t("pickHint", {
                  mode: pickMode === "start" ? t("modeStart") : t("modeEnd"),
                })}
                {pickMode === "end" && (
                  <>
                    {" "}
                    ·{" "}
                    <button
                      type="button"
                      className="text-[#2DD4BF] underline-offset-2 hover:underline"
                      onClick={() => setPickMode("start")}
                    >
                      {t("reselectStart")}
                    </button>
                  </>
                )}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {nodes.map((node) => {
                  const isStart = node === start;
                  const isEnd = node === end;
                  const isPulledEnd = node === cable.pulled_end;
                  return (
                    <button
                      key={node}
                      type="button"
                      onClick={() => pickNode(node)}
                      className={cn(
                        "rounded border px-2 py-1 font-mono-data text-xs",
                        isStart && "border-[#38bdf8] bg-[#38bdf8]/20 text-[#7DD3FC]",
                        isEnd && !isStart && "border-[#38bdf8] bg-[#38bdf8]/20 text-[#7DD3FC]",
                        !isStart &&
                          !isEnd &&
                          isPulledEnd &&
                          "border-[#F97316]/50 bg-[#F97316]/10 text-[#FDBA74]",
                        !isStart &&
                          !isEnd &&
                          !isPulledEnd &&
                          "border-[#27272A] bg-[#0C0C0E] text-[#A1A1AA] hover:border-[#52525B] hover:text-[#FAFAFA]"
                      )}
                    >
                      {node}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-[#71717A]">{t("startLabel")}</span>
                <button
                  type="button"
                  title={t("insertA", { node: cable.node_a || "—" })}
                  disabled={!cable.node_a}
                  className="inline-flex h-6 w-6 items-center justify-center rounded border border-[#27272A] text-[#A1A1AA] hover:border-[#2DD4BF]/50 hover:text-[#2DD4BF] disabled:opacity-40"
                  onClick={() => {
                    if (!cable.node_a) return;
                    setStart(cable.node_a);
                    setPickMode("end");
                  }}
                >
                  <ArrowDownToLine size={14} />
                </button>
              </div>
              <Input
                className="mt-1 font-mono-data"
                value={start}
                onChange={(e) => {
                  setStart(e.target.value);
                  setPickMode("end");
                }}
                placeholder={cable.node_a || "Startpont"}
              />
              <p className="mt-1 font-mono-data text-[11px] text-[#52525B]">A: {cable.node_a || "—"}</p>
            </div>
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-[#71717A]">{t("endLabel")}</span>
                <button
                  type="button"
                  title={t("insertE", { node: cable.node_e || "—" })}
                  disabled={!cable.node_e}
                  className="inline-flex h-6 w-6 items-center justify-center rounded border border-[#27272A] text-[#A1A1AA] hover:border-[#2DD4BF]/50 hover:text-[#2DD4BF] disabled:opacity-40"
                  onClick={() => {
                    if (!cable.node_e) return;
                    setEnd(cable.node_e);
                  }}
                >
                  <ArrowDownToLine size={14} />
                </button>
              </div>
              <Input
                className="mt-1 font-mono-data"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                placeholder={cable.node_e || t("endPlaceholder")}
              />
              <p className="mt-1 font-mono-data text-[11px] text-[#52525B]">E: {cable.node_e || "—"}</p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={resetAll}>
              Reset
            </Button>
          </div>

          {overlap?.has_overlap && (
            <div className="mt-4 rounded-md border border-[#F43F5E]/40 bg-[#450A0A]/40 px-3 py-2 text-sm text-[#FECDD3]">
              <p>{overlap.message}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {overlap.suggest_start && (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={() => {
                      setStart(overlap.suggest_start);
                      setPickMode("end");
                    }}
                  >
                    Start → {overlap.suggest_start}
                  </Button>
                )}
                {overlap.suggest_end && (
                  <Button
                    type="button"
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={() => setEnd(overlap.suggest_end)}
                  >
                    {t("suggestEnd", { end: overlap.suggest_end })}
                  </Button>
                )}
              </div>
            </div>
          )}

          <div className="mt-6 rounded-md border border-[#27272A] bg-[#0C0C0E] px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs uppercase tracking-wide text-[#71717A]">{t("nowLength")}</p>
              {result?.ok && (
                <button
                  type="button"
                  title={t("copyExcel")}
                  className="inline-flex h-7 w-7 items-center justify-center rounded border border-[#27272A] text-[#A1A1AA] hover:border-[#2DD4BF]/50 hover:text-[#2DD4BF]"
                  onClick={async () => {
                    const value = Number(result.meters || 0).toFixed(1).replace(".", ",");
                    try {
                      await navigator.clipboard.writeText(value);
                      setCopied(true);
                      window.setTimeout(() => setCopied(false), 1500);
                    } catch {
                      /* ignore */
                    }
                  }}
                >
                  {copied ? <Check size={14} className="text-[#2DD4BF]" /> : <Copy size={14} />}
                </button>
              )}
            </div>
            {result?.ok ? (
              <>
                <p className="mt-1 font-mono-data text-2xl font-semibold text-[#2DD4BF]">
                  {fmtM(result.meters)}
                </p>
                <p className="mt-2 text-xs text-[#A1A1AA]">
                  Nyomvonal: {fmtM(result.route_m)}
                  {(result.allowance_a || 0) > 0 && (
                    <>{t("allowanceA", { m: fmtM(result.allowance_a) })}</>
                  )}
                  {(result.allowance_e || 0) > 0 && (
                    <>{t("allowanceE", { m: fmtM(result.allowance_e) })}</>
                  )}
                </p>
              </>
            ) : result && !result.ok ? (
              <p className="mt-1 text-sm text-[#F87171]">{result.error}</p>
            ) : (
              <p className="mt-1 text-sm text-[#71717A]">{t("needPoints")}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
