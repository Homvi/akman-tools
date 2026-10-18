"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api, qs } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { TopProgress } from "@/components/progress-bar";

type Plan = {
  thin_pace: number;
  thick_pace: number;
  h_per_stuetze: number;
  pullers: number;
  max_per_room: number;
  hours_per_week: number;
};

type Totals = {
  person_hours?: number;
  remaining_m?: number;
  cables?: number;
  pulled_pct?: number;
  schedule?: { kw?: string; workdays?: number; end_date?: string | null };
};

const OVERVIEW_COLS = [
  "name",
  "deck",
  "cables",
  "thick",
  "thin",
  "through",
  "terminate",
  "stop",
  "pulled_pct",
  "remaining_m",
  "person_hours",
  "crew",
  "start_date",
  "workdays",
  "kw",
];

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
};

export default function AreasPage() {
  const [summaries, setSummaries] = useState<Record<string, unknown>[]>([]);
  const [totals, setTotals] = useState<Totals>({});
  const [plan, setPlan] = useState<Plan>(DEFAULT_PLAN);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function planQs() {
    return qs({
      thin_pace: plan.thin_pace,
      thick_pace: plan.thick_pace,
      h_per_stuetze: plan.h_per_stuetze,
      pullers: plan.pullers,
      max_per_room: plan.max_per_room,
      hours_per_week: plan.hours_per_week,
    });
  }

  async function load(nextPlan?: Plan) {
    const p = nextPlan || plan;
    setLoading(true);
    setError("");
    try {
      const data = await api.get<{
        summaries: Record<string, unknown>[];
        totals: Totals;
        plan?: Plan;
      }>(
        `/areas/summaries${qs({
          thin_pace: p.thin_pace,
          thick_pace: p.thick_pace,
          h_per_stuetze: p.h_per_stuetze,
          pullers: p.pullers,
          max_per_room: p.max_per_room,
          hours_per_week: p.hours_per_week,
        })}`
      );
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
    // initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  async function saveAndReload() {
    setLoading(true);
    setError("");
    try {
      await api.put("/areas/settings", plan);
      await load(plan);
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

  return (
    <div>
      <TopProgress show={loading} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#FAFAFA]">Areas</h1>
          <p className="mt-1 text-sm text-[#71717A]">
            Helység ütemezés — személyóra, KW, through/terminate, shared puller pool (max / room).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-[#27272A] bg-transparent px-3 text-sm text-[#FAFAFA] hover:bg-[#18181B]">
            Upload Helység Excel
            <input type="file" accept=".xlsx" className="hidden" onChange={onUpload} />
          </label>
          <Button
            type="button"
            variant="outline"
            disabled={!summaries.length}
            onClick={() => api.download(`/areas/export${planQs()}`, "areas_export.xlsx")}
          >
            <Download size={16} />
            Excel
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
          <Button type="button" onClick={() => void saveAndReload()} disabled={loading}>
            Számítás / mentés
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

      <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-[#71717A]">Overview</h2>
      <DataTable rows={summaries} columns={OVERVIEW_COLS} />

      <h2 className="mb-2 mt-6 text-sm font-medium uppercase tracking-wide text-[#71717A]">
        From zero
      </h2>
      <DataTable rows={summaries} columns={ZERO_COLS} />
    </div>
  );
}
