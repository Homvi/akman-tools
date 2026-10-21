"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { DataTable } from "@/components/data-table";
import { TopProgress } from "@/components/progress-bar";

type WeekRow = {
  KW?: string;
  Partial?: number;
  Complete?: number;
  Total?: number;
  Cumulative?: number;
  Thick?: number;
  Thin?: number;
  Unknown?: number;
  [key: string]: unknown;
};

type Stats = {
  total_m?: number;
  partial_m?: number;
  complete_m?: number;
  avg_m_per_day?: number;
  avg_last7?: number;
  events?: number;
  total_length_m?: number;
  fully_pulled_m?: number;
  partially_pulled_m?: number;
  pulled_total_m?: number;
};

function fmtM(n: number | null | undefined) {
  return `${Number(n || 0).toFixed(1).replace(".", ",")} m`;
}

function shortDate(value: unknown) {
  const s = String(value ?? "");
  return s.length >= 10 ? s.slice(0, 10) : s;
}

export default function ProgressPage() {
  const [daily, setDaily] = useState<Record<string, unknown>[]>([]);
  const [weekly, setWeekly] = useState<WeekRow[]>([]);
  const [anschlussWeekly, setAnschlussWeekly] = useState<WeekRow[]>([]);
  const [anschlussTotal, setAnschlussTotal] = useState(0);
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .get<{
        daily: Record<string, unknown>[];
        weekly: WeekRow[];
        anschluss_weekly?: WeekRow[];
        anschluss_total?: number;
        stats: Stats;
      }>("/progress/daily")
      .then((d) => {
        setDaily(d.daily || []);
        setWeekly(d.weekly || []);
        setAnschlussWeekly(d.anschluss_weekly || []);
        setAnschlussTotal(Number(d.anschluss_total || 0));
        setStats(d.stats || {});
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const dailyChart = useMemo(
    () =>
      daily.map((row) => ({
        ...row,
        Date: shortDate(row.Date),
        Partial: Number(row.Partial || 0),
        Complete: Number(row.Complete || 0),
      })),
    [daily]
  );

  const weeklyChart = useMemo(
    () =>
      weekly.map((row) => ({
        KW: String(row.KW || ""),
        Partial: Number(row.Partial || 0),
        Complete: Number(row.Complete || 0),
        Total: Number(row.Total || 0),
      })),
    [weekly]
  );

  const anschlussChart = useMemo(
    () =>
      anschlussWeekly.map((row) => ({
        KW: String(row.KW || ""),
        Thick: Number(row.Thick || 0),
        Thin: Number(row.Thin || 0),
        Unknown: Number(row.Unknown || 0),
        Total: Number(row.Total || 0),
      })),
    [anschlussWeekly]
  );

  const weekTable = useMemo(
    () =>
      weekly.map((row) => ({
        KW: row.KW,
        "Részleges m": Number(row.Partial || 0).toFixed(1).replace(".", ","),
        "Teljes m": Number(row.Complete || 0).toFixed(1).replace(".", ","),
        "Összesen m": Number(row.Total || 0).toFixed(1).replace(".", ","),
        "Kumulált m": Number(row.Cumulative || 0).toFixed(1).replace(".", ","),
      })),
    [weekly]
  );

  const anschlussTable = useMemo(
    () =>
      anschlussWeekly.map((row) => ({
        KW: row.KW,
        Vastag: Number(row.Thick || 0),
        Vékony: Number(row.Thin || 0),
        ...(Number(row.Unknown || 0) > 0 ? { Ismeretlen: Number(row.Unknown || 0) } : {}),
        Összesen: Number(row.Total || 0),
      })),
    [anschlussWeekly]
  );

  return (
    <div>
      <TopProgress show={loading} />
      <h1 className="mb-1 text-2xl font-semibold tracking-tight text-[#FAFAFA]">Progress</h1>
      <p className="mb-4 text-sm text-[#A1A1AA]">
        A felső számok a jelenlegi állapot (ugyanaz, mint a Dashboard). A grafikonok heti/napi{" "}
        <span className="text-[#FAFAFA]">események</span>: Gestoppt = részleges, verlegt nap = fennmaradó
        teljes.
      </p>
      {error && <p className="mb-3 text-sm text-[#F87171]">{error}</p>}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="text-xs uppercase tracking-wide text-[#71717A]">Össz behúzott</p>
          <p className="mt-1 text-xl font-semibold text-[#FAFAFA]">
            {fmtM(stats.pulled_total_m ?? stats.total_m)}
          </p>
        </div>
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="text-xs uppercase tracking-wide text-[#71717A]">Részleges / teljes</p>
          <p className="mt-1 text-xl font-semibold text-[#FAFAFA]">
            <span className="text-[#F97316]">{fmtM(stats.partially_pulled_m ?? stats.partial_m)}</span>
            {" · "}
            <span className="text-[#2DD4BF]">{fmtM(stats.fully_pulled_m ?? stats.complete_m)}</span>
          </p>
        </div>
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="text-xs uppercase tracking-wide text-[#71717A]">Átlag / nap</p>
          <p className="mt-1 text-xl font-semibold text-[#FAFAFA]">{fmtM(stats.avg_m_per_day)}</p>
        </div>
        <div className="rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
          <p className="text-xs uppercase tracking-wide text-[#71717A]">Utolsó 7 nap</p>
          <p className="mt-1 text-xl font-semibold text-[#FAFAFA]">{fmtM(stats.avg_last7)}</p>
        </div>
      </div>

      <div className="mb-6 h-80 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">
          Napi behúzás — narancs = részleges, teal = teljes
        </p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={dailyChart}>
            <CartesianGrid stroke="#27272A" vertical={false} />
            <XAxis dataKey="Date" tick={{ fontSize: 11, fill: "#71717A" }} />
            <YAxis tick={{ fontSize: 11, fill: "#71717A" }} />
            <Tooltip
              contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 8 }}
              labelStyle={{ color: "#FAFAFA" }}
            />
            <Legend />
            <Bar dataKey="Partial" name="Részleges" stackId="m" fill="#F97316" radius={[0, 0, 0, 0]} />
            <Bar dataKey="Complete" name="Teljes" stackId="m" fill="#2DD4BF" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mb-3 h-80 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">
          Heti behúzás (KW) — részleges + teljes oszlopok
        </p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={weeklyChart}>
            <CartesianGrid stroke="#27272A" vertical={false} />
            <XAxis dataKey="KW" tick={{ fontSize: 11, fill: "#71717A" }} />
            <YAxis tick={{ fontSize: 11, fill: "#71717A" }} />
            <Tooltip
              contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 8 }}
              labelStyle={{ color: "#FAFAFA" }}
            />
            <Legend />
            <Bar dataKey="Partial" name="Részleges" stackId="m" fill="#F97316" />
            <Bar dataKey="Complete" name="Teljes" stackId="m" fill="#2DD4BF" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mb-8">
        <p className="mb-2 text-sm text-[#A1A1AA]">Heti tábla (méter)</p>
        <DataTable
          rows={weekTable}
          columns={["KW", "Részleges m", "Teljes m", "Összesen m", "Kumulált m"]}
        />
      </div>

      <div className="mb-3 h-80 rounded-md border border-[#27272A] bg-[#0C0C0E] p-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[#71717A]">
          Heti kötések (Anschluss) — vastag / vékony · összesen {anschlussTotal.toLocaleString()}
        </p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={anschlussChart}>
            <CartesianGrid stroke="#27272A" vertical={false} />
            <XAxis dataKey="KW" tick={{ fontSize: 11, fill: "#71717A" }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#71717A" }} />
            <Tooltip
              contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 8 }}
              labelStyle={{ color: "#FAFAFA" }}
            />
            <Legend />
            <Bar dataKey="Thick" name="Vastag" stackId="a" fill="#FB923C" />
            <Bar dataKey="Thin" name="Vékony" stackId="a" fill="#38BDF8" radius={[2, 2, 0, 0]} />
            {anschlussChart.some((r) => r.Unknown > 0) && (
              <Bar dataKey="Unknown" name="Ismeretlen" stackId="a" fill="#71717A" />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mb-4">
        <p className="mb-2 text-sm text-[#A1A1AA]">
          Heti kötés-tábla (Anschluss 1 + 2 dátumok száma)
        </p>
        <DataTable
          rows={anschlussTable}
          columns={
            anschlussTable.some((r) => "Ismeretlen" in r)
              ? ["KW", "Vastag", "Vékony", "Ismeretlen", "Összesen"]
              : ["KW", "Vastag", "Vékony", "Összesen"]
          }
        />
      </div>
    </div>
  );
}
